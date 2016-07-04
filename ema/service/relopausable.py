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
from twisted.python    import components
from twisted.internet  import defer, task
from twisted.application.service import IService, Service as BaseService, MultiService as BaseMultiService, Process

#--------------
# local imports
# -------------

from .interfaces import IPausable, IReloadable


# ----------------
# Global functions
# -----------------


def sigpause(signum, frame):
   '''
   Signal handler (SIGUSR1)
   '''
   TopLevelService.instance.sigpause = True

def sigresume(signum, frame):
   '''
   Signal handler (SIGUSR2)
   '''
   TopLevelService.instance.sigresume = True

def sigreload(signum, frame):
   '''
   Signal handler (SIGHUP)
   '''
   TopLevelService.instance.sigreload = True
   



# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------

@implementer(IPausable, IReloadable)
class Service(BaseService):

    paused = 0

    def __getstate__(self):
        '''I don't know if this makes sense'''
        dic = BaseService.__getstate__(self)
        if "paused" in dic:
            del dic['paused']
        return dic

    #--------------------------------
    # Extended Service API
    # -------------------------------

    def reloadService(self, options=None):
        pass

    def pauseService(self):
        paused = 1
        
    def resumeService(self):
        paused = 0
        
# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------

@implementer(IPausable, IReloadable)
class MultiService(BaseMultiService):
    '''
    Container for pausable & reloadable services
    '''

    #-----------------------------------------
    # Extended Pausable-Reloadable BaseService API
    # ----------------------------------------

    def reloadService(self, options=None):
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.reloadService, options))
        return defer.DeferredList(dl)


    def pauseService(self):
        paused = 1
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.pauseService))
        return defer.DeferredList(dl)


    def resumeService(self):
        paused = 0
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.resumeService))
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

    @staticmethod
    def sigreload(signum, frame):
        '''
        Signal handler (SIGHUP)
        '''
        TopLevelService.instance.sigreload = True

    @staticmethod
    def sigpause(signum, frame):
        '''
        Signal handler (SIGUSR1)
        '''
        TopLevelService.instance.sigpause = True

    @staticmethod
    def sigresume(signum, frame):
        '''
        Signal handler (SIGUSR2)
        '''
        TopLevelService.instance.sigresume = True

    def __init__(self):
        MultiService.__init__(self)
        TopLevelService.instance = self
        self.sigreloaded = False
        self.sigpaused   = False
        self.sigresumed  = False
        self.periodicTask = task.LoopingCall(self._sighandler)

    def __getstate__(self):
        '''I don't know if this makes sense'''
        dic = Service.__getstate__(self)
        if "instance" in dic:
            del dic['instance']
        if "sigpaused" in dic:
            del dic['sigpaused']
        if "sigresumed" in dic:
            del dic['sigresumed']
        if "sigreloaded" in dic:
            del dic['sigreloaded']
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
        if self.sigpaused:
            self.sigpaused = False
            self.pauseService()
        if self.sigresumed:
            self.sigresumed = False
            self.resumeService()
        if self.sigreloaded:
            self.sigreloaded = False
            self.reloadService()
        
if os.name != "nt":
    # Install these signal handlers
    signal.signal(signal.SIGHUP,  TopLevelService.sigreload)
    signal.signal(signal.SIGUSR1, TopLevelService.sigpause)
    signal.signal(signal.SIGUSR2, TopLevelService.sigresume)

# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------


def Application(name, uid=None, gid=None):
    """
    Return a compound class.
    Return an object supporting the L{IService}, L{IPausable}, L{IReloadable}, L{IServiceCollection},
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
]