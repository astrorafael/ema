# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

import os
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks, returnValue


#--------------
# local imports
# -------------

from ..logger   import setLogLevel
from .protocol  import EMAProtocol, EMAProtocolFactory, EMARangeError, EMAReturnError, EMATimeoutError
from .devices   import Device

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
    
class Watchdog(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'period': { 
                'title' : 'Watchdog Period',
                'value' : None,
                'invariant': False,
                'get':   self.parent.protocol.getWatchdogPeriod,
                'set':   self.parent.protocol.setWatchdogPeriod
            },
        }
        self.pingTask  = task.LoopingCall(self.ping)

    def start(self):
        self.pingTask.start(self.options['period']//2, now=False)

    def stop(self):
        self.pingTask.stop()

    @inlineCallbacks
    def ping(self):
        try:
            res = yield self.parent.protocol.ping()
        except EMATimeoutError as e:
            pass


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [
    Watchdog,
]