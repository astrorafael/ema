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

from   collections import deque

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
from .protocol  import (
    EMARangeError, EMAReturnError, EMATimeoutError,
    ROOF_RELAY, AUX_RELAY
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

class RoofRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {}
        self.switchon = deque(maxlen=2)
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[ROOF_RELAY]
        level = 1 if code == 'A' or code == 'a' else 0
        self.switchon.append(level)
        if len(self.switchon) < 2:
            return
        diff = self.switchon[0] - self.switchon[1]
        if diff < 0:    # Transition Off -> On
            self.parent.onEventExecute('roof_relay', 'On' , code)
        elif diff > 0:  # Transition On -> Off
            self.parent.onEventExecute('roof_relay', 'Off' , code)
        else:
            pass



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class AuxiliarRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'mode': { 
                'title' : 'Aux Relay Mode',
                'value' : None,
                'invariant': False,
                'get':   self.parent.protocol.getAuxRelayMode,
                'set':   self.parent.protocol.setAuxRelayMode
            },
        } 
        self.switchon = deque(maxlen=2)
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[AUX_RELAY]
        level = 1 if code == 'E' or code == 'e' else 0
        self.switchon.append(level)
        if len(self.switchon) < 2:
            return
        diff = self.switchon[0] - self.switchon[1]
        if diff < 0:    # Transition Off -> On
            self.parent.onEventExecute('aux_relay', 'On' , code)
        elif diff > 0:  # Transition On -> Off
            self.parent.onEventExecute('aux_relay', 'Off' , code)
        else:
            pass


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [

    "RoofRelay",
    "AuxiliarRelay",
]