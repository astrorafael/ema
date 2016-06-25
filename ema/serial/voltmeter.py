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
from .devices   import Device
from .protocol  import (
    EMAProtocol, EMAProtocolFactory, 
    EMARangeError, EMAReturnError, EMATimeoutError,
    PERIOD as EMA_PERIOD
)

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

class Voltmeter(Device):

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Threshold',
                'value' : None,
                'invariant': False,
                'get':   self.parent.protocol.getVoltmeterThreshold,
                'set':   self.parent.protocol.setVoltmeterThreshold
            },
            'offset': { 
                'title' : 'Offset',
                'option': 'offset',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getVoltmeterOffset,
                'set':   self.parent.protocol.setVoltmeterOffset
            },
        }

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [
    Voltmeter,
]