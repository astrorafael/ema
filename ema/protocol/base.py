# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#--------------------
# System wide imports
# -------------------

import datetime
import re
from   collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted.logger              import Logger, LogLevel
from twisted.internet            import reactor, defer, task
from twisted.internet.defer      import inlineCallbacks
from twisted.protocols.basic     import LineOnlyReceiver
from twisted.internet.protocol   import ClientFactory


#--------------
# local imports
# -------------

from ..        import PY2
from .status   import decodeAsDict
from .error    import EMATimeoutError
from .interval import Interval
from .commands import (
    BulkDumpCommand,
    Ping, 
    GetWatchdogPeriod,
    SetWatchdogPeriod,
    GetRTCDateTime,
    SetRTCDateTime, 
    GetCurrentWindSpeedThreshold,
    SetCurrentWindSpeedThreshold,  
    GetAverageWindSpeedThreshold, 
    SetAverageWindSpeedThreshold,
    GetAnemometerCalibrationConstant,
    SetAnemometerCalibrationConstant,  
    GetAnemometerModel,
    SetAnemometerModel,
    GetBarometerHeight,
    SetBarometerHeight, 
    GetBarometerOffset,
    SetBarometerOffset,
    GetCloudSensorThreshold,
    SetCloudSensorThreshold, 
    GetCloudSensorGain,
    SetCloudSensorGain,
    GetPhotometerThreshold,
    SetPhotometerThreshold, 
    GetPhotometerOffset,
    SetPhotometerOffset,
    GetPluviometerCalibration,
    SetPluviometerCalibration,
    GetPyranometerGain,
    SetPyranometerGain,
    GetPyranometerOffset,
    SetPyranometerOffset,
    GetRainSensorThreshold,
    SetRainSensorThreshold,
    GetThermometerDeltaTempThreshold,
    SetThermometerDeltaTempThreshold,
    GetVoltmeterThreshold,
    SetVoltmeterThreshold, 
    GetVoltmeterOffset,
    SetVoltmeterOffset,
    GetAuxRelaySwitchOnTime,
    SetAuxRelaySwitchOnTime, 
    GetAuxRelaySwitchOffTime,
    SetAuxRelaySwitchOffTime, 
    GetAuxRelayMode,
    SetAuxRelayMode,
    SetRoofRelayMode,
    GetDailyMinMaxDump,
    Get5MinAveragesDump,
    )


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

log  = Logger(namespace='serial')
log2 = Logger(namespace='protoc')

# ----------------
# Module functions
# ----------------

def match(line):
    '''Returns matched command descriptor or None'''
    for regexp in UNSOLICITED_PATTERNS:
        if regexp.search(line):
            log.debug("matched {pattern}", pattern=UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]['name'])
            return UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]
    return None



# -------
# Classes
# -------

class EMAProtocolFactory(ClientFactory):

    def startedConnecting(self, connector):
        log.debug('Factory: Started to connect.')

    def buildProtocol(self, addr):
        log.debug('Factory: Connected.')
        return EMAProtocol()

    def clientConnectionLost(self, connector, reason):
        log.debug('Factory: Lost connection. Reason: {reason}', reason=reason)

    def clientConnectionFailed(self, connector, reason):
        log.febug('Factory: Connection failed. Reason: {reason}', reason=reason)



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
        log2.debug("<== EMA {line}", line=line)
        handled = self._handleCommandResponse(line, now)
        if handled:
            return
        handled = self._handleUnsolicitedResponse(line, now)
        if handled:
            return
        log.debug("Unknown message {line}", line=line)


    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, including the delimiter.
        @type line: C{bytes}
        """
        log2.debug("==> EMA {line}", line=line)
        return self.transport.write(line)
        
    # ================
    # EMA Protocol API
    # ================

    def setStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus = callback

    # ------------
    # EMA Watchdog
    # ------------

    def ping(self):
        '''
        Send a keepalive message to EMA
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(Ping(), nretries=0)

    def getWatchdogPeriod(self, nretries=3):
        return self._enqueue(GetWatchdogPeriod(), nretries)

    def setWatchdogPeriod(self, value, nretries=3):
        return self._enqueue(SetWatchdogPeriod(value), nretries)

       

    # -------
    # EMA RTC
    # -------

    def getRTCDateTime(self, nretries=3):
        '''
        Get EMA current RTC time
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(GetRTCDateTime(), nretries)


    def setRTCDateTime(self, value, nretries=0):
        '''
        Set EMA current RTC time
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(SetRTCDateTime(value), nretries)

    # --------------
    # EMA Anemometer
    # --------------

    def getCurrentWindSpeedThreshold(self, nretries=3):
        return self._enqueue(GetCurrentWindSpeedThreshold(), nretries)

    def setCurrentWindSpeedThreshold(self, value, nretries=3):
        return self._enqueue(SetCurrentWindSpeedThreshold(value), nretries)

    def getAverageWindSpeedThreshold(self, nretries=3):
        return self._enqueue(GetAverageWindSpeedThreshold(), nretries)

    def setAverageWindSpeedThreshold(self, value, nretries=3):
        return self._enqueue(SetAverageWindSpeedThreshold(value), nretries)

    def getAnemometerCalibrationConstant(self, nretries=3):
        return self._enqueue(GetAnemometerCalibrationConstant(), nretries)

    def setAnemometerCalibrationConstant(self, value, nretries=3):
        return self._enqueue(SetAnemometerCalibrationConstant(value), nretries)

    def getAnemometerModel(self, nretries=3):
        return self._enqueue(GetAnemometerModel(), nretries)

    def setAnemometerModel(self, value, nretries=3):
        return self._enqueue(SetAnemometerModel(value), nretries)

    # -------------
    # EMA Barometer
    # -------------

    def getBarometerHeight(self, nretries=3):
        return self._enqueue(GetBarometerHeight(), nretries)

    def setBarometerHeight(self, value, nretries=3):
        return self._enqueue(SetBarometerHeight(value), nretries)

    def getBarometerOffset(self, nretries=3):
        return self._enqueue(GetBarometerOffset(), nretries)

    def setBarometerOffset(self, value, nretries=3):
        return self._enqueue(SetBarometerOffset(value), nretries)

    # ------------------
    # EMA Cloud Detector
    # ------------------

    def getCloudSensorThreshold(self, nretries=3):
        return self._enqueue(GetCloudSensorThreshold(), nretries)

    def setCloudSensorThreshold(self, value, nretries=3):
        return self._enqueue(SetCloudSensorThreshold(value), nretries)

    def getCloudSensorGain(self, nretries=3):
        return self._enqueue(GetCloudSensorGain(), nretries)

    def setCloudSensorGain(self, value, nretries=3):
        return self._enqueue(SetCloudSensorGain(value), nretries)

    # --------------
    # EMA Photometer
    # --------------

    def getPhotometerThreshold(self, nretries=3):
        return self._enqueue(GetPhotometerThreshold(), nretries)

    def setPhotometerThreshold(self, value, nretries=3):
        return self._enqueue(SetPhotometerThreshold(value), nretries)

    def getPhotometerOffset(self, nretries=3):
        return self._enqueue(GetPhotometerOffset(), nretries)

    def setPhotometerOffset(self, value, nretries=3):
        return self._enqueue(SetPhotometerOffset(value), nretries)

    # ---------------
    # EMA Pluviometer
    # ---------------

    def getPluviometerCalibration(self, nretries=3):
        return self._enqueue(GetPluviometerCalibration(), nretries)

    def setPluviometerCalibration(self, value, nretries=3):
        return self._enqueue(SetPluviometerCalibration(value), nretries)

    # ---------------
    # EMA Pyranometer
    # ---------------

    def getPyranometerGain(self, nretries=3):
        return self._enqueue(GetPyranometerGain(), nretries)

    def setPyranometerGain(self, value, nretries=3):
        return self._enqueue(SetPyranometerGain(value), nretries)

    def getPyranometerOffset(self, nretries=3):
        return self._enqueue(GetPyranometerOffset(), nretries)

    def setPyranometerOffset(self, value, nretries=3):
        return self._enqueue(SetPyranometerOffset(value), nretries)

    # ---------------
    # EMA Rain Sensor
    # ---------------

    def getRainSensorThreshold(self, nretries=3):
        return self._enqueue(GetRainSensorThreshold(), nretries)

    def setRainSensorThreshold(self, value, nretries=3):
        return self._enqueue(SetRainSensorThreshold(value), nretries)
  
    # ---------------
    # EMA Thermometer
    # ---------------

    def getThermometerDeltaTempThreshold(self, nretries=3):
        return self._enqueue(GetThermometerDeltaTempThreshold(), nretries)

    def setThermometerDeltaTempThreshold(self, value, nretries=3):
        return self._enqueue(SetThermometerDeltaTempThreshold(value), nretries)

    # -------------
    # EMA Voltmeter
    # -------------

    def getVoltmeterThreshold(self, nretries=3):
        '''
        Get EMA calibration Voltage Threshold
        Retunrs a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(GetVoltmeterThreshold(), nretries)

    def setVoltmeterThreshold(self, value, nretries=3):
        return self._enqueue(SetVoltmeterThreshold(value), nretries)

    def getVoltmeterOffset(self, nretries=3):
        '''
        Get EMA calibration Voltage Offset
        Retuns a deferred. 
        Success callback returns ?
        An errback may be invoked with EMATimeoutError
        '''
        return self._enqueue(GetVoltmeterOffset(), nretries)

    def setVoltmeterOffset(self, value, nretries=3):
        return self._enqueue(SetVoltmeterOffset(value), nretries)

    # ------------------
    # EMA Auxiliar Relay
    # -----------------

    def getAuxRelaySwitchOnTime(self, nretries=3):
        return self._enqueue(GetAuxRelaySwitchOnTime(), nretries)

    def setAuxRelaySwitchOnTime(self, value, nretries=3):
        return self._enqueue(SetAuxRelaySwitchOnTime(value), nretries)

    def getAuxRelaySwitchOffTime(self, nretries=3):
        return self._enqueue(GetAuxRelaySwitchOffTime(), nretries)

    def setAuxRelaySwitchOffTime(self, value, nretries=3):
        return self._enqueue(SetAuxRelaySwitchOffTime(value), nretries)

    def getAuxRelayMode(self, nretries=3):
        return self._enqueue(GetAuxRelayMode(), nretries)

    def setAuxRelayMode(self, value, nretries=3):
        return self._enqueue(SetAuxRelayMode(value), nretries)

    # --------------
    # EMA Roof Relay
    # --------------

    def setRoofRelayMode(self, value, nretries=3):
        return self._enqueue(SetRoofRelayMode(value), nretries)

    # --------------
    # EMA Bulk Dumps
    # --------------

    def getDailyMinMaxDump(self, nretries=0):
        return self._enqueue(GetDailyMinMaxDump(), nretries)

    def get5MinAveragesDump(self, nretries=0):
        return self._enqueue(Get5MinAveragesDump(), nretries)




    # --------------
    # Helper methods
    # --------------


    def _enqueue(self, request, nretries):
        '''
        Starts the ball rolling for the given request
        '''
        request.interval = Interval(Interval.maxDelay) if isinstance(request, BulkDumpCommand) else Interval() 
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
        log.debug("-> {request.name} (retries={request.retries}/{request.nretries})", 
            request=request)
        self.sendLine(str(request.encoded) if PY2 else bytes(request.encoded))


    def _responseTimeout(self):
        '''
        Handle lack of response
        '''
        request = self._queue[0]
        log.error("Command {request.name} {timeout}", request=request, timeout="timeout")
        if request.retries == request.nretries:
            request.deferred.errback(EMATimeoutError(request.name))
            request.deferred = None
            self._queue.popleft()
            del request
            if len(self._queue):    # Continue with the next command
                self._retry()
        else:
            request.retries += 1
            request.reset()
            self._retry()


    def _handleCommandResponse(self, line, tstamp):
        '''
        Handle incoming command responses.
        Returns True if handled or finished, False otherwise
        '''
        if len(self._queue) == 0:
            return False

        request = self._queue[0]
        handled, finished = request.decode(line)
        if finished:
            self._queue.popleft()
            request.alarm.cancel()
            if len(self._queue):    # Fires next command if any
                    self._retry()
            request.deferred.callback(request.getResult()) # Fire callback after _retry() !!!
            del request
        return handled or finished

    def _handleUnsolicitedResponse(self, line, tstamp):
        '''
        Handle unsolicited responses from EMA.
        Returns True if handled, False otherwise
        '''
        ur = match(line)
        if not ur:
            return False

        if ur['name'] == 'Current status message':
            curState = decodeAsDict(line)
            if self._onStatus:
                self._onStatus((curState, tstamp))
            return True
        if ur['name'] == 'Photometer begin':
            return True
        if ur['name'] == 'Photometer end':
            return True
        if ur['name'] == 'Thermopile I2C':
            return True
        log.error("We should never have reached this unsolicited response")
        return False
        