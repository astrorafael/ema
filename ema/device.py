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

log  = Logger(namespace='serial')




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
        for name, param in self.PARAMS.iteritems():
            value = yield self.parent.serialService.protocol.send(param['get']())
            param['value'] = value
            configured = self.options[name]
            if not self.paramEquals(value, configured):
                log.warn("{title} values do not match [EMA = {read}] [file = {file}]", title=param['title'], read=value, file=configured)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    param['value'] = yield self.parent.serialService.protocol.send(param['set'](configured))
            else:
                log.info("{title} already synchronized", title=param['title'])


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
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Current Wind Speed Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.Anemometer.GetCurrentWindSpeedThreshold,
                'set':   command.Anemometer.SetCurrentWindSpeedThreshold,
                'units': metadata.Anemometer.WindSpeedThreshold.units,
                'range': metadata.Anemometer.WindSpeedThreshold.domain,
                'type' : metadata.Anemometer.WindSpeedThreshold.kind,
            },
            'ave_threshold': { 
                'title' : 'Average Wind Speed Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.Anemometer.GetAverageWindSpeedThreshold,
                'set':   command.Anemometer.SetAverageWindSpeedThreshold,
                'units': metadata.Anemometer.WindSpeedThreshold.units,
                'range': metadata.Anemometer.WindSpeedThreshold.domain,
                'type' : metadata.Anemometer.WindSpeedThreshold.kind,
            },
            'calibration': { 
                'title' : 'Calibration Constant',
                'value' : None,
                'invariant': True,
                'get':   command.Anemometer.GetCalibrationFactor,
                'set':   command.Anemometer.SetCalibrationFactor,
                'units': metadata.Anemometer.CalibrationFactor.units,
                'range': metadata.Anemometer.CalibrationFactor.domain,
                'type' : metadata.Anemometer.CalibrationFactor.kind,
            },
            'model': { 
                'title' : 'Model',
                'value' : None,
                'invariant': True,
                'get':   command.Anemometer.GetModel,
                'set':   command.Anemometer.SetModel,
                'units': metadata.Anemometer.Model.units,
                'range': metadata.Anemometer.Model.domain,
                'type' : metadata.Anemometer.Model.kind,
            },
        }

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Barometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'height': { 
                'title' : 'Barometer Height',
                'value' : None,
                'invariant': True,
                'get':   command.Barometer.GetHeight,
                'set':   command.Barometer.SetHeight,
                'units': metadata.Barometer.Height.units,
                'range': metadata.Barometer.Height.domain,
                'type' : metadata.Barometer.Height.kind,
            },
            'offset': { 
                'title' : 'Barometer Offset',
                'value' : None,
                'invariant': True,
                'get':   command.Barometer.GetOffset,
                'set':   command.Barometer.SetOffset,
                'units': metadata.Barometer.Offset.units,
                'range': metadata.Barometer.Offset.domain,
                'type' : metadata.Barometer.Offset.kind,
            },
        }

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class CloudSensor(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Cloud Sensor Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.CloudSensor.GetThreshold,
                'set':   command.CloudSensor.SetThreshold,
                'units': metadata.CloudSensor.Threshold.units,
                'range': metadata.CloudSensor.Threshold.domain,
                'type' : metadata.CloudSensor.Threshold.kind,
            },
            'gain': { 
                'title' : 'Cloud Sensor Gain',
                'value' : None,
                'invariant': True,
                'get':   command.CloudSensor.GetGain,
                'set':   command.CloudSensor.SetGain,
                'units': metadata.CloudSensor.Gain.units,
                'range': metadata.CloudSensor.Gain.domain,
                'type' : metadata.CloudSensor.Gain.kind,
            },
        }   

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Photometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Photometer Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.Photometer.GetThreshold,
                'set':   command.Photometer.SetThreshold,
                'units': metadata.Photometer.Threshold.units,
                'range': metadata.Photometer.Threshold.domain,
                'type' : metadata.Photometer.Threshold.kind,
            },
            'offset': { 
                'title' : 'Photometer Offset',
                'value' : None,
                'invariant': True,
                'get':   command.Photometer.GetOffset,
                'set':   command.Photometer.SetOffset,
                'units': metadata.Photometer.Offset.units,
                'range': metadata.Photometer.Offset.domain,
                'type' : metadata.Photometer.Offset.kind,
            },
        } 


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Pluviometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'calibration': { 
                'title' : 'Pluviometer Calibration',
                'value' : None,
                'invariant': True,
                'get':   command.Pluviometer.GetCalibrationFactor,
                'set':   command.Pluviometer.SetCalibrationFactor,
                'units': metadata.Pluviometer.Factor.units,
                'range': metadata.Pluviometer.Factor.domain,
                'type' : metadata.Pluviometer.Factor.kind,
            },
        } 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


class Pyranometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'gain': { 
                'title' : 'Pyranometer Gain',
                'value' : None,
                'invariant': True,
                'get':   command.Pyranometer.GetGain,
                'set':   command.Pyranometer.SetGain,
                'units': metadata.Pyranometer.Gain.units,
                'range': metadata.Pyranometer.Gain.domain,
                'type' : metadata.Pyranometer.Gain.kind,
            },
            'offset': { 
                'title' : 'Pyranometer Offset',
                'value' : True,
                'invariant': True,
                'get':   command.Pyranometer.GetOffset,
                'set':   command.Pyranometer.SetOffset,
                'units': metadata.Pyranometer.Offset.units,
                'range': metadata.Pyranometer.Offset.domain,
                'type' : metadata.Pyranometer.Offset.kind,
            },
        } 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RainSensor(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Rain Sensor Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.RainSensor.GetThreshold,
                'set':   command.RainSensor.SetThreshold,
                'units': metadata.RainSensor.Threshold.units,
                'range': metadata.RainSensor.Threshold.domain,
                'type' : metadata.RainSensor.Threshold.kind,
            },
        } 

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Thermometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'delta_threshold': { 
                'title' : 'Thermometer Delta Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.Thermometer.GetThreshold,
                'set':   command.Thermometer.SetThreshold,
                'units': metadata.Thermometer.Threshold.units,
                'range': metadata.Thermometer.Threshold.domain,
                'type' : metadata.Thermometer.Threshold.kind,
            },
        } 



# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RoofRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {}
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
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'mode': { 
                'title' : 'Aux Relay Mode',
                'value' : None,
                'invariant': False,
                'get':   command.AuxRelay.GetMode,
                'set':   command.AuxRelay.SetMode,
                'units': metadata.AuxRelay.Mode.units,
                'range': metadata.AuxRelay.Mode.domain,
                'type' : metadata.AuxRelay.Mode.kind,
            },
        } 
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

    def mode(self, value):
        '''
        Program Auxiliar Relay Mode
        Either 'Auto','Open', 'Close', 'Timer/On', 'Timer/Off'
        Returns a deferred
        '''
        return self.parent.serialService.protocol.send(command.AuxRelay.SetMode(value))

    @inlineCallbacks
    def nextRelayCycle(self, inactiveInterval):
        yield self.parent.serialService.protocol.send(
        		command.AuxRelay.SetSwitchOffTime(inactiveInterval.t0.time()))
        yield self.parent.serialService.protocol.send(
        		command.AuxRelay.SetSwitchOnTime(inactiveInterval.t1.time()))

#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class RealTimeClock(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'max_drift': { 
                'title' : 'EMA RTC',
                'value' : None,
                'invariant': False,
                'get':   command.RealTimeClock.GetDateTime,
                'set':   command.RealTimeClock.SetDateTime,
                'units': metadata.RealTimeClock.DateTime.units,
                'range': metadata.RealTimeClock.DateTime.domain,
                'type' : metadata.RealTimeClock.DateTime.kind,
            },
        }

    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes EMA RTC Clock to Host Clock. 
        Returns a deferred whose success callback value is a flag
        True = synch process ok, False = synch process went wrong
        '''
        param     = self.PARAMS['max_drift']
        max_drift = self.options['max_drift']
        log.info("Synchronizing {title} from Host RTC", title=param['title'])
        try:
            value = yield self.parent.serialService.protocol.send(param['get']())
        except EMATimeoutError as e:
            log.error("EMA RTC sync exception => {exception}", exception=e)
            returnValue(False)
        now = datetime.datetime.utcnow()
        if abs((value - now).total_seconds()) > max_drift:
            log.warn("{title} not synchronized [EMA = {EMA!s}] [Host = {host!s}]", title=param['title'], EMA=value, host=now)
            log.info("Synchronizing {title} to Host RTC", title=param['title'])
            try:
                value = yield self.parent.serialService.protocol.send(param['set'](None))
            except EMATimeoutError as e:
                log.error("RTC sync exception => {exception}", exception=e)
                returnValue(False)
            if abs((value - datetime.datetime.utcnow()).total_seconds()) > max_drift:
                log.warn("{title} still not synchronized to Host RTC", title=param['title'])
        else:
            log.info("{title} already synchronized to Host RTC", title=param['title'])
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
            utvalue = yield command.RTCDateTime.Get()
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
            utvalue = yield command.RTCDateTime.Get()
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

    def __init__(self, parent, options, upload_period, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'threshold': { 
                'title' : 'Threshold',
                'value' : None,
                'invariant': False,
                'get':   command.Voltmeter.GetThreshold,
                'set':   command.Voltmeter.SetThreshold,
                'units': metadata.Voltmeter.Threshold.units,
                'range': metadata.Voltmeter.Threshold.domain,
                'type' : metadata.Voltmeter.Threshold.kind,
            },
            'offset': { 
                'title' : 'Offset',
                'option': 'offset',
                'value' : None,
                'invariant': True,
                'get':   command.Voltmeter.GetOffset,
                'set':   command.Voltmeter.SetOffset,
                'units': metadata.Voltmeter.Offset.units,
                'range': metadata.Voltmeter.Offset.domain,
                'type' : metadata.Voltmeter.Offset.kind,
            },
        }
        self.voltage = deque(maxlen=(upload_period//command.PERIOD))
        #scripts = chop(options["script"], ',')
        #for script in scripts:
        #    self.parent.addScript('VoltageLow', script, options['mode'])
        self.parent.serialService.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        self.voltage.append(message[command.POWER_VOLT])
        n       = len(self.voltage)
        average = sum(self.voltage) / n
        if  self.PARAMS['threshold']['value'] is None:
            log.debug("No threshold value yet from EMA")
            return
        threshold = self.options['delta'] + self.PARAMS['threshold']['value']
        if average < threshold:
            self.parent.onEventExecute('low_voltage', average, threshold, n)

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
    
class Watchdog(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {
            'period': { 
                'title' : 'Watchdog Period',
                'value' : None,
                'invariant': False,
                'get':   command.Watchdog.GetPeriod,
                'set':   command.Watchdog.SetPeriod,
                'units': metadata.Watchdog.Period.units,
                'range': metadata.Watchdog.Period.domain,
                'type' : metadata.Watchdog.Period.kind,
            },
        }
        self.pingTask  = task.LoopingCall(self.ping)

    def start(self):
        self.pingTask.start(self.options['period']//2+random.random(), now=False)

    def stop(self):
        self.pingTask.stop()

    @inlineCallbacks
    def ping(self):
        try:
            res = yield self.parent.serialService.protocol.send(command.Watchdog.GetPresence())
        except EMATimeoutError as e:
            pass

