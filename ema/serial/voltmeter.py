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
    EMAProtocol, EMAProtocolFactory, 
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
        self.parent.protocol.addStatusCallback(self.onStatus)
        scripts = chop(options["script"], ',')
        for script in scripts:
            pass
            #self.parent.notifier.addScript('VoltageLow', options['mode'], script)


    def onStatus(self, message, timestamp):
        self.voltage.append(message[POWER_VOLT])
        accum = sum(self.voltage)
        n     = len(self.voltage)
        average = accum / n
        if  self.PARAMS['threshold'] is None:
            log.debug("No thershold value yet from EMA")
            return
        lowvolt = self.options['delta'] + self.PARAMS['threshold']
        if average < lowvolt:
            pass
            log.warn("Low voltage detected")
            #self.parent.notifier.onEventExecute('VoltageLow', 
            #    '--voltage', "{0:.1f}".format(average), 
            #    '--threshold', "{0:.1f}".format(lowvolt), 
            #    '--size' , str(n))



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [
    Voltmeter,
]