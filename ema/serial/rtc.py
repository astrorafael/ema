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
from ..utils    import setSystemTime

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
        Synchronizes EMA RTC Clock to Host Clock. 
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

    @inlineCallbacks
    def inverseSync(self):
        '''
        Synchronizes Host Clock Clock from EMA RTC as master clock. 
        Returns a deferred whose success callback value is a flag
        True = synch process ok, False = synch process went wrong
        '''
        max_drift = self.options['max_drift']
        try:
            utvalue = yield self.parent.protocol.getRTCDateTime()
        except EMATimeoutError as e:
            log.error("RTC inverseSync exception => {exception}", exception=e)
            returnValue(False)

        utnow = datetime.datetime.utcnow()
        if abs((utvalue - utnow).total_seconds()) <= max_drift:
            log.info("{title} already synchronized", title=param['title'])
            returnValue(True)

        log.warn("Host computer not synchronized with EMA[EMA = {EMA!s}] [Host = {host!s}]",  EMA=utvalue, host=utnow)
        
        try:
            log.info("Synchronizing Host computer from EMA RTC")
            # Assume Host Compuer works in UTC !!!
            setSystemTime(utvalue.timetuple())
            utvalue = yield self.parent.protocol.getRTCDateTime()
        except Exception as e:
            log.error("RTC inverseSync exception => {exception}", exception=e)
            returnValue(False)    
        # This may fail if the host compuer is not set in UTC.
        if abs((utvalue - datetime.datetime.utcnow()).total_seconds()) > max_drift:
            log.warn("Host Computer RTC still not synchronized")
            returnValue(False)
        
        returnValue(True)


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------



__all__ = [
    RealTimeClock,
]