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

# ---------------
# Twisted imports
# ---------------

from twisted.logger              import Logger, LogLevel

#--------------
# local imports
# -------------

import metadata

from . import PY2

# -----------------------
# Module global variables
# -----------------------

log  = Logger(namespace='ema')


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
        if self.mdata.kind == str:
            result = self.mapping[int(self.matchobj[self.selindex].group(1))]
            if result not in self.mdata.domain: 
                raise EMAReturnError(self.__class__.__name__, result, self.mdata.domain)
        else:
            result = self.mdata.kind(int(self.matchobj[self.selindex].group(1)) / self.scale)
            if not (self.mdata.domain[0] <= result <= self.mdata.domain[1]): 
                raise EMAReturnError(self.__class__.__name__, result, self.mdata.domain)
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
        # No estoy seguro de que esto haga falta
        self.validate(value)
        # Ni esto tampoco
        self.value = value if (self.mdata.kind == datetime.datetime) or (self.mdata.kind == datetime.time) else self.mdata.kind(value)


    def encode(self):
        self.encoded = self.cmdformat.format(int(self.value * self.scale))


    def validate(self, value):
        '''Validate input'''
        if self.mdata.kind == str:
            if value not in self.mdata.domain: 
                raise EMARangeError(self.__class__.__name__, value, self.mdata.domain)
        else:
            if not (self.mdata.domain[0] <= value <= self.mdata.domain[1]): 
                raise EMARangeError(self.__class__.__name__, value, self.mdata.domain)




# ------------------------------------------------------------------------------
#                               REAL TIME CLOCK COMMANDS
# ------------------------------------------------------------------------------

class RealTimeClock(object):
    '''Namespace for children commands'''

    class GetDateTime(GetCommand):
        '''Get Real Time Clock Date & Time Command'''
        mdata           = metadata.RealTimeClock.DateTime
        cmdformat       = '(y)'
        ack_patterns    = [ '^\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' ]
        ema_time_format = '(%H:%M:%S %d/%m/%Y)'
        retries         = 2
        timeout         = {'min': 1, 'max': 128, 'factor': 2}

        def getResult(self):
            result = datetime.datetime.strptime(self.response[0], self.ema_time_format)
            if not (self.mdata.domain[0] <= result <= self.mdata.domain[1]): 
                    raise EMAReturnError(self.__class__.__name__, result, self.mdata.domain)
            return result

    # ------------------------------------------------------------------------------

    class SetDateTime(SetCommand):
        '''Set Real Time Clock Date & Time Command'''
        mdata           = metadata.RealTimeClock.DateTime
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
            if not (self.mdata.domain[0] <= self.value <= self.mdata.domain[1]): 
                raise EMARangeError(self.__class__.__name__, self.value, self.mdata.domain)


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
        mdata        = metadata.Watchdog.Presence
        cmdformat    = '( )'
        ack_patterns = [ '^\( \)' ]
        retries      = 0
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


        def getResult(self):
            return self.response[0]


    class GetPeriod(GetCommand):
        '''Get Watchdog Period Command'''
        mdata        = metadata.Watchdog.Period
        cmdformat    = '(t)'
        ack_patterns = [ '^\(T(\d{3})\)' ]
        ack_index    = 0
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetPeriod(SetCommand):
        '''Set Watchdog Period Command'''
        mdata        = metadata.Watchdog.Period
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
        mdata        = metadata.Anemometer.WindSpeedThreshold
        cmdformat    = '(w)'
        ack_patterns = [ '^\(W(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
        
    class SetCurrentWindSpeedThreshold(SetCommand):
        '''Set Current Wind Speed Threshold Command'''
        mdata        = metadata.Anemometer.WindSpeedThreshold
        cmdformat    = '(W{:03d})'
        ack_patterns = [ '^\(W(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
   

    # ------------------------------------------------------------------------------

    class GetAverageWindSpeedThreshold(GetCommand):
        '''Get 10min Average Wind Speed Threshold Command'''
        mdata        = metadata.Anemometer.WindSpeedThreshold
        cmdformat    = '(o)'
        ack_patterns = [ '^\(O(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
     
    class SetAverageWindSpeedThreshold(SetCommand):
        '''Set 10min Average Wind Speed Threshold Command'''
        mdata        = metadata.Anemometer.WindSpeedThreshold
        cmdformat    = '(O{:03d})'
        ack_patterns = [ '^\(O(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetCalibrationFactor(GetCommand):
        '''Get Anemometer Calibration Factor'''
        mdata        = metadata.Anemometer.CalibrationFactor
        cmdformat    = '(a)'
        ack_patterns = [ '^\(A(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
         

    class SetCalibrationFactor(SetCommand):
        '''Set Anemometer Calibration Factor'''
        mdata        = metadata.Anemometer.CalibrationFactor
        cmdformat    = '(A{:03d})'
        ack_patterns = [ '^\(A(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       
    # ------------------------------------------------------------------------------

    class GetModel(GetCommand):
        '''Get Anemometer Model Command'''
        mdata        = metadata.Anemometer.Model
        cmdformat    = '(z)'
        ack_patterns = [ '^\(Z(\d{3})\)' ]
        mapping      = { 1: 'TX20', 0: 'Simple'}
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

           

    class SetModel(SetCommand):
        '''Set Anemometer Model Command'''
        mdata        = metadata.Anemometer.Model
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
        mdata        = metadata.Barometer.Height
        cmdformat    = '(m)'
        ack_patterns = [ '^\(M(\d{5})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetHeight(SetCommand):
        '''Set Barometer Height Command'''
        mdata        = metadata.Barometer.Height
        cmdformat    = '(M{:05d})'
        ack_patterns = [ '^\(M(\d{5})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetOffset(GetCommand):
        '''Get Barometer Offset Command'''
        mdata        = metadata.Barometer.Offset
        cmdformat    = '(b)'
        ack_patterns = [ '^\(B([+-]\d{2})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}



    class SetOffset(SetCommand):
        '''Set Barometer Offset Command'''
        mdata        = metadata.Barometer.Offset
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
        mdata        = metadata.CloudSensor.Threshold
        cmdformat    = '(n)'
        ack_patterns = [ '^\(N(\d{3})\)' ]
        ack_index    = 0
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetThreshold(SetCommand):
        '''Set Cloud Sensor Threshold Command'''
        mdata        = metadata.CloudSensor.Threshold
        cmdformat    = '(N{:03d})'
        ack_patterns = [ '^\(N(\d{3})\)' ]
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetGain(GetCommand):
        '''Get Cloud Sensor Gain Command'''
        mdata        = metadata.CloudSensor.Gain
        cmdformat    = '(r)'
        ack_patterns = [ '^\(R(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetGain(SetCommand):
        '''Set Cloud Sensor Gain Command'''
        mdata        = metadata.CloudSensor.Gain
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
        mdata        = metadata.Photometer.Threshold
        cmdformat    = '(i)'
        ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
        ack_index    = 0
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
       

    class SetThreshold(SetCommand):
        '''Set Photometer Threshold Command'''
        mdata        = metadata.Photometer.Threshold
        cmdformat    = '(I{:03d})'
        ack_patterns = [ '^\(I(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    # ------------------------------------------------------------------------------

    class GetOffset(GetCommand):
        '''Get Photometer Gain Offset'''
        mdata        = metadata.Photometer.Offset
        cmdformat    = '(i)'
        ack_patterns = [ '^\(I(\d{3})\)',  '^\(I([+-]\d{2})\)',  '^\(I(\d{5})\)']
        ack_index    = 1
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetOffset(SetCommand):
        '''Set Photometer Gain Offset'''
        mdata        = metadata.Photometer.Offset
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
        mdata        = metadata.Pluviometer.Factor
        cmdformat    = '(p)'
        ack_patterns = [ '^\(P(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetCalibrationFactor(SetCommand):
        '''Set Pluviometer Calibration Constant Command'''
        mdata        = metadata.Pluviometer.Factor
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
        mdata        = metadata.Pyranometer.Gain
        cmdformat    = '(j)'
        ack_patterns = [ '^\(J(\d{3})\)']
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetGain(SetCommand):
        '''Set Pyranometer Gain Command'''
        mdata        = metadata.Pyranometer.Gain
        cmdformat    = '(J{:03d})'
        ack_patterns = [ '^\(J(\d{3})\)']
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        


    class GetOffset(GetCommand):
        '''Get Pyranometer Offset Command'''
        mdata        = metadata.Pyranometer.Offset
        cmdformat    = '(u)'
        ack_patterns = [ '^\(U(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
      


    class SetOffset(SetCommand):
        '''Get Pyranometer Offset Command'''
        mdata        = metadata.Pyranometer.Offset
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
        mdata        = metadata.RainSensor.Threshold
        cmdformat    = '(l)'
        ack_patterns = [ '^\(L(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetThreshold(SetCommand):
        '''Set Rain Sensor Threshold Command'''
        mdata        = metadata.RainSensor.Threshold
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
        mdata        = metadata.Thermometer.Threshold
        cmdformat    = '(c)'
        ack_patterns = [ '^\(C(\d{3})\)']
        scale        = 1
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        

    class SetThreshold(SetCommand):
        '''Set Thermometer DeltaTemp Threshold Command'''
        mdata        = metadata.Thermometer.Threshold
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
        mdata        = metadata.Voltmeter.Threshold
        cmdformat    = '(f)'
        ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
        ack_index    = 0
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetThreshold(SetCommand):
        '''Set Voltmeter Threshold Command'''
        mdata        = metadata.Voltmeter.Threshold
        cmdformat    = '(F{:03d})'
        ack_patterns = [ '^\(F(\d{3})\)' ]
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class GetOffset(GetCommand):
        '''Get Voltmeter Offset Command'''
        mdata        = metadata.Voltmeter.Offset
        cmdformat    = '(f)'
        ack_patterns = [ '^\(F(\d{3})\)', '^\(F([+-]\d{2})\)' ]
        ack_index    = 1
        scale        = 10
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}


    class SetOffset(SetCommand):
        '''Set Voltmeter Offset Command'''
        mdata        = metadata.Voltmeter.Offset
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
        mdata        = metadata.RoofRelay.Mode
        cmdformat    = '(X{:03d})'
        ack_patterns = [ '^\(X(\d{3})\)' ,  '^(dummy)' ]
        ack_index    = 0
        mapping      = { 'Closed': 0, 'Open' : 7, }
        inv_mapping  = { 0: 'Closed', 7: 'Open',  }
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}
        
        def __init__(self, value):
            SetCommand.__init__(self, value)
           # Patches the last compiled expression
            if self.value == 'Open':
                self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Abrir Obs\. FORZADO\)')
            elif self.value == 'Closed':
                self.ackPat[1] = re.compile('^\(\d{2}:\d{2}:\d{2} Cerrar Obs\.\)')

        def encode(self):
            self.encoded = self.cmdformat.format(self.mapping[self.value])
           
        def getResult(self):
            return self.inv_mapping[int(self.matchobj[0].group(1))]


# ------------------------------------------------------------------------------
#                               AUX RELAY COMMANDS
# ------------------------------------------------------------------------------

class AuxRelay(object):
    '''Namespace for chldren commands'''

    class GetSwitchOnTime(GetCommand):
        '''Get Aux Relay Switch-On Time Command'''
        mdata           = metadata.AuxRelay.SwitchOnTime
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
        mdata           = metadata.AuxRelay.SwitchOnTime
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
        mdata           = metadata.AuxRelay.SwitchOffTime
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
        mdata           = metadata.AuxRelay.SwitchOffTime
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
        mdata        = metadata.AuxRelay.Mode
        cmdformat    = '(s)'
        ack_patterns = [ '^\(S(\d{3})\)', '^\(Son\d{4}\)', '^\(Sof\d{4}\)' ]
        ack_index    = 0
        mapping      = { 0 : 'Auto', 4: 'Closed', 5 : 'Open', 8 : 'Timer/Off', 9 : 'Timer/On' }
        retries      = 2
        timeout      = {'min': 2, 'max': 128, 'factor': 2}

        

    class SetMode(SetCommand):
        '''Set Aux Relay Mode Command'''
        mdata        = metadata.AuxRelay.Mode
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
       

