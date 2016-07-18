# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

import os
import errno
import sys
import datetime
import json
import math
import random

from collections import deque

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task, defer
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.serialport  import SerialPort
from twisted.application.service  import Service
from twisted.application.internet import ClientService
from twisted.internet.endpoints   import clientFromString


#--------------
# local imports
# -------------

import device

from .service.interfaces import IReloadable, IPausable
from .logger   import setLogLevel
from .utils    import chop,  setSystemTime
from .protocol import EMAProtocol, EMAProtocolFactory, EMATimeoutError
from .command  import EMARangeError, EMAReturnError
from .command  import ROOF_RELAY, AUX_RELAY, POWER_VOLT, PERIOD as EMA_PERIOD

# ----------------
# Module constants
# ----------------


# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')


#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

@implementer(IPausable, IReloadable)
class SerialService(ClientService):

    # Service name
    NAME = 'Serial Service'


    def __init__(self, options):
        self.options    = options    
        protocol_level  = 'debug' if self.options['log_messages'] else 'info'
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        setLogLevel(namespace='serial', levelStr=self.options['log_level'])
        setLogLevel(namespace='ema.serial.protocol.base.EMAProtocolFactory', levelStr='error')
        self.factory   = EMAProtocolFactory()
        self.serport   = None
        self.protocol  = None
        self.vmag      = None
        self.devices   = []
        self.goSerial  = self._decide()


    def _decide(self):
        '''Decide which endpoint must be built, either TCP or Serial'''

        def backoffPolicy(initialDelay=4.0, maxDelay=60.0, factor=2):
            '''Custom made backoff policy to exit after a number of reconnection attempts'''
            def policy(attempt):
                delay = min(initialDelay * (factor ** attempt), maxDelay)
                if attempt > 3:
                    self.stopService()
                return delay
            return policy


        parts = chop(self.options['endpoint'], sep=':')
        if parts[0] == 'serial':
            self.endpoint = parts[1:]
            Service.__init__(self)
            return True
        else:
            self.endpoint = clientFromString(reactor, self.options['endpoint'])
            ClientService.__init__(self, self.endpoint, self.factory, retryPolicy=backoffPolicy())
            return False

    
    def startService(self):
        '''
        Starts the Serial Service that takls to EMA
        By exception, this returns a deferred that is handled by emaservice
        '''
        log.info("starting Serial Service")
        if self.goSerial:
            Service.startService(self)
            if self.serport is None:
                self.protocol = self.factory.buildProtocol(0)
                self.serport  = SerialPort(self.protocol, self.endpoint[0], reactor, baudrate=self.endpoint[1])
            self.gotProtocol(self.protocol)
        else:
            ClientService.startService(self)
            d = self.whenConnected()
            d.addCallback(self.gotProtocol)
            return d
            

    def _buildDevices(self):
        self.rtc         = device.RealTimeClock(self, self.options['rtc'])
        self.voltmeter   = device.Voltmeter(self, self.options['voltmeter'],
                            upload_period=self.options['upload_period'], 
                            global_sync=self.options['sync'])
        self.anemometer  = device.Anemometer(self, self.options['anemometer'],
                            global_sync=self.options['sync'])
        self.barometer   = device.Barometer(self, self.options['barometer'],
                            global_sync=self.options['sync'])
        self.cloudsensor = device.CloudSensor(self, self.options['cloudsensor'],
                            global_sync=self.options['sync'])
        self.photometer  = device.Photometer(self, self.options['photometer'],
                            global_sync=self.options['sync'])
        self.pluviometer = device.Pluviometer(self, self.options['pluviometer'],
                            global_sync=self.options['sync'])
        self.pyranometer = device.Pyranometer(self, self.options['pyranometer'],
                            global_sync=self.options['sync'])
        self.rainsensor  = device.RainSensor(self, self.options['rainsensor'],
                            global_sync=self.options['sync'])
        self.thermometer = device.Thermometer(self, self.options['thermometer'],
                            global_sync=self.options['sync'])
        self.watchdog    = device.Watchdog(self, self.options['watchdog'],
                            global_sync=self.options['sync'])
        self.aux_relay   = device.AuxiliarRelay(self, self.options['aux_relay'],
                            global_sync=self.options['sync'])
        self.roof_relay  = device.RoofRelay(self, self.options['roof_relay'], global_sync=False)
        self.devices     = [self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.roof_relay]


    def gotProtocol(self, protocol):
        log.debug("got Protocol")
        self.protocol  = protocol
        self.protocol.addStatusCallback(self.onStatus)
        self.protocol.addPhotometerCallback(self.onVisualMagnitude)
        self._buildDevices()
        self.watchdog.start()


    def onVisualMagnitude(self, vmag, tstamp):
        '''Records last visual magnitude update'''
        self.vmag = vmag


    def onStatus(self, status, tstamp):
        '''
        Adds last visual magnitude estimate
        and pass it upwards
        '''
        if self.vmag:
            status.append(self.vmag)
        else:
            status.append(24.0)
        self.parent.onStatus(status, tstamp)

        
    @inlineCallbacks
    def detectEMA(self, nretries=3):
        '''
        Returns True if EMA responds
        '''
        try:
            res = yield self.protocol.send(ema.command.Watchdog.GetPresence(),nretries)
        except EMATimeoutError as e:
            returnValue(False)
        else:
            returnValue(True)

    @inlineCallbacks
    def sync(self):
        '''
        Devices synchronization.
        Cannot send EMA MQTT registration until not sucessfully synchronized
        '''
        ok = True
        for device in self.devices:
            try:
                yield device.sync()
            except (EMARangeError, EMATimeoutError) as e:
                log.error("Synchronization error => {error}", error=e)
                self.parent.logMQTTEvent(msg="Synchronization error", kind="error")
                ok = False
                break
        returnValue(ok)


    def getParameters(self):
        '''
        Get all parameters once al devices synchronized
        '''
        with open("/sys/class/net/eth0/address",'r') as fd:
            mac = fd.readline().rstrip('\r\n')
        mydict = { 'mac': mac }
        for device in self.devices:
            mydict.update(device.parameters())
        log.debug("PARAMETERS = {p}", p=mydict)
        return mydict
       

    def syncRTC(self):
        return self.rtc.sync()
        

    def syncHostRTC(self):
        return self.rtc.inverseSync()
        

    @inlineCallbacks
    def stopService(self):
        if not self.goSerial:
            try:
                yield ClientService.stopService(self)
            except Exception as e:
                log.error("Exception {excp!s}", excp=e)
                raise 
        else:
            Service.stopService(self)

    def nextRelayCycle(self, inactiveI):
        '''
        Program next auxiliar relay switch on/off cycle
        Returns a Deferred with Noneas value
        '''
        return self.aux_relay.nextRelayCycle(inactiveT)


    def auxRelayTimer(self, flag):
        '''
        Activates/Deactivates Auxiliar timer mode
        Returns a Deferred 
        '''
        if flag:
            return self.aux_relay.mode('Timer/On')
        else:
            return self.aux_relay.mode('Timer/Off')
        

    def getDailyMinMaxDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self.protocol.getDailyMinMaxDump()


    def get5MinAveragesDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self.protocol.getDailyMinMaxDump()


    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['serial']
        protocol_level  = 'debug' if options['log_messages'] else 'info'
        setLogLevel(namespace='serial', levelStr=options['log_level'])
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        log.info("new log level is {lvl}", lvl=options['log_level'])
        self.options = options
        
    # -------------
    # EMA API
    # -------------



    # ----------
    # Events API
    # ----------

    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        self.parent.onEventExecute(event, *args)
    
    # --------------
    # Helper methods
    # ---------------
   
  
    def onPublish(self):
        '''
        Serial message Handler
        '''
        pass


__all__ = [
    "Watchdog",
    "Voltmeter",
    "RealTimeClock",
    "RoofRelay",
    "AuxiliarRelay",
    "Anemometer",
    "Barometer",
    "CloudSensor",
    "Photometer",
    "Pluviometer",
    "Pyranometer",
    "RainSensor",
    "Thermometer",
    "Thermopile",
    "SerialService",
]