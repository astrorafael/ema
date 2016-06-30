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

from .logger import setLogLevel

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='inet')



class ReloadableService(Service):


    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        pass

    def pauseService(self):
        pass

    def resumeService(self):
        pass
        

__all__ = [
    ReloadableService
]