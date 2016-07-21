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

class Metadata(object):
    '''Marker class for all metadata'''
    pass

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


class RealTimeClock(object):
    '''Namespace for children metadata'''

    class DateTime(Metadata):
        '''Real Time Clock Date & Time'''
        kind            = datetime.datetime 
        domain          = [datetime.datetime(2016, 1, 1), datetime.datetime(2100, 12, 31)]
        units           = 'ISO 8601'
        volatile        = True   # Must not be cached in memory
        stable          = False  # if mutable, never stable

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Watchdog(object):
    '''Namespace for children metadata'''

    class Presence(Metadata):
        '''EMA Presence'''
        kind         = str
        domain       = [ '( )' ]
        units        = ''
        volatile     = True     # Must not be cached in memory
       

    class Period(Metadata):
        '''Watchdog Period'''
        kind         = int
        domain       = [0, 999]
        units        = 'sec'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # if mutable, never stable
   
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Anemometer(object):
    '''Namespace for children metadata'''

    class WindSpeedThreshold(Metadata):
        '''Wind Speed Threshold'''
        kind         = int
        domain       = [0, 999]
        units        = 'Km/h'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  
       

    class CalibrationFactor(Metadata):
        '''Anemometer Calibration Constant'''
        kind         = int
        domain       = [0, 999]
        units        = 'Km/h (TX20) or mm (Simple)'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True   # stable parameter: only changed after a recalibration
   

    class Model(Metadata):
        '''Anemometer Model'''
        kind         = str
        domain       = ['TX20', 'Simple']
        units        = ''
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration
     
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Barometer(object):
    '''Namespace for children metadata'''

    class Height(Metadata):
        '''Barometer Height'''
        kind         = int
        domain       = [0, 99999]
        units        = 'm'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration


    class Offset(Metadata):
        '''Barometer Offset'''
        kind         = int
        domain       = [-99, 99]
        units        = 'mBar'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class CloudSensor(object):
    '''Namespace for children metadata'''

    class Threshold(Metadata):
        '''Cloud Sensor Threshold'''
        kind         = int
        domain       = [0, 100]
        units        = '%'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  
      
    class Gain(Metadata):
        '''Cloud Sensor Gain'''
        kind         = float
        domain       = [0.0, 99.9]
        units        = '?'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True   # stable parameter: only changed after a recalibration
   
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Photometer(object):
    '''Namespace for children metadata'''

    class Threshold(Metadata):
        '''Photometer Threshold'''
        kind         = float
        domain       = [0.0, 99.9]
        units        = 'Mv/arcsec^2'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  

       
    class Offset(Metadata):
        '''Photometer Gain Offset'''
        kind         = float
        domain       = [-99.9, +99.9]
        units        = 'Mv/arcsec^2'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True   # stable parameter: only changed after a recalibration

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Pluviometer(object):
    '''Namespace for children metadata'''

    class Factor(Metadata):
        '''Pluviometer Calibration Factor'''
        kind         = int
        domain       = [0, 999]
        units        = 'mm'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True   # stable parameter: only changed after a recalibration


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Pyranometer(object):
    '''Namespace for children metadata'''

    class Gain(Metadata):
        '''Pyranometer Gain'''
        kind         = float
        domain       = [0.0, 99.9]
        units        = '?'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration


    class Offset(Metadata):
        '''Pyranometer Offset'''
        kind         = int
        domain       = [0, 999]
        units        = '?'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class RainSensor(object):
    '''Namespace for children metadata'''

    class Threshold(Metadata):
        '''Rain Sensor Threshold'''
        kind         = int
        domain       = [0, 999]
        units        = 'mm'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Thermometer(object):
    '''Namespace for children metadata'''

    class Threshold(Metadata):
        '''Thermometer Delta Temperature Threshold'''
        kind         = int
        domain       = [0, 999]
        units        = 'deg C'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  
  
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Voltmeter(object):
    '''Namespace for children metadata'''

    class Threshold(Metadata):
        '''Voltmeter Threshold'''
        kind         = float
        domain       = [0.0, 25.5]
        units        = 'V'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  


    class Offset(Metadata):
        '''Voltmeter Offset'''
        kind         = float
        domain       = [-99.9, +99.9]
        units        = 'V'
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class RoofRelay(object):
    '''Namespace for children metadata'''

    class Mode(Metadata):
        '''Set Roof Relay Mode'''
        kind         = str
        domain       = ['Auto', 'Closed', 'Open']
        units        = ''
        volatile     = False  # may be cached in memory for efficiency
        stable       = True  # stable parameter: only changed after a recalibration

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class AuxiliarRelay(object):
    '''Namespace for children metadata'''

    class Mode(Metadata):
        '''Auxiliar Relay Mode'''
        kind         = str
        domain       = ['Auto', 'Closed', 'Open', 'Timer/Off', 'Timer/On']
        units        = ''
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  


    class Time(Metadata):
        '''Auxiliar Relay Switch-On Time'''
        kind         = datetime.time
        domain       = [datetime.time(0,0), datetime.time(23,59)]
        units        = 'HH:MM:SS'
        volatile     = False  # may be cached in memory for efficiency
        stable       = False  # not subject to recalibration, may be changed at will  
       

__all__ = [
    "RealTimeClock.DateTime",
    "Watchdog.Presence",
    "Watchdog.Period",
    "Anemometer.WindSpeedThreshold",
    "Anemometer.CalibrationFactor",
    "Anemometer.Model",
    "Barometer.Height",
    "Barometer.Offset",
    "CloudSensor.Threshold",
    "CloudSensor.Gain",
    "Photometer.Threshold",
    "Photometer.Offset",
    "Pluviometer.Factor",
    "Pyranometer.Gain",
    "Pyranometer.Offset",
    "RainSensor.Threshold",
    "Thermometer.Threshold",
    "Voltmeter.Offset",
    "Voltmeter.Threshold",
    "RoofRelay.Mode",
    "AuxiliarRelay.Mode",
    "AuxiliarRelay.SwitchOnTime",
    "AuxiliarRelay.SwitchOffTime",
]