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


IService(application).startService()
reactor.run()
