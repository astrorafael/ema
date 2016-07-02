# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division


# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks
from twisted.application.service  import Service

#--------------
# local imports
# -------------

from ..logger import setLogLevel
from .intervallist import IntervalList
#from ..service import ReloadableService


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

    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='sched', levelStr=options['log_level'])
        self.periodicTask = task.LoopingCall(self._schedule)
        self.callables = dict()

    
    def startService(self):
        Service.startService(self)
        log.info("starting Scheduler Service")
        self.windows  = IntervalList.parse(self.options['intervals'], 15)
        self.periodicTask.start(self.T, now=False) # call every T seconds
        
       

    def stopService(self):
        self.periodicTask.cancel()
        Service.stopService(self)

    def addActivity( func, tstamp )
        '''
        Ads and activity ( a function) to be called at a given datetime.datetime.timestamp.
        '''
        li =  self.callables.get(tstamp, []) 
        li.append(func)
        self.callables[tstamp] = li

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='inet', levelStr=new_options['log_level'])
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        if self.deferred:
            log.debug("cancelling previous poll")
            self.deferred.cancel()
        self.options = new_options
        

    def pauseService(self):
        pass

    def resumeService(self):
        pass
        

    # --------------
    # Helper methods
    # ---------------

    def _schedule(self):
        '''
        Runs a schedule cycle.
        '''
        ts = datetime.datetime.utcnow().replace(microseconds=0)
        for f in sorted(self.callables.keys()):
            pass

    

__all__ = [
    "ScheduleService"
]