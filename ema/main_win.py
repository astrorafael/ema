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

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------


# ------------------------
# Module Utility Functions
# ------------------------

print("Starting {0} {1} Windows program".format(IService(application).name, __version__ ))
IService(application).startService()
reactor.run()
print("{0} {1} Windows program stopped".format( IService(application).name, __version__ ))

