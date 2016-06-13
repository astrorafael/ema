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

from twisted.logger              import Logger, LogLevel
from twisted.internet            import reactor, task
from twisted.internet.defer      import inlineCallbacks
from twisted.internet.serialport import SerialPort
from twisted.application.service import Service

#--------------
# local imports
# -------------

from .logger   import setLogLevel
from .utils    import chop
from .protocol import EMAProtocol
from .error    import EMATimeoutError

# ----------------
# Module constants
# ----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')



class SerialService(Service):


    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='serial', levelStr=options['log_level'])
       
        self.protocol  = EMAProtocol()
        self.port      = None

        self.resetCounters()
        self.pingTask   = task.LoopingCall(self.ping)
        self.syncTask   = self.protocol.callLater(10, self.sync)
        Service.__init__(self)

    
    def startService(self):
        log.info("starting Serial Service")
        if self.port is None:
            self.port      = SerialPort(self.protocol, self.options['port'], reactor, baudrate=self.options['baud'])
        self.pingTask.start(20, now=False)
        Service.startService(self)


    @inlineCallbacks
    def stopService(self):
        try:
            yield Service.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)
            reactor.stop()

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='serial', levelStr=new_options['log_level'])
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
        try:

            res = yield self.protocol.getTime()
            log.debug("GET RTC. Result = {result}", result=res)
            res = yield self.protocol.getCurrentWindSpeedThreshold()
            log.debug("GET CURR WIND THRESH. Result = {result}", result=res)
            res = yield self.protocol.getAverageWindSpeedThreshold()
            log.debug("GET AVER WIND THRESH. Result = {result}", result=res)
            res = yield self.protocol.getAnemometerCalibrationConstant()
            log.debug("GET ANEMOMENTER CALIB CONSTANT. Result = {result}", result=res)
            res = yield self.protocol.getAnemometerModel()
            log.debug("GET ANEMOMETER MODEL. Result = {result}", result=res)
            res = yield self.protocol.getBarometerHeight()
            log.debug("GET BAROMETER HEIGHT. Result = {result}", result=res)
            res = yield self.protocol.getBarometerOffset()
            log.debug("GET BAROMETER OFFSET. Result = {result}", result=res)
            res = yield self.protocol.getCloudSensorThreshold()
            log.debug("GET CLOUD SENSOR THRESHOLD. Result = {result}", result=res)
            res = yield self.protocol.getCloudSensorGain()
            log.debug("GET CLOUD SENSOR GAIN. Result = {result}", result=res)
            res = yield self.protocol.getPhotometerThreshold()
            log.debug("GET PHOTOMETER THRESHOLD. Result = {result}", result=res)
            res = yield self.protocol.getPhotometerOffset()
            log.debug("GET PHOTOMETER OFFSET. Result = {result}", result=res)


        except EMATimeoutError as e:
            log.error("{excp!s}", excp=e)
        else:
            pass


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