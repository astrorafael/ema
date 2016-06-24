# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import os
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks


#--------------
# local imports
# -------------

from ..logger   import setLogLevel
from .protocol  import EMAProtocol, EMAProtocolFactory, EMARangeError, EMAReturnError, EMATimeoutError


# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')


class Device(object):
    def __init__(self, parent, options, global_sync):
        self.options     = options
        self.parent      = parent
        self.global_sync = global_sync
        self.PARAMS      = []

    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes parameters. 
        Returns a deferred
        '''
        for param in self.PARAMS:
            value = yield param['get']()
            configured = self.options[param['option']]
            if value != configured:
                log.warn("{title} not synchronized [read = {read}] [file = {file}]", title=param['title'], read=value, file=configured)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    yield param['set'](configured)
            else:
                log.info("{title} already synchronized", title=param['title'])
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Anemometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Current Wind Speed Threshold',
                'option': 'threshold',
                'get':   self.parent.protocol.getCurrentWindSpeedThreshold,
                'set':   self.parent.protocol.setCurrentWindSpeedThreshold
            },
            { 
                'title' : 'Average Wind Speed Threshold',
                'option': 'ave_threshold',
                'get':   self.parent.protocol.getAverageWindSpeedThreshold,
                'set':   self.parent.protocol.setAverageWindSpeedThreshold
            },
            { 
                'title' : 'Calibration Constant',
                'option': 'calibration',
                'get':   self.parent.protocol.getAnemometerCalibrationConstant,
                'set':   self.parent.protocol.setAnemometerCalibrationConstant
            },
            { 
                'title' : 'Model',
                'option': 'model',
                'get':   self.parent.protocol.getAnemometerModel,
                'set':   self.parent.protocol.setAnemometerModel
            },
        ]


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Barometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Barometer Height',
                'option': 'height',
                'get':   self.parent.protocol.getBarometerHeight,
                'set':   self.parent.protocol.setBarometerHeight
            },
            { 
                'title' : 'Barometer Offset',
                'option': 'offset',
                'get':   self.parent.protocol.getBarometerOffset,
                'set':   self.parent.protocol.setBarometerOffset
            },
        ]



class CloudSensor(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Cloud Sensor Threshold',
                'option': 'threshold',
                'get':   self.parent.protocol.getCloudSensorThreshold,
                'set':   self.parent.protocol.setCloudSensorThreshold
            },
            { 
                'title' : 'Cloud Sensor Gain',
                'option': 'gain',
                'get':   self.parent.protocol.getCloudSensorGain,
                'set':   self.parent.protocol.setCloudSensorGain
            },
        ]    


class Photometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Photometer Threshold',
                'option': 'threshold',
                'get':   self.parent.protocol.getPhotometerThreshold,
                'set':   self.parent.protocol.getPhotometerThreshold
            },
            { 
                'title' : 'Photometer Offset',
                'option': 'offset',
                'get':   self.parent.protocol.getPhotometerOffset,
                'set':   self.parent.protocol.setPhotometerOffset
            },
        ] 


class Pluviometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Pluviometer Calibration',
                'option': 'calibration',
                'get':   self.parent.protocol.getPluviometerCalibration,
                'set':   self.parent.protocol.setPluviometerCalibration
            },
        ] 

class Pyranometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Pyranometer Gain',
                'option': 'gain',
                'get':   self.parent.protocol.getPyranometerGain,
                'set':   self.parent.protocol.setPyranometerGain
            },
            { 
                'title' : 'Pyranometer Offset',
                'option': 'offset',
                'get':   self.parent.protocol.getPyranometerOffset,
                'set':   self.parent.protocol.setPyranometerOffset
            },
        ] 


class RainSensor(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Rain Sensor Threshold',
                'option': 'threshold',
                'get':   self.parent.protocol.getRainSensorThreshold,
                'set':   self.parent.protocol.setRainSensorThreshold
            },
        ] 


class RealTimeClock(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'RTC',
                'option': 'max_drift',
                'get':   self.parent.protocol.getRTCDateTime,
                'set':   self.parent.protocol.setRTCDateTime
            },
        ]

    @inlineCallbacks
    def sync(self):
        '''
        Synchronizes parameters. 
        Returns a deferred
        '''
        param = self.PARAMS[0]
        max_drift = self.options[param['option']]
        value = yield param['get']()
        now = datetime.datetime.utcnow()
        if abs((value - now).total_seconds()) > max_drift:
                log.warn("{title} not synchronized [EMA = {EMA!s}] [Host = {host!s}]", title=param['title'], EMA=value, host=now)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    value = yield param['set'](None)
                    if abs((value - datetime.datetime.utcnow()).total_seconds()) > max_drift:
                        log.warn("{title} still not synchronized", title=param['title'])
        else:
            log.info("{title} already synchronized", title=param['title'])


class Thermometer(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Thermometer Delta Threshold',
                'option': 'delta_threshold',
                'get':   self.parent.protocol.getThermometerDeltaTempThreshold,
                'set':   self.parent.protocol.setThermometerDeltaTempThreshold
            },
        ] 

class Thermopile(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class Voltmeter(Device):

    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Threshold',
                'option': 'threshold',
                'get':   self.parent.protocol.getVoltmeterThreshold,
                'set':   self.parent.protocol.setVoltmeterThreshold
            },
            { 
                'title' : 'Offset',
                'option': 'offset',
                'get':   self.parent.protocol.getVoltmeterOffset,
                'set':   self.parent.protocol.setVoltmeterOffset
            },
        ]

    
    
class Watchdog(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = [
            { 
                'title' : 'Watchdog Period',
                'option': 'period',
                'get':   self.parent.protocol.getWatchdogPeriod,
                'set':   self.parent.protocol.setWatchdogPeriod
            },
        ] 

class RoofRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        pass  


class AuxiliarRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    

__all__ = [
    Anemometer,
    Barometer,
    CloudSensor,
    Photometer,
    Pluviometer,
    Pyranometer,
    RainSensor,
    RealTimeClock,
    Thermometer,
    Thermopile,
    Voltmeter,
    Watchdog,
    RoofRelay,
    AuxiliarRelay,
]