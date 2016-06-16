# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------

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



from __future__ import division

# ----------------
# Standard modules
# ----------------

import re
import datetime
import math

# ----------------
# Twisted  modules
# ----------------

from twisted.logger import Logger

# -----------
# Own modules
# -----------

#from .     import PY2
#from .error import StringValueError, PayloadValueError, PayloadTypeError


log = Logger(namespace='serial')


# ------------------------------------------------------------------------------

class Command(object):
    '''
    Generic Command for the most common type of commands
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
        Can be overriden.
        Must be called only after decode() returns True
        '''
        return int(self.matchobj[self.selindex].group(1)) / float(self.SCALE)

    # ----------------------------
    # Protected API for subclasses
    # ----------------------------

    def reset(self):
        '''reinitialization for retries after a tiemout'''
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
        self.value = value

    def encode(self):
        self.encoded = self.CMDFORMAT.format(int(math.ceil(self.value * self.SCALE)))




# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTCDateTime(GetCommand):
    '''Get Real Time Clock Date & Time Command'''
    CMDFORMAT       = '(y)'
    ACK_PATTERNS    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'

    def getResult(self):
        return  datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------

class SetRTCDateTime(SetCommand):
    '''Set Real Time Clock Date & Time Command'''
    CMDFORMAT       = '(Y%d%m%y%H%M%S)'
    ACK_PATTERNS    = [ '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self, value):
        self.renew = False
        SetCommand.__init__(self, value)
        if value is None:
            self.renew = True
            self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)

    def reset(self):
        Command.reset(self)
        if self.renew:
            self.value = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)

    def encode(self):
        self.encoded = self.value.strftime(self.CMDFORMAT)

    def getResult(self):
        return  datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------
#                               WATCHDOG COMMANDS
# ------------------------------------------------------------------------------

class Ping(GetCommand):
    '''Ping'''
    CMDFORMAT    = '( )'
    ACK_PATTERNS = [ '^\( \)' ]

    def getResult(self):
        return self.response[0]


class GetWatchdogPeriod(GetCommand):
    '''Get Watchdog Period Command'''
    CMDFORMAT    = '(t)'
    ACK_PATTERNS = [ '^\(T(\d{3})\)' ]
    ACK_INDEX    = 0
    UNITS        = 'sec'
    SCALE        = 1
    

class SetWatchdogPeriod(SetCommand):
    '''Set Watchdog Period Command'''
    CMDFORMAT    = '(T{:03d})'
    ACK_PATTERNS = [ '^\(T(\d{3})\)' ]
    ACK_INDEX    = 0
    SCALE        = 1
    UNITS        = 'sec'
    

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------


class GetCurrentWindSpeedThreshold(GetCommand):
    '''Get Current Wind Speed Threshold Command'''
    CMDFORMAT    = '(w)'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    
    
class SetCurrentWindSpeedThreshold(SetCommand):
    '''Set Current Wind Speed Threshold Command'''
    CMDFORMAT    = '(W{:03d})'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
   

# ------------------------------------------------------------------------------

class GetAverageWindSpeedThreshold(GetCommand):
    '''Get 10min Average Wind Speed Threshold Command'''
    CMDFORMAT    = '(o)'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    
 
class SetAverageWindSpeedThreshold(SetCommand):
    '''Set 10min Average Wind Speed Threshold Command'''
    CMDFORMAT    = '(O{:03d})'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Km/h'
    

# ------------------------------------------------------------------------------

class GetAnemometerCalibrationConstant(GetCommand):
    '''Get Anemometer Calibration Constant'''
    CMDFORMAT    = '(a)'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Unknown'
     

class SetAnemometerCalibrationConstant(SetCommand):
    '''Set Anemometer Calibration Constant'''
    CMDFORMAT    = '(A{:03d})'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    SCALE        = 1
    UNITS        = 'Unknown'
   
# ------------------------------------------------------------------------------

class GetAnemometerModel(GetCommand):
    '''Get Anemometer Model Command'''
    CMDFORMAT    = '(z)'
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    MAPPING      = { 1: 'TX20', 0: 'Homemade'}

    def getResult(self):
        return self.MAPPING[int(self.matchobj[0].group(1))]
       

class SetAnemometerModel(SetCommand):
    '''Set Anemometer Model Command'''
    CMDFORMAT    = '(Z{:03d})'
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    MAPPING      = {'TX20': 1, 'Homemade': 0 }
    INV_MAPPING  = { 1: 'TX20', 0: 'Homemade'}

    def encode(self):
        self.encoded = self.CMDFORMAT.format(self.MAPPING[self.value])
    
    def getResult(self):
        return self.INV_MAPPING[int(self.matchobj[0].group(1))]

# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class GetBarometerHeight(GetCommand):
    '''Get Barometer Height Command'''
    CMDFORMAT    = '(m)'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    SCALE        = 1
    UNITS        = 'm.'
   

class SetBarometerHeight(SetCommand):
    '''Set Barometer Height Command'''
    CMDFORMAT    = '(M{:05d})'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    SCALE        = 1
    UNITS        = 'm.'
    

# ------------------------------------------------------------------------------

class GetBarometerOffset(GetCommand):
    '''Get Barometer Offset Command'''
    UNITS        = 'mBar'
    SCALE        = 1
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    CMDFORMAT    = '(b)'


class SetBarometerOffset(SetCommand):
    '''Set Barometer Offset Command'''
    CMDFORMAT    = '(B{:+03d})'
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    SCALE        = 1
    UNITS        = 'mBar'
   

# ------------------------------------------------------------------------------
#                               CLOUD DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetCloudSensorThreshold(GetCommand):
    '''Get Cloud Sensor Threshold Command'''
    CMDFORMAT    = '(n)'
    ACK_PATTERNS = [ '^\(N(\d{3})\)' ]
    ACK_INDEX    = 0
    SCALE        = 1
    UNITS        = '%'
    

class SetCloudSensorThreshold(SetCommand):
    '''Set Cloud Sensor Threshold Command'''
    CMDFORMAT    = '(N{:03d})'
    ACK_PATTERNS = [ '^\(N(\d{3})\)' ]
    SCALE        = 1
    UNITS        = '%'
    

# ------------------------------------------------------------------------------

class GetCloudSensorGain(GetCommand):
    '''Get Cloud Sensor Gain Command'''
    CMDFORMAT    = '(r)'
    ACK_PATTERNS = [ '^\(R(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Unknown'
   

class SetCloudSensorGain(SetCommand):
    '''Set Cloud Sensor Gain Command'''
    CMDFORMAT    = '(R{:03d})'
    ACK_PATTERNS = [ '^\(R(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Unknown'
    

# ------------------------------------------------------------------------------
#                               PHOTOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPhotometerThreshold(GetCommand):
    '''Get Photometer Threshold Command'''
    CMDFORMAT    = '(i)'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    ACK_INDEX    = 0
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
   

class SetPhotometerThreshold(SetCommand):
    '''Set Photometer Threshold Command'''
    CMDFORMAT    = '(I{:03d})'
    ACK_PATTERNS = [ '^\(I(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    

# ------------------------------------------------------------------------------

class GetPhotometerOffset(GetCommand):
    '''Get Photometer Gain Offset'''
    CMDFORMAT    = '(i)'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    ACK_INDEX    = 1
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    


class SetPhotometerOffset(SetCommand):
    '''Set Photometer Gain Offset'''
    CMDFORMAT    = '(I{:+03d})'
    ACK_PATTERNS = [ '^\(I([+-]\d{2})\)']
    SCALE        = 10
    UNITS        = 'Mv/arcsec^2'
    

# ------------------------------------------------------------------------------
#                               PLUVIOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPluviometerCalibration(GetCommand):
    '''Get Pluviometer Calibration Constant Command'''
    CMDFORMAT    = '(p)'
    ACK_PATTERNS = [ '^\(P(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'


class SetPluviometerCalibration(SetCommand):
    '''Set Pluviometer Calibration Constant Command'''
    CMDFORMAT    = '(P{:03d})'
    ACK_PATTERNS = [ '^\(P(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    
    
# ------------------------------------------------------------------------------
#                               PYRANOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPyranometerGain(GetCommand):
    '''Get Pyranometer Gain Command'''
    CMDFORMAT    = '(j)'
    ACK_PATTERNS = [ '^\(J(\d{3})\)']
    SCALE        = 10
    UNITS        = 'Unknown'  


class SetPyranometerGain(SetCommand):
    '''Set Pyranometer Gain Command'''
    CMDFORMAT    = '(J{:03d})'
    ACK_PATTERNS = [ '^\(J(\d{3})\)']
    SCALE        = 10
    UNITS        = 'Unknown'
    


class GetPyranometerOffset(GetCommand):
    '''Get Pyranometer Offset Command'''
    CMDFORMAT    = '(u)'
    ACK_PATTERNS = [ '^\(U(\d{3})\)']
    SCALE        = 1
    UNITS        = 'Unknown'
  


class SetPyranometerOffset(SetCommand):
    '''Get Pyranometer Offset Command'''
    CMDFORMAT    = '(U{:03d})'
    ACK_PATTERNS = [ '^\(U(\d{3})\)']
    SCALE        = 1
    UNITS        = 'Unknown'

    

# ------------------------------------------------------------------------------
#                               RAIN SENSOR DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetRainSensorThreshold(GetCommand):
    '''Get Rain Sensor Threshold Command'''
    CMDFORMAT    = '(l)'
    ACK_PATTERNS = [ '^\(L(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'


class SetRainSensorThreshold(SetCommand):
    '''Set Rain Sensor Threshold Command'''
    CMDFORMAT    = '(L{:03d})'
    ACK_PATTERNS = [ '^\(L(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    

# ------------------------------------------------------------------------------
#                               THERMOMETER DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetThermometerDeltaTempThreshold(GetCommand):
    '''Get Thermometer DeltaTemp Threshold Command'''
    CMDFORMAT    = '(c)'
    ACK_PATTERNS = [ '^\(C(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
    

class SetThermometerDeltaTempThreshold(SetCommand):
    '''Set Thermometer DeltaTemp Threshold Command'''
    CMDFORMAT    = '(C{:03d})'
    ACK_PATTERNS = [ '^\(C(\d{3})\)']
    SCALE        = 1
    UNITS        = 'mm'
  

# ------------------------------------------------------------------------------
#                               VOLTMETER COMMANDS
# ------------------------------------------------------------------------------

class GetVoltmeterThreshold(GetCommand):
    '''Get Voltmeter Threshold Command'''
    CMDFORMAT    = '(f)'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    ACK_INDEX    = 0
    UNITS        = 'V'
    SCALE        = 10


class SetVoltmeterThreshold(SetCommand):
    '''Set Voltmeter Threshold Command'''
    CMDFORMAT    = '(F{:03d})'
    ACK_PATTERNS = [ '^\(F(\d{3})\)' ]
    SCALE        = 10
    UNITS        = 'V'


class GetVoltmeterOffset(GetCommand):
    '''Get Voltmeter Offset Command'''
    CMDFORMAT    = '(f)'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    ACK_INDEX    = 1
    SCALE        = 10
    UNITS        = 'V'


class SetVoltmeterOffset(SetCommand):
    '''Set Voltmeter Offset Command'''
    CMDFORMAT    = '(F{:+03d})'
    ACK_PATTERNS = [ '^\(F([+-]\d{2})\)' ]
    SCALE        = 10
    UNITS        = 'V'
    

# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------


class SetRoofRelayMode(SetCommand):
    '''Set Roof Relay Mode Command'''
    CMDFORMAT    = '(X{:03d})'
    ACK_PATTERNS = [ '^\(X(\d{3})\)' ,  '^(dummy)' ]
    ACK_INDEX    = 0
    MAPPING      = { 'Closed': 0, 'Open' : 7, }
    INV_MAPPING  = { 0: 'Closed', 7: 'Open',  }
    
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
    CMDFORMAT       = '(s)'
    ACK_PATTERNS    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX       = 1
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Son%H%M)'

    def getResult(self):
        return datetime.datetime.strptime(self.response[1], self.EMA_TIME_FORMAT).time()


class SetAuxRelaySwitchOnTime(SetCommand):
    '''Set Aux Relay Switch-On Time Command'''
    CMDFORMAT       = '(Son{:04d})'
    ACK_PATTERNS    = [ '^\(Son\d{4}\)' ]
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Son%H%M)'

    def encode(self):
        self.encoded = self.value.strftime(self.EMA_TIME_FORMAT)

    def getResult(self):
        return datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT).time()


class GetAuxRelaySwitchOffTime(GetCommand):
    '''Get Aux Relay Switch-Off Time Command'''
    CMDFORMAT       = '(s)'
    ACK_PATTERNS    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX       = 2
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Sof%H%M)'

    def getResult(self):
         return datetime.datetime.strptime(self.response[2], self.EMA_TIME_FORMAT).time()


class SetAuxRelaySwitchOffTime(SetCommand):
    '''Set Aux Relay Switch-Off Time Command'''
    CMDFORMAT       = '(Sof{:04d})'
    ACK_PATTERNS    = [ '^\(Sof\d{4}\)' ]
    UNITS           = 'HH:MM:00'
    EMA_TIME_FORMAT = '(Sof%H%M)'

    def encode(self):
        self.encoded = self.value.strftime(self.EMA_TIME_FORMAT)

    def getResult(self):
       return datetime.datetime.strptime(self.response[0], self.EMA_TIME_FORMAT).time()


class GetAuxRelayMode(GetCommand):
    '''Get Aux Relay Mode Command'''
    CMDFORMAT    = '(s)'
    ACK_PATTERNS = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    ACK_INDEX    = 0
    MAPPING      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }

       
    def getResult(self):
        return self.MAPPING[int(self.matchobj[0].group(1))]
    

class SetAuxRelayMode(SetCommand):
    '''Set Aux Relay Mode Command'''
    CMDFORMAT    = '(S{:03d})'
    ACK_PATTERNS = [ '^\(S(\d{3})\)', '^(dummy)' ]
    ACK_INDEX    = 0
    MAPPING      = { 'Auto': 0,  'Closed': 4, 'Open' : 5, 'Timer/Off': 8,  'Timer/On' : 9 }
    INV_MAPPING  = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
   
    
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
      

    def encode(self):
        self.encoded = self.CMDFORMAT.format(self.MAPPING[self.value])
       
    def getResult(self):
        return self.INV_MAPPING[int(self.matchobj[0].group(1))]


# ------------------------------------------------------------------------------
#                                BULK DUMP COMMANDS
# ------------------------------------------------------------------------------

class GetDailyMinMaxDump(Command):
    '''Get Daily Min/Max Dump Command'''
    ACK_PATTERNS = [ '^\(.{76}M\d{4}\)', '^\(.{76}m\d{4}\)', '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    CMDFORMAT    = '(@H0300)'
    NIters       = 24

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.CMDFORMAT, NIters=self.NIters)

    def collectData(self, line, matchobj):
        self.response.append(line)

    def getResult(self, line, matchobj):
        pass



__all__ = [
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
]