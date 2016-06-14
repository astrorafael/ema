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

    def __init__(self, ack_patterns, fmt=None, Niters=1):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in ack_patterns ]
        self.N        = len(self.ackPat)
        self.NIters   = Niters
        self.fmt      = fmt
        self.encoded  = None
        self.name     = self.__doc__
        self.reset()

    def reset(self):
        '''reinitialization for retries'''
        self.i         = 0
        self.iteration = 1
        self.response  = []

    def encode(self):
        self.encoded = self.fmt
        return self.encoded
    
    def extractValues(self, line, matchobj):
        '''Default implementation, maybe overriden'''
        self.response = int(matchobj.group(1))

    def collectData(self, line, matchobj):
        '''To be subclassed if necessary'''
        pass

    def getResponse(self):
        '''Returns a response object. Must be called only after decode() returns True'''
        return self.response

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
            log.debug("Matched {command.name} echo response, awaiting data", command=self)
        return handled, finished

class GetCommand(Command):
    '''Abstract Get Command'''
 
    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)


# ------------------------------------------------------------------------------
#                               PING COMMAND
# ------------------------------------------------------------------------------

class Ping(GetCommand):
    '''Ping'''

    ACK_PATTERNS = [ '^\( \)' ]
    FMT = '( )'


    def extractValues(self, line, matchobj):
        self.response = line


# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTC(GetCommand):
    '''Get Real Time Clock time Command'''
    ACK_PATTERNS = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    FMT = '(y)'
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'


    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------

class SetRTC(Command):
    '''Set Real Time Clock time Command'''

    ACK_PATTERNS = [ '(Y\d{2}\d{2}\d{4}\d{2}\d{2}\d{2})','\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    FMT = '(Y%d%m%y%H%M%S)'
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self, tstamp=None):
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)
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
        return self.encoded

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------
#                               ANEMOMETER COMMANDS
# ------------------------------------------------------------------------------

        

class GetCurrentWindSpeedThreshold(GetCommand):
    '''Get Current Wind Speed Threshold Command'''
    units = 'Km/h'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    FMT = '(w)'
    

# ------------------------------------------------------------------------------

class GetAverageWindSpeedThreshold(GetCommand):
    '''Get 10min Average Wind Speed Threshold Command'''
    units = 'Km/h'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    FMT = '(o)'
 

# ------------------------------------------------------------------------------

class GetAnemometerCalibrationConstant(GetCommand):
    '''Get Anemometer Calibration Constant'''
    units = 'Unknown'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    FMT = '(a)'
 
   
# ------------------------------------------------------------------------------

class GetAnemometerModel(GetCommand):
    '''Get Anemometer Model Command'''
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    FMT = '(z)'

    def extractValues(self, line, matchobj):
        self.response = int(matchobj.group(1))
        self.response = "TX20" if self.response == 1 else "Homemade"

 
# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class GetBarometerHeight(GetCommand):
    '''Get Barometer Height Command'''
    units = 'm.'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    FMT = '(m)'


# ------------------------------------------------------------------------------

class GetBarometerOffset(GetCommand):
    '''Get Barometer Offset Command'''
    units = 'mBar'
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    FMT = '(b)'


# ------------------------------------------------------------------------------
#                               CLOUD DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetCloudSensorThreshold(GetCommand):
    '''Get Cloud Sensor Threshold Command'''
    units = '%'
    ACK_PATTERNS = [ '^\(N(\d{3})\)' ]
    FMT = '(n)'


# ------------------------------------------------------------------------------

class GetCloudSensorGain(GetCommand):
    '''Get Cloud Sensor Gain Command'''
    units = 'Unknown'
    ACK_PATTERNS = [ '^\(R(\d{3})\)' ]
    FMT = '(r)'

    def extractValues(self, line, matchobj):
        self.response = int(matchobj.group(1)) * 0.10

# ------------------------------------------------------------------------------
#                               PHOTOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPhotometerThreshold(GetCommand):
    '''Get Photometer Threshold Command'''
    units = 'Mv/arcsec^2'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    FMT = '(i)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)

    def extractValues(self, line, matchobj):
        self.response.append(int(matchobj.group(1)))
        self.response = self.response[0]

# ------------------------------------------------------------------------------

class GetPhotometerOffset(GetCommand):
    '''Get Photometer Gain Offset'''
    units = 'Mv/arcsec^2'
    ACK_PATTERNS = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
    FMT = '(i)'

   
    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)

    def extractValues(self, line, matchobj):
        self.response.append(int(matchobj.group(1)))
        self.response = self.response[1]


# ------------------------------------------------------------------------------
#                               PLUVIOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPluviometerCalibration(GetCommand):
    '''Get Pluviometer Calibration Constant Command'''
    units = 'mm'
    ACK_PATTERNS = [ '^\(P(\d{3})\)']
    FMT = '(p)'

# ------------------------------------------------------------------------------
#                               PYRANOMETER COMMANDS
# ------------------------------------------------------------------------------

class GetPyranometerGain(GetCommand):
    '''Get Pyranometer Gain Command'''
    units = 'Unknown'
    ACK_PATTERNS = [ '^\(J(\d{3})\)']
    FMT = '(j)'

    def extractValues(self, line, matchobj):
        self.response = int(matchobj.group(1)) * 0.10


class GetPyranometerOffset(GetCommand):
    '''Get Pyranometer Offset Command'''
    units = 'Unknown'
    ACK_PATTERNS = [ '^\(U(\d{3})\)']
    FMT = '(u)'

# ------------------------------------------------------------------------------
#                               RAIN SENSOR DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetRainSensorThreshold(GetCommand):
    '''Get Rain Sensor Threshold Command'''
    units = 'mm'
    ACK_PATTERNS = [ '^\(L(\d{3})\)']
    FMT = '(l)'

# ------------------------------------------------------------------------------
#                               THERMOMETER DETECTOR COMMANDS
# ------------------------------------------------------------------------------

class GetThermometerDeltaTempThreshold(GetCommand):
    '''Get Thermometer DeltaTemp Threshold Command'''
    units = 'mm'
    ACK_PATTERNS = [ '^\(C(\d{3})\)']
    FMT = '(c)'

# ------------------------------------------------------------------------------
#                               VOLTMETER COMMANDS
# ------------------------------------------------------------------------------

class GetVoltmeterThreshold(GetCommand):
    '''Get Voltmeter Threshold Command'''
    units = 'V'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    FMT = '(f)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)

    def extractValues(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)
        self.response = self.response[0]


class GetVoltmeterOffset(GetCommand):
    '''Get Voltmeter Offset Command'''
    units = 'V'
    ACK_PATTERNS = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
    FMT = '(f)'

    def collectData(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)

    def extractValues(self, line, matchobj):
        self.response.append(int(matchobj.group(1)) * 0.10)
        self.response = self.response[1]


# ------------------------------------------------------------------------------
#                               ROOF RELAY COMMANDS
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class GetAuxRelaySwitchOnTime(GetCommand):
    '''Get Aux Relay Switch-On Time Command'''
    units           = 'HH:MM'
    ACK_PATTERNS    = [ '^\(S009\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    FMT             = '(s)'
    EMA_TIME_FORMAT = '(Son%H%M)'

    def collectData(self, line, matchobj):
        self.response.append(line)

    def extractValues(self, line, matchobj):
        self.response.append(line)
        self.response = datetime.datetime.strptime(self.response[1], self.EMA_TIME_FORMAT).time()


class GetAuxRelaySwitchOffTime(GetCommand):
    '''Get Aux Relay Switch-Off Time Command'''
    units           = 'HH:MM'
    ACK_PATTERNS    = [ '^\(S009\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
    FMT             = '(s)'
    EMA_TIME_FORMAT = '(Sof%H%M)'

    def collectData(self, line, matchobj):
        self.response.append(line)

    def extractValues(self, line, matchobj):
        self.response.append(line)
        self.response = datetime.datetime.strptime(self.response[2], self.EMA_TIME_FORMAT).time()

