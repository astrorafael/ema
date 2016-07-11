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

from .      import PY2

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
  status.append(int(line[SWDB:SWDE]))                    # Wind direction, degrees
  #status['type']    = STATUS_TYPE[line[SMTB:SMTE]]      # status type
  page = int(line[SMFB:SMFE])                            # Flash page number
  return status, page


# ----------
# Exceptions
# ----------

class EMARangeError(ValueError):
    '''Command value out of range'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: <{1}> ({2}) not in {3}'.format(s, self.args[0], self.args[1], self.args[2])
        s = '{0}.'.format(s)
        return s

class EMAReturnError(EMARangeError):
    '''Command return value out of range'''
    pass


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


# EMA Commands consists of request messages like (<weq>) 
# and one or more response messages like (<resp1>)(<resp2>)(<resp3>)
# The usual kind of command is one that sets or gets a configurable
# parameter and only one of the responses above contains the desired value.
# Parameters are usually numeric physical quantities, 
# subject to an SCALE value to accomodate the message format.
# The base Command class implementation addresses this kind of most 
# common command class. Other specific subclasses address specific responses
# due to datatypes used (dates, string labels, etc.)
#
# Bulk Dump commands extend this behaviour by repeating 
# (<resp1>)(<resp2>)(<resp3>) responses a number of times.
#
# The use of Class variables as constants, not even referenced in the base class
# allows us to define commands in an extremely compatc way

class Command(object):
    '''
    Generic Command for the most common type of commands
    Uppercase class variables must be defined in the proper subclasses.
    '''

    def __init__(self):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in self.ACK_PATTERNS ]
        self.N        = len(self.ackPat)
        self.name     = self.__doc__
        self.encoded  = None
        self.selindex = 0 if self.N == 1 else self.ACK_INDEX
        self.reset()

    # ----------
    # Public API
    # ----------

    def encode(self):
        '''
        Simple encoding implementation. May be overriden by subclasses
        '''
        self.encoded = self.CMDFORMAT


    def getEncoded(self):
        '''
        Default implementation is to return the cached result
        '''
        return str(self.encoded) if PY2 else bytes(self.encoded)


    def decode(self, line):
        '''
        Generic decoding algorithm for commands
        Must again and again until returns True
        '''
        matchobj = self.ackPat[self.i].search(line)
        if not matchobj:
            handled = False; finished = False
            log.debug("Line does not match {command.name} response", command=self)
        elif self.i  < self.N - 1:
            self.response.append(line)
            self.matchobj.append(matchobj)   
            self.i += 1
            handled = True; finished = False
            log.debug("Matched {command.name} response, awaiting data", command=self)
        else:
            self.response.append(line)
            self.matchobj.append(matchobj)
            handled = True; finished = True
            log.debug("Matched {command.name} response, command complete", command=self)
        return handled, finished


    def getResult(self):
        '''
        Returns a response.
        Must be called only after decode() returns True
        '''
        if self.TYPE == str:
            result = self.MAPPING[int(self.matchobj[self.selindex].group(1))]
            if result not in self.RANGE: 
                raise EMAReturnError(self.__class__.__name__, result, self.RANGE)
        else:
            result = self.TYPE(int(self.matchobj[self.selindex].group(1)) / self.SCALE)
            if not (self.RANGE[0] <= result <= self.RANGE[1]): 
                raise EMAReturnError(self.__class__.__name__, result, self.RANGE)
        return result

   
    def reset(self):
        '''reinitialization for retries after a timeout'''
        self.i         = 0
        self.response  = []
        self.matchobj  = []
   



# ------------------------------------------------------------------------------

class GetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self):
        # Request format
        Command.__init__(self)


# ------------------------------------------------------------------------------

class SetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self, value):
        # Request format
        Command.__init__(self)
        self.value = value if (self.TYPE == datetime.datetime) or (self.TYPE == datetime.time) else self.TYPE(value)
        if self.TYPE == str:
            if self.value not in self.RANGE: 
                raise EMARangeError(self.__class__.__name__, self.value, self.RANGE)
        else:
            if not (self.RANGE[0] <= self.value <= self.RANGE[1]): 
                raise EMARangeError(self.__class__.__name__, self.value, self.RANGE)


    def encode(self):
        self.encoded = self.CMDFORMAT.format(int(self.value * self.SCALE))



# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTCDateTime(GetCommand):
    '''Get Real Time Clock Date & Time Command'''
    TYPE            = datetime.datetime 
    RANGE           = [datetime.datetime(2016, 1, 1), datetime.datetime(2100, 12, 31)]
    CMDFORMAT       = '(y)'
    ACK_PATTERNS    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'
    RETRIES         = 2
    TIMEOUT         = {'min': 1, 'max': 128, 'factor': 2}

    def getResult(self):
        result = datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT)
        if not (self.RANGE[0] <= result <= self.RANGE[1]): 
                raise EMAReturnError(self.__class__.__name__, result, self.RANGE)
        return result

# ------------------------------------------------------------------------------

class SetRTCDateTime(SetCommand):
    '''Set Real Time Clock Date & Time Command'''
    TYPE            = datetime.datetime
    RANGE           = [datetime.datetime(2016, 1, 1), datetime.datetime(2100, 12, 31)]
    CMDFORMAT       = '(Y%d%m%y%H%M%S)'
    ACK_PATTERNS    = [ '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'
    RETRIES         = 2
    TIMEOUT         = {'min': 1, 'max': 128, 'factor': 2}


    def __init__(self, value):
        self.renew = False
        Command.__init__(self)
        if value is None:
            self.renew = True
            self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)
        else:
            self.value = value
        if not (self.RANGE[0] <= self.value <= self.RANGE[1]): 
            raise EMARangeError(self.__class__.__name__, self.value, self.RANGE)

    def encode(self):
        self.encoded = self.value.strftime(self.CMDFORMAT)

    def getEncoded(self):
        if self.renew:
            self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)
            self.encoded = self.value.strftime(self.CMDFORMAT)
        return self.encoded

    def getResult(self):
        return  datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------
#                               WATCHDOG COMMANDS
# ------------------------------------------------------------------------------

class Ping(GetCommand):
    '''Ping'''
    TYPE         = str
    RANGE        = [ '( )' ]
    CMDFORMAT    = '( )'
    ACK_PATTERNS = [ '^\( \)' ]
    RETRIES      = 0
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


    def getResult(self):
        return self.response[0]


class GetWatchdogPeriod(GetCommand):
    '''Get Watchdog Period Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(t)'
    ACK_PATTERNS = [ '^\(T(\d{3})\)' ]
    ACK_INDEX    = 0
    UNITS        = 'sec'
    SCALE        = 1
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

class SetWatchdogPeriod(SetCommand):
    '''Set Watchdog Period Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(T{:03d})'
    ACK_PATTERNS = [ '^\(T(\d{3})\)' ]
    ACK_INDEX    = 0
    SCALE        = 1
    UNITS        = 'sec'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------


class GetCurrentWindSpeedThreshold(GetCommand):
    '''Get Current Wind Speed Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(w)'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    
    
class SetCurrentWindSpeedThreshold(SetCommand):
    '''Set Current Wind Speed Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(W{:03d})'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   

# ------------------------------------------------------------------------------

class GetAverageWindSpeedThreshold(GetCommand):
    '''Get 10min Average Wind Speed Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(o)'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    
 
class SetAverageWindSpeedThreshold(SetCommand):
    '''Set 10min Average Wind Speed Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(O{:03d})'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------

class GetAnemometerCalibrationConstant(GetCommand):
    '''Get Anemometer Calibration Constant'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(a)'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
     

class SetAnemometerCalibrationConstant(SetCommand):
    '''Set Anemometer Calibration Constant'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(A{:03d})'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   
# ------------------------------------------------------------------------------

class GetAnemometerModel(GetCommand):
    '''Get Anemometer Model Command'''
    TYPE         = str
    RANGE        = ['TX20', 'Simple']
    CMDFORMAT    = '(z)'
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    MAPPING      = { 1: 'TX20', 0: 'Simple'}
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}

       

class SetAnemometerModel(SetCommand):
    '''Set Anemometer Model Command'''
    TYPE         = str
    RANGE        = ['TX20', 'Simple']
    CMDFORMAT    = '(Z{:03d})'
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    MAPPING      = {'TX20': 1, 'Simple': 0 }
    INV_MAPPING  = { 1: 'TX20', 0: 'Simple'}
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}

    def encode(self):
        self.encoded = self.CMDFORMAT.format(self.MAPPING[self.value])
    
    def getResult(self):
        return self.INV_MAPPING[int(self.matchobj[0].group(1))]

# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class GetBarometerHeight(GetCommand):
    '''Get Barometer Height Command'''
    TYPE         = int
    RANGE        = [0, 99999]
    CMDFORMAT    = '(m)'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    SCALE        = 1
    UNITS        = 'm.'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   

class SetBarometerHeight(SetCommand):
    '''Set Barometer Height Command'''
    TYPE         = int
    RANGE        = [0, 99999]
    CMDFORMAT    = '(M{:05d})'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    SCALE        = 1
    UNITS        = 'm.'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------

class GetBarometerOffset(GetCommand):
    '''Get Barometer Offset Command'''
    TYPE         = int
    RANGE        = [-99, 99]
    CMDFORMAT    = '(b)'
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    SCALE        = 1
    UNITS        = 'mBar'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}



class SetBarometerOffset(SetCommand):
    '''Set Barometer Offset Command'''
    TYPE         = int
    RANGE        = [-99, 99]
    CMDFORMAT    = '(B{:+03d})'
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    SCALE        = 1
    UNITS        = 'mBar'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   

# ------------------------------------------------------------------------------
#                               CLOUD DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetCloudSensorThreshold(GetCommand):
    '''Get Cloud Sensor Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(n)'
    ACK_PATTERNS = [ '^\(N(\d{3})\)' ]
    ACK_INDEX    = 0
    SCALE        = 1
    UNITS        = '%'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

class SetCloudSensorThreshold(SetCommand):
    '''Set Cloud Sensor Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(N{:03d})'
    ACK_PATTERNS = [ '^\(N(\d{3})\)' ]
    SCALE        = 1
    UNITS        = '%'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------

class GetCloudSensorGain(GetCommand):
    '''Get Cloud Sensor Gain Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(r)'
    ACK_PATTERNS = [ '^\(R(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   

class SetCloudSensorGain(SetCommand):
    '''Set Cloud Sensor Gain Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(R{:03d})'
    ACK_PATTERNS = [ '^\(R(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               PHOTOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPhotometerThreshold(GetCommand):
    '''Get Photometer Threshold Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(i)'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    ACK_INDEX    = 0
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   

class SetPhotometerThreshold(SetCommand):
    '''Set Photometer Threshold Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(I{:03d})'
    ACK_PATTERNS = [ '^\(I(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------

class GetPhotometerOffset(GetCommand):
    '''Get Photometer Gain Offset'''
    TYPE         = float
    RANGE        = [-99.9, +99.9]
    CMDFORMAT    = '(i)'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    ACK_INDEX    = 1
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    


class SetPhotometerOffset(SetCommand):
    '''Set Photometer Gain Offset'''
    TYPE         = float
    RANGE        = [-99.9, +99.9]
    CMDFORMAT    = '(I{:+03d})'
    ACK_PATTERNS = [ '^\(I([+-]\d{2})\)']
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               PLUVIOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPluviometerCalibration(GetCommand):
    '''Get Pluviometer Calibration Constant Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(p)'
    ACK_PATTERNS = [ '^\(P(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class SetPluviometerCalibration(SetCommand):
    '''Set Pluviometer Calibration Constant Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(P{:03d})'
    ACK_PATTERNS = [ '^\(P(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    
    
# ------------------------------------------------------------------------------
#                               PYRANOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPyranometerGain(GetCommand):
    '''Get Pyranometer Gain Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(j)'
    ACK_PATTERNS = [ '^\(J(\d{3})\)']
    SCALE        = 10
    UNITS        = 'Unknown'  
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class SetPyranometerGain(SetCommand):
    '''Set Pyranometer Gain Command'''
    TYPE         = float
    RANGE        = [0.0, 99.9]
    CMDFORMAT    = '(J{:03d})'
    ACK_PATTERNS = [ '^\(J(\d{3})\)']
    SCALE        = 10
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    


class GetPyranometerOffset(GetCommand):
    '''Get Pyranometer Offset Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(u)'
    ACK_PATTERNS = [ '^\(U(\d{3})\)']
    SCALE        = 1
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
  


class SetPyranometerOffset(SetCommand):
    '''Get Pyranometer Offset Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(U{:03d})'
    ACK_PATTERNS = [ '^\(U(\d{3})\)']
    SCALE        = 1
    UNITS        = 'Unknown'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}

    

# ------------------------------------------------------------------------------
#                               RAIN SENSOR DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetRainSensorThreshold(GetCommand):
    '''Get Rain Sensor Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(l)'
    ACK_PATTERNS = [ '^\(L(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class SetRainSensorThreshold(SetCommand):
    '''Set Rain Sensor Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(L{:03d})'
    ACK_PATTERNS = [ '^\(L(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               THERMOMETER DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetThermometerDeltaTempThreshold(GetCommand):
    '''Get Thermometer DeltaTemp Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(c)'
    ACK_PATTERNS = [ '^\(C(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

class SetThermometerDeltaTempThreshold(SetCommand):
    '''Set Thermometer DeltaTemp Threshold Command'''
    TYPE         = int
    RANGE        = [0, 999]
    CMDFORMAT    = '(C{:03d})'
    ACK_PATTERNS = [ '^\(C(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
  

# ------------------------------------------------------------------------------
#                               VOLTMETER COMMANDS
# ------------------------------------------------------------------------------

class GetVoltmeterThreshold(GetCommand):
    '''Get Voltmeter Threshold Command'''
    TYPE         = float
    RANGE        = [0.0, 25.5]
    CMDFORMAT    = '(f)'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    ACK_INDEX    = 0
    UNITS        = 'V'
    SCALE        = 10
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class SetVoltmeterThreshold(SetCommand):
    '''Set Voltmeter Threshold Command'''
    TYPE         = float
    RANGE        = [0.0, 25.5]
    CMDFORMAT    = '(F{:03d})'
    ACK_PATTERNS = [ '^\(F(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'V'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class GetVoltmeterOffset(GetCommand):
    '''Get Voltmeter Offset Command'''
    TYPE         = float
    RANGE        = [-99.9, +99.9]
    CMDFORMAT    = '(f)'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    ACK_INDEX    = 1
    SCALE        = 10
    UNITS        = 'V'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}


class SetVoltmeterOffset(SetCommand):
    '''Set Voltmeter Offset Command'''
    TYPE         = float
    RANGE        = [-99.9, +99.9]
    CMDFORMAT    = '(F{:+03d})'
    ACK_PATTERNS = [ '^\(F([+-]\d{2})\)' ]
    SCALE        = 10
    UNITS        = 'V'
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------


class SetRoofRelayMode(SetCommand):
    '''Set Roof Relay Mode Command'''
    TYPE         = str
    RANGE        = ['Closed', 'Open']
    CMDFORMAT    = '(X{:03d})'
    ACK_PATTERNS = [ '^\(X(\d{3})\)' ,  '^(dummy)' ]
    ACK_INDEX    = 0
    MAPPING      = { 'Closed': 0, 'Open' : 7, }
    INV_MAPPING  = { 0: 'Closed', 7: 'Open',  }
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
    
    def __init__(self, value):
        SetCommand.__init__(self, value)
       # Patches the last compiled expression
        if self.value == 'Open':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Abrir Obs\. FORZADO\)')
        elif self.value == 'Closed':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Cerrar Obs\.\)')

    def encode(self):
        self.encoded = self.CMDFORMAT.format(self.MAPPING[self.value])
       
    def getResult(self):
        return self.INV_MAPPING[int(self.matchobj[0].group(1))]


# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class GetAuxRelaySwitchOnTime(GetCommand):
    '''Get Aux Relay Switch-On Time Command'''
    TYPE            = datetime.time
    RANGE           = [datetime.time(0,0), datetime.time(23,59)]
    CMDFORMAT       = '(s)'
    ACK_PATTERNS    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX       = 1
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Son%H%M)'
    RETRIES         = 2
    TIMEOUT         = {'min': 2, 'max': 128, 'factor': 2}

    def getResult(self):
        return datetime.datetime.strptime(self.response[1], self.EMA_TIME_FORMAT).time()


class SetAuxRelaySwitchOnTime(SetCommand):
    '''Set Aux Relay Switch-On Time Command'''
    TYPE            = datetime.time
    RANGE           = [datetime.time(0,0), datetime.time(23,59)]
    CMDFORMAT       = '(Son{:04d})'
    ACK_PATTERNS    = [ '^\(Son\d{4}\)' ]
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Son%H%M)'
    RETRIES         = 2
    TIMEOUT         = {'min': 2, 'max': 128, 'factor': 2}

    def encode(self):
        self.encoded = self.value.strftime(self.EMA_TIME_FORMAT)

    def getResult(self):
        return datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT).time()


class GetAuxRelaySwitchOffTime(GetCommand):
    '''Get Aux Relay Switch-Off Time Command'''
    TYPE            = datetime.time
    CMDFORMAT       = '(s)'
    ACK_PATTERNS    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX       = 2
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Sof%H%M)'
    RETRIES         = 2
    TIMEOUT         = {'min': 2, 'max': 128, 'factor': 2}

    def getResult(self):
         return datetime.datetime.strptime(self.response[2], self.EMA_TIME_FORMAT).time()


class SetAuxRelaySwitchOffTime(SetCommand):
    '''Set Aux Relay Switch-Off Time Command'''
    TYPE            = datetime.time
    RANGE           = [datetime.time(0,0), datetime.time(23,59)]
    CMDFORMAT       = '(Sof{:04d})'
    ACK_PATTERNS    = [ '^\(Sof\d{4}\)' ]
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Sof%H%M)'
    RETRIES         = 2
    TIMEOUT         = {'min': 2, 'max': 128, 'factor': 2}

    def encode(self):
        self.encoded = self.value.strftime(self.EMA_TIME_FORMAT)

    def getResult(self):
       return datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT).time()


class GetAuxRelayMode(GetCommand):
    '''Get Aux Relay Mode Command'''
    TYPE         = str
    RANGE        = ['Auto', 'Closed', 'Open', 'Timer/Off', 'Timer/On']
    CMDFORMAT    = '(s)'
    ACK_PATTERNS = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX    = 0
    MAPPING      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}

    

class SetAuxRelayMode(SetCommand):
    '''Set Aux Relay Mode Command'''
    TYPE         = str
    RANGE        = ['Auto', 'Closed', 'Open', 'Timer/Off', 'Timer/On']
    CMDFORMAT    = '(S{:03d})'
    ACK_PATTERNS = [ '^\(S(\d{3})\)', '^(dummy)' ]
    ACK_INDEX    = 0
    MAPPING      = { 'Auto': 0,  'Closed': 4, 'Open' : 5, 'Timer/Off': 8,  'Timer/On' : 9 }
    INV_MAPPING  = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
    RETRIES      = 2
    TIMEOUT      = {'min': 2, 'max': 128, 'factor': 2}
   
    
    def __init__(self, value):
        SetCommand.__init__(self, value)
       # Patches the last compiled expression
        if self.value == 'Open':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Calentador on\.\)')
        elif self.value == 'Closed':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Calentador off\.\)')
        elif self.value == 'Timer/On':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer ON\)')
        elif self.value == 'Timer/Off':
            self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer OFF\)')
        elif self.value == 'Auto':
            self.N = 1
      

    def encode(self):
        self.encoded = self.CMDFORMAT.format(self.MAPPING[self.value])
       
    def getResult(self):
        return self.INV_MAPPING[int(self.matchobj[0].group(1))]

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class BulkDumpCommand(object):
    '''
    Generic Command for the most common type of commands
    Uppercase class variables must be defined in the proper subclasses.
    '''

    def __init__(self):
        # Request format
        self.ackPat    = [ re.compile(pat) for pat in self.ACK_PATTERNS ]
        self.N         = len(self.ackPat)
        self.name      = self.__doc__
        self.encoded   = None
        self.reset()

    # ----------
    # Public API
    # ----------

    def encode(self):
        '''
        Simple encoding implementation. May be overriden by subclasses
        '''
        self.encoded = self.CMDFORMAT

    def getEncoded(self):
        '''
        Default implementation is to return the cached result
        '''
        return str(self.encoded) if PY2 else bytes(self.encoded)

    def decodeOneIteration(self, line):
        '''
        Generic decoding algorithm for one iteration of commands
        '''
        matchobj = self.ackPat[self.i].search(line)
        if not matchobj:
            handled = False; finished = False
            log.debug("Line does not match {command.name} response", command=self)
        elif self.i  < self.N - 1:
            self.accumulate(line, matchobj)
            self.i += 1
            handled = True; finished = False
            log.debug("Matched {command.name} response, awaiting iteration {i} data", command=self, i=self.iteration-1)
        else:
            self.accumulate(line, matchobj)
            handled = True; finished = True
            log.debug("Matched {command.name} response, iteration {i} complete", command=self, i=self.iteration)
        return handled, finished

    def accumulate(self, line, matchobj):
        '''Default implementation, maybe overriden in subclasses'''
        self.response[self.iteration].append(line)
      

    def decode(self, line):
        '''
        Generic decoding algorithm for bulk dumps commands
        Must again and again until returns True
        '''
        handled, finished = self.decodeOneIteration(line)
        if not handled:
            return False, False
        if not finished:
            return True, False
        # Finished all iterations
        if self.iteration == self.ITERATIONS-1:
            return True, True

        # Do one more iteration
        self.i         = 0
        self.iteration += 1
        self.response.append([])
        return True, False

    def getResult(self):
        '''
        Returns the response matrix.
        Must be called only after decode() returns True
        '''
        return self.response


    def reset(self):
        '''reinitialization for retries after a timeout'''
        self.i         = 0
        self.iteration = 0
        self.response  = []
        self.response.append([])
       
     
   

# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#                                BULK DUMP COMMANDS
# ------------------------------------------------------------------------------

class GetDailyMinMaxDump(BulkDumpCommand):
    '''Get Daily Min/Max Dump Command'''
    ACK_PATTERNS = [ '^\(.{76}M\d{4}\)', '^\(.{76}m\d{4}\)', '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    CMDFORMAT    = '(@H0300)'
    ITERATIONS   = 24
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'
    RETRIES      = 0
    TIMEOUT      = {'min': 128, 'max': 128, 'factor': 2}

    def accumulate(self, line, matchobj):
        '''Default implementation, maybe overriden in subclasses'''

        if self.i < 2:
            vec, _ = decodeStatus(line)
            self.response[self.iteration].append(vec)
        else:
            tstamp = datetime.datetime.strptime(line, self.EMA_TIME_FORMAT)
            self.response[self.iteration].append(tstamp)    # Make room
            # Swap triplet components
            self.response[self.iteration][2] = self.response[self.iteration][1]
            self.response[self.iteration][1] = self.response[self.iteration][0]
            self.response[self.iteration][0] = tstamp
      

class Get5MinAveragesDump(BulkDumpCommand):
    '''Get 5 min Averages Bulk Dump'''
    ACK_PATTERNS = [ '^\(.{76}t\d{4}\)' ]
    CMDFORMAT    = '(@t0000)'
    ITERATIONS   = 288
    RETRIES      = 0
    TIMEOUT      = {'min': 256, 'max': 256, 'factor': 2}

    ONE_DAY = datetime.timedelta(days=1)

    def toPage(self, time):
      '''Computes the flash page corresponding to a given time'''
      return (time.hour*60 + time.minute)//5

    def toTime(self, page):
      '''Computes the end time coresponding to a given page'''
      minutes = page*5 + 5
      hour    = (minutes//60) %  24
      carry   = (minutes//60) // 24    # One day overflow in the last page
      return datetime.time(hour=hour, minute=minutes % 60), datetime.timedelta(days=carry)

    def accumulate(self, line, matchobj):
        '''Accumulate lines and calculate timestamps on the fly'''
        today        = datetime.datetime.utcnow()
        yesterday    = today - self.ONE_DAY
        todayPage    = self.toPage(today.time())
        status, page = decodeStatus(line)
        if todayPage < page:
            log.debug("Timestamping with today's day")
            time, _ = self.toTime(page)
            tstamp = datetime.datetime.combine(today.date(), time)
        else:
            log.debug("Timestamping with yesterday's day")
            time, carry = self.toTime(page)
            tstamp = datetime.datetime.combine(yesterday.date() + carry, time)
        self.response[self.iteration].append(tstamp)
        self.response[self.iteration].append(status)
       

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
        ur, matchobj = match_unsolicited(line)
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
            mag = float(matchobj.group(1))
            for callback in self._onPhotometer:
                callback(mag, tstamp)
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
    "EMARangeError", 
    "EMAReturnError",
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