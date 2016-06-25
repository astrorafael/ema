# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import os
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

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

from ..logger   import setLogLevel
from ..utils    import chop
from .protocol  import EMAProtocol, EMAProtocolFactory, EMARangeError, EMAReturnError, EMATimeoutError
from .devices   import (
    Voltmeter, Anemometer, Barometer, CloudSensor, Photometer, Pluviometer, Pyranometer, RainSensor, 
    Thermometer, RealTimeClock, Watchdog, RoofRelay, AuxiliarRelay,
)


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



class SerialService(ClientService):


    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        protocol_level  = 'debug' if options['log_messages'] else 'info'
        setLogLevel(namespace='serial', levelStr=options['log_level'])
        setLogLevel(namespace='protoc', levelStr=protocol_level)
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


    def printParameters(self, result):
        mydict = {}
        for device in self.devices:
            mydict.update(device.parameters())
        log.info("PARAMETERS = {p}", p=mydict)

    def gotProtocol(self, protocol):
        log.debug("got Protocol")
        self.protocol  = protocol
        self.pingTask  = task.LoopingCall(self.ping)
        self.pingTask.start(100, now=False)
        #self.syncTask  = self.protocol.callLater(10, self.sync)
        self.voltmeter   = Voltmeter(self, self.options['voltmeter'])
        self.anemometer  = Anemometer(self, self.options['anemometer'])
        self.barometer   = Barometer(self, self.options['barometer'])
        self.cloudsensor = CloudSensor(self, self.options['cloudsensor'])
        self.photometer  = Photometer(self, self.options['photometer'])
        self.pluviometer = Pluviometer(self, self.options['pluviometer'])
        self.pyranometer = Pyranometer(self, self.options['pyranometer'])
        self.rainsensor  = RainSensor(self, self.options['rainsensor'])
        self.thermometer = Thermometer(self, self.options['thermometer'])
        self.watchdog    = Watchdog(self, self.options['watchdog'])
        self.rtc         = RealTimeClock(self, self.options['rtc'])
        self.aux_relay   = AuxiliarRelay(self, self.options['aux_relay'])
        self.devices     = [self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.rtc]

        self.sync().addCallback(self.printParameters)
        
       
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
        try:
            yield ClientService.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)
            reactor.stop()

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
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

    @inlineCallbacks
    def ping(self):
        try:
            res = yield self.protocol.ping()
        except EMATimeoutError as e:
            log.error("{excp!s}", excp=e)
        else:
            log.debug("PINGED. Result = {result}", result=res)


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


__all__ = [SerialService]