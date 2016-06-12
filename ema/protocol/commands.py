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

# ----------------
# Twisted  modules
# ----------------

from twisted.logger import Logger

# -----------
# Own modules
# -----------

#from .     import PY2
#from .error import StringValueError, PayloadValueError, PayloadTypeError


log = Logger(namespace='pdu')


# ------------------------------------------------------------------------------

class Command(object):
    '''
    Get Real Time Clock time Command
    '''

    def __init__(self, ack_patterns, Niters=1):
        # Request format
        self.ackPat   = [ re.compile(pat) for pat in ack_patterns ]
        self.N        = len(self.ackPat)
        self.Niters   = Niters
        self.encoded = None
        self.reset()

    def reset(self):
        '''reinitialization for retries'''
        self.i         = 0
        self.iteration = 1

    def encode(self):
        raise NotImplementedError
    
    def extractValues(self, line):
        raise NotImplementedError

    def collectData(self, line):
        raise NotImplementedError

    def getResponse(self):
        '''Returns a response object. Must be called only after decode() returns True'''
        return self.response

    def decode(self, line):
        '''
        Generic decoding algorithm for commands
        Must again and again until returns True'''
        matched = self.ackPat[self.i].search(line)
        if not matched:
            log.debug("Matched {command} response, command complete", command=self.__class__.__name__)
            return False
        if (self.i + 1) == self.N and self.iteration == self.NIters:
            self.extractValues(line)
            finished = True
            log.debug("Matched {command} response, command complete", command=self.__class__.__name__)
        if (self.i + 1) == self.N and self.iteration < self.NIters:
            self.collectValues(line)
            finished = True
            self.iteration += 1
            log.debug("Matched {command} response, command complete, accumulating data", command=self.__class__.__name__)
        else:   
            self.collectValues(line)
            self.i += 1
            finished = False
            log.debug("Matched {command} echo response, awaiting data", command=self.__class__.__name__)
        return finished



# ------------------------------------------------------------------------------

class GetRTC(Command):
    '''
    Get Real Time Clock time Command
    '''

    ACK_PATTERNS = [ '^\(y\)', '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
    EMA_TFORMAT = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self):
        # Request format
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS)
        self.fmt    =  '(y)'
        
    def encode(self):
        self.encoded   = self.fmt
        return self.encoded

    def extractValues(self, line):
        self.response = datetime.datetime.strptime(line, self.EMA_TFORMAT)

    def collectData(self, line):
        pass

# ------------------------------------------------------------------------------

class SetRTC(Command):

    ACK_PATTERNS = [ '(Y\d{2}\d{2}\d{4}\d{2}\d{2}\d{2})','\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)']
    EMA_TFORMAT = '(%H:%M:%S %d/%m/%Y)'

    def __init__(self, tstamp=None):
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS)
        self.fmt =  '(Y%d%m%y%H%M%S)'
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

    def extractValues(self, line):
        self.response = datetime.datetime.strptime(line, self.EMA_TFORMAT)

    def collectData(self, line):
        pass

# ------------------------------------------------------------------------------

class Ping(Command):

    ACK_PATTERNS = [ '^\( \)' ]

    def __init__(self):
        Command.__init__(self, ack_patterns=self.ACK_PATTERNS)
        pass
        
    def encode(self):
        self.encoded = '( )'
        return self.encoded

    def extractValues(self, line):
        self.response = line

    def collectData(self, line):
        pass

# ------------------------------------------------------------------------------

