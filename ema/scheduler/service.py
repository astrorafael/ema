# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

import datetime

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks
#from twisted.application.service  import Service

#--------------
# local imports
# -------------

from ..logger import setLogLevel
from .intervallist import IntervalList
from ..service.relopausable import Service


# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='sched')



class SchedulerService(Service):

    T = 9

    def __init__(self, options):
        Service.__init__(self)
        self.options = options
        self.periodicTask = task.LoopingCall(self._schedule)
        self.callables = dict()
        setLogLevel(namespace='sched', levelStr=self.options['log_level'])

    
    def startService(self):
        Service.startService(self)
        log.info("starting Scheduler Service")
        self.windows  = IntervalList.parse(self.options['intervals'], 15)
        self.periodicTask.start(self.T, now=False) # call every T seconds
        

    def stopService(self):
        self.periodicTask.stop()
        Service.stopService(self)

    def addActivity( func, tstamp ):
        '''
        Ads and activity ( a function) to be called at a given datetime.datetime.timestamp.
        '''
        li =  self.callables.get(tstamp, []) 
        li.append(func)
        self.callables[tstamp] = li

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self):
        log.info("new log level is {lvl}", lvl=self.new_options['log_level'])
        setLogLevel(namespace='inet', levelStr=self.new_options['log_level'])
        if self.periodicTask:
            self.periodicTask.reset()   # ESTO HAY QUE VERLO, A LO MEJOR HAY QUE CREAR OTRA TAREA
        self.options = self.new_options

    # --------------
    # Helper methods
    # ---------------

    def _schedule(self):
        '''
        Runs a schedule cycle.
        '''
        ts = datetime.datetime.utcnow().replace(microsecond=0)

    

__all__ = [
    "ScheduleService"
]