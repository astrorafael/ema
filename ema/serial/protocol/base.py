# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

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

from .status   import decode, STATLEN
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
        self._onStatus     = set()                # callback sets
        self._onPhotometer = set()
        self._queue        = deque()              # Command queue
      
    def connectionMade(self):
        log.debug("connectionMade()")


    def lineReceived(self, line):
        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.5)
        line = line.lstrip(' \t\n\r') + b')'
        # Dirty hack: EMA status Voltage is sent as a non-ASCII character
        # 13.0V ==> chr(130) 
        # and the log system complains. I did my best t avoid it ...
        l = len(line)
        offending = (l == STATLEN) and (ord(line[3]) > 127)
        if offending:
            line2 = bytearray(line)
            line2[3] = b'+'
            log2.debug("<== EMA+[{l}] {line}", l=l, line=line2)
        else:
            log2.debug("<== EMA [{l}] {line}", l=l, line=line)
        handled = self._handleCommandResponse(line, now)
        if handled:
            return
        handled = self._handleUnsolicitedResponse(line, now)
        if handled:
            return
        if offending:
            log.debug("Unknown/Unexpected message")
        else:
            log.debug("Unknown/Unexpected message {line}", line=line)


    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, including the delimiter.
        @type line: C{bytes}
        """
        log2.debug("==> EMA [{l}] {line}", l=len(line), line=line)
        return self.transport.write(line)
        
    # ================
    # EMA Protocol API
    # ================

    def addStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus.add(callback)

    def delStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus.remove(callback)

    def addPhotometerCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onPhotometer.add(callback)

    def delPhotometerCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onPhotometer.remove(callback)

    # ------------
    # EMA Watchdog
    # ------------

    def ping(self, nretries=Ping.RETRIES):
        '''
        Send a keepalive message to EMA.
        See Ping (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(Ping(), nretries=nretries)


    def getWatchdogPeriod(self, nretries=GetWatchdogPeriod.RETRIES):
        '''
        Get EMA watchdong period before switching off aux relay.
        See GetWatchdogPeriod(commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetWatchdogPeriod(), nretries)


    def setWatchdogPeriod(self, value, nretries=SetWatchdogPeriod.RETRIES):
        '''
        Set EMA watchdog period before switching off aux relay with a new value.
        See SetWatchdogPeriod (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetWatchdogPeriod(value), nretries)

       

    # -------
    # EMA RTC
    # -------

    def getRTCDateTime(self, nretries=GetRTCDateTime.RETRIES):
        '''
        Get EMA current RTC time
        See GetRTCDateTime (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetRTCDateTime(), nretries)


    def setRTCDateTime(self, value, nretries=SetRTCDateTime.RETRIES):
        '''
        Set EMA current RTC time with a new value.
        See SetRTCDateTime (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetRTCDateTime(value), nretries)

    # --------------
    # EMA Anemometer
    # --------------

    def getCurrentWindSpeedThreshold(self, nretries=GetCurrentWindSpeedThreshold.RETRIES):
        '''
        Get EMA current Wind Speed Threshold.
        See GetCurrentWindSpeedThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetCurrentWindSpeedThreshold(), nretries)


    def setCurrentWindSpeedThreshold(self, value, nretries=SetCurrentWindSpeedThreshold.RETRIES):
        '''
        Set EMA current Wind Speed Threshold with a new value.
        See SetCurrentWindSpeedThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns the value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetCurrentWindSpeedThreshold(value), nretries)


    def getAverageWindSpeedThreshold(self, nretries=GetAverageWindSpeedThreshold.RETRIES):
        '''
        Get EMA average Wind Speed Threshold.
        See GetAverageWindSpeedThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAverageWindSpeedThreshold(), nretries)


    def setAverageWindSpeedThreshold(self, value, nretries=SetAverageWindSpeedThreshold.RETRIES):
        '''
        Set EMA average Wind Speed Threshold with a new value.
        See SetAverageWindSpeedThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns the value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAverageWindSpeedThreshold(value), nretries)


    def getAnemometerCalibrationConstant(self, nretries=GetAnemometerCalibrationConstant.RETRIES):
        '''
        Get EMA anemometer calibration constant.
        In case of 'Simple' anemometer this is the arm length in mm. In 'TX20', it should be 36.
        See GetAnemometerCalibrationConstant (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAnemometerCalibrationConstant(), nretries)


    def setAnemometerCalibrationConstant(self, value, nretries=SetAnemometerCalibrationConstant.RETRIES):
        '''
        Set EMA anemometer calibration constant with a new value.
        See SetAnemometerCalibrationConstant (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns the value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAnemometerCalibrationConstant(value), nretries)


    def getAnemometerModel(self, nretries=GetAnemometerModel.RETRIES):
        '''
        Get EMA anemometer model.
        See GetAnemometerModel (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAnemometerModel(), nretries)


    def setAnemometerModel(self, value, nretries=SetAnemometerModel.RETRIES):
        '''
        Set EMA anemometer mpdel with a new value,
        See SetAnemometerModel (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAnemometerModel(value), nretries)

    # -------------
    # EMA Barometer
    # -------------

    def getBarometerHeight(self, nretries=GetBarometerHeight.RETRIES):
        '''
        Get EMA barometer height.
        See GetBarometerHeight (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetBarometerHeight(), nretries)


    def setBarometerHeight(self, value, nretries=SetBarometerHeight.RETRIES):
        '''
        Set EMA barometer height with a new value.
        See SetBarometerHeight (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetBarometerHeight(value), nretries)

    def getBarometerOffset(self, nretries=GetBarometerOffset.RETRIES):
        '''
        Get EMA barometer offset.
        See GetBarometerOffset (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetBarometerOffset(), nretries)

    def setBarometerOffset(self, value, nretries=SetBarometerOffset.RETRIES):
        '''
        Set EMA barometer offset with a new value.
        See SetBarometerOffset (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetBarometerOffset(value), nretries)

    # ------------------
    # EMA Cloud Detector
    # ------------------

    def getCloudSensorThreshold(self, nretries=GetCloudSensorThreshold.RETRIES):
        '''
        Get EMA cloud sensor threshold.
        See GetCloudSensorThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetCloudSensorThreshold(), nretries)


    def setCloudSensorThreshold(self, value, nretries=SetCloudSensorThreshold.RETRIES):
        '''
        Set EMA cloud sensor threshold with a new value.
        See SetCloudSensorThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetCloudSensorThreshold(value), nretries)

    def getCloudSensorGain(self, nretries=GetCloudSensorGain.RETRIES):
        '''
        Get EMA cloud sensor gain.
        See GetCloudSensorGain (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetCloudSensorGain(), nretries)


    def setCloudSensorGain(self, value, nretries=SetCloudSensorGain.RETRIES):
        '''
        Set EMA cloud sensor gain with a new value.
        See SetCloudSensorGain (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetCloudSensorGain(value), nretries)

    # --------------
    # EMA Photometer
    # --------------

    def getPhotometerThreshold(self, nretries=GetPhotometerThreshold.RETRIES):
        '''
        Get EMA photometer threshold.
        See GetPhotometerThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetPhotometerThreshold(), nretries)


    def setPhotometerThreshold(self, value, nretries=SetPhotometerThreshold.RETRIES):
        '''
        Set EMA photometer threshold with a new value.
        See SetPhotometerThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetPhotometerThreshold(value), nretries)


    def getPhotometerOffset(self, nretries=GetPhotometerOffset.RETRIES):
        '''
        Get EMA photometer offset.
        See GetPhotometerOffset (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetPhotometerOffset(), nretries)


    def setPhotometerOffset(self, value, nretries=SetPhotometerOffset.RETRIES):
        '''
        Set EMA photometer offset with a new value.
        See SetPhotometerOffset (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetPhotometerOffset(value), nretries)

    # ---------------
    # EMA Pluviometer
    # ---------------

    def getPluviometerCalibration(self, nretries=GetPluviometerCalibration.RETRIES):
        '''
        Get EMA pluviometer calibration constant.
        See GetPluviometerCalibration (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetPluviometerCalibration(), nretries)

    def setPluviometerCalibration(self, value, nretries=SetPluviometerCalibration.RETRIES):
        '''
        Set EMA pluviometer calibration constant with a new value.
        See SetPluviometerCalibration (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetPluviometerCalibration(value), nretries)

    # ---------------
    # EMA Pyranometer
    # ---------------

    def getPyranometerGain(self, nretries=GetPyranometerGain.RETRIES):
        '''
        Get EMA pyranometer gain.
        See GetPyranometerGain (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetPyranometerGain(), nretries)


    def setPyranometerGain(self, value, nretries=SetPyranometerGain.RETRIES):
        '''
        Set EMA pyranometer gain with a new value.
        See SetPyranometerGain(commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetPyranometerGain(value), nretries)


    def getPyranometerOffset(self, nretries=GetPyranometerOffset.RETRIES):
        '''
        Get EMA pyranometer offset.
        See GetPyranometerOffset (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetPyranometerOffset(), nretries)


    def setPyranometerOffset(self, value, nretries=SetPyranometerOffset.RETRIES):
        '''
        Set EMA pyranometer offset with a new value.
        See SetPyranometerOffset (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetPyranometerOffset(value), nretries)

    # ---------------
    # EMA Rain Sensor
    # ---------------

    def getRainSensorThreshold(self, nretries=GetRainSensorThreshold.RETRIES):
        '''
        Get EMA rain sensor threshold (an integer).
        See GetRainSensorThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetRainSensorThreshold(), nretries)


    def setRainSensorThreshold(self, value, nretries=SetRainSensorThreshold.RETRIES):
        '''
        Set EMA rain sensor threshold with a new value.
        See SetRainSensorThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetRainSensorThreshold(value), nretries)
  
    # ---------------
    # EMA Thermometer
    # ---------------

    def getThermometerDeltaTempThreshold(self, nretries=GetThermometerDeltaTempThreshold.RETRIES):
        '''
        Get EMA thermometer delta Temp threshold.
        See GetThermometerDeltaTempThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetThermometerDeltaTempThreshold(), nretries)


    def setThermometerDeltaTempThreshold(self, value, nretries=SetThermometerDeltaTempThreshold.RETRIES):
        '''
        Set EMA thermometer delta Temp threshold with a new value.
        See SetThermometerDeltaTempThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetThermometerDeltaTempThreshold(value), nretries)

    # -------------
    # EMA Voltmeter
    # -------------

    def getVoltmeterThreshold(self, nretries=GetVoltmeterThreshold.RETRIES):
        '''
        Get EMA power supply power-off threshold.
        See GetVoltmeterThreshold (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetVoltmeterThreshold(), nretries)


    def setVoltmeterThreshold(self, value, nretries=SetVoltmeterThreshold.RETRIES):
        '''
        Set EMA power supply power-off threshold with a new value.
        See SetVoltmeterThreshold (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetVoltmeterThreshold(value), nretries)


    def getVoltmeterOffset(self, nretries=GetVoltmeterOffset.RETRIES):
        '''
        Get EMA voltmeter offset.
        See GetVoltmeterOffset (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetVoltmeterOffset(), nretries)


    def setVoltmeterOffset(self, value, nretries=SetVoltmeterOffset.RETRIES):
        '''
        Set EMA power supply power-off threshold with a new value.
        See SetVoltmeterOffset (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetVoltmeterOffset(value), nretries)

    # ------------------
    # EMA Auxiliar Relay
    # -----------------

    def getAuxRelaySwitchOnTime(self, nretries=GetAuxRelaySwitchOnTime.RETRIES):
        '''
        Get EMA auxiliar relay Switch On time.
        See GetAuxRelaySwitchOnTime (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAuxRelaySwitchOnTime(), nretries)


    def setAuxRelaySwitchOnTime(self, value, nretries=SetAuxRelaySwitchOnTime.RETRIES):
        '''
        Set EMA auxiliar relay Switch On time with a new value.
        See SetAuxRelaySwitchOnTime (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAuxRelaySwitchOnTime(value), nretries)


    def getAuxRelaySwitchOffTime(self, nretries=GetAuxRelaySwitchOffTime.RETRIES):
        '''
        Get EMA auxiliar relay Switch Off time.
        See GetAuxRelaySwitchOffTime (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAuxRelaySwitchOffTime(), nretries)


    def setAuxRelaySwitchOffTime(self, value, nretries=SetAuxRelaySwitchOffTime.RETRIES):
        '''
        Set EMA auxiliar relay Switch Off time with a new value.
        See SetAuxRelaySwitchOffTime (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAuxRelaySwitchOffTime(value), nretries)


    def getAuxRelayMode(self, nretries=GetAuxRelayMode.RETRIES):
        '''
        Get EMA auxiliar relay mode.
        See GetAuxRelayMode (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetAuxRelayMode(), nretries)


    def setAuxRelayMode(self, value, nretries=SetAuxRelayMode.RETRIES):
        '''
        Set EMA auxiliar relay with a new value.
        See SetAuxRelayMode (commands.py) for input value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetAuxRelayMode(value), nretries)

    # --------------
    # EMA Roof Relay
    # --------------

    def setRoofRelayMode(self, value, nretries=SetRoofRelayMode.RETRIES):
        '''
        Set EMA roof relay with a new value.
        See SetRoofRelayMode (commands.py) for returned value type, range and units.
        Retuns a Deferred whose success callback returns this value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(SetRoofRelayMode(value), nretries)

    # --------------
    # EMA Bulk Dumps
    # --------------

    def getDailyMinMaxDump(self, nretries=GetDailyMinMaxDump.RETRIES):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(GetDailyMinMaxDump(), nretries)


    def get5MinAveragesDump(self, nretries=Get5MinAveragesDump.RETRIES):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self._enqueue(Get5MinAveragesDump(), nretries)


    # --------------
    # Helper methods
    # --------------


    def _enqueue(self, request, nretries):
        '''
        Starts the ball rolling for the given request
        '''
        request.interval = Interval(initial=request.TIMEOUT['min'], 
                                    maxDelay=request.TIMEOUT['max'],
                                    factor=request.TIMEOUT['factor']) 
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
        Transmit/Retransmit the oldest request
        '''
        request = self._queue[0]
        t = request.interval()
        request.alarm = self.callLater(t, self._responseTimeout)
        log.info("Executing -> {request.name} (retries={request.retries}/{request.nretries}) [Timeout={t}]", 
            request=request, t=t)
        self.sendLine(request.getEncoded())


    def _responseTimeout(self):
        '''
        Handle lack of response from EMA by retries or raising a Failure
        '''
        request = self._queue[0]
        log.error("{timeout} {request.name}", request=request, timeout="Timeout")
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
            log.info("Completed -> {request.name} (retries={request.retries}/{request.nretries})", 
            request=request)
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
            curState, _ = decode(line)
            for callback in self._onStatus:
                callback(curState, tstamp)
            return True
        if ur['name'] == 'Photometer begin':
            return True
        if ur['name'] == 'Photometer end':
            for callback in self._onPhotometer:
                callback(curState, tstamp)
            return True
        if ur['name'] == 'Thermopile I2C':
            return True
        log.error("We should never have reached this unsolicited response")
        return False
        
__all__ = [ "EMAProtocolFactory", "EMAProtocol"]
