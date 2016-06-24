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
    Voltmeter, Anemometer, Barometer, CloudSensor, Photometer, Pluviometer, Pyranometer,
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
        self.pyranometer.sync()

        
       
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


    @inlineCallbacks
    def sync(self):
        '''
        Asynchronous Parameter syncronization process
        Returns a Deferred when all synchronization is complete
        '''
        getFuncs = [ 
            self.protocol.getRTCDateTime,
            self.protocol.getCurrentWindSpeedThreshold,
            self.protocol.getAverageWindSpeedThreshold,
            self.protocol.getAnemometerCalibrationConstant,
            self.protocol.getAnemometerModel,
            self.protocol.getBarometerHeight,
            self.protocol.getBarometerOffset,
            self.protocol.getCloudSensorThreshold,
            self.protocol.getCloudSensorGain,
            self.protocol.getPhotometerThreshold,
            self.protocol.getPhotometerOffset,
            self.protocol.getPluviometerCalibration ,
            self.protocol.getPyranometerGain ,
            self.protocol.getPyranometerOffset ,
            self.protocol.getRainSensorThreshold ,
            self.protocol.getThermometerDeltaTempThreshold,
            self.protocol.getVoltmeterThreshold,
            self.protocol.getVoltmeterOffset,
            self.protocol.getAuxRelaySwitchOnTime,
            self.protocol.getAuxRelaySwitchOffTime,
            self.protocol.getAuxRelayMode,
            self.protocol.getWatchdogPeriod,
        ]

        getFuncs = [ 
           self.protocol.get5MinAveragesDump
        ]

        setFuncs = [ 
            (self.protocol.setCurrentWindSpeedThreshold, 20),
            (self.protocol.setAverageWindSpeedThreshold, 66),
            (self.protocol.setAnemometerCalibrationConstant, 70),
            (self.protocol.setAnemometerModel, 'Simple'),
            (self.protocol.setBarometerHeight, 711),
            (self.protocol.setBarometerOffset, -10),
            (self.protocol.setCloudSensorThreshold, 67),
            (self.protocol.setCloudSensorGain, 1.0),
            (self.protocol.setPhotometerThreshold, 10.5),
            (self.protocol.setPhotometerOffset, 0),
            (self.protocol.setPluviometerCalibration, 124),
            (self.protocol.setPyranometerGain, 14),
            (self.protocol.setPyranometerOffset, 0),
            (self.protocol.setRainSensorThreshold, 1),
            (self.protocol.setThermometerDeltaTempThreshold, 5),
            (self.protocol.setVoltmeterThreshold, 0),
            (self.protocol.setVoltmeterOffset, -1.4),
            (self.protocol.setAuxRelaySwitchOnTime,  datetime.time(hour=6)),
            (self.protocol.setAuxRelaySwitchOffTime, datetime.time(hour=9)),
            (self.protocol.setAuxRelayMode, 'Timer/On'),
            (self.protocol.setWatchdogPeriod, 200),
            (self.protocol.setRTCDateTime, None),
            (self.protocol.setRoofRelayMode, 'Closed'),

        ]

        setFuncs = [ 
        ]

        if True:
            for getter in getFuncs:
                try:
                    res = yield getter()
                    log.debug("Result = {result}", result=res)
                except EMATimeoutError as e:
                    log.error("{excp!s}", excp=e)
                    continue
        if True:
            for setter in setFuncs:
                try:
                    res = yield setter[0](setter[1])
                    log.debug("Result = {result}", result=res)
                except EMATimeoutError as e:
                    log.error("{excp!s}", excp=e)
                    continue

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