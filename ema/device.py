#--------------------
# System wide imports
# -------------------

from __future__ import division

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

import metadata
import command

from serial import EMATimeoutError
from utils  import setSystemTime


# -----------------------
# Module global variables
# -----------------------

log  = Logger(namespace='ema')


class Property(object):

    # Service from where to obtain the protocol
    service = None

    @classmethod
    def bind(cls, service):
        '''Binds the Proerty with servicee where to obtain the protocol'''
        cls.service = service

    def __init__(self, parameter):
        self.parameter = parameter


    def __delete__(self, obj):
        raise AttributeError("can't delete attribute")


    def assertService(self):
        '''Assets the runtime is ready'''
        if self.service is None:
            raise RuntimeError("Not bound to a service yet")
        if self.service.protocol is None:
            raise RuntimeError("descriptor service not bound to a protocol yet")

    def validate(self, value):
        '''Validates value against parameter's setter metadata type and range'''
        if self.parameter.setter is None:
            raise RuntimeError("This descriptor does no support assignments")
        if self.parameter.setter.metadata.kind == str:
            if value not in self.parameter.setter.metadata.domain: 
                raise EMARangeError(self.__class__.__name__, value, self.parameter.setter.metadata.domain)
        else:
            if not (self.parameter.setter.metadata.domain[0] <= value <= self.parameter.setter.metadata.domain[1]): 
                raise EMARangeError(self.__class__.__name__, value, self.metadata.parameter.domain)


def deferred(attrname):
    '''
    Factory function that returns a Descriptor Class
    with customized private attribute and deff
    '''
    class Descriptor(Property):
        '''Threshold descriptor'''
        def __init__(self, parameter):
            Property.__init__(self, parameter)
            self.attr_name      = '__' + attrname
            self.attr_dfrd_name = '__' + attrname + '_deferred'

        def __get__(self, obj, objtype=None):
            '''Descriptor get protocol'''
            def complete(value):
                setattr(obj, '__' + attrname,     value)
                setattr(obj, '__' + attrname + '_deferred', None)
                return value
            def failed(failure):
                setattr(obj, self.attr_name,      None)
                setattr(obj, self.attr_dfrd_name, None)
                return failure
            if obj is not None:
                attr_val     =  getattr(obj, self.attr_name,      None)
                attr_def_val =  getattr(obj, self.attr_dfrd_name, None)
                # sharing deferred with __set__
                if attr_def_val is not None:
                    return  attr_def_val
                if attr_val is not None and not self.parameter.getter.metadata.volatile:
                    return defer.succeed(attr_val)
                self.assertService()
                cmd = self.parameter.getter()
                d = self.service.protocol.execute(cmd)
                setattr(obj, self.attr_dfrd_name, d)
                d.addCallbacks(complete, failed)
                return  d
            else:   
                # Access through class, not instance
                # returns the parameter class in order to retrieve metadata
                return self.parameter


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
            self.assertService()
            attr_def_val =  getattr(obj, self.attr_dfrd_name, None)
            if attr_def_val is not None:
                raise RuntimeError("Operation in progress")
            setattr(obj, self.attr_name, None)
            cmd = self.parameter.setter(value)
            d = self.service.protocol.execute(cmd)
            setattr(obj, self.attr_dfrd_name, d)
            d.addCallbacks(complete, failed)
        

    return Descriptor







class Device(object):
    def __init__(self, parent, options, global_sync):
        self.name        = self.__class__.__name__ 
        self.options     = options
        self.parent      = parent
        self.global_sync = global_sync
        self.PARAMS      = []


    def parameters(self):
        '''
        Return a dictionary of current parameter values
        '''
        return { (self.name + '_' + name).lower(): param['value'] 
            for name, param in self.PARAMS.iteritems() if param['invariant']}

    @inlineCallbacks
    def parameters(self):
        '''
        Return a dictionary of current parameter values
        '''
        
        # Selected attributes only
        attrs = [ self.__class__.__name__.lower() + '_' + attr for attr in self.PARAMS 
                if getattr(self.__class__, attr).getter.metadata.stable ]
        # Selected values in form of deferreds
        dl = [ getattr(self, attr) for attr in self.PARAMS 
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
        for name in self.PARAMS:
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
        getter = command.Anemometer.GetCurrentWindSpeedThreshold
        setter = command.Anemometer.SetCurrentWindSpeedThreshold
    class AverageThreshold(object):
        '''Average Wind Speed Threshold'''
        getter = command.Anemometer.GetAverageWindSpeedThreshold
        setter = command.Anemometer.GetAverageWindSpeedThreshold
    class Calibration(object):
        '''Calibration Constant'''
        getter = command.Anemometer.GetCalibrationFactor
        setter = command.Anemometer.SetCalibrationFactor
    class Model(object):
        '''Anemometer Model'''
        getter = command.Anemometer.GetModel
        setter = command.Anemometer.SetModel

    # Deferred attribute handling via Descriptors
    threshold     = deferred("threshold")(Threshold())
    ave_threshold = deferred("ave_threshold")(AverageThreshold())
    calibration   = deferred("calibration")(Calibration())
    model         = deferred("model")(Model())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold', 'ave_threshold','calibration','model']

    def stable(self):
        '''
        Return a dictionary of current parameter values
        '''
        pass

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Barometer(Device):

    class Height(object):
        '''Barometer Height'''
        getter = command.Barometer.GetHeight
        setter = command.Barometer.SetHeight
    class Offset(object):
        '''Barometer Offset'''
        getter = command.Barometer.GetOffset
        setter = command.Barometer.SetOffset

    # Deferred attribute handling via Descriptors
    height    = deferred("height")(Height())
    offset    = deferred("offset")(Offset())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['height', 'offset']

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class CloudSensor(Device):

    class Threshold(object):
        '''Cloud Sensor Threshold'''
        getter = command.CloudSensor.GetThreshold
        setter = command.CloudSensor.SetThreshold
    class Gain(object):
        '''Cloud Sensor Gain'''
        getter = command.CloudSensor.GetGain
        setter = command.CloudSensor.SetGain

    # Deferred attribute handling via Descriptors
    threshold = deferred("threshold")(Threshold())
    gain      = deferred("gain")(Gain())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold', 'gain']

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Photometer(Device):

    class Threshold(object):
        '''Photometer Threshold'''
        getter = command.Photometer.GetThreshold
        setter = command.Photometer.SetThreshold
    class Offset(object):
        '''Photometer Offset'''
        getter = command.Photometer.GetOffset
        setter = command.Photometer.SetOffset

    # Deferred attribute handling via Descriptors
    threshold = deferred("threshold")(Threshold())
    offset    = deferred("offset")(Offset())
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold', 'offset']



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Pluviometer(Device):

    class CalibrationFactor(object):
        '''Pluviometer Calibration Constant'''
        getter = command.Pluviometer.GetCalibrationFactor
        setter = command.Pluviometer.SetCalibrationFactor

    # Deferred attribute handling via Descriptors
    calibration      = deferred("calibration")(CalibrationFactor())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['calibration']

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class Pyranometer(Device):

    class Gain(object):
        '''Pyranometer Gain'''
        getter = command.Pyranometer.GetGain
        setter = command.Pyranometer.SetGain
    class Offset(object):
        '''Pyranometer Offset'''
        getter = command.Pyranometer.GetOffset
        setter = command.Pyranometer.SetOffset

    # Deferred attribute handling via Descriptors
    gain      = deferred("gain")(Gain())
    offset    = deferred("offset")(Offset())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['gain','offset'] 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RainSensor(Device):

    class Threshold(object):
        '''Rain Sensor Threshold'''
        getter = command.RainSensor.GetThreshold
        setter = command.RainSensor.SetThreshold
  
    # Deferred attribute handling via Descriptors
    threshold = deferred("threshold")(Threshold())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold'] 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Thermometer(Device):

    class Threshold(object):
        '''Thermometer Delta Temperature Threshold'''
        getter = command.Thermometer.GetThreshold
        setter = command.Thermometer.SetThreshold
  
    # Deferred attribute handling via Descriptors
    threshold = deferred("threshold")(Threshold())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold'] 



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RoofRelay(Device):

    class Mode(object):
        getter = None
        setter = command.RoofRelay.SetMode

    # Deferred attribute handling via Descriptors
    mode          = deferred("mode")(Mode())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = []
        self.switchon = deque(maxlen=2)
        self.parent.serialService.protocol.addStatusCallback(self.onStatus)


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
        getter = command.AuxRelay.GetSwitchOnTime
        setter = command.AuxRelay.SetSwitchOnTime
    class SwitchOffTime(object):
        '''Auxiliar Relay Switch Off Time'''
        getter = command.AuxRelay.GetSwitchOffTime
        setter = command.AuxRelay.SetSwitchOffTime
    class Mode(object):
        '''AuxiliarRelay Mode'''
        getter = command.AuxRelay.GetMode
        setter = command.AuxRelay.SetMode

    # Deferred attribute handling via Descriptors
    switchOnTime  = deferred("switchOnTime")(SwitchOnTime())
    switchOffTime = deferred("switchOffTime")(SwitchOffTime())
    mode          = deferred("mode")(SwitchOffTime())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['mode']  
        self.switchon = deque(maxlen=2)
        self.parent.serialService.protocol.addStatusCallback(self.onStatus)


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
        getter = command.RealTimeClock.GetDateTime
        setter = command.RealTimeClock.SetDateTime

    # Deferred attribute handling via Descriptors
    dateTime = deferred("dateTime")(DateTime())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = []


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
        getter = command.Voltmeter.GetThreshold
        setter = command.Voltmeter.SetThreshold
    class Offset(object):
        getter = command.Voltmeter.GetOffset
        setter = command.Voltmeter.SetOffset

    # Deferred attribute handling via Descriptors
    threshold = deferred("threshold")(Threshold())
    offset    = deferred("offset")(Offset())

    def __init__(self, parent, options, upload_period, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['threshold', 'offset']
        self.voltage = deque(maxlen=(upload_period//command.PERIOD))
        self.parent.serialService.protocol.addStatusCallback(self.onStatus)


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
        getter = command.Watchdog.GetPeriod
        setter = command.Watchdog.SetPeriod
    class Presence(object):
        '''Watchdog presence message'''
        getter = command.Watchdog.GetPresence
        setter = None

    # Deferred attribute handling via Descriptors
    period   = deferred("period")(Period())
    presence = deferred("presence")(Presence())

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = ['period']
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
        

