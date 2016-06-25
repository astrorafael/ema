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
from twisted.internet.defer       import inlineCallbacks, returnValue


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
            value = yield param['get']()
            param['value'] = value
            configured = self.options[name]
            if not self.paramEquals(value, configured):
                log.warn("{title} values do not match [EMA = {read}] [file = {file}]", title=param['title'], read=value, file=configured)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    param['value'] = yield param['set'](configured)
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
                'get':   self.parent.protocol.getCurrentWindSpeedThreshold,
                'set':   self.parent.protocol.setCurrentWindSpeedThreshold,
            },
            'ave_threshold': { 
                'title' : 'Average Wind Speed Threshold',
                'value' : None,
                'invariant': False,
                'get':   self.parent.protocol.getAverageWindSpeedThreshold,
                'set':   self.parent.protocol.setAverageWindSpeedThreshold
            },
            'calibration': { 
                'title' : 'Calibration Constant',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getAnemometerCalibrationConstant,
                'set':   self.parent.protocol.setAnemometerCalibrationConstant
            },
            'model': { 
                'title' : 'Model',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getAnemometerModel,
                'set':   self.parent.protocol.setAnemometerModel
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
                'get':   self.parent.protocol.getBarometerHeight,
                'set':   self.parent.protocol.setBarometerHeight
            },
            'offset': { 
                'title' : 'Barometer Offset',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getBarometerOffset,
                'set':   self.parent.protocol.setBarometerOffset
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
                'get':   self.parent.protocol.getCloudSensorThreshold,
                'set':   self.parent.protocol.setCloudSensorThreshold
            },
            'gain': { 
                'title' : 'Cloud Sensor Gain',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getCloudSensorGain,
                'set':   self.parent.protocol.setCloudSensorGain
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
                'get':   self.parent.protocol.getPhotometerThreshold,
                'set':   self.parent.protocol.getPhotometerThreshold
            },
            'offset': { 
                'title' : 'Photometer Offset',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getPhotometerOffset,
                'set':   self.parent.protocol.setPhotometerOffset
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
                'get':   self.parent.protocol.getPluviometerCalibration,
                'set':   self.parent.protocol.setPluviometerCalibration
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
                'get':   self.parent.protocol.getPyranometerGain,
                'set':   self.parent.protocol.setPyranometerGain
            },
            'offset': { 
                'title' : 'Pyranometer Offset',
                'value' : True,
                'invariant': True,
                'get':   self.parent.protocol.getPyranometerOffset,
                'set':   self.parent.protocol.setPyranometerOffset
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
                'get':   self.parent.protocol.getRainSensorThreshold,
                'set':   self.parent.protocol.setRainSensorThreshold
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
                'get':   self.parent.protocol.getThermometerDeltaTempThreshold,
                'set':   self.parent.protocol.setThermometerDeltaTempThreshold
            },
        } 


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

__all__ = [
    Anemometer,
    Barometer,
    CloudSensor,
    Photometer,
    Pluviometer,
    Pyranometer,
    RainSensor,
    Thermometer,
    Thermopile,
]