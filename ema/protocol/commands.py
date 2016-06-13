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

    name = 'Abstract command'

    def __init__(self, ack_patterns, fmt=None, Niters=1):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in ack_patterns ]
        self.N        = len(self.ackPat)
        self.NIters   = Niters
        self.fmt      = fmt
        self.encoded  = None
        self.reset()

    def reset(self):
        '''reinitialization for retries'''
        self.i         = 0
        self.iteration = 1

    def encode(self):
        self.encoded = self.fmt
        return self.encoded
    
    def extractValues(self, line, matchobj):
        raise NotImplementedError

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
       
        matched = self.ackPat[self.i].search(line)
        if not matched:
            log.debug("Line does not match {command.name} response", command=self)
            return False

        if (self.i + 1) == self.N and self.iteration == self.NIters:
            self.extractValues(line, matched)
            finished = True
            log.debug("Matched {command.name} response, command complete", command=self)
        elif (self.i + 1) == self.N and self.iteration < self.NIters:
            self.collectData(line, matched)
            finished = True
            self.iteration += 1
            log.debug("Matched {command.name} response, command complete, accumulating data", command=self)
        else:   
            self.collectData(line, matched)
            self.i += 1
            finished = False
            log.debug("Matched {command.name} echo response, awaiting data", command=self)
        return finished

# ------------------------------------------------------------------------------

class Ping(Command):

    name = 'Ping'
    ACK_PATTERNS = [ '^\( \)' ]
    FMT = '( )'

    def __init__(self):
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)

    def extractValues(self, line, matchobj):
        self.response = line


# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class GetRTC(Command):
    '''
    Get Real Time Clock time Command
    '''
    name = 'Get Real Time Clock time'
    ACK_PATTERNS = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    FMT = '(y)'
    EMA_TIME_FORMAT = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)

    def extractValues(self, line, matchobj):
        self.response = datetime.datetime.strptime(line, self.EMA_TIME_FORMAT)

# ------------------------------------------------------------------------------

class SetRTC(Command):

    name = 'Set Real Time Clock time'
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

class GetAnemometerParameter(Command):
    '''
    Get Current Wind Speed Threshold Command
    '''
 
    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)
        

    def extractValues(self, line, matchobj):
        '''Return threshold in Km/h'''
        self.response = int(line[2:-1])

# ------------------------------------------------------------------------------

class GetCurrentWindSpeedThreshold(GetAnemometerParameter):
    '''
    Get Current Wind Speed Threshold Command
    '''
    name = 'Get Current Wind Speed Threshold'
    ACK_PATTERNS = [ '^\(W(\d{3})\)' ]
    FMT = '(w)'
    

# ------------------------------------------------------------------------------

class GetAverageWindSpeedThreshold(GetAnemometerParameter):
    '''
    Get Average Wind Speed Threshold Command, over an interval of 10 min.
    '''
    name = 'Get Average Wind Speed Threshold'
    ACK_PATTERNS = [ '^\(O(\d{3})\)' ]
    FMT = '(o)'
 


class GetAnemometerCalibrationConstant(GetAnemometerParameter):
    '''
    Get Anemometer Calibration Constant.
    '''
    name = 'Get Anemometer Calibration Constant'
    ACK_PATTERNS = [ '^\(A(\d{3})\)' ]
    FMT = '(a)'
 
   

class GetAnemometerModel(GetAnemometerParameter):
    '''
    Get Anemometer Model.
    '''
    name = 'Get Anemometer Model'
    ACK_PATTERNS = [ '^\(Z(\d{3})\)' ]
    FMT = '(z)'

    def extractValues(self, line, matchobj):
        GetAnemometerParameter.extractValues(self, line, matchobj)
        self.response = "TX20" if self.response == 1 else "Homemade"
 
# ------------------------------------------------------------------------------
#                               BAROMETER COMMANDS
# ------------------------------------------------------------------------------

class GetBarometerHeight(Command):
    '''
    Get Current Wind Speed Threshold Command
    '''
    name = 'Get Barometer Height'
    ACK_PATTERNS = [ '^\(M(\d{5})\)' ]
    FMT = '(m)'

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)
        

    def extractValues(self, line, matchobj):
        '''Return threshold in Km/h'''
        self.response = int(line[2:-1])


class GetBarometerOffset(Command):
    '''
    Get Current Wind Speed Threshold Command
    '''
    name = 'Get Barometer Offset'
    ACK_PATTERNS = [ '^\(B([+-]\d{2})\)' ]
    FMT = '(b)'

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS, fmt=self.FMT)
        

    def extractValues(self, line, matchobj):
        '''Return threshold in Km/h'''
        self.response = int(matchobj.group(1))


