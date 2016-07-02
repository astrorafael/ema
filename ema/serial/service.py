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

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks
from twisted.internet.serialport  import SerialPort
from twisted.application.service  import Service
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet.endpoints   import clientFromString


#--------------
# local imports
# -------------

from ..service.interfaces import IReloadable, IPausable
from ..logger   import setLogLevel
from ..utils    import chop
from .protocol  import (
    EMAProtocol, EMAProtocolFactory, 
    EMARangeError, EMAReturnError, EMATimeoutError,
    )

from .devices   import (
    Anemometer, Barometer, CloudSensor, Photometer, Pluviometer, Pyranometer, RainSensor, 
    Thermometer, 
)
from .voltmeter import Voltmeter
from .rtc       import RealTimeClock
from .watchdog  import Watchdog
from .relays    import RoofRelay, AuxiliarRelay


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


@implementer(IPausable, IReloadable)
class SerialService(ClientService):


    def __init__(self, options):
        self.options    = options    
        protocol_level  = 'debug' if self.options['log_messages'] else 'info'
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        setLogLevel(namespace='serial', levelStr=self.options['log_level'])
        self.factory   = EMAProtocolFactory()
        self.serport   = None
        self.protocol  = None
        self.devices   = []
        self.synchroComplete = False
        self.synchroError    = False
        self.resetCounters()
        self.goSerial = self._decide()


    def _decide(self):
        '''Decide which endpoint must be built, either TCP or Serial'''
        parts = chop(self.options['endpoint'], sep=':')
        if parts[0] == 'serial':
            self.endpoint = parts[1:]
            Service.__init__(self)
            return True
        else:
            self.endpoint = clientFromString(reactor, self.options['endpoint'])
            ClientService.__init__(self, self.endpoint, self.factory, 
                retryPolicy=backoffPolicy(initialDelay=2, factor=2, maxDelay=300))
            return False

    
    def startService(self):
        log.info("starting Serial Service")
        if self.goSerial:
            if self.serport is None:
                self.protocol  = self.factory.buildProtocol(0)
                self.serport      = SerialPort(self.protocol, self.endpoint[0], reactor, baudrate=self.endpoint[1])
            Service.startService(self)
            self.gotProtocol(self.protocol)
        else:
            self.whenConnected().addCallback(self.gotProtocol)
            ClientService.startService(self)


    def parameters(self, result):
        with open("/sys/class/net/eth0/address",'r') as fd:
            mac = fd.readline().rstrip('\r\n')
        mydict = { 'mac': mac }
        for device in self.devices:
            mydict.update(device.parameters())
        log.info("PARAMETERS = {p}", p=mydict)
        reactor.callLater(5, self.protocol.setRoofRelayMode, 'Closed')
        reactor.callLater(10, self.protocol.setRoofRelayMode, 'Open')


    def _buildDevices(self):
        self.rtc         = RealTimeClock(self, self.options['rtc'])
        self.voltmeter   = Voltmeter(self, self.options['voltmeter'],
                            upload_period=self.options['upload_period'], 
                            global_sync=self.options['sync'])
        self.anemometer  = Anemometer(self, self.options['anemometer'],
                            global_sync=self.options['sync'])
        self.barometer   = Barometer(self, self.options['barometer'],
                            global_sync=self.options['sync'])
        self.cloudsensor = CloudSensor(self, self.options['cloudsensor'],
                            global_sync=self.options['sync'])
        self.photometer  = Photometer(self, self.options['photometer'],
                            global_sync=self.options['sync'])
        self.pluviometer = Pluviometer(self, self.options['pluviometer'],
                            global_sync=self.options['sync'])
        self.pyranometer = Pyranometer(self, self.options['pyranometer'],
                            global_sync=self.options['sync'])
        self.rainsensor  = RainSensor(self, self.options['rainsensor'],
                            global_sync=self.options['sync'])
        self.thermometer = Thermometer(self, self.options['thermometer'],
                            global_sync=self.options['sync'])
        self.watchdog    = Watchdog(self, self.options['watchdog'],
                            global_sync=self.options['sync'])
        self.aux_relay   = AuxiliarRelay(self, self.options['aux_relay'],
                            global_sync=self.options['sync'])
        self.roof_relay  = RoofRelay(self, self.options['roof_relay'], global_sync=False)
        self.devices     = [self.rtc, self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.roof_relay]


    def gotProtocol(self, protocol):
        log.debug("got Protocol")
        self.protocol  = protocol
        self._buildDevices()
        self.sync().addCallback(self.parameters)
        self.watchdog.start()
        
       
    @inlineCallbacks
    def sync(self):
        '''
        Devices synchronization.
        Cannot send EMA MQTT registration until not sucessfully synchronized
        '''
        self.synchroError    = False
        self.synchroComplete = False
        for device in self.devices:
            try:
                yield device.sync()
            except (EMARangeError, EMATimeoutError) as e:
                log.error("Synchronization error => {error}", error=e)
                self.parent.logMQTTEvent(msg="Synchronization error", kind="error")
                self.synchroError = True
                break
        self.synchroComplete = True


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

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self):
        protocol_level  = 'debug' if new_options['log_messages'] else 'info'
        setLogLevel(namespace='serial', levelStr=new_options['log_level'])
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        self.options = new_options
        

    def pauseService(self):
        pass

    def resumeService(self):
        pass

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
    
  
    # -------------
    # log stats API
    # -------------

    def resetCounters(self):
        '''Resets stat counters'''
        pass
        

    def getCounters(self):
        return [ ]

    def logCounters(self):
        '''log stat counters'''
        pass
        

    # --------------
    # Helper methods
    # ---------------
   
  


    def onPublish(self):
        '''
        Serial message Handler
        '''
        pass


__all__ = ["SerialService"]