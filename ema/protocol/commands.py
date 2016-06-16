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
# subject to an scale value to accomodate the message format.
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

    def __init__(self, ack_patterns, fmt=None, index=-1):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in ack_patterns ]
        self.N        = len(self.ackPat)
        self.fmt      = fmt
        self.name     = self.__doc__
        self.encoded  = None
        self.selindex = index
        self.reset()

    # ----------
    # Public API
    # ----------

    def encode(self):
        '''
        Simple encoding implementation. May be overriden by subclasses
        '''
        self.encoded = self.fmt

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
        The default response is to apply the last match object to the last line.
        Can be overriden.
        Must be called only after decode() returns True
        '''
        return int(self.matchobj[self.selindex].group(1)) / float(self.scale)

    # ----------------------------
    # Protected API for subclasses
    # ----------------------------

    def reset(self):
        '''reinitialization for retries after a tiemout'''
        self.i         = 0
        self.iteration = 1
        self.response  = []
        self.matchobj  = []
   

# ------------------------------------------------------------------------------

class GetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat, index=self.ack_index)


# ------------------------------------------------------------------------------

class SetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self, value):
        # Request format
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat, index=self.ack_index)
        self.value = value

    def encode(self):
        self.encoded = self.cmdformat.format(int(math.ceil(self.value * self.scale)))




# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTCDateTime(GetCommand):
    '''Get Real Time Clock Date & Time Command'''
    cmdformat       = '(y)'
    ack_patterns    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    ack_index       = 0
    ema_time_format = '(%H:%M:%S %d/%m/%Y)'

    def getResult(self):
        return  datetime.datetime.strptime(self.response[0], self.ema_time_format)

# ------------------------------------------------------------------------------

class SetRTCDateTime(SetCommand):
    '''Set Real Time Clock Date & Time Command'''
    cmdformat       = '(Y%d%m%y%H%M%S)'
    ack_patterns    = [ '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    ack_index       = 0
    ema_time_format = '(%H:%M:%S %d/%m/%Y)'

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
        self.encoded = self.value.strftime(self.fmt)

    def getResult(self):
        return  datetime.datetime.strptime(self.response[0], self.ema_time_format)

# ------------------------------------------------------------------------------
#                               WATCHDOG COMMANDS
# ------------------------------------------------------------------------------

class Ping(GetCommand):
    '''Ping'''
    cmdformat    = '( )'
    ack_patterns = [ '^\( \)' ]
    ack_index    = 0

    def getResult(self):
        return self.response[0]


class GetWatchdogPeriod(GetCommand):
    '''Get Watchdog Period Command'''
    cmdformat    = '(t)'
    ack_patterns = [ '^\(T(\d{3})\)' ]
    ack_index    = 0
    units        = 'sec'
    scale        = 1
    

class SetWatchdogPeriod(SetCommand):
    '''Set Watchdog Period Command'''
    cmdformat    = '(T{:03d})'
    ack_patterns = [ '^\(T(\d{3})\)' ]
    ack_index    = 0
    units        = 'sec'
    scale        = 1

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------


class GetCurrentWindSpeedThreshold(GetCommand):
    '''Get Current Wind Speed Threshold Command'''
    cmdformat    = '(w)'
    ack_patterns = [ '^\(W(\d{3})\)' ]
    ack_index    = 0
    units        = 'Km/h'
    scale        = 1
   
    
class SetCurrentWindSpeedThreshold(SetCommand):
    '''Set Current Wind Speed Threshold Command'''
    cmdformat    = '(W{:03d})'
    ack_patterns = [ '^\(W(\d{3})\)' ]
    ack_index    = 0
    units        = 'Km/h'
    scale        = 1


# ------------------------------------------------------------------------------

class GetAverageWindSpeedThreshold(GetCommand):
    '''Get 10min Average Wind Speed Threshold Command'''
    units        = 'Km/h'
    scale        = 1
    ack_patterns = [ '^\(O(\d{3})\)' ]
    cmdformat    = '(o)'
 
class SetAverageWindSpeedThreshold(SetCommand):
    '''Set 10min Average Wind Speed Threshold Command'''
    units        = 'Km/h'
    scale        = 1
    ack_patterns = [ '^\(O(\d{3})\)' ]
    cmdformat    = '(O{:03d})'
 

# ------------------------------------------------------------------------------

class GetAnemometerCalibrationConstant(GetCommand):
    '''Get Anemometer Calibration Constant'''
    units        = 'Unknown'
    scale        = 1
    ack_patterns = [ '^\(A(\d{3})\)' ]
    cmdformat    = '(a)'

class SetAnemometerCalibrationConstant(SetCommand):
    '''Set Anemometer Calibration Constant'''
    units        = 'Unknown'
    scale        = 1
    ack_patterns = [ '^\(A(\d{3})\)' ]
    cmdformat    = '(A{:03d})'
 
   
# ------------------------------------------------------------------------------

class GetAnemometerModel(GetCommand):
    '''Get Anemometer Model Command'''
    ack_patterns = [ '^\(Z(\d{3})\)' ]
    cmdformat    = '(z)'
    MAPPING      = { 1: 'TX20', 0: 'Homemade'}

    def getResult(self, line, matchobj):
        self.response = self.MAPPING[int(matchobj.group(1))]
       

class SetAnemometerModel(SetCommand):
    '''Set Anemometer Model Command'''
    ack_patterns = [ '^\(Z(\d{3})\)' ]
    cmdformat    = '(Z{:03d})'
    MAPPING      = {'TX20': 1, 'Homemade': 0, 1: 'TX20', 0: 'Homemade'}

    def encode(self):
        self.encoded = self.cmdformat.format(self.MAPPING[self.value])
    
    def getResult(self, line, matchobj):
        self.response = self.MAPPING[int(matchobj.group(1))]

# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class GetBarometerHeight(GetCommand):
    '''Get Barometer Height Command'''
    units        = 'm.'
    scale        = 1
    ack_patterns = [ '^\(M(\d{5})\)' ]
    cmdformat    = '(m)'

class SetBarometerHeight(SetCommand):
    '''Set Barometer Height Command'''
    units        = 'm.'
    scale        = 1
    ack_patterns = [ '^\(M(\d{5})\)' ]
    cmdformat    = '(M{:05d})'

# ------------------------------------------------------------------------------

class GetBarometerOffset(GetCommand):
    '''Get Barometer Offset Command'''
    units        = 'mBar'
    scale        = 1
    ack_patterns = [ '^\(B([+-]\d{2})\)' ]
    cmdformat    = '(b)'

class SetBarometerOffset(SetCommand):
    '''Set Barometer Offset Command'''
    units        = 'mBar'
    scale        = 1
    ack_patterns = [ '^\(B([+-]\d{2})\)' ]
    cmdformat    = '(B{:+03d})'


# ------------------------------------------------------------------------------
#                               CLOUD DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetCloudSensorThreshold(GetCommand):
    '''Get Cloud Sensor Threshold Command'''
    units        = '%'
    scale        = 1
    ack_patterns = [ '^\(N(\d{3})\)' ]
    cmdformat    = '(n)'

class SetCloudSensorThreshold(SetCommand):
    '''Set Cloud Sensor Threshold Command'''
    units        = '%'
    scale        = 1
    ack_patterns = [ '^\(N(\d{3})\)' ]
    cmdformat    = '(N{:03d})'

# ------------------------------------------------------------------------------

class GetCloudSensorGain(GetCommand):
    '''Get Cloud Sensor Gain Command'''
    units        = 'Unknown'
    scale        = 10
    ack_patterns = [ '^\(R(\d{3})\)' ]
    cmdformat    = '(r)'

class SetCloudSensorGain(SetCommand):
    '''Set Cloud Sensor Gain Command'''
    units        = 'Unknown'
    scale        = 10
    ack_patterns = [ '^\(R(\d{3})\)' ]
    cmdformat    = '(R{:03d})'

# ------------------------------------------------------------------------------
#                               PHOTOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPhotometerThreshold(GetCommand):
    '''Get Photometer Threshold Command'''
    units        = 'Mv/arcsec^2'
    scale        = 10
    ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    cmdformat    = '(i)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)))

    def getResult(self, line, matchobj):
        self.response = self.response[0] / float(self.scale)


class SetPhotometerThreshold(SetCommand):
    '''Set Photometer Threshold Command'''
    units        = 'Mv/arcsec^2'
    scale        = 10
    ack_patterns = [ '^\(I(\d{3})\)' ]
    cmdformat    = '(I{:03d})'

# ------------------------------------------------------------------------------

class GetPhotometerOffset(GetCommand):
    '''Get Photometer Gain Offset'''
    units        = 'Mv/arcsec^2'
    scale        = 10
    ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    cmdformat    = '(i)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)))

    def getResult(self, line, matchobj):
        self.response = self.response[1] / float(self.scale)


class SetPhotometerOffset(SetCommand):
    '''Set Photometer Gain Offset'''
    units        = 'Mv/arcsec^2'
    scale        = 10
    ack_patterns = [ '^\(I([+-]\d{2})\)']
    cmdformat    = '(I{:+03d})'

# ------------------------------------------------------------------------------
#                               PLUVIOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPluviometerCalibration(GetCommand):
    '''Get Pluviometer Calibration Constant Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(P(\d{3})\)']
    cmdformat    = '(p)'


class SetPluviometerCalibration(SetCommand):
    '''Set Pluviometer Calibration Constant Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(P(\d{3})\)']
    cmdformat    = '(P{:03d})'

# ------------------------------------------------------------------------------
#                               PYRANOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPyranometerGain(GetCommand):
    '''Get Pyranometer Gain Command'''
    units        = 'Unknown'
    scale        = 10
    ack_patterns = [ '^\(J(\d{3})\)']
    cmdformat    = '(j)'


class SetPyranometerGain(SetCommand):
    '''Set Pyranometer Gain Command'''
    units        = 'Unknown'
    scale        = 10
    ack_patterns = [ '^\(J(\d{3})\)']
    cmdformat    = '(J{:03d})'


class GetPyranometerOffset(GetCommand):
    '''Get Pyranometer Offset Command'''
    units        = 'Unknown'
    scale        = 1
    ack_patterns = [ '^\(U(\d{3})\)']
    cmdformat    = '(u)'


class SetPyranometerOffset(SetCommand):
    '''Get Pyranometer Offset Command'''
    units        = 'Unknown'
    scale        = 1
    ack_patterns = [ '^\(U(\d{3})\)']
    cmdformat    = '(U{:03d})'

# ------------------------------------------------------------------------------
#                               RAIN SENSOR DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetRainSensorThreshold(GetCommand):
    '''Get Rain Sensor Threshold Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(L(\d{3})\)']
    cmdformat    = '(l)'


class SetRainSensorThreshold(SetCommand):
    '''Set Rain Sensor Threshold Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(L(\d{3})\)']
    cmdformat    = '(L{:03d})'

# ------------------------------------------------------------------------------
#                               THERMOMETER DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetThermometerDeltaTempThreshold(GetCommand):
    '''Get Thermometer DeltaTemp Threshold Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(C(\d{3})\)']
    cmdformat    = '(c)'


class SetThermometerDeltaTempThreshold(SetCommand):
    '''Set Thermometer DeltaTemp Threshold Command'''
    units        = 'mm'
    scale        = 1
    ack_patterns = [ '^\(C(\d{3})\)']
    cmdformat    = '(C{:03d})'


# ------------------------------------------------------------------------------
#                               VOLTMETER COMMANDS
# ------------------------------------------------------------------------------

class GetVoltmeterThreshold(GetCommand):
    '''Get Voltmeter Threshold Command'''
    units        = 'V'
    scale        = 10
    ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    cmdformat    = '(f)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)))

    def getResult(self, line, matchobj):
        self.response = self.response[0] / float(self.scale)

class SetVoltmeterThreshold(SetCommand):
    '''Set Voltmeter Threshold Command'''
    units        = 'V'
    scale        = 10
    ack_patterns = [ '^\(F(\d{3})\)' ]
    cmdformat    = '(F{:03d})'


class GetVoltmeterOffset(GetCommand):
    '''Get Voltmeter Offset Command'''
    units        = 'V'
    scale        = 10
    ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    cmdformat    = '(f)'


class SetVoltmeterOffset(SetCommand):
    '''Set Voltmeter Offset Command'''
    units        = 'V'
    scale        = 10
    ack_patterns = [ '^\(F([+-]\d{2})\)' ]
    cmdformat    = '(F{:+03d})'

# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------


class SetRoofRelayMode(Command):
    '''Set Roof Relay Mode Command'''
    ack_patterns = [ '^\(X(\d{3})\)' ]
    cmdformat    = '(X{:03d})'
    MAPPING      = {  0: 'Closed', 7: 'Open',  'Closed': 0, 'Open' : 7,  }
    
    def __init__(self, value):
        self.value    = value
        self.NIters   = 1
        self.fmt      = self.cmdformat
        self.name     = self.__doc__
        self.encoded  = None
        self.ackPat   = [ re.compile(pat) for pat in self.ack_patterns ]
        if self.value == 'Open':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} Abrir Obs\. FORZADO\)'))
        elif self.value == 'Closed':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} Cerrar Obs\.\)'))
        self.N        = len(self.ackPat)
        self.reset()

    def encode(self):
        self.encoded = self.cmdformat.format(self.MAPPING[self.value])
    
    def collectData(self, line, matchobj):
        if self.i == 0:
            self.response = self.MAPPING[int(matchobj.group(1))]
       
    def getResult(self, line, matchobj):
        pass


# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class GetAuxRelaySwitchOnTime(GetCommand):
    '''Get Aux Relay Switch-On Time Command'''
    units           = 'HH:MM:00'
    ack_patterns    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat       = '(s)'
    ema_time_format = '(Son%H%M)'

    def collectData(self, line, matchobj):
        self.response.append(line)

    def getResult(self, line, matchobj):
        self.response = datetime.datetime.strptime(self.response[1], self.ema_time_format).time()


class SetAuxRelaySwitchOnTime(SetCommand):
    '''Set Aux Relay Switch-On Time Command'''
    units           = 'HH:MM:00'
    ack_patterns    = [ '^\(Son\d{4}\)' ]
    cmdformat       = '(Son{:04d})'
    ema_time_format = '(Son%H%M)'

    def encode(self):
        self.encoded = self.value.strftime(self.ema_time_format)

    def getResult(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format).time()


class GetAuxRelaySwitchOffTime(GetCommand):
    '''Get Aux Relay Switch-Off Time Command'''
    units           = 'HH:MM:00'
    ack_patterns    = [ '^\(S\d{3}\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat       = '(s)'
    ema_time_format = '(Sof%H%M)'

    def getResult(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format).time()


class SetAuxRelaySwitchOffTime(SetCommand):
    '''Set Aux Relay Switch-Off Time Command'''
    units           = 'HH:MM:00'
    ack_patterns    = [ '^\(Sof\d{4}\)' ]
    cmdformat       = '(Sof{:04d})'
    ema_time_format = '(Sof%H%M)'

    def encode(self):
        self.encoded = self.value.strftime(self.ema_time_format)

    def getResult(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format).time()


class GetAuxRelayMode(GetCommand):
    '''Get Aux Relay Mode Command'''
    ack_patterns = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat    = '(s)'
    MAPPING      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }

    def collectData(self, line, matchobj):
        if self.i == 0:
            self.response = self.MAPPING[int(matchobj.group(1))]
       
    def getResult(self, line, matchobj):
        pass
    

class SetAuxRelayMode(Command):
    '''Set Aux Relay Mode Command'''
    ack_patterns = [ '^\(S(\d{3})\)' ]
    cmdformat    = '(S{:03d})'
    MAPPING      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On', 
                    'Auto': 0, 'Closed': 4, 'Open' : 5, 'Timer/Off': 8, 'Timer/On' : 9 }
    
    def __init__(self, value):
        self.value    = value
        self.NIters   = 1
        self.fmt      = self.cmdformat
        self.name     = self.__doc__
        self.encoded  = None
        self.ackPat   = [ re.compile(pat) for pat in self.ack_patterns ]
        if self.value == 'Open':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} Calentador on\.\)'))
        elif self.value == 'Closed':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} Calentador off\.\)'))
        elif self.value == 'Timer/On':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer ON\)'))
        elif self.value == 'Timer/Off':
            self.ackPat.append(re.compile('^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer OFF\)'))
        self.N        = len(self.ackPat)
        self.reset()

    def encode(self):
        self.encoded = self.cmdformat.format(self.MAPPING[self.value])
    
    def collectData(self, line, matchobj):
        if self.i == 0:
            self.response = self.MAPPING[int(matchobj.group(1))]
       
    def getResult(self, line, matchobj):
        pass


# ------------------------------------------------------------------------------
#                                BULK DUMP COMMANDS
# ------------------------------------------------------------------------------

class GetDailyMinMaxDump(Command):
    '''Get Daily Min/Max Dump Command'''
    ack_patterns = [ '^\(.{76}M\d{4}\)', '^\(.{76}m\d{4}\)', '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    cmdformat    = '(@H0300)'
    NIters       = 24

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat, NIters=self.NIters)

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