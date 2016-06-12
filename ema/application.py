# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#--------------------
# System wide imports
# -------------------

import sys
from collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted.logger   import Logger, LogLevel
from twisted.internet import task
from twisted.internet.defer  import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread

#--------------
# local imports
# -------------

from .config import VERSION_STRING, loadCfgFile
from .logger import setLogLevel

#from .mqttservice import MQTTService

from .serialservice import SerialService


# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='ema')



class EMAApplication(object):

    # Pointer to self
    instance = None

    # Signal handler polling period
    T = 1

    # Periodic task in seconds
    TLOG = 60


    def __init__(self, cfgFilePath, config_opts):
        
        EMAApplication.instance = self
        self.cfgFilePath = cfgFilePath
        self.queue  = { 'status':  deque() , 'ave5min':   deque(), 'ave1h': deque() }
        self.sigreload  = False
        self.sigpause   = False
        self.sigresume  = False
        self.reloadTask   = task.LoopingCall(self.sighandler)
        #self.reportTask   = task.LoopingCall(self.reporter)
        #self.statsTask    = task.LoopingCall(self.logCounters)
        #self.mqttService  = MQTTService(self, config_opts['mqtt'])
        self.serialService = SerialService(self, config_opts['serial'])
        setLogLevel(namespace='ema', levelStr=config_opts['ema']['log_level'])
        self.reloadTask.start(self.T, now=False) # call every T seconds

    def reporter(self):
        '''
        Periodic task to log queue size
        '''
        log.info("Readings queue size is {size}", size=len(self.queue['tess_readings']))


    def sighandler(self):
        '''
        Periodic task to check for signal events
        '''
        if self.sigreload:
            self.sigreload = False
            self.reload()
        if self.sigpause:
            self.sigpause = False
            self.pause()
        if self.sigresume:
            self.sigresume = False
            self.resume()


    def pause(self):
        '''
        Pause application
        '''
        pass
        #self.dbaseService.pauseService()
        #if not self.reportTask.running:
        #    self.reportTask.start(self.TLOG, now=True) # call every T seconds


    def resume(self):
        '''
        Resume application
        '''
        pass
        #self.dbaseService.resumeService()
        #if self.reportTask.running:
        #    self.reportTask.stop()


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
            pass
            #self.mqttService.reloadService(config_opts['mqtt'])
            #self.dbaseService.reloadService(config_opts['dbase'])
            level = config_opts['ema']['log_level']
            setLogLevel(namespace='ema', levelStr=level)
            log.info("new log level is {lvl}", lvl=level)
           
    
 
    def start(self):
        log.info('starting {ema}', ema=VERSION_STRING)
        self.serialService.startService()
        #self.mqttService.startService()
        #self.statsTask.start(self.T_STAT, now=False) # call every T seconds
    
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
