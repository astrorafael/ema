# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

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



#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RealTimeClock(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'max_drift': { 
                'title' : 'RTC',
                'value' : None,
                'invariant': False,
                'get':   self.parent.protocol.getRTCDateTime,
                'set':   self.parent.protocol.setRTCDateTime
            },
        }

    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes parameters. 
        Returns a deferred whose success callback value is a flag
        True = synch process ok, False = synch process went wrong
        '''
        param     = self.PARAMS['max_drift']
        max_drift = self.options['max_drift']
        try:
            value = yield param['get']()
        except EMATimeoutError as e:
            log.error("RTC sync exception => {exception}", exception=e)
            returnValue(False)
        now = datetime.datetime.utcnow()
        if abs((value - now).total_seconds()) > max_drift:
                log.warn("{title} not synchronized [EMA = {EMA!s}] [Host = {host!s}]", title=param['title'], EMA=value, host=now)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    try:
                        value = yield param['set'](None)
                    except EMATimeoutError as e:
                        log.error("RTC sync exception => {exception}", exception=e)
                        returnValue(False)
                    if abs((value - datetime.datetime.utcnow()).total_seconds()) > max_drift:
                        log.warn("{title} still not synchronized", title=param['title'])
        else:
            log.info("{title} already synchronized", title=param['title'])
        returnValue(True)


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------



__all__ = [
    RealTimeClock,
]