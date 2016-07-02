# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


#--------------------
# System wide imports
# -------------------

# ---------------
# Twisted imports
# ---------------

from twisted.internet import reactor
from twisted.application.service import IService

#--------------
# local imports
# -------------

from .  import __version__
from .application import application
from .logger      import sysLogInfo
from .config      import VERSION_STRING

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------


# ------------------------
# Module Utility Functions
# ------------------------

sysLogInfo("Starting {0}".format(VERSION_STRING))
IService(application).startService()
reactor.run()
sysLogInfo("ema Linux service stopped {0}".format( __version__ ))
