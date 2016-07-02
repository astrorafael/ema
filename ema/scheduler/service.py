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


    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='sched', levelStr=options['log_level'])

    
    def startService(self):
        Service.startService(self)
        self.windows  = IntervalList.parse(self.options['intervals'], 15)
        log.info("starting Scheduler Service")
        
       

    def stopService(self):
       Service.stopService(self)


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

    def _syncHasConnectivity(self):
        '''
        Returns last cached quorum state.
        '''
        return self.quorum

    def _asyncHasConnectivity(self):
        '''
        Returns a deferred that when triggered returns True or False
        '''
        d1 = self.agent.request('HEAD',self.options['site1'],
            Headers({'User-Agent': ['Twisted Web Client']}),
            None)
        d2 = self.agent.request('HEAD',self.options['site2'],
            Headers({'User-Agent': ['Twisted Web Client']}),
            None)
        d3 = self.agent.request('HEAD',self.options['site3'],
            Headers({'User-Agent': ['Twisted Web Client']}),
            None)

        d1.addCallbacks(self._logResponse, self._logFailure)
        d2.addCallbacks(self._logResponse, self._logFailure)
        d3.addCallbacks(self._logResponse, self._logFailure)
        self.deferred = DeferredList([d1,d2,d3], consumeErrors=True)
        self.deferred.addCallback(self._quourm)
        return self.deferred
   
  
    def _logFailure(self, failure):
        log.debug("reported {message}", message=failure.getErrorMessage())
        return failure

    def _logResponse(self, response):
        log.debug("from {response.request.absoluteURI}: {response.code}", response=response)
        return True

    def _quourm(self, result):
        '''
        Perform a voting between three results. Majority wins.
        Receices a list of 3 tuples each with (success,value)
        Value is either the value returned by _logResponse or _logFailure
        '''
        self.quorum = (result[0][0] and result[1][0]) or (result[0][0] and result[2][0]) or (result[1][0] and result[2][0])
        log.info("Internet connectivity = {quorum}", quorum=self.quorum)
        return self.quorum


__all__ = [
    "InternetService"
]