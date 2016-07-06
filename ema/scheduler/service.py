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

from ..service.relopausable import Service
from ..logger   import setLogLevel
from .intervals import Interval, IntervalList
from .error    import BadSlice


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

    # Service name
    NAME = 'Scheduler Service'

    # Interval constants
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    
    T = 9

    def __init__(self, options):
        Service.__init__(self)
        self.options = options
        self.callables = dict()
        self.periodicTask = None
        setLogLevel(namespace='sched', levelStr=self.options['log_level'])

    
    def startService(self):
        log.info("starting {name}", name=self.name)
        Service.startService(self)
        self.windows  = IntervalList.parse(self.options['intervals'], 15)
        self.gaps     = ~ self.windows
        self.periodicTask = task.LoopingCall(self._schedule)
        self.periodicTask.start(self.T, now=False) # call every T seconds
      

    def stopService(self):
        self.periodicTask.stop()
        Service.stopService(self)


    def addActivity(self, func, sliceperc):
        '''
        Add and activity (a callable) to be called at the current or next active window.
        '''
        if sliceperc not in [10, 30, 50, 70, 90]:
            raise BadSlice(sliceperc)
        active, inactive, where = self.findCurrentInterval()
        tPerc = (active.t0 + datetime.timedelta(seconds=int(active.duration()*sliceperc/100))).time()
        log.debug("Interval = {interval}, tPerc = {tPerc}", interval=active, tPerc=tPerc)
       

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['scheduler']
        log.info("new log level is {lvl}", lvl=options['log_level'])
        setLogLevel(namespace='inet', levelStr=options['log_level'])
        if self.periodicTask:
            self.periodicTask.reset()   # ESTO HAY QUE VERLO, A LO MEJOR HAY QUE CREAR OTRA TAREA
        self.options = options

    # --------------
    # Helper methods
    # ---------------

    def _schedule(self):
        '''
        Runs a schedule cycle.
        '''
        ts = datetime.datetime.utcnow().replace(microsecond=0)

    def findCurrentInterval(self):
        '''Find the current interval'''     
        tNow = datetime.datetime.utcnow()
        log.debug("checking active intervals {active}", active=self.windows)
        found, i = self.windows.find(tNow)
        if found:
            where    = self.ACTIVE
            active   = self.windows[i]
            inactive = self.gaps[i]
            log.info("now {now} we are in the active window {window}", now=tNow.strftime("%H:%M:%S"), window=active)
            log.info("Next inactive gap will be {gap}",  gap=inactive)
        else:
            log.debug("checking inactive intervals {inactive}", inactive=self.gaps)
            where = self.INACTIVE
            found, i = self.gaps.find(tNow)
            inactive = self.gaps[i]
            active   = self.windows[i+1 % len(self.windows)]
            log.info("now {now} we are in the inactive window {gap}", now=tNow.strftime("%H:%M:%S"), gap=inactive)
            log.info("Next active gap will be {window}", window=active)
        return active, inactive, where
           
__all__ = [
    "ScheduleService"
]