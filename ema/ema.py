# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


#--------------------
# System wide imports
# -------------------

from __future__ import division

import sys
import datetime
import random
from collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted.logger   import Logger, LogLevel
from twisted.internet import task, reactor, defer
from twisted.internet.defer  import inlineCallbacks, returnValue, DeferredList
from twisted.internet.threads import deferToThread

#--------------
# local imports
# -------------

from .config import VERSION_STRING, loadCfgFile
from .logger import setLogLevel

from .service.relopausable import MultiService

#from ..mqtt.service import MQTTService, NAME as MQTT_NAME

from .protocol       import PERIOD as EMA_PERIOD
from .serial         import SerialService
from .scripts        import ScriptsService, AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from .scheduler      import SchedulerService
from .internet       import InternetService
from .mqttpub        import MQTTService

# ----------------
# Module constants
# ----------------

# Service name
NAME = 'EMA'

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='ema')



class EMAService(MultiService):

    # Service name
    NAME = 'EMA'


    def __init__(self, options, cfgFilePath):
        MultiService.__init__(self)
        self.cfgFilePath = cfgFilePath
        self.options     = options
        self.counter = 0
        self.NSAMPLES = self.options['period'] // EMA_PERIOD
        self.queue       = { 
            'status'  : deque(), 
            'ave5min' : deque(), 
            'minmax'  : deque(),
            'log'     : deque(),
            'register': deque(), 
        }
        setLogLevel(namespace='ema', levelStr=self.options['log_level'])
        

    def reporter(self):
        '''
        Periodic task to log queue size
        '''
        log.info("Readings queue size is {size}", size=len(self.queue['tess_readings']))



    @inlineCallbacks
    def reloadService(self, options):
        '''
        Reload application parameters
        '''
        log.warn("{ema} config being reloaded", ema=VERSION_STRING)
        try:
            options  = yield deferToThread(loadCfgFile, self.cfgFilePath)
        except Exception as e:
            log.error("Error trying to reload: {excp!s}", excp=e)
        else:
            self.options                  = options['ema']
            MultiService.reloadService(self, options)
           
    @inlineCallbacks
    def startService(self):
        '''
        Starts only two services and see if we can continue.
        '''
        log.info('starting {name}', name=self.name)
        self.scriptsService   = self.getServiceNamed(ScriptsService.NAME)
        self.internetService  = self.getServiceNamed(InternetService.NAME)
        self.serialService    = self.getServiceNamed(SerialService.NAME)
        self.schedulerService = self.getServiceNamed(SchedulerService.NAME)
        self.mqttService      = self.getServiceNamed(MQTTService.NAME)
        try:
            self.scriptsService.startService()
            yield defer.maybeDeferred(self.serialService.startService)
        except Exception as e:
            log.error("{excp}", excp=e)
            log.critical("Problems initializing {name}. Exiting gracefully", name=self.serialService.name)
            reactor.callLater(0,reactor.stop)
        else:
            self.internetService.startService()
            d1 = self.serialService.detectEMA(nretries=self.options['nretries'])
            d2 = self.internetService.hasConnectivity()
            dl = DeferredList([d1,d2], consumeErrors=True)
            dl.addCallback(self._maybeExit)
       
       
    
    # -------------
    # MQTT API
    # -------------

    def logMQTTEvent(self, msg, kind='info'):
        '''Logs important evento to MQTT'''
        record = { 'tstamp': datetime.datetime.utcnow(), 'type': kind, 'msg': msg}
        # aqui que el MQTT service le ponga el who
        self.queue['log'].append(record)
       

    # ----------
    # Events API
    # ----------
    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        self.scriptsService.onEventExecute(event, *args)


    def onStatus(self, status, tstamp):
        '''
        Decimate EMA status message and enqueue
        '''
        if self.counter == 0:
            self.queue['status'].append( (status, tstamp) )
        # Increments with modulo
        self.counter += 1
        self.counter %= self.NSAMPLES
        

    # ----------------
    # Helper functions
    # ----------------


    @inlineCallbacks
    def syncRTCActivity(self, skipInternet = False):
        '''
        Sync RTC activity to be programmed under the scheduler
        '''
        if not skipInternet:
            internet = yield self.internetService.hasConnectivity()
        else:
            internet = True
        if internet and self.options['host_rtc']:
            syncResult = yield self.serialService.syncRTC()
        elif internet and not self.options['host_rtc']:
            syncResult = yield self.serialService.syncRTC()
        else:
            syncResult = yield self.serialService.syncHostRTC()
        returnValue(syncResult)

    @inlineCallbacks
    def _maybeExit(self, results):
        log.debug("results = {results!r}", results=results)
        if results[0][1] == False:
            log.critical("No EMA detected. Exiting gracefully")
            #reactor.stop()
            #return
        syncResult = yield self.syncRTCActivity(skipInternet = True)
        if not syncResult:
            log.critical("could not sync RTCs. Existing gracefully")
            #reactor.stop()
            #return
        self.mqttService.startService()
        self.schedulerService.startService()
        self.addActivities()


    def addActivities(self):
        '''
        Register all activities to the scheduler
        '''

        @inlineCallbacks
        def activity10(activeInterval, inactiveInterval):
            '''
            Sunchronizes device parameters, then send MQTT registration
            '''
            self.logMQTTEvent(msg="At 10% of active time window {0}".format(activeInterval), kind='info')
            result = yield self.serialService.sync()
            if result:
                record = self.serialService.getParameters()
                self.queue['register'].append(record)

        @inlineCallbacks
        def activity30(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 30% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.serialService.getDailyMinMaxDump()
                self.queue['minmax'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity50(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 50% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.serialService.get5MinAveragesDump()
                self.queue['ave5min'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')
    
        @inlineCallbacks
        def activity70(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 70% of active time window {0}".format(activeInterval), kind='info')
            try:
                if self.options['relay_shutdown']:
                    yield self.serialService.nextRelayCycle(inactiveInterval)
                    yield self.serialService.auxRelayTimer(True)
                else:
                    yield self.serialService.auxRelayTimer(False)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity90(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 90% of active time window {0}".format(activeInterval), kind='info')
            syncResult = yield self.serialService.syncRTC()
            if not syncResult:
                self.logMQTTEvent(msg="EMA RTC could not be synchronized", kind='info')
            if self.options['shutdown']:
                log.warn("EMAd program shutting down gracefully in 10 seconds")
                reactor.callLater(10+random.random(), reactor.stop)
            

        active, inactive = self.schedulerService.findCurrentInterval()
        self.schedulerService.addActivity(activity10, 10, active, inactive)
        self.schedulerService.addActivity(activity30, 30, active, inactive)
        self.schedulerService.addActivity(activity50, 50, active, inactive)
        self.schedulerService.addActivity(activity70, 70, active, inactive)
        self.schedulerService.addActivity(activity90, 90, active, inactive)


    
       


        

__all__ = [ "EMAService" ]