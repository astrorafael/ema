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
from .devices   import Device
from .protocol  import (
    EMARangeError, EMAReturnError, EMATimeoutError,
    PERIOD as EMA_PERIOD, POWER_VOLT
)

from ..utils import chop

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

    def __init__(self, parent, options, upload_period, global_sync=True):
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
        self.voltage = deque(maxlen=(upload_period//EMA_PERIOD))
        #scripts = chop(options["script"], ',')
        #for script in scripts:
        #    self.parent.addScript('VoltageLow', script, options['mode'])
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        self.voltage.append(message[POWER_VOLT])
        n       = len(self.voltage)
        average = sum(self.voltage) / n
        if  self.PARAMS['threshold']['value'] is None:
            log.debug("No thershold value yet from EMA")
            return
        threshold = self.options['delta'] + self.PARAMS['threshold']['value']
        if average < threshold:
            self.parent.onEventExecute('low_voltage', average, threshold, n)

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [
    Voltmeter,
]