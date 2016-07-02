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

import signal

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer, Interface

from twisted.persisted import sob
from twisted.python    import components
from twisted.internet  import defer, task
from twisted.application.service  import Service, MultiService, Process

#--------------
# local imports
# -------------

from .interfaces import IPausable, IReloadable


@implementer(IPausable, IReloadable)
class PausableReloadableService(Service):

    paused = 0

    def __getstate__(self):
        '''I don't know if this makes sense'''
        dic = Service.__getstate__(self)
        if "paused" in dic:
            del dic['paused']
        return dic

    #--------------------------------
    # Extended Reloadable Service API
    # -------------------------------

    def reloadService(self):
        return defer.succeed(None)

    def pauseService(self):
        paused = 1
        return defer.succeed(None)

    def resumeService(self):
        paused = 0
        return defer.succeed(None)


@implementer(IPausable, IReloadable)
class PausableReloadableMultiService(MultiService):
    '''
    Container for pausable & reloadable services
    '''

    #-----------------------------------------
    # Extended Pausable-Reloadable Service API
    # ----------------------------------------

    def reloadService(self):
        PausableReloadableService.reloadService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.reloadService))
        return defer.DeferredList(l)


    def pauseService(self):
        PausableReloadableService.pauseService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.pauseService))
        return defer.DeferredList(l)


    def resumeService(self):
        PausableReloadableService.resumeService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.resumeService))
        return defer.DeferredList(l)
        
     

class TopLevelService(PausableReloadableMultiService):    
    '''
    This one is for use with the ReloadableApplication below
    '''    
    instance = None
    T = 1

    def __init__(self):
        PausableReloadableMultiService.__init__(self)
        TopLevelService.instance = self
        self.sigreload = False
        self.sigpause  = False
        self.sigresume = False
        self.periodicTask = task.LoopingCall(self._sighandler)

    def __getstate__(self):
        '''I don't know if this makes sense'''
        dic = PausableReloadableService.__getstate__(self)
        if "sigpause" in dic:
            del dic['sigreload']
        if "sigresume" in dic:
            del dic['sigreload']
        if "sigreload" in dic:
            del dic['sigreload']
        if "periodicTask" in dic:
            del dic['periodicTask']
        return dic

    def startService(self):
        self.periodicTask.start(self.T, now=False) # call every T seconds
        MultiService.startService()

    def stopService(self):
        self.periodicTask.cancel() # call every T seconds
        return MultiService.stopService()

    def _sighandler(self):
        '''
        Periodic task to check for signal events
        '''
        if self.sigpause:
            self.sigpause = False
            self.pause()
        if self.sigresume:
            self.sigresume = False
            self.resume()
        if self.sigreload:
            self.sigreload = False
            self.reload()
        
        
# ---------------
# SIGNAL HANDLERS
# ---------------

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
   

# Install signal handlers
signal.signal(signal.SIGHUP,  sigreload)
signal.signal(signal.SIGUSR1, sigpause)
signal.signal(signal.SIGUSR2, sigresume)

# -----------
# APPLICATION
# -----------

def Application(name, uid=None, gid=None):
    """
    Return a compound class.
    Return an object supporting the L{IService}, L{IPausable}, L{IServiceCollection},
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
    "PausableReloadableService",
    "PausableReloadableMultiService",
    "TopLevelService",
    "Application"
]