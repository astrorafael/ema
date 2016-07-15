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
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.task        import deferLater
from twisted.internet.defer       import DeferredList
from twisted.application.service  import Service

#--------------
# local imports
# -------------

from .logger import setLogLevel
from .service.relopausable import Service

# ----------------
# Module constants
# ----------------


# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='web')



class WebService(Service):

    # Service name
    NAME = 'Web Service'

    def __init__(self, options):
        self.options  = options
        setLogLevel(namespace='web', levelStr=self.options['log_level'])
      

    
    def startService(self):
        log.info("starting {name}", name=self.name)
        Service.startService(self)
       
    
    def stopService(self):
        Service.stopService(self)

    @inlineCallbacks
    def hasConnectivity(self):
        '''
        Returns a deferred that when triggered returns True or False
        '''
        i = 1
        quorum = False
        while i <= self.N:
            log.info("probe attempt {i}/{N}", i=i, N=self.N)
            quorum = yield self.probe()
            if quorum:
               break
            i += 1
            log.info("waiting {s} seconds for next probe", s=self.T)
            yield deferLater(reactor, self.T, lambda: None)
        if not quorum:
            self.parent.onEventExecute('no_internet')
        returnValue(quorum)

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['internet']
        setLogLevel(namespace='web', levelStr=options['log_level'])
        log.info("new log level is {lvl}", lvl=options['log_level'])
        self.options = options
    
    # --------------
    # Helper methods
    # --------------

    

__all__ = [
    "WebService"
]