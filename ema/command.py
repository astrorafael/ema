# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import math
import datetime
import re

# ---------------
# Twisted imports
# ---------------

from twisted.logger              import Logger, LogLevel

#--------------
# local imports
# -------------

from ema import PY2

import ema.metadata as mdata

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

# -----------------------
# Module global variables
# -----------------------

log  = Logger(namespace='serial')


# EMA Commands consists of request messages like (<req>) 
# and one or more response messages like (<resp1>)(<resp2>)(<resp3>)
# The usual kind of command is one that sets or gets a configurable
# parameter and only one of the responses above contains the desired value.
# Parameters are usually numeric physical quantities, 
# subject to an scale value to accomodate the message format.
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
        self.ackPat   = [ re.compile(pat) for pat in self.ack_patterns ]
        self.N        = len(self.ackPat)
        self.name     = self.__doc__
        self.encoded  = None
        self.selindex = 0 if self.N == 1 else self.ack_index
        self.reset()

    # ----------
    # Public API
    # ----------

    def encode(self):
        '''
        Simple encoding implementation. May be overriden by subclasses
        '''
        self.encoded = self.cmdformat


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
        if self.metadata.kind == str:
            result = self.mapping[int(self.matchobj[self.selindex].group(1))]
        else:
            result = self.metadata.kind(int(self.matchobj[self.selindex].group(1)) / self.scale)
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
    '''Abstract Set Command'''
 
    def __init__(self, value):
        # Request format
        Command.__init__(self)
        # no se si hace falta
        self.value = value if (self.metadata.kind == datetime.datetime) or (self.metadata.kind == datetime.time) else self.metadata.kind(value)

    def encode(self):
        self.encoded = self.cmdformat.format(int(self.value * self.scale))



# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class RealTimeClock(object):
    '''Namespace for children commands'''


    class GetDateTime(GetCommand):
        '''Get Real Time Clock Date & Time Command'''
        metadata        = mdata.RealTimeClock.DateTime
        cmdformat       = '(y)'
        ack_patterns    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
        ema_time_format = '(%H:%M:%S %d/%m/%Y)'
        retries         = 2
        timeout         = {'min': 1, 'max': 128, 'factor': 2}

        def getResult(self):
            return datetime.datetime.strptime(self.response[0], self.ema_time_format)

    # ------------------------------------------------------------------------------

    class SetDateTime(SetCommand):
        '''Set Real Time Clock Date & Time Command'''
        metadata        = mdata.RealTimeClock.DateTime
        cmdformat       = '(Y%d%m%y%H%M%S)'
        ack_patterns    = [ '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
        ema_time_format = '(%H:%M:%S %d/%m/%Y)'
        retries         = 2
        timeout         = {'min': 1, 'max': 128, 'factor': 2}


        def __init__(self, value):
            self.renew = False
            Command.__init__(self)
            if value is None:
                self.renew = True
                self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)
            else:
                self.value = value

        def encode(self):
            self.encoded = self.value.strftime(self.cmdformat)


        def getEncoded(self):
            if self.renew:
                self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)
                self.encoded = self.value.strftime(self.cmdformat)
            return self.encoded


        def getResult(self):
            return  datetime.datetime.strptime(self.response[0], self.ema_time_format)

# ------------------------------------------------------------------------------
#                               WATCHDOG COMMANDS
# ------------------------------------------------------------------------------

class Watchdog(object):
    '''Namespace for chldren commands'''


    class GetPresence(GetCommand):
        '''Ping'''
        metadata     = mdata.Watchdog.Presence
        cmdformat    = '( )'
        ack_patterns = [ '^\( \)' ]
        retries      = 0
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


        def getResult(self):
            return self.response[0]


    class GetPeriod(GetCommand):
        '''Get Watchdog Period Command'''
        metadata     = mdata.Watchdog.Period
        cmdformat    = '(t)'
        ack_patterns = [ '^\(T(\d{3})\)' ]
        ack_index    = 0
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetPeriod(SetCommand):
        '''Set Watchdog Period Command'''
        metadata     = mdata.Watchdog.Period
        cmdformat    = '(T{:03d})'
        ack_patterns = [ '^\(T(\d{3})\)' ]
        ack_index    = 0
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------

class Anemometer(object):
    '''Namespace for chldren commands'''

    class GetCurrentWindSpeedThreshold(GetCommand):
        '''Get Current Wind Speed Threshold Command'''
        metadata     = mdata.Anemometer.WindSpeedThreshold
        cmdformat    = '(w)'
        ack_patterns = [ '^\(W(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
        
    class SetCurrentWindSpeedThreshold(SetCommand):
        '''Set Current Wind Speed Threshold Command'''
        metadata     = mdata.Anemometer.WindSpeedThreshold
        cmdformat    = '(W{:03d})'
        ack_patterns = [ '^\(W(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
   

    # ------------------------------------------------------------------------------

    class GetAverageWindSpeedThreshold(GetCommand):
        '''Get 10min Average Wind Speed Threshold Command'''
        metadata     = mdata.Anemometer.WindSpeedThreshold
        cmdformat    = '(o)'
        ack_patterns = [ '^\(O(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
     
    class SetAverageWindSpeedThreshold(SetCommand):
        '''Set 10min Average Wind Speed Threshold Command'''
        metadata     = mdata.Anemometer.WindSpeedThreshold
        cmdformat    = '(O{:03d})'
        ack_patterns = [ '^\(O(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetCalibrationFactor(GetCommand):
        '''Get Anemometer Calibration Factor'''
        metadata     = mdata.Anemometer.CalibrationFactor
        cmdformat    = '(a)'
        ack_patterns = [ '^\(A(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
         

    class SetCalibrationFactor(SetCommand):
        '''Set Anemometer Calibration Factor'''
        metadata     = mdata.Anemometer.CalibrationFactor
        cmdformat    = '(A{:03d})'
        ack_patterns = [ '^\(A(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       
    # ------------------------------------------------------------------------------

    class GetModel(GetCommand):
        '''Get Anemometer Model Command'''
        metadata     = mdata.Anemometer.Model
        cmdformat    = '(z)'
        ack_patterns = [ '^\(Z(\d{3})\)' ]
        mapping      = { 1: 'TX20', 0: 'Simple'}
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

           

    class SetModel(SetCommand):
        '''Set Anemometer Model Command'''
        metadata     = mdata.Anemometer.Model
        cmdformat    = '(Z{:03d})'
        ack_patterns = [ '^\(Z(\d{3})\)' ]
        mapping      = {'TX20': 1, 'Simple': 0 }
        inv_mapping  = { 1: 'TX20', 0: 'Simple'}
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

        def encode(self):
            self.encoded = self.cmdformat.format(self.mapping[self.value])
        
        def getResult(self):
            return self.inv_mapping[int(self.matchobj[0].group(1))]

# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class Barometer(object):
    '''Namespace for chldren commands'''

    class GetHeight(GetCommand):
        '''Get Barometer Height Command'''
        metadata     = mdata.Barometer.Height
        cmdformat    = '(m)'
        ack_patterns = [ '^\(M(\d{5})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetHeight(SetCommand):
        '''Set Barometer Height Command'''
        metadata     = mdata.Barometer.Height
        cmdformat    = '(M{:05d})'
        ack_patterns = [ '^\(M(\d{5})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetOffset(GetCommand):
        '''Get Barometer Offset Command'''
        metadata     = mdata.Barometer.Offset
        cmdformat    = '(b)'
        ack_patterns = [ '^\(B([+-]\d{2})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}



    class SetOffset(SetCommand):
        '''Set Barometer Offset Command'''
        metadata     = mdata.Barometer.Offset
        cmdformat    = '(B{:+03d})'
        ack_patterns = [ '^\(B([+-]\d{2})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

# ------------------------------------------------------------------------------
#                               CLOUD DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class CloudSensor(object):
    '''Namespace for chldren commands'''

    class GetThreshold(GetCommand):
        '''Get Cloud Sensor Threshold Command'''
        metadata     = mdata.CloudSensor.Threshold
        cmdformat    = '(n)'
        ack_patterns = [ '^\(N(\d{3})\)' ]
        ack_index    = 0
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetThreshold(SetCommand):
        '''Set Cloud Sensor Threshold Command'''
        metadata     = mdata.CloudSensor.Threshold
        cmdformat    = '(N{:03d})'
        ack_patterns = [ '^\(N(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetGain(GetCommand):
        '''Get Cloud Sensor Gain Command'''
        metadata     = mdata.CloudSensor.Gain
        cmdformat    = '(r)'
        ack_patterns = [ '^\(R(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetGain(SetCommand):
        '''Set Cloud Sensor Gain Command'''
        metadata     = mdata.CloudSensor.Gain
        cmdformat    = '(R{:03d})'
        ack_patterns = [ '^\(R(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

# ------------------------------------------------------------------------------
#                               PHOTOMETER COMMANDS
# ------------------------------------------------------------------------------

class Photometer(object):
    '''Namespace for chldren commands'''


    class GetThreshold(GetCommand):
        '''Get Photometer Threshold Command'''
        metadata     = mdata.Photometer.Threshold
        cmdformat    = '(i)'
        ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
        ack_index    = 0
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetThreshold(SetCommand):
        '''Set Photometer Threshold Command'''
        metadata     = mdata.Photometer.Threshold
        cmdformat    = '(I{:03d})'
        ack_patterns = [ '^\(I(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetOffset(GetCommand):
        '''Get Photometer Offset'''
        metadata     = mdata.Photometer.Offset
        cmdformat    = '(i)'
        ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
        ack_index    = 1
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetOffset(SetCommand):
        '''Set Photometer Offset'''
        metadata     = mdata.Photometer.Offset
        cmdformat    = '(I{:+03d})'
        ack_patterns = [ '^\(I([+-]\d{2})\)']
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

# ------------------------------------------------------------------------------
#                               PLUVIOMETER COMMANDS
# ------------------------------------------------------------------------------

class Pluviometer(object):
    '''Namespace for chldren commands'''

    class GetCalibrationFactor(GetCommand):
        '''Get Pluviometer Calibration Factor Command'''
        metadata     = mdata.Pluviometer.Factor
        cmdformat    = '(p)'
        ack_patterns = [ '^\(P(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetCalibrationFactor(SetCommand):
        '''Set Pluviometer Calibration Constant Command'''
        metadata     = mdata.Pluviometer.Factor
        cmdformat    = '(P{:03d})'
        ack_patterns = [ '^\(P(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
    
    
# ------------------------------------------------------------------------------
#                               PYRANOMETER COMMANDS
# ------------------------------------------------------------------------------

class Pyranometer(object):
    '''Namespace for chldren commands'''

    class GetGain(GetCommand):
        '''Get Pyranometer Gain Command'''
        metadata     = mdata.Pyranometer.Gain
        cmdformat    = '(j)'
        ack_patterns = [ '^\(J(\d{3})\)']
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetGain(SetCommand):
        '''Set Pyranometer Gain Command'''
        metadata     = mdata.Pyranometer.Gain
        cmdformat    = '(J{:03d})'
        ack_patterns = [ '^\(J(\d{3})\)']
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        


    class GetOffset(GetCommand):
        '''Get Pyranometer Offset Command'''
        metadata     = mdata.Pyranometer.Offset
        cmdformat    = '(u)'
        ack_patterns = [ '^\(U(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
      


    class SetOffset(SetCommand):
        '''Set Pyranometer Offset Command'''
        metadata     = mdata.Pyranometer.Offset
        cmdformat    = '(U{:03d})'
        ack_patterns = [ '^\(U(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

    

# ------------------------------------------------------------------------------
#                               RAIN SENSOR DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class RainSensor(object):
    '''Namespace for chldren commands'''

    class GetThreshold(GetCommand):
        '''Get Rain Sensor Threshold Command'''
        metadata     = mdata.RainSensor.Threshold
        cmdformat    = '(l)'
        ack_patterns = [ '^\(L(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetThreshold(SetCommand):
        '''Set Rain Sensor Threshold Command'''
        metadata     = mdata.RainSensor.Threshold
        cmdformat    = '(L{:03d})'
        ack_patterns = [ '^\(L(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
    

# ------------------------------------------------------------------------------
#                               THERMOMETER DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class Thermometer(object):
    '''Namespace for chldren commands'''

    class GetThreshold(GetCommand):
        '''Get Thermometer DeltaTemp Threshold Command'''
        metadata     = mdata.Thermometer.Threshold
        cmdformat    = '(c)'
        ack_patterns = [ '^\(C(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetThreshold(SetCommand):
        '''Set Thermometer DeltaTemp Threshold Command'''
        metadata     = mdata.Thermometer.Threshold
        cmdformat    = '(C{:03d})'
        ack_patterns = [ '^\(C(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
  

# ------------------------------------------------------------------------------
#                               VOLTMETER COMMANDS
# ------------------------------------------------------------------------------

class Voltmeter(object):
    '''Namespace for chldren commands'''


    class GetThreshold(GetCommand):
        '''Get Voltmeter Threshold Command'''
        metadata     = mdata.Voltmeter.Threshold
        cmdformat    = '(f)'
        ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
        ack_index    = 0
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetThreshold(SetCommand):
        '''Set Voltmeter Threshold Command'''
        metadata     = mdata.Voltmeter.Threshold
        cmdformat    = '(F{:03d})'
        ack_patterns = [ '^\(F(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class GetOffset(GetCommand):
        '''Get Voltmeter Offset Command'''
        metadata     = mdata.Voltmeter.Offset
        cmdformat    = '(f)'
        ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
        ack_index    = 1
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetOffset(SetCommand):
        '''Set Voltmeter Offset Command'''
        metadata     = mdata.Voltmeter.Offset
        cmdformat    = '(F{:+03d})'
        ack_patterns = [ '^\(F([+-]\d{2})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------

class RoofRelay(object):
    '''Namespace for chldren commands'''

    class SetMode(SetCommand):
        '''Set Roof Relay Mode Command'''
        metadata     = mdata.RoofRelay.Mode
        cmdformat    = '(X{:03d})'
        ack_patterns = [ '^\(X(\d{3})\)' ,  '^(dummy)' ]
        ack_index    = 0
        mapping      = { 'Closed': 0, 'Open' : 7, 'Auto': 1 }
        inv_mapping  = { 0: 'Closed', 7: 'Open',  1: 'Auto' }
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
        def __init__(self, value):
            SetCommand.__init__(self, value)
           # Patches the last compiled expression
            if self.value == 'Open':
                self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Abrir Obs\. FORZADO\)')
            elif self.value == 'Closed':
                self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Cerrar Obs\.\)')
            elif self.value == 'Auto':
                self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Abrir Obs\.\)')

        def encode(self):
            self.encoded = self.cmdformat.format(self.mapping[self.value])
           
        def getResult(self):
            return self.inv_mapping[int(self.matchobj[0].group(1))]


# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class AuxiliarRelay(object):
    '''Namespace for chldren commands'''


    class GetSwitchOnTime(GetCommand):
        '''Get Aux Relay Switch-On Time Command'''
        metadata        = mdata.AuxiliarRelay.Time
        cmdformat       = '(s)'
        ack_patterns    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
        ack_index       = 1
        ema_time_format = '(Son%H%M)'
        retries         = 2
        timeout         = {'min': 2, 'max': 128, 'factor': 2}

        def getResult(self):
            return datetime.datetime.strptime(self.response[1], self.ema_time_format).time()


    class SetSwitchOnTime(SetCommand):
        '''Set Aux Relay Switch-On Time Command'''
        metadata        = mdata.AuxiliarRelay.Time
        cmdformat       = '(Son{:04d})'
        ack_patterns    = [ '^\(Son\d{4}\)' ]
        ema_time_format = '(Son%H%M)'
        retries         = 2
        timeout         = {'min': 2, 'max': 128, 'factor': 2}

        def encode(self):
            self.encoded = self.value.strftime(self.ema_time_format)

        def getResult(self):
            return datetime.datetime.strptime(self.response[0], self.ema_time_format).time()


    class GetSwitchOffTime(GetCommand):
        '''Get Aux Relay Switch-Off Time Command'''
        metadata        = mdata.AuxiliarRelay.Time
        cmdformat       = '(s)'
        ack_patterns    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
        ack_index       = 2
        ema_time_format = '(Sof%H%M)'
        retries         = 2
        timeout         = {'min': 2, 'max': 128, 'factor': 2}

        def getResult(self):
             return datetime.datetime.strptime(self.response[2], self.ema_time_format).time()


    class SetSwitchOffTime(SetCommand):
        '''Set Aux Relay Switch-Off Time Command'''
        metadata        = mdata.AuxiliarRelay.Time
        cmdformat       = '(Sof{:04d})'
        ack_patterns    = [ '^\(Sof\d{4}\)' ]
        ema_time_format = '(Sof%H%M)'
        retries         = 2
        timeout         = {'min': 2, 'max': 128, 'factor': 2}

        def encode(self):
            self.encoded = self.value.strftime(self.ema_time_format)

        def getResult(self):
           return datetime.datetime.strptime(self.response[0], self.ema_time_format).time()


    class GetMode(GetCommand):
        '''Get Aux Relay Mode Command'''
        metadata     = mdata.AuxiliarRelay.Mode
        cmdformat    = '(s)'
        ack_patterns = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
        ack_index    = 0
        mapping      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

        

    class SetMode(SetCommand):
        '''Set Aux Relay Mode Command'''
        metadata     = mdata.AuxiliarRelay.Mode
        cmdformat    = '(S{:03d})'
        ack_patterns = [ '^\(S(\d{3})\)', '^(dummy)' ]
        ack_index    = 0
        mapping      = { 'Auto': 0,  'Closed': 4, 'Open' : 5, 'Timer/Off': 8,  'Timer/On' : 9 }
        inv_mapping  = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       
        
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
            self.encoded = self.cmdformat.format(self.mapping[self.value])
           
        def getResult(self):
            return self.inv_mapping[int(self.matchobj[0].group(1))]

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
        self.ackPat    = [ re.compile(pat) for pat in self.ack_patterns ]
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
        self.encoded = self.cmdformat

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
        if self.iteration == self.iterations-1:
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
    ack_patterns = [ '^\(.{76}M\d{4}\)', '^\(.{76}m\d{4}\)', '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    cmdformat    = '(@H0300)'
    iterations   = 24
    ema_time_format = '(%H:%M:%S %d/%m/%Y)'
    retries      = 0
    timeout      = {'min': 128, 'max': 128, 'factor': 2}

    def accumulate(self, line, matchobj):
        '''Default implementation, maybe overriden in subclasses'''

        if self.i < 2:
            vec, _ = decodeStatus(line)
            self.response[self.iteration].append(vec)
        else:
            tstamp = datetime.datetime.strptime(line, self.ema_time_format)
            self.response[self.iteration].append(tstamp)    # Make room
            # Swap triplet components
            self.response[self.iteration][2] = self.response[self.iteration][1]
            self.response[self.iteration][1] = self.response[self.iteration][0]
            self.response[self.iteration][0] = tstamp
      

class Get5MinAveragesDump(BulkDumpCommand):
    '''Get 5 min Averages Bulk Dump'''
    ack_patterns = [ '^\(.{76}t\d{4}\)' ]
    cmdformat    = '(@t0000)'
    iterations   = 288
    retries      = 0
    timeout      = {'min': 256, 'max': 256, 'factor': 2}

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
       

__all__ = [
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