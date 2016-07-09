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

from ..config import VERSION_STRING, loadCfgFile
from ..logger import setLogLevel

from ..service.relopausable import MultiService

#from ..mqtt.service import MQTTService, NAME as MQTT_NAME

from ..serial.service import SerialService
from ..scripts        import ScriptsService
from ..scheduler      import SchedulerService
from ..internet       import InternetService
from ..scripts        import AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound

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

    # Periodic task in seconds
    TLOG = 60


    def __init__(self, options, cfgFilePath):
        MultiService.__init__(self)
        self.cfgFilePath = cfgFilePath
        self.options     = options
        self.queue       = { 'status':  deque() , 'ave5min':   deque(), 'ave1h': deque() }
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
        try:
            yield defer.maybeDeferred(self.serialService.startService)
        except Exception as e:
            log.error("{excp}", excp=e)
            log.critical("Problems initializing {name}. Exiting gracefully", name=self.serialService.name)
            reactor.callLater(0,reactor.stop)
        else:
            self.internetService.startService()
            d1 = self.serialService.detectEMA(nretries=0)
            d2 = self.internetService.hasConnectivity()
            dl = DeferredList([d1,d2], consumeErrors=True)
            dl.addCallback(self._maybeExit)
       
       
    
    # -------------
    # MQTT API
    # -------------

    def logMQTTEvent(self, msg, kind='info'):
        '''Resets stat counters'''
        record = { 'tstamp': datetime.datetime.utcnow(), 'type': kind, 'msg': msg}
        # aqui falta encolarlo y que el MQTT service leponga el who

    # ----------
    # Events API
    # ----------
    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        self.scriptsService.onEventExecute(event, *args)

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


    def addActivities(self):


        @inlineCallbacks
        def foo10(*args):
            log.debug("   => HOLA, BEGIN FOO 10 <=")
            yield task.deferLater(reactor, 305, lambda: None)
            log.debug("   => HOLA, END   FOO 10 <=")

        @inlineCallbacks
        def foo30(*args):
            log.debug("   => HOLA, BEGIN FOO 30 <=")
            yield task.deferLater(reactor, 323, lambda: None)
            log.debug("   => HOLA, END   FOO 30 <=")

        @inlineCallbacks
        def foo50(*args):
            log.debug("   => HOLA, BEGIN FOO 50 <=")
            yield task.deferLater(reactor, 334, lambda: None)
            log.debug("   => HOLA, END   FOO 50 <=")

        @inlineCallbacks    
        def foo70(*args):
            log.debug("   => HOLA, BEGIN FOO 70 <=")
            yield task.deferLater(reactor, 351, lambda: None)
            log.debug("   => HOLA, END   FOO 70 <=")

        @inlineCallbacks
        def foo90(*args):
            log.debug("   => HOLA, BEGIN FOO 90 <=")
            yield task.deferLater(reactor, 302, lambda: None)
            log.debug("   => HOLA, END   FOO 90 <=")

        active, inactive = self.schedulerService.findCurrentInterval()
        self.schedulerService.addActivity(foo10, 10, active, inactive)
        self.schedulerService.addActivity(foo30, 30, active, inactive)
        self.schedulerService.addActivity(foo50, 50, active, inactive)
        self.schedulerService.addActivity(foo70, 70, active, inactive)
        self.schedulerService.addActivity(foo90, 90, active, inactive)


    @inlineCallbacks
    def _maybeExit(self, results):
        log.debug("results = {results!r}", results=results)
        if results[0][1] == False:
            log.critical("No EMA detected. Exiting gracefully")
            reactor.stop()
            return
        syncResult = yield self.syncRTCActivity(skipInternet = True)
        if not syncResult:
            log.critical("could not sync RTCs. Existing gracefully")
            reactor.stop()
            return
        self.schedulerService.startService()
        self.addActivities()
       


        

__all__ = [ "EMAService" ]