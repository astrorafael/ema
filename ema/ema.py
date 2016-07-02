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
from twisted.internet import task, reactor
from twisted.internet.defer  import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread

#--------------
# local imports
# -------------

from .config import VERSION_STRING, loadCfgFile
from .logger import setLogLevel

from .service.relopausable import MultiService

#from .mqttservice import MQTTService

from .serial.service import SerialService
from .internet       import InternetService
from .scripts        import ScriptsService, AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from .scheduler      import SchedulerService


# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='ema')



class EMAService(MultiService):

    # Periodic task in seconds
    TLOG = 60


    def __init__(self, options):
        MultiService.__init__(self)
        self.cfgFilePath = None
        self.queue       = { 'status':  deque() , 'ave5min':   deque(), 'ave1h': deque() }
        self.options     = options
        setLogLevel(namespace='ema', levelStr=self.options['log_level'])
        

    def reporter(self):
        '''
        Periodic task to log queue size
        '''
        log.info("Readings queue size is {size}", size=len(self.queue['tess_readings']))



    @inlineCallbacks
    def reload(self):
        '''
        Reload application parameters
        '''
        log.warn("{ema} config being reloaded", ema=VERSION_STRING)
        try:
            config_opts  = yield deferToThread(loadCfgFile, self.cfgFilePath)
        except Exception as e:
            log.error("Error trying to reload: {excp!s}", excp=e)
        else:
            self.options = config_opts
            MultiService.reload(self)
           
    
    def startService(self):
       
        log.info('starting {ema}', ema=VERSION_STRING)
        MultiService.startService(self)
       
       
    
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

    # -------------
    # log stats API
    # -------------

    def resetCounters(self):
        '''Resets stat counters'''
        pass
        #self.mqttService.resetCounters()
        #self.dbaseService.resetCounters()

    def logCounters(self):
        '''log stat counters'''
        pass
        #self.mqttService.logCounters()
        #yield self.dbaseService.logCounters()
        self.resetCounters()

__all__ = [ "EMAService" ]