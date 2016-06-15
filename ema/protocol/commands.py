# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------

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
    Get Real Time Clock time Command
    '''

    def __init__(self, ack_patterns, fmt=None, NIters=1):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in ack_patterns ]
        self.N        = len(self.ackPat)
        self.NIters   = NIters
        self.fmt      = fmt
        self.name     = self.__doc__
        self.encoded  = None
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
        elif (self.i + 1) == self.N and self.iteration == self.NIters:
            self.extractValues(line, matchobj)
            handled = True; finished = True
            log.debug("Matched {command.name} response, command complete", command=self)
        elif (self.i + 1) == self.N and self.iteration < self.NIters:
            self.collectData(line, matchobj)
            self.iteration += 1
            handled = True; finished = False
            log.debug("Matched {command.name} response, command complete, accumulating data", command=self)
        else:   
            self.collectData(line, matchobj)
            self.i += 1
            handled = True; finished = False
            log.debug("Matched {command.name} response, awaiting data", command=self)
        return handled, finished

    def getResponse(self):
        '''
        Returns a response object. 
        Must be called only after decode() returns True
        '''
        return self.response

    # ----------------------------
    # Protected API for subclasses
    # ----------------------------

    def reset(self):
        '''reinitialization for retries'''
        self.i         = 0
        self.iteration = 1
        self.response  = []
    
    
    def extractValues(self, line, matchobj):
        '''Default implementation, maybe overriden'''
        self.response = int(matchobj.group(1)) / float(self.scale)

    def collectData(self, line, matchobj):
        '''To be subclassed if necessary'''
        pass

   

# ------------------------------------------------------------------------------

class GetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat)


# ------------------------------------------------------------------------------

class SetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self, value):
        # Request format
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat)
        self.value = value

    def encode(self):
        self.encoded = self.cmdformat.format(int(math.ceil(self.value * self.scale)))



# ------------------------------------------------------------------------------
#                               PING COMMAND
# ------------------------------------------------------------------------------

class Ping(GetCommand):
    '''Ping'''
    ack_patterns = [ '^\( \)' ]
    cmdformat    = '( )'

    def extractValues(self, line, matchobj):
        self.response = line


# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTC(GetCommand):
    '''Get Real Time Clock time Command'''
    ack_patterns    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    cmdformat       = '(y)'
    ema_time_format = '(%H:%M:%S %d/%m/%Y)'

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format)

# ------------------------------------------------------------------------------

class SetRTC(Command):
    '''Set Real Time Clock time Command'''
    ack_patterns    = [ '(Y\d{2}\d{2}\d{4}\d{2}\d{2}\d{2})','\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    cmdformat       = '(Y%d%m%y%H%M%S)'
    ema_time_format = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self, tstamp=None):
        Command.__init__(self, ack_patterns=self.ack_patterns, fmt=self.cmdformat)
        if tstamp is not None:
            self.tstamp = tstamp
            self.renew = False
        else:
            self.renew = True
            self.tstamp = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)

    def reset(self):
        Command.reset()
        if self.renew:
            self.tstamp = datetime.datetime.utcnow()+datetime.timedelta(seconds=0.5)

    def encode(self):
        self.encoded = self.tstamp.strftime(self.fmt)

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format)

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------


class GetCurrentWindSpeedThreshold(GetCommand):
    '''Get Current Wind Speed Threshold Command'''
    units        = 'Km/h'
    scale        = 1
    ack_patterns = [ '^\(W(\d{3})\)' ]
    cmdformat    = '(w)'
    
class SetCurrentWindSpeedThreshold(SetCommand):
    '''Set Current Wind Speed Threshold Command'''
    units        = 'Km/h'
    scale        = 1
    ack_patterns = [ '^\(W(\d{3})\)' ]
    cmdformat    = '(W{:03d})'


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

    def extractValues(self, line, matchobj):
        self.response = self.MAPPING[int(matchobj.group(1))]
       

class SetAnemometerModel(SetCommand):
    '''Set Anemometer Model Command'''
    ack_patterns = [ '^\(Z(\d{3})\)' ]
    cmdformat    = '(Z{:03d})'
    MAPPING      = {'TX20': 1, 'Homemade': 0, 1: 'TX20', 0: 'Homemade'}

    def encode(self):
        self.encoded = self.cmdformat.format(self.MAPPING[self.value])
    
    def extractValues(self, line, matchobj):
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

    def extractValues(self, line, matchobj):
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

    def extractValues(self, line, matchobj):
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

    def extractValues(self, line, matchobj):
        self.response = self.response[0] / float(self.scale)


class GetVoltmeterOffset(GetCommand):
    '''Get Voltmeter Offset Command'''
    units        = 'V'
    scale        = 10
    ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    cmdformat    = '(f)'


# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class GetAuxRelaySwitchOnTime(GetCommand):
    '''Get Aux Relay Switch-On Time Command'''
    units           = 'HH:MM'
    ack_patterns    = [ '^\(S009\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat       = '(s)'
    ema_time_format = '(Son%H%M)'

    def collectData(self, line, matchobj):
        self.response.append(line)

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(self.response[1], self.ema_time_format).time()


class GetAuxRelaySwitchOffTime(GetCommand):
    '''Get Aux Relay Switch-Off Time Command'''
    units           = 'HH:MM'
    ack_patterns    = [ '^\(S009\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat       = '(s)'
    ema_time_format = '(Sof%H%M)'

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.ema_time_format).time()


class GetAuxRelayMode(GetCommand):
    '''Get Aux Relay Mode Command'''
    ack_patterns = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    cmdformat    = '(s)'
    MAPPING      = { 0 : 'Auto', 5 : 'Manual', 9 : 'Timed' }

    def collectData(self, line, matchobj):
        if self.i == 0:
            self.response = self.MAPPING[int(matchobj.group(1))]
       
    def extractValues(self, line, matchobj):
        pass
        

__all__ = [
    Ping, 
    GetRTC, 
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
    GetVoltmeterOffset,
    GetAuxRelaySwitchOnTime, 
    GetAuxRelaySwitchOffTime, 
    GetAuxRelayMode
]