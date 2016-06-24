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
                log.warn("{title} [read = {read}] [file = {file}]", title=param['title'], read=value, file=configured)
                if self.options['sync'] and self.global_sync:
                    log.info("Synchronizing {title}", title=param['title'])
                    yield param['set'](configured)

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



class CloudDetector(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    


class Photometer(Device):
    def __init__(self, parent, options, global_sync=True):
        pass   


class Pluviometer(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    


class Pyranometer(Device):
    def __init__(self, parent, options, global_sync=True):
        pass   


class RainDetector(Device):
    def __init__(self, parent, options, global_sync=True):
        pass


class RealTimeClock(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    


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
        pass


class RoofRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        pass  


class AuxiliarRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        pass    

__all__ = [
    Anemometer,
    Barometer,
    CloudDetector,
    Photometer,
    Pluviometer,
    Pyranometer,
    RainDetector,
    RealTimeClock,
    Thermopile,
    Voltmeter,
    Watchdog,
    RoofRelay,
    AuxiliarRelay,
]