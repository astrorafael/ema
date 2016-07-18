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
import math
from collections import deque

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

from . import PY2

# ----------------
# Module constants
# ----------------
# Constants belonging the EMA Protocol v2, for portability issues
# EMA protocol is sometimes revised
#
VERSION = 2

# EMA send status messages every 5 seconds
PERIOD = 5

# Status message length including ( and ) 
STATLEN = 83            

# -------------------------------------------------------
# OFFSETS IN GEHERAL STATUS MESSAGE
# 'end' constants are 1 character past the given field , 
# to directly use in string slicing with [:]
# These constants are for internal use only
# --------------------------------------------------------

SRRB = 1          # Status Roof Relay Begin
SRRE = SRRB + 1      # Status Roof Relay End

SARB = 2             # Status Aux Relay Begin
SARE = SARB + 1      # Status Aux Relay End

SPSB = 3             # Status Power Supply Begin
SPSE = SPSB + 1      # Status Power Supply End

SRAB = 5       # Status Rain Detector Begin
SRAE = SRAB + 3      # Status Rain Detector End

SCLB = 9       # Status Cloud sensor Begin
SCLE = SCLB + 3      # Status Cloud Sensor Emd

SCBB = 13         # Status Calibrated Barometric pressure Begin
SCBE = SCBB + 5      # Status Calibrated Barometric oressure End

SABB = 19         # Status Absolute Barometric pressure Begin
SABE = SABB + 5      # Status Absolute Barometric pressuer End

SPCB = 25         # Status Pluviometer Current value Begin
SPCE = SPCB +  4  # Status Pluviometer Current value End

SPAB = 30         # Status Pluviometer Accumulated value Begin
SPAE = SPAB + 4      # Status Pluviometer Accumulated value End

SPYB = 35         # Status Pyrometer Begin
SPYE = SPYB + 3   # Status Pyrometer End

SPHB = 39         # Status Photometer Begin
SPHE = SPHB + 5      # Status Photometer End

SATB = 45         # Status Ambient Temperature Begin
SATE = SATB + 4   # Status Ambient Temperature End

SRHB = 50         # Status Relative Humidity Begin
SRHE = SRHB + 3   # Status Relative Humidity End

SDPB = 54         # Status Dew Point Begin
SDPE = SDPB + 4   # Status Dew Point End

SAAB = 64         # Status Anemometer Accumlated value Begin
SAAE = SAAB + 3   # Status Anemometer Accumulated value End

SACB = 68         # Status Anemometer Current wind Begin
SACE = SACB + 4   # Status Anemometer Curent wind End

SWDB = 73         # Status Wind Direction Begin
SWDE = SWDB + 3   # Status Wind direction End

SMTB = 77         # Status Message Type Begin
SMTE = SMTB + 1   # Status Message Type End

SMFB = 78         # Status Message Flash Page Begin
SMFE = SMFB + 4   # Status Message Flash Page End 

# Status Message Types
MTCUR = 'a'       # Current values status message type
MTHIS = 't'       # 24h historic values message type
MTISO = '0'       # 24h isolated historic values message type
MTMIN = 'm'       # daily minima message type
MTMAX = 'M'       # daily maxima message type

STATUS_TYPE = {
  'a' : 'current',
  't' : 'historic',
  'm' : 'minima',
  'M' : 'maxima',
  '0' : 'isolated' 
}

# Independen Thermpile message
THERMOINF = 4     # Thermopile digit string offset ('0' = infrared ; '1' = ambient)

# Offset to magnitude visual digits (18:35:43 mv:24.00)
MVI = 13 # Integer part
MVD = 16 # decimal part

# Timestamp format, the EMA way
EMA_STRFTIME = "(%H:%M:%S %d/%m/%Y)"


K_INV_LOG10_2_5 = 1.0/math.log10(2.5)
K_INV_230      = (1.0/230)

# When everithing goes wrong in computing magnitude
MAG_CLIP_VALUE = 24

# -------------------------------------------
# Indexes to the decoded status message array
# -------------------------------------------

ROOF_RELAY     =  0
AUX_RELAY      =  1
POWER_VOLT     =  2
RAIN_PROB      =  3
CLOUD_LEVEL    =  4
ABS_PRESSURE   =  5
CAL_PRESSURE   =  6
CUR_PLUVIOM    =  7
ACC_PLUVIOM    =  8
PYRANOMETER    =  9
PHOTOM_FREQ    = 10
AMB_TEMP       = 11
HUMIDITY       = 12
DEW_POINT      = 13
CUR_WIND_SPEED = 14
AVE_WIND_SPEED = 15
WIND_DIRECTION = 16

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
        'pattern' : '^\(\d{2}:\d{2}:\d{2} mv:(\d{2}\.\d{2})\)',            
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

def encodeFreq(hertz):
    '''Encode frequency in Hertz into EMA format field'''
    hertz *= 1000               # to milihertz
    exp = 0
    while hertz > 9999:
        hertz /= 10
        exp += 1
    return "%d%04d" % (exp, hertz)
        
def decodeFreq(enc):
    '''
    Decode a EMMMM frequency EMA format fragment. 
    Returns frequency in Hertz
    '''
    exp  = int(enc[0])-3
    mant = int(enc[1:5])
    return round(mant*math.pow(10, exp), 3)
        
# --------------------------------------------------------------------
# Visual magnitude computed by the following C function
# --------------------------------------------------------------------
# float HzToMag(float HzTSL ) 
# {
#  float mv;
#     mv = HzTSL/230.0;             // Iradiancia en (uW/cm2)/10
#     if (mv>0){
#        mv = mv * 0.000001;       //irradiancia en W/cm2
#        mv = -1*(log10(mv)/log10(2.5));    //log en base 2.5
#        if (mv < 0) mv = 24;
#     }
#     else mv = 24;
#
#     return mv;
#}
# --------------------------------------------------------------------

def magnitude(frequency):
    '''Extract and Transform into Visual maginitued per arcsec 2'''
    mv = frequency * K_INV_230 * 1.0e-6
    if mv > 0.0:
        mv = -1.0 * math.log10(mv) * K_INV_LOG10_2_5
        mv = MAG_CLIP_VALUE if mv < 0.0 else mv
    else:
        mv = MAG_CLIP_VALUE
    return round(mv,1)


def match_unsolicited(line):
    '''Returns matched command descriptor or None'''
    for regexp in UNSOLICITED_PATTERNS:
        matchobj = regexp.search(line)
        if matchobj:
            log.debug("matched {pattern}", pattern=UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]['name'])
            return UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)], matchobj
    return None, None

def decodeStatus(line):
    '''Decode an EMA status line'''
    #status = { 'rev': VERSION, 'tstamp': timestamp.strftime(TSTAMP_FORMAT) }
    status            = []
    status.append(line[SRRB])                              # Roof Relay state character
    status.append(line[SARB])                              # Aux Relay state character
    status.append(round(ord(line[SPSB])       * 0.10, 1))  # Volts
    status.append(round(int(line[SRAB:SRAE])  * 0.10, 1))  # Rain %
    status.append(round(int(line[SCLB:SCLE])  * 0.10, 1))  # Cloud %
    status.append(round(int(line[SABB:SABE])  * 0.10, 1))  # Abs Press HPa
    status.append(round(int(line[SCBB:SCBE])  * 0.10, 1))  # Calib Press HPa
    status.append(round(int(line[SPCB:SPCE])  * 0.10, 1))  # Current pluviom mm
    status.append(int(line[SPAB:SPAE]))                    # Accumulated pluviom mm
    status.append(round(int(line[SPYB:SPYE])  * 0.10, 1))  # Pyranomenter %
    status.append(decodeFreq(line[SPHB:SPHE]))             # Photometer Hz
    status.append(round(int(line[SATB:SATE]) * 0.10, 1))   # Ambient Temp deg C
    status.append(round(int(line[SRHB:SRHE]) * 0.10, 1))   # Humidity %
    status.append(round(int(line[SDPB:SDPE]) * 0.10, 1))   # Dew Point deg C
    status.append(round(int(line[SACB:SACE]) * 0.10, 1))   # Wind Speed Km/h
    status.append(int(line[SAAB:SAAE]))                    # Wind Speedn 10 min Km/h
    status.append(int(line[SWDB:SWDE]) % 360)              # Wind direction, degrees
    #status['type']    = STATUS_TYPE[line[SMTB:SMTE]]      # status type
    page = int(line[SMFB:SMFE])                            # Flash page number
    return status, page


# ----------
# Exceptions
# ----------


class EMAError(Exception):
    '''Base class for all exceptions below'''
    pass


class EMATimeoutError(EMAError):
    '''EMA no responding to command'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

# -------
# Classes
# -------


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Interval(object):
    '''
    This class build automatically incrementing interval objects, 
    to be used in requests timeouts.
    
    Use like:
    C{interval = Interval()}
    C{Interval.maxDelay = 16}
    C{t = interval()}
    C{t = interval()}

    @var initial:  Initial interval value, in seconds.
    @var maxDelay: maximun interval value produced, in seconds.
    @var factor:   multiplier for the next interval.
    '''
  
    def __init__(self, initial=1, maxDelay=256, factor=2):
        '''Initialize interval object'''
        self.initial = initial
        self.factor = factor
        self.maxDelay = max(initial, maxDelay)
        self._value   = self.initial


    def __call__(self):
        '''Call the interval with an id and produce a new value for that id'''
        self._value *= self.factor
        self._value = min(self._value, self.maxDelay)
        return self._value



# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

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

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

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
        self.busy   = False
        self.paused = False
      
    def connectionMade(self):
        log.debug("connectionMade()")


    def lineReceived(self, line):
        
        def fix(string):
            '''
            Dirty hack to translate invalid ASCII strings from EMA
            into something valid for the logging subsystem
            '''
            tmp = bytearray(string)
            for i in range(0,len(tmp)):
                tmp[i] = b'?' if tmp[i] > 127 else tmp[i]
            return str(tmp)

        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.5)
        line = line.lstrip(' \t\n\r') + b')'
        handled = self._handleCommandResponse(line, now)
        if handled:
            return
        handled = self._handleUnsolicitedResponse(line, now)
        if handled:
            return
        log.debug("Unknown/Unexpected message {line}", line=fix(line))



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


    def send(self, command, nretries=None):
        '''
        API Entry Point.
        Send a command to EMA.
        Retuns a Deferred whose success callback returns the command value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        nretries = nretries or command.retries
        return self._enqueue(command, nretries=nretries)

    # --------------
    # Helper methods
    # --------------

    def _pause(self):
        '''
        Pauses the sending of commands
        '''
        log.debug("EMA protocol pause()")
        self.paused = True

    def _resume(self):
        '''
        Resume the sending of commands
        '''
        log.debug("EMA protocol resume()")
        self.paused = False
        if len(self._queue) and not self.busy:
            self._retry()


    def _enqueue(self, request, nretries):
        '''
        Starts the ball rolling for the given request
        '''
        request.interval = Interval(initial=request.timeout['min'], 
                                    maxDelay=request.timeout['max'],
                                    factor=request.timeout['factor']) 
        request.nretries = nretries
        request.retries  = 0  
        request.deferred = defer.Deferred()
        request.encode()
        request.reset()
        self._queue.append(request)
        if not self.busy and not self.paused:    # start the ball rolling
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
        self.busy = True


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
            self.busy = False
            if len(self._queue) and not self.paused:    # Continue with the next command
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
            self.busy = False
            request.alarm.cancel()
            if len(self._queue) and not self.paused:    # Fires next command if any
                self._retry()
            request.deferred.callback(request.getResult()) # Fire callback after _retry() !!!
            del request
        return handled or finished

    def _handleUnsolicitedResponse(self, line, tstamp):
        '''
        Handle unsolicited responses from EMA.
        Returns True if handled, False otherwise
        '''
        ur, matchobj = match_unsolicited(line)
        if not ur:
            return False
        if ur['name'] == 'Photometer begin':
            self._pause()
            return True
        if ur['name'] == 'Photometer end':
            mag = float(matchobj.group(1))
            for callback in self._onPhotometer:
                callback(mag, tstamp)
            self._resume()
            return True
        if ur['name'] == 'Current status message':
            curState, _ = decodeStatus(line)
            for callback in self._onStatus:
                callback(curState, tstamp)
            return True
        if ur['name'] == 'Thermopile I2C':
            return True
        log.error("We should never have reached this unsolicited response")
        return False
        

__all__ = [
    "Interval",
    "EMAProtocol", 
    "EMAProtocolFactory",
    "EMATimeoutError",
    "PERIOD",
    "ROOF_RELAY",
    "AUX_RELAY",
    "POWER_VOLT",
    "RAIN_PROB",
    "CLOUD_LEVEL",
    "ABS_PRESSURE",
    "CAL_PRESSURE",
    "CUR_PLUVIOM",
    "ACC_PLUVIOM",
    "PYRANOMETER",
    "PHOTOM_FREQ",
    "AMB_TEMP",
    "HUMIDITY",
    "DEW_POINT",
    "CUR_WIND_SPEED",
    "AVE_WIND_SPEED",
    "WIND_DIRECTION",
]