#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import os
import errno
import sys
import datetime
import json
import math
import random

from collections import deque

# ---------------
# Twisted imports
# ---------------


from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task, defer
from twisted.internet.defer       import inlineCallbacks, returnValue

#--------------
# local imports
# -------------

import ema.metadata as metadata
import ema.command  as command

from .serial  import EMATimeoutError
from .utils   import setSystemTime

# ----------
# Exceptions
# ----------

class EMARangeError(ValueError):
    '''EMA Attribute value out of range'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: {1} whose value <{2}> is not in {3} range'.format(s, self.args[0], self.args[1], self.args[2])
        s = '{0}.'.format(s)
        return s

class EMATypeError(TypeError):
    '''EMA Attribute value type mismatch'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: in {1} expected {2}, got {3}'.format(s, self.args[0], self.args[1], self.args[2])
        s = '{0}.'.format(s)
        return s

class EMAAttributeError(AttributeError):
    '''EMA Attribute Error'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: {1} is {2}'.format(s, self.args[0], self.args[1], self.args[2])
        s = '{0}.'.format(s)
        return s

class EMADeleteAttributeError(AttributeError):
    '''EMA Delete Attribute Error'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: {1} -> {2}'.format(s, self.args[0], self.args[1])
        s = '{0}.'.format(s)
        return s


class EMARuntimeError(RuntimeError):
    '''EMA Runtime Error'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: {1}, {2}'.format(s, self.args[0], self.args[1])
        s = '{0}.'.format(s)
        return s


# -----------------------
# Module global variables
# -----------------------

log  = Logger(namespace='ema')


class Attribute(object):

    # Protocol to use
    protocol = None

    @classmethod
    def bind(cls, protocol):
        '''Binds the deferred Attribute to the protrocol for command execution'''
        cls.protocol = protocol

    @classmethod
    def deferred(cls, parameter):
        '''Builds the deferred attribute instance'''
        return cls(parameter)


    def __init__(self, parameter):
        self.parameter = parameter
        self.attr_name      = '__' + parameter.name
        self.attr_dfrd_name = '__' + parameter.name + '_deferred'


    def validate(self, value):
        '''Validates value against parameter's setter metadata type and range'''
        if self.parameter.setter is None:
            raise EMAAttributeError(self.parameter.name, "r/o attribute")
        if type(value) != self.parameter.setter.metadata.kind:
            raise EMATypeError(value, self.parameter.setter.metadata.kind, type(value))
        if self.parameter.setter.metadata.kind == str:
            if value not in self.parameter.setter.metadata.domain: 
                raise EMARangeError(self.attr_name[2:], value, self.parameter.setter.metadata.domain)
        else:
            if not (self.parameter.setter.metadata.domain[0] <= value <= self.parameter.setter.metadata.domain[1]): 
                raise EMARangeError(self.attr_name[2:], value, self.parameter.setter.metadata.domain)


    def __delete__(self, obj):
        '''Descriptor delete protocol'''
        raise EMADeleteAttributeError(self.parameter.name, "not implemented operation")


    def __get__(self, obj, objtype=None):
        '''Descriptor get protocol'''
        def complete(value):
            setattr(obj, self.attr_name,     value)
            setattr(obj, self.attr_dfrd_name, None)
            return value
        def failed(failure):
            setattr(obj, self.attr_name,      None)
            setattr(obj, self.attr_dfrd_name, None)
            return failure
        if obj is None:
            return self.parameter
        attr_val     =  getattr(obj, self.attr_name,      None)
        attr_def_val =  getattr(obj, self.attr_dfrd_name, None)
        # sharing deferred with __set__
        if attr_def_val is not None:
            return  attr_def_val
        # checking the getter after the deferred makes it possible
        # to capture the deferred generated in the __set__ operation
        # even for w/o attributies
        if self.parameter.getter is None:
            raise EMAAttributeError(self.parameter.name, "w/o attribute")
        if attr_val is not None and not self.parameter.getter.metadata.volatile:
            return defer.succeed(attr_val)
        if self.protocol is None:
            raise EMARuntimeError(self.parameter.name, "attribute not bound to a protocol yet")
        cmd = self.parameter.getter()
        d = self.protocol.execute(cmd)
        setattr(obj, self.attr_dfrd_name, d)
        d.addCallbacks(complete, failed)
        return  d
           

    def __set__(self, obj, value):
        '''Descriptor set protocol'''
        def complete(ignored_value):
            setattr(obj, self.attr_name,     value)
            setattr(obj, self.attr_dfrd_name, None)
            return value
        def failed(failure):
            setattr(obj, self.attr_dfrd_name, None)
            return failure
        self.validate(value)
        if self.protocol is None:
            raise EMARuntimeError(self.parameter.name, "attribute not bound to a protocol yet")
        attr_def_val =  getattr(obj, self.attr_dfrd_name, None)
        if attr_def_val is not None:
            raise EMARuntimeError(self.parameter.name, "operation in progress")
        setattr(obj, self.attr_name, None)
        cmd = self.parameter.setter(value)
        d = self.protocol.execute(cmd)
        setattr(obj, self.attr_dfrd_name, d)
        d.addCallbacks(complete, failed)
        

#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class Device(object):
    '''Base class for al EMA virtual instruments, actuators and other devices'''
    def __init__(self, parent, options, global_sync):
        self.name        = self.__class__.__name__ 
        self.options     = options
        self.parent      = parent
        self.global_sync = global_sync
        self.sync_params = []

    @inlineCallbacks
    def parameters(self):
        '''
        Return a dictionary of current syncable parameter 
        for this device values
        '''
        
        # Selected attributes only
        attrs = [ self.__class__.__name__.lower() + '_' + attr for attr in self.sync_params 
                if getattr(self.__class__, attr).getter.metadata.stable ]
        # Selected values in form of deferreds
        dl = [ getattr(self, attr) for attr in self.sync_params 
                if getattr(self.__class__, attr).getter.metadata.stable ]
        result = yield defer.DeferredList(dl, consumeErrors=True)
        mydict = { attrs[i] : result[i][1] for i in range(0,len(attrs))  }
        returnValue(mydict)


    def paramEquals(self, value, target,  threshold=0.001):
        if type(value) == float:
            return math.fabs(value - target) < threshold
        else:
            return value == target

    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes parameters. 
        Returns a deferred whose success callback value None
        '''
        for name in self.sync_params:
            configured = self.options[name]
            value = yield getattr(self, name)
            if not self.paramEquals(value, configured):
                log.warn("{title} values do not match [EMA = {read}] [file = {file}]", 
                    title=name, read=value, file=configured)
                if self.options['sync'] and self.global_sync:
                        log.info("Synchronizing {title}", title=name)
                        setattr(self, name, configured)
            else:
                log.info("{title} already synchronized",title=name)


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Thermopile(Device):


    def __init__(self, parent, options, global_sync=True):
        pass    
        
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Anemometer(Device):

    class Threshold(object):
        '''Current Wind Speed Threshold'''
        name   = 'threshold'
        getter = command.Anemometer.GetCurrentWindSpeedThreshold
        setter = command.Anemometer.SetCurrentWindSpeedThreshold
    class AverageThreshold(object):
        '''Average Wind Speed Threshold'''
        name   = 'ave_threshold'
        getter = command.Anemometer.GetAverageWindSpeedThreshold
        setter = command.Anemometer.SetAverageWindSpeedThreshold
    class Calibration(object):
        '''Calibration Constant'''
        name   = 'calibration'
        getter = command.Anemometer.GetCalibrationFactor
        setter = command.Anemometer.SetCalibrationFactor
    class Model(object):
        '''Anemometer Model'''
        name   = 'model'
        getter = command.Anemometer.GetModel
        setter = command.Anemometer.SetModel

    # Deferred attribute handling via Descriptors
    threshold     = Attribute.deferred(parameter=Threshold())
    ave_threshold = Attribute.deferred(parameter=AverageThreshold())
    calibration   = Attribute.deferred(parameter=Calibration())
    model         = Attribute.deferred(parameter=Model())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Anemometer.Threshold.name, 
            Anemometer.AverageThreshold.name, 
            Anemometer.Calibration.name, 
            Anemometer.Model.name]


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Barometer(Device):

    class Height(object):
        '''Barometer Height'''
        name   = 'height'
        getter = command.Barometer.GetHeight
        setter = command.Barometer.SetHeight
    class Offset(object):
        '''Barometer Offset'''
        name   = 'offset'
        getter = command.Barometer.GetOffset
        setter = command.Barometer.SetOffset

    # Deferred attribute handling via Descriptors
    height    = Attribute.deferred(parameter=Height())
    offset    = Attribute.deferred(parameter=Offset())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Barometer.Height.name, Barometer.Offset.name]

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class CloudSensor(Device):

    class Threshold(object):
        '''Cloud Sensor Threshold'''
        name   = 'threshold'
        getter = command.CloudSensor.GetThreshold
        setter = command.CloudSensor.SetThreshold
    class Gain(object):
        '''Cloud Sensor Gain'''
        name   = 'gain'
        getter = command.CloudSensor.GetGain
        setter = command.CloudSensor.SetGain

    # Deferred attribute handling via Descriptors
    threshold = Attribute.deferred(parameter=Threshold())
    gain      = Attribute.deferred(parameter=Gain())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [CloudSensor.Threshold.name, CloudSensor.Gain.name]

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Photometer(Device):

    class Threshold(object):
        '''Photometer Threshold'''
        name   = 'threshold'
        getter = command.Photometer.GetThreshold
        setter = command.Photometer.SetThreshold
    class Offset(object):
        '''Photometer Offset'''
        name   = 'offset'
        getter = command.Photometer.GetOffset
        setter = command.Photometer.SetOffset

    # Deferred attribute handling via Descriptors
    threshold = Attribute.deferred(parameter=Threshold())
    offset    = Attribute.deferred(parameter=Offset())
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Photometer.Threshold.name, Photometer.Offset.name]



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Pluviometer(Device):

    class CalibrationFactor(object):
        '''Pluviometer Calibration Constant'''
        name   = 'calibration'
        getter = command.Pluviometer.GetCalibrationFactor
        setter = command.Pluviometer.SetCalibrationFactor

    # Deferred attribute handling via Descriptors
    calibration      = Attribute.deferred(parameter=CalibrationFactor())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Pluviometer.CalibrationFactor.name]

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class Pyranometer(Device):

    class Gain(object):
        '''Pyranometer Gain'''
        name   = 'gain'
        getter = command.Pyranometer.GetGain
        setter = command.Pyranometer.SetGain
    class Offset(object):
        '''Pyranometer Offset'''
        name   = 'offset'
        getter = command.Pyranometer.GetOffset
        setter = command.Pyranometer.SetOffset

    # Deferred attribute handling via Descriptors
    gain      = Attribute.deferred(parameter=Gain())
    offset    = Attribute.deferred(parameter=Offset())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Pyranometer.Gain.name, Pyranometer.Offset.name] 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RainSensor(Device):

    class Threshold(object):
        '''Rain Sensor Threshold'''
        name   = 'threshold'
        getter = command.RainSensor.GetThreshold
        setter = command.RainSensor.SetThreshold
  
    # Deferred attribute handling via Descriptors
    threshold = Attribute.deferred(parameter=Threshold())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [RainSensor.Threshold.name] 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Thermometer(Device):

    class Threshold(object):
        '''Thermometer Delta Temperature Threshold'''
        name   = 'threshold'
        getter = command.Thermometer.GetThreshold
        setter = command.Thermometer.SetThreshold
  
    # Deferred attribute handling via Descriptors
    threshold = Attribute.deferred(parameter=Threshold())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Thermometer.Threshold.name] 



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RoofRelay(Device):

    class Mode(object):
        name   = 'mode'
        getter = None
        setter = command.RoofRelay.SetMode

    # Deferred attribute handling via Descriptors
    mode          = Attribute.deferred(parameter=Mode())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = []
        self.switchon = deque(maxlen=2)
        self.parent.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[command.ROOF_RELAY]
        level = 1 if code == 'A' or code == 'a' else 0
        self.switchon.append(level)
        if len(self.switchon) < 2:
            return
        diff = self.switchon[0] - self.switchon[1]
        if diff < 0:    # Transition Off -> On
            self.parent.onEventExecute('roof_relay', 'On' , code)
        elif diff > 0:  # Transition On -> Off
            self.parent.onEventExecute('roof_relay', 'Off' , code)
        else:
            pass



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class AuxiliarRelay(Device):

    class SwitchOnTime(object):
        '''Auxiliar Relay Switch On Time'''
        name   = 'switchOnTime'
        getter = command.AuxiliarRelay.GetSwitchOnTime
        setter = command.AuxiliarRelay.SetSwitchOnTime
    class SwitchOffTime(object):
        '''Auxiliar Relay Switch Off Time'''
        name   = 'switchOffTime'
        getter = command.AuxiliarRelay.GetSwitchOffTime
        setter = command.AuxiliarRelay.SetSwitchOffTime
    class Mode(object):
        '''AuxiliarRelay Mode'''
        name   = 'mode'
        getter = command.AuxiliarRelay.GetMode
        setter = command.AuxiliarRelay.SetMode

    # Deferred attribute handling via Descriptors
    switchOnTime  = Attribute.deferred(parameter=SwitchOnTime())
    switchOffTime = Attribute.deferred(parameter=SwitchOffTime())
    mode          = Attribute.deferred(parameter=Mode())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [AuxiliarRelay.Mode.name]  
        self.switchon = deque(maxlen=2)
        self.parent.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[command.AUX_RELAY]
        level = 1 if code == 'E' or code == 'e' else 0
        self.switchon.append(level)
        if len(self.switchon) < 2:
            return
        diff = self.switchon[0] - self.switchon[1]
        if diff < 0:    # Transition Off -> On
            self.parent.onEventExecute('aux_relay', 'On' , code)
        elif diff > 0:  # Transition On -> Off
            self.parent.onEventExecute('aux_relay', 'Off' , code)
        else:
            pass


    @inlineCallbacks
    def nextRelayCycle(self, inactiveInterval):
        off = inactiveInterval.t0.time()
        on  = inactiveInterval.t1.time()
        self.switchOffTime = off
        yield self.switchOffTime
        self.switchOnTime  = on
        yield self.switchOffTime

    

#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RealTimeClock(Device):

    class DateTime(object):
        '''EMA Date Time Clock Adjustment'''
        name   = 'dateTime'
        getter = command.RealTimeClock.GetDateTime
        setter = command.RealTimeClock.SetDateTime

    # Deferred attribute handling via Descriptors
    dateTime = Attribute.deferred(parameter=DateTime())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [RealTimeClock.DateTime.name]


    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes EMA RTC Clock to Host Clock. 
        Returns a deferred whose success callback value is a flag
        True = synch process ok, False = synch process went wrong
        '''
        max_drift = self.options['max_drift']
        log.info("Synchronizing {title} from Host RTC", title='EMA RTC')
        try:
            value = yield self.dateTime
        except EMATimeoutError as e:
            log.error("EMA RTC sync exception => {exception}", exception=e)
            returnValue(False)
        now = datetime.datetime.utcnow()
        if abs((value - now).total_seconds()) > max_drift:
            log.warn("{title} not synchronized [EMA = {EMA!s}] [Host = {host!s}]", title='EMA RTC', EMA=value, host=now)
            log.info("Synchronizing {title} to Host RTC", title='EMA RTC')
            try:
                self.dateTime = value
                value = yield self.dateTime
            except EMATimeoutError as e:
                log.error("RTC sync exception => {exception}", exception=e)
                returnValue(False)
            if abs((value - datetime.datetime.utcnow()).total_seconds()) > max_drift:
                log.warn("{title} still not synchronized to Host RTC", title='EMA RTC')
        else:
            log.info("{title} already synchronized to Host RTC", title='EMA RTC')
        returnValue(True)


    @inlineCallbacks
    def inverseSync(self):
        '''
        Synchronizes Host Clock Clock from EMA RTC as master clock. 
        Returns a deferred whose success callback value is a flag
        True = synch process ok, False = synch process went wrong
        '''
        log.info("Synchronizing Host RTC from EMA RTC")
        max_drift = self.options['max_drift']
        try:
            utvalue = yield self.dateTime
        except EMATimeoutError as e:
            log.error("RTC inverseSync exception => {exception}", exception=e)
            returnValue(False)

        utnow = datetime.datetime.utcnow()
        if abs((utvalue - utnow).total_seconds()) <= max_drift:
            log.info("Host RTC already synchronized from EMA RTC")
            returnValue(True)

        log.warn("Host computer not synchronized from EMA [EMA = {EMA!s}] [Host = {host!s}]",  EMA=utvalue, host=utnow)
        
        try:
            log.info("Synchronizing Host computer from EMA RTC")
            # Assume Host Compuer works in UTC !!!
            setSystemTime(utvalue.timetuple())
            utvalue = yield  self.dateTime
        except Exception as e:
            log.error("RTC inverseSync exception => {exception}", exception=e)
            returnValue(False)    
        # This may fail if the host compuer is not set in UTC timezone.
        # This is unlikely to happen in the foreseen usage but
        # for a proper way to do it, see 
        # http://stackoverflow.com/questions/1681143/how-to-get-tz-info-object-corresponding-to-current-timezone
        if abs((utvalue - datetime.datetime.utcnow()).total_seconds()) > max_drift:
            log.warn("Host Computer RTC still not synchronized")
            returnValue(False)
        
        returnValue(True)

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Voltmeter(Device):

    class Threshold(object):
        name   = 'threshold'
        getter = command.Voltmeter.GetThreshold
        setter = command.Voltmeter.SetThreshold
    class Offset(object):
        name   = 'offset'
        getter = command.Voltmeter.GetOffset
        setter = command.Voltmeter.SetOffset

    # Deferred attribute handling via Descriptors
    threshold = Attribute.deferred(parameter=Threshold())
    offset    = Attribute.deferred(parameter=Offset())

    def __init__(self, parent, options, upload_period, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Voltmeter.Threshold.name, Voltmeter.Offset.name]
        self.voltage = deque(maxlen=(upload_period//command.PERIOD))
        self.parent.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        self.voltage.append(message[command.POWER_VOLT])
        n       = len(self.voltage)
        average = sum(self.voltage) / n
        # This is a dirty trick, bypassing the attribute descriptor
        value = getattr(self, '__threshold', None)
        if  value is None:
            log.debug("No threshold value yet from EMA")
            return
        secure_threshold = self.options['delta'] + value
        if average < secure_threshold:
            self.parent.onEventExecute('low_voltage', average, secure_threshold, n)

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
    
class Watchdog(Device):

    class Period(object):
        '''Watchdog Period'''
        name   = 'period'
        getter = command.Watchdog.GetPeriod
        setter = command.Watchdog.SetPeriod
    class Presence(object):
        name   = 'presence'
        '''Watchdog presence message'''
        getter = command.Watchdog.GetPresence
        setter = None

    # Deferred attribute handling via Descriptors
    period   = Attribute.deferred(parameter=Period())
    presence = Attribute.deferred(parameter=Presence())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.sync_params = [Watchdog.Period.name]
        self.pingTask  = task.LoopingCall(self.ping)

    def start(self):
        self.pingTask.start(self.options['period']//2+random.random(), now=False)

    def stop(self):
        self.pingTask.stop()

    @inlineCallbacks
    def ping(self):
        try:
            val = yield self.presence 
        except EMATimeoutError as e:
            pass
        

