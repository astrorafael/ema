# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

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

from zope.interface import implementer

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task, defer
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.serialport  import SerialPort
from twisted.application.service  import Service
from twisted.application.internet import ClientService
from twisted.internet.endpoints   import clientFromString


#--------------
# local imports
# -------------

from .service.interfaces import IReloadable, IPausable
from .logger   import setLogLevel
from .utils    import chop,  setSystemTime
from .protocol import EMAProtocol, EMAProtocolFactory, EMARangeError, EMAReturnError, EMATimeoutError
from .protocol import ROOF_RELAY, AUX_RELAY, POWER_VOLT, PERIOD as EMA_PERIOD

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

class RoofRelay(Device):
    def __init__(self, parent, options, global_sync=True):
        Device.__init__(self, parent, options, global_sync)
        self.PARAMS = {}
        self.switchon = deque(maxlen=2)
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[ROOF_RELAY]
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
                'get':   self.parent.protocol.getAuxRelayMode,
                'set':   self.parent.protocol.setAuxRelayMode
            },
        } 
        self.switchon = deque(maxlen=2)
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        code = message[AUX_RELAY]
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
        return self.parent.protocol.setAuxRelayMode(value)

    @inlineCallbacks
    def nextRelayCycle(self, inactiveInterval):
        yield self.parent.protocol.setAuxRelaySwitchOffTime(inactiveInterval.t0.time())
        yield self.parent.protocol.setAuxRelaySwitchOnTime(inactiveInterval.t1.time())

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
                'get':   self.parent.protocol.getRTCDateTime,
                'set':   self.parent.protocol.setRTCDateTime
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
            value = yield param['get']()
        except EMATimeoutError as e:
            log.error("EMA RTC sync exception => {exception}", exception=e)
            returnValue(False)
        now = datetime.datetime.utcnow()
        if abs((value - now).total_seconds()) > max_drift:
            log.warn("{title} not synchronized [EMA = {EMA!s}] [Host = {host!s}]", title=param['title'], EMA=value, host=now)
            log.info("Synchronizing {title} to Host RTC", title=param['title'])
            try:
                value = yield param['set'](None)
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
            utvalue = yield self.parent.protocol.getRTCDateTime()
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
            utvalue = yield self.parent.protocol.getRTCDateTime()
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
                'get':   self.parent.protocol.getVoltmeterThreshold,
                'set':   self.parent.protocol.setVoltmeterThreshold
            },
            'offset': { 
                'title' : 'Offset',
                'option': 'offset',
                'value' : None,
                'invariant': True,
                'get':   self.parent.protocol.getVoltmeterOffset,
                'set':   self.parent.protocol.setVoltmeterOffset
            },
        }
        self.voltage = deque(maxlen=(upload_period//EMA_PERIOD))
        #scripts = chop(options["script"], ',')
        #for script in scripts:
        #    self.parent.addScript('VoltageLow', script, options['mode'])
        self.parent.protocol.addStatusCallback(self.onStatus)


    def onStatus(self, message, timestamp):
        '''
        EMA status message handler
        '''
        self.voltage.append(message[POWER_VOLT])
        n       = len(self.voltage)
        average = sum(self.voltage) / n
        if  self.PARAMS['threshold']['value'] is None:
            log.debug("No thershold value yet from EMA")
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
                'get':   self.parent.protocol.getWatchdogPeriod,
                'set':   self.parent.protocol.setWatchdogPeriod
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
            res = yield self.parent.protocol.ping()
        except EMATimeoutError as e:
            pass


#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

@implementer(IPausable, IReloadable)
class SerialService(ClientService):

    # Service name
    NAME = 'Serial Service'


    def __init__(self, options):
        self.options    = options    
        protocol_level  = 'debug' if self.options['log_messages'] else 'info'
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        setLogLevel(namespace='serial', levelStr=self.options['log_level'])
        setLogLevel(namespace='ema.serial.protocol.base.EMAProtocolFactory', levelStr='error')
        self.factory   = EMAProtocolFactory()
        self.serport   = None
        self.protocol  = None
        self.vmag      = None
        self.devices   = []
        self.goSerial  = self._decide()


    def _decide(self):
        '''Decide which endpoint must be built, either TCP or Serial'''

        def backoffPolicy(initialDelay=4.0, maxDelay=60.0, factor=2):
            '''Custom made backoff policy to exit after a number of reconnection attempts'''
            def policy(attempt):
                delay = min(initialDelay * (factor ** attempt), maxDelay)
                if attempt > 3:
                    self.stopService()
                return delay
            return policy


        parts = chop(self.options['endpoint'], sep=':')
        if parts[0] == 'serial':
            self.endpoint = parts[1:]
            Service.__init__(self)
            return True
        else:
            self.endpoint = clientFromString(reactor, self.options['endpoint'])
            ClientService.__init__(self, self.endpoint, self.factory, retryPolicy=backoffPolicy())
            return False

    
    def startService(self):
        '''
        Starts the Serial Service that takls to EMA
        By exception, this returns a deferred that is handled by emaservice
        '''
        log.info("starting Serial Service")
        if self.goSerial:
            Service.startService(self)
            if self.serport is None:
                self.protocol = self.factory.buildProtocol(0)
                self.serport  = SerialPort(self.protocol, self.endpoint[0], reactor, baudrate=self.endpoint[1])
            self.gotProtocol(self.protocol)
        else:
            ClientService.startService(self)
            d = self.whenConnected()
            d.addCallback(self.gotProtocol)
            return d
            

    def _buildDevices(self):
        self.rtc         = RealTimeClock(self, self.options['rtc'])
        self.voltmeter   = Voltmeter(self, self.options['voltmeter'],
                            upload_period=self.options['upload_period'], 
                            global_sync=self.options['sync'])
        self.anemometer  = Anemometer(self, self.options['anemometer'],
                            global_sync=self.options['sync'])
        self.barometer   = Barometer(self, self.options['barometer'],
                            global_sync=self.options['sync'])
        self.cloudsensor = CloudSensor(self, self.options['cloudsensor'],
                            global_sync=self.options['sync'])
        self.photometer  = Photometer(self, self.options['photometer'],
                            global_sync=self.options['sync'])
        self.pluviometer = Pluviometer(self, self.options['pluviometer'],
                            global_sync=self.options['sync'])
        self.pyranometer = Pyranometer(self, self.options['pyranometer'],
                            global_sync=self.options['sync'])
        self.rainsensor  = RainSensor(self, self.options['rainsensor'],
                            global_sync=self.options['sync'])
        self.thermometer = Thermometer(self, self.options['thermometer'],
                            global_sync=self.options['sync'])
        self.watchdog    = Watchdog(self, self.options['watchdog'],
                            global_sync=self.options['sync'])
        self.aux_relay   = AuxiliarRelay(self, self.options['aux_relay'],
                            global_sync=self.options['sync'])
        self.roof_relay  = RoofRelay(self, self.options['roof_relay'], global_sync=False)
        self.devices     = [self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.roof_relay]


    def gotProtocol(self, protocol):
        log.debug("got Protocol")
        self.protocol  = protocol
        self.protocol.addStatusCallback(self.onStatus)
        self.protocol.addPhotometerCallback(self.onVisualMagnitude)
        self._buildDevices()
        self.watchdog.start()


    def onVisualMagnitude(self, vmag, tstamp):
        '''Records last visual magnitude update'''
        self.vmag = vmag


    def onStatus(self, status, tstamp):
        '''
        Adds last visual magnitude estimate
        and pass it upwards
        '''
        if self.vmag:
            status['mag'] = self.vmag
        self.parent.onStatusReceived(status, tstamp)

        
    @inlineCallbacks
    def detectEMA(self, nretries=3):
        '''
        Returns True if EMA responds
        '''
        try:
            res = yield self.protocol.ping(nretries)
        except EMATimeoutError as e:
            returnValue(False)
        else:
            returnValue(True)

    @inlineCallbacks
    def sync(self):
        '''
        Devices synchronization.
        Cannot send EMA MQTT registration until not sucessfully synchronized
        '''
        ok = True
        for device in self.devices:
            try:
                yield device.sync()
            except (EMARangeError, EMATimeoutError) as e:
                log.error("Synchronization error => {error}", error=e)
                self.parent.logMQTTEvent(msg="Synchronization error", kind="error")
                ok = False
                break
        returnValue(ok)


    def getParameters(self):
        '''
        Get all parameters once al devices synchronized
        '''
        with open("/sys/class/net/eth0/address",'r') as fd:
            mac = fd.readline().rstrip('\r\n')
        mydict = { 'mac': mac }
        for device in self.devices:
            mydict.update(device.parameters())
        log.info("PARAMETERS = {p}", p=mydict)
        return mydict
       

    def syncRTC(self):
        return self.rtc.sync()
        

    def syncHostRTC(self):
        return self.rtc.inverseSync()
        

    @inlineCallbacks
    def stopService(self):
        if not self.goSerial:
            try:
                yield ClientService.stopService(self)
            except Exception as e:
                log.error("Exception {excp!s}", excp=e)
                raise 
        else:
            Service.stopService(self)

    def nextRelayCycle(self, inactiveI):
        '''
        Program next auxiliar relay switch on/off cycle
        Returns a Deferred with Noneas value
        '''
        return self.aux_relay.nextRelayCycle(inactiveT)


    def auxRelayTimer(self, flag):
        '''
        Activates/Deactivates Auxiliar timer mode
        Returns a Deferred 
        '''
        if flag:
            return self.aux_relay.mode('Timer/On')
        else:
            return self.aux_relay.mode('Timer/On')
        

    def getDailyMinMaxDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self.protocol.getDailyMinMaxDump()


    def get5MinAveragesDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        return self.protocol.getDailyMinMaxDump()


    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['serial']
        protocol_level  = 'debug' if options['log_messages'] else 'info'
        setLogLevel(namespace='serial', levelStr=options['log_level'])
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        log.info("new log level is {lvl}", lvl=options['log_level'])
        self.options = options
        
    # -------------
    # EMA API
    # -------------



    # ----------
    # Events API
    # ----------

    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        self.parent.onEventExecute(event, *args)
    
    # --------------
    # Helper methods
    # ---------------
   
  
    def onPublish(self):
        '''
        Serial message Handler
        '''
        pass


__all__ = [
    "Watchdog",
    "Voltmeter",
    "RealTimeClock",
    "RoofRelay",
    "AuxiliarRelay",
    "Anemometer",
    "Barometer",
    "CloudSensor",
    "Photometer",
    "Pluviometer",
    "Pyranometer",
    "RainSensor",
    "Thermometer",
    "Thermopile",
    "SerialService",
]