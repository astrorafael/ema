# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#--------------------
# System wide imports
# -------------------

import os
import errno
import sys
import json
import math

import datetime
import re
from collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted.logger              import Logger, LogLevel
from twisted.internet            import reactor, defer, task
from twisted.internet.defer      import inlineCallbacks
from twisted.protocols.basic     import LineOnlyReceiver


#--------------
# local imports
# -------------

from ..        import PY2
from .status   import decode
from ..error   import EMATimeoutError
from .commands import Ping, GetRTC
from .interval import Interval

# ----------------
# Module constants
# ----------------

# Unsolicited Responses Patterns
UNSOLICITED_RESPONSES = (
    {
        'name'    : 'Current status message',
        'pattern' : '^\(.{76}a\d{4}\)',       
    },
    {
        'name'    : 'Photometer begin',
        'pattern' : '^\(\d{2}:\d{2}:\d{2} wait\)',            
    },
    {
        'name'    : 'Photometer end',
        'pattern' : '^\(\d{2}:\d{2}:\d{2} mv:\d{2}\.\d{2}\)',            
    },
    {
        'name'    : 'Thermopile I2C',
        'pattern' : '^\(>10[01] ([+-]\d+\.\d+)\)',            
    },
)

UNSOLICITED_PATTERNS = [ re.compile(ur['pattern']) for ur in UNSOLICITED_RESPONSES ]

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')

# ----------------
# Module functions
# ----------------

def match(line):
    '''Returns matched command descriptor or None'''
    for regexp in UNSOLICITED_PATTERNS:
        if regexp.search(line):
            log.debug("matched {pattern}", pattern=UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]['name'])
            return UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]
    log.debug("No unsolicited pattern matched input")
    return None

class EMAProtocol(LineOnlyReceiver):


    # So that we can patch it in tests with Clock.callLater ...
    callLater = reactor.callLater

    # -------------------------
    # Twisted Line Receiver API
    # -------------------------

    def __init__(self):
        '''Sets the delimiter to the closihg parenthesis'''
        LineOnlyReceiver.delimiter = b')'
        self._onStatus = None
        self._queue    = deque()              # Command queue
      
    def connectionMade(self):
        log.debug("connectionMade()")


    def lineReceived(self, line):
        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.5)
        line = line.lstrip(' \t\n\r') + b')'
        log.debug("<== EMA {line}", line=line)

        # Match against current pending command, if any
        if len(self._queue) > 0:
            request = self._queue[0]
            ack = request.decode(line)
            if ack:
                self._queue.popleft()
                request.alarm.cancel()
                response = request.getResponse()
                request.deferred.callback(response)
                del request
                if len(self._queue):    # Fires next command if any
                    self._retry()
                return
            
        # Match unsolicited reponses
        ur = match(line)
        if ur:
            if ur['name'] == 'Current status message':
                curState = decode(line)
                if self._onStatus:
                    self._onStatus((curState, timestamp))
            elif ur['name'] == 'Photometer begin':
                pass
            elif ur['name'] == 'Photometer end':
                pass
            elif ur['name'] == 'Thermopile I2C':
                pass
            else:
                log.error("We should never hace reached this")

    

    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, including the delimiter.
        @type line: C{bytes}
        """
        log.debug("==> EMA {line}", line=line)
        return self.transport.write(line)
        
    # ================
    # EMA Protocol API
    # ================

    def setStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus = callback


    def ping(self):
        '''
        Send a keepalive message to EMA
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(Ping(), nretries=0)

    
    def getTime(self):
        '''
        Get EMA current RTC time
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(GetRTC(), nretries=0)


    def setTime(self, tstamp=None):
        '''
        Set EMA current RTC time
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def getVoltageOffset(self):
        '''
        Get EMA calibration Voltage Offset
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass

    def setVoltageOffset(self, value):
        '''
        Set EMA calibration Voltage Offset
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def getVoltageThreshold(self):
        '''
        Get EMA calibration Voltage Threshold
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def setVoltageThreshold(self, value):
        '''
        Set EMA calibration Voltage Threshold
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass
 

    def roofRelaySwitch(self, onFlag):
        '''
        Roof Relay force open/close. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def auxRelaySwitch(self, onFlag):
        '''
        Auxiliar Relay force open/close. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def auxRelayGetStatus(self):
        '''
        Get Auxiliar Relay status. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass

    def auxRelaySetMode(self, mode):
        '''
        Set Aunx relay mode, either AUTO, MANUAL or TIMED 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass


    def auxRelayTimerOn(self, time):
        '''
        Programs Auxiliar Relay 'On' time in TIMED mode. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass

    def auxRelayTimerOff(self, time):
        '''
        Programs Auxiliar Relay 'Off' time in TIMED mode. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass

    def getHourlyMinMax(self, time):
        '''
        Get 24h Hourly MinMax Bulk Dump. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass

    def get5MinData(self, time):
        '''
        24h 5m Averages Bulk Dump. 
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        pass




    # --------------
    # Helper methods
    # --------------


    def _enqueue(self, request, nretries):
        '''
        Starts the ball rolling for the given request
        '''
        request.interval = Interval()   
        request.nretries = nretries
        request.retries  = 0  
        request.deferred = defer.Deferred()
        request.encode()
        request.reset()
        self._queue.append(request)
        if len(self._queue) == 1:    # start the ball rolling
            self._retry()
        return request.deferred

    def _retry(self):
        '''
        Transmit/Retransmit the front request
        '''
        request = self._queue[0]
        request.alarm = self.callLater(request.interval(), self._responseTimeout)
        log.debug("==> {request.__class__.__name__} (retries={request.retries}/{request.nretries})", 
            request=request)
        self.sendLine(str(request.encoded) if PY2 else bytes(request.encoded))


    def _responseTimeout(self):
        '''
        Handle lack of response
        '''
        request = self._queue[0]
        log.error("Command {request.__class__.__name__} {timeout}", 
             request=request, timeout="timeout")
        if request.retries == request.nretries:
            request.deferred.errback(EMATimeoutError(request.__class__.__name__))
            request.deferred = None
            self._queue.popleft()
            del request
            if len(self._queue):    # Continue with the next command
                self._retry()
        else:
            request.retries += 1
            self._retry()


    