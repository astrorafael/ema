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
from twisted.python import components
from twisted.internet import defer
from twisted.application.service  import Service, MultiService, Process

#--------------
# local imports
# -------------


# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

class IReloadable(Interface):
    """
    A reloadable interface for services.
    Run start-up and shut-down code at the appropriate times.
    @type name:            C{string}
    @ivar name:            The name of the service (or None)
    @type running:         C{boolean}
    @ivar running:         Whether the service is running.
    """


    def reloadService():
        """
        Reloads the service by reading again its service configuration file.
        Configuration can be stored be a file (more likely) or a database.
        All this without stooping the service.
        @rtype: L{Deferred<defer.Deferred>}
        @return: a L{Deferred<defer.Deferred>} which is triggered when the
            service has finished reloading. If reloading is immediate,
            a value can be returned (usually, C{None}).
        """

    def pauseService():
        """
        Pauses the service. It can take a while, so it returns a Deferred
        @rtype: L{Deferred<defer.Deferred>}
        @return: a L{Deferred<defer.Deferred>} which is triggered when the
            service has finished shutting down. If shutting down is immediate,
            a value can be returned (usually, C{None}).
        """

    def resumeService():
        """
        Resumes the service.
        """

@implementer(IReloadable)
class ReloadableService(Service):

    #--------------------------------
    # Extended Reloadable Service API
    # -------------------------------

    def reloadService(self):
        return defer.succeed(None)

    def pauseService(self):
        return defer.succeed(None)

    def resumeService(self):
        pass


@implementer(IReloadable)
class ReloadableMultiService(MultiService):

    # Pointer to self in signal handlers
    instance = None

    #--------------------------------
    # Extended Reloadable Service API
    # -------------------------------

    def __init__(self):
        MultiService.__init__(self)
        ReloadableMultiService.instance = self
        self.sigreload  = False
        self.sigpause   = False
        self.sigresume  = False


    def reloadService(self):
        Service.reloadService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.reloadService))
        return defer.DeferredList(l)


    def pauseService(self):
        Service.pauseService(self)
        dl = []
        services = list(self)
        services.reverse()
        for service in services:
            dl.append(defer.maybeDeferred(service.pauseService))
        return defer.DeferredList(l)


    def resumeService(self):
        Service.resumeService(self)
        for service in self:
            service.resumeService()
      

# SIGNAL HANDLERS

def sigreload(signum, frame):
   '''
   Signal handler (SIGHUP)
   '''
   ReloadableMultiService.instance.sigreload = True
   
def sigpause(signum, frame):
   '''
   Signal handler (SIGUSR1)
   '''
   ReloadableMultiService.instance.sigpause = True

def sigresume(signum, frame):
   '''
   Signal handler (SIGUSR2)
   '''
   ReloadableMultiService.instance.sigresume = True

# Install signal handlers
signal.signal(signal.SIGHUP,  sigreload)
signal.signal(signal.SIGUSR1, sigpause)
signal.signal(signal.SIGUSR2, sigresume)

def ReloadableApplication(name, uid=None, gid=None):
    """
    Return a compound class.
    Return an object supporting the L{IService}, L{IReloadable}, L{IServiceCollection},
    L{IProcess} and L{sob.IPersistable} interfaces, with the given
    parameters. Always access the return value by explicit casting to
    one of the interfaces.
    """
    ret = components.Componentized()
    availableComponents = [ReloadableMultiService(), Process(uid, gid),
                           sob.Persistent(ret, name)]

    for comp in availableComponents:
        ret.addComponent(comp, ignoreClass=1)
    IService(ret).setName(name)
    return ret  

__all__ = [
    "IReloadable",
    "ReloadableService",
    "ReloadableMultiService",
    "ReloadableApplication"
]