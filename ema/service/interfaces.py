# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer, Interface

class IPausable(Interface):
    """
    A pausable interface for services.
    Run pause/resume code at the appropriate times.
    @type paused:         C{boolean}
    @ivar paused:         Whether the service is paused.
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
        Resumes the service. It can take a while, so it returns a Deferred
        @rtype: L{Deferred<defer.Deferred>}
        @return: a L{Deferred<defer.Deferred>} which is triggered when the
            service has finished shutting down. If shutting down is immediate,
            a value can be returned (usually, C{None}).
        """


class IReloadable(Interface):
    """
    A reloadable interface for services.
    Run reload code at the appropriate times.
    """


    def reloadService():
        """
        Reloads the service by reading on the fly its service configuration file.
        Configuration can be stored be a file (more likely) or a database.
        @rtype: L{Deferred<defer.Deferred>}
        @return: a L{Deferred<defer.Deferred>} which is triggered when the
            service has finished reloading. If reloading is immediate,
            a value can be returned (usually, C{None}).
        """


__all__ = [ "IReloadable", "IPausable" ]