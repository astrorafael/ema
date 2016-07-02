# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# Some parts:
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#--------------------
# System wide imports
# -------------------

from __future__ import division

import os
import signal

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer, Interface

from twisted.persisted import sob
from twisted.python import components
from twisted.internet import defer, task
from twisted.application.service import IService, Service as BaseService, MultiService as BaseMultiService, Process

#--------------
# local imports
# -------------

from .interfaces import IReloadable

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


def sigreload(signum, frame):
   '''
   Signal handler (SIGHUP)
   '''
   TopLevelService.instance.sigreload = True
   

if os.name != "nt":
    # Install this signal handlers
    signal.signal(signal.SIGHUP,  sigreload)

# -----------------------
# Module global variables
# -----------------------


# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------

@implementer(IReloadable)
class Service(BaseService):

    #--------------------------------
    # Extended Service API
    # -------------------------------

    def reloadService(self):
        pass

# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------

@implementer(IReloadable)
class MultiService(BaseMultiService):
    '''
    Container for reloadable services
    '''

    #--------------------------------
    # Extended Service API
    # -------------------------------
       
    def reloadService(self):
        Service.reloadService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.reloadService))
        return defer.DeferredList(dl)

# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------


class TopLevelService(MultiService):    
    '''
    This one is for use with the Application below
    '''    
    instance = None
    T = 1

    def __init__(self):
        MultiService.__init__(self)
        TopLevelService.instance = self
        self.sigreload  = False
        self.periodicTask   = task.LoopingCall(self._sighandler)

    def __getstate__(self):
        '''I don't know if this makes sense'''
        dic = BaseService.__getstate__(self)
        if "sigreload" in dic:
            del dic['sigreload']
        if "periodicTask" in dic:
            del dic['periodicTask']
        return dic

    def startService(self):
        self.periodicTask.start(self.T, now=False) # call every T seconds
        BaseMultiService.startService(self)

    def stopService(self):
        self.periodicTask.cancel() # call every T seconds
        return BaseMultiService.stopService(self)


    def _sighandler(self):
        '''
        Periodic task to check for signal events
        '''
        if self.sigreload:
            self.sigreload = False
            self.reloadService()
        

# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------


def Application(name, uid=None, gid=None):
    """
    Return a compound class.
    Return an object supporting the L{IService}, L{IReloadable}, L{IServiceCollection},
    L{IProcess} and L{sob.IPersistable} interfaces, with the given
    parameters. Always access the return value by explicit casting to
    one of the interfaces.
    """
    ret = components.Componentized()
    availableComponents = [TopLevelService(), Process(uid, gid),
                           sob.Persistent(ret, name)]

    for comp in availableComponents:
        ret.addComponent(comp, ignoreClass=1)
    IService(ret).setName(name)
    return ret  

__all__ = [
    "Service",
    "MultiService",
    "TopLevelService",
    "Application",
    "sigreload"
]