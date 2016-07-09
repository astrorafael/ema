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
from twisted.internet.defer       import inlineCallbacks, returnValue
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

def toRefDate(ts):
    '''
    Sets the datetome.datetime object ts to the given reference date'''
    return ts.replace(year=2000, month=1, day=1, microsecond=0)

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


    def addActivity(self, func, sliceperc, active, inactive):
        '''
        Add and activity (a callable) to be called active window.
        '''
        if sliceperc not in [10, 30, 50, 70, 90]:
            raise BadSlice(sliceperc)
        tPerc = (active.t0 + datetime.timedelta(seconds=int(active.duration()*sliceperc/100))).time()
        log.debug("Adding activity to interval = {interval}, tPerc = {tPerc}", interval=active, tPerc=tPerc)
        values = self.callables.get(tPerc, list())
        self.callables[tPerc] = values
        # register non duplicate activities in order
        if (func, active, inactive) not in values:
            self.callables[tPerc].append((func, active, inactive))
       

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

    @inlineCallbacks
    def _schedule(self):
        '''
        Runs a schedule cycle.
        '''
        now = toRefDate(datetime.datetime.utcnow())
        tstamps = [ datetime.datetime.combine(now.date(), t) for t in sorted(self.callables.keys(), reverse=False) ]
        if len(tstamps) == 0:
            log.debug("Registering all activities again")
            self.parent.addActivities()
            returnValue(None)

        for target in tstamps:
            delta = (target - now).total_seconds()
            log.debug("target = {target}, delta={delta}", target=target, delta=delta)
            if 0<= delta < self.T:
                yield task.deferLater(reactor, delta, lambda: None)
                info = self.callables[target.time()]
                del self.callables[target.time()]
                for item in info: 
                    item[0](item[1], item[2])
                break
            elif delta < 0 and self.findActiveInactive(now) == self.ACTIVE:
                log.debug("deleting OBSOLETE activity at {target}", target=target)
                info = self.callables[target.time()]
                del self.callables[target.time()]
               

    def findCurrentInterval(self):
        '''Find the current interval'''     
        tNow = datetime.datetime.utcnow()
        found, i = self.windows.find(tNow)
        if found:
            active   = self.windows[i]
            inactive = self.gaps[i]
            log.debug("now {now} we are in the active window {window}", now=tNow.strftime("%H:%M:%S"), window=active)
            log.debug("Next inactive gap will be {gap}",  gap=inactive)
        else:
            found, i = self.gaps.find(tNow)
            inactive = self.gaps[i]
            active   = self.windows[i+1 % len(self.windows)]
            log.debug("now {now} we are in the inactive window {gap}", now=tNow.strftime("%H:%M:%S"), gap=inactive)
            log.debug("Next active gap will be {window}", window=active)
        return active, inactive


    def findActiveInactive(self, tNow):
        '''A shorter version which only returns ACTIVE or INACTIVE state'''
        found, i = self.windows.find(tNow)
        if found:
            where = self.ACTIVE
        else:
            where = self.INACTIVE
        return where
           
__all__ = [
    "ScheduleService"
]