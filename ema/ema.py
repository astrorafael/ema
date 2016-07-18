# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


#--------------------
# System wide imports
# -------------------

from __future__ import division

import sys
import datetime
import random
from collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted.logger   import Logger, LogLevel
from twisted.internet import task, reactor, defer
from twisted.internet.defer  import inlineCallbacks, returnValue, DeferredList
from twisted.internet.threads import deferToThread

#--------------
# local imports
# -------------

from .config import VERSION_STRING, loadCfgFile
from .logger import setLogLevel

from .service.relopausable import MultiService

#from ..mqtt.service import MQTTService, NAME as MQTT_NAME

from .command        import PERIOD as EMA_PERIOD
from .metadata       import EMARangeError
from .serial         import SerialService, EMATimeoutError
from .scripts        import ScriptsService, AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from .scheduler      import SchedulerService
from .probe          import ProbeService
from .mqttpub        import MQTTService
from .web            import WebService

import command
import device

# ----------------
# Module constants
# ----------------

# Service name
NAME = 'EMA'

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='ema')



class EMAService(MultiService):

    # Service name
    NAME = 'EMA'


    def __init__(self, options, cfgFilePath):
        MultiService.__init__(self)
        self.cfgFilePath = cfgFilePath
        self.options     = options
        self.counter = 0
        self.NSAMPLES = self.options['period'] // EMA_PERIOD
        self.queue       = { 
            'status'  : deque(), 
            'ave5min' : deque(), 
            'minmax'  : deque(),
            'log'     : deque(),
            'register': deque(), 
        }
        setLogLevel(namespace='ema', levelStr=self.options['log_level'])
        

    def reporter(self):
        '''
        Periodic task to log queue size
        '''
        log.info("Readings queue size is {size}", size=len(self.queue['tess_readings']))



    @inlineCallbacks
    def reloadService(self, options):
        '''
        Reload application parameters
        '''
        log.warn("{ema} config being reloaded", ema=VERSION_STRING)
        try:
            options  = yield deferToThread(loadCfgFile, self.cfgFilePath)
        except Exception as e:
            log.error("Error trying to reload: {excp!s}", excp=e)
        else:
            self.options                  = options['ema']
            MultiService.reloadService(self, options)
           
    @inlineCallbacks
    def startService(self):
        '''
        Starts only two services and see if we can continue.
        '''
        log.info('starting {name}', name=self.name)
        self.scriptsService   = self.getServiceNamed(ScriptsService.NAME)
        self.probeService    = self.getServiceNamed(ProbeService.NAME)
        self.serialService    = self.getServiceNamed(SerialService.NAME)
        self.schedulerService = self.getServiceNamed(SchedulerService.NAME)
        self.mqttService      = self.getServiceNamed(MQTTService.NAME)
        self.webService       = self.getServiceNamed(WebService.NAME)
        try:
            self.scriptsService.startService()
            yield defer.maybeDeferred(self.serialService.startService)
            self.buildDevices()
            self.watchdog.start()

        except Exception as e:
            log.failure("{excp}", excp=e)
            log.critical("Problems initializing {name}. Exiting gracefully", name=self.serialService.name)
            reactor.callLater(0,reactor.stop)
        else:
            self.probeService.startService()
            d1 = self.detectEMA(nretries=self.options['nretries'])
            d2 = self.probeService.hasConnectivity()
            dl = DeferredList([d1,d2], consumeErrors=True)
            dl.addCallback(self._maybeExit)
       
       
    
    # -------------
    # MQTT API
    # -------------

    def logMQTTEvent(self, msg, kind='info'):
        '''Logs important evento to MQTT'''
        record = { 'tstamp': datetime.datetime.utcnow(), 'type': kind, 'msg': msg}
        # aqui que el MQTT service le ponga el who
        self.queue['log'].append(record)
       

    # ----------
    # Events API
    # ----------
    def onEventExecute(self, event, *args):
        '''
        Event Handler coming from the Voltmeter
        '''
        self.scriptsService.onEventExecute(event, *args)


    def onStatus(self, status, tstamp):
        '''
        Decimate EMA status message and enqueue
        '''
        if self.counter == 0:
            self.queue['status'].append( (status, tstamp) )
        # Increments with modulo
        self.counter += 1
        # Esto es ilogico, mi capitan pero parece que 
        # se cuela 1 muestra de mas
        self.counter %= self.NSAMPLES-1 
        

    # ----------------
    # Helper functions
    # ----------------


    @inlineCallbacks
    def syncRTCActivity(self, skipInternet = False):
        '''
        Sync RTC activity to be programmed under the scheduler
        '''
        if not skipInternet:
            internet = yield self.probeService.hasConnectivity()
        else:
            internet = True
        if internet and self.options['host_rtc']:
            syncResult = yield self.syncRTC()
        elif internet and not self.options['host_rtc']:
            syncResult = yield self.syncRTC()
        else:
            syncResult = yield self.syncHostRTC()
        returnValue(syncResult)

    @inlineCallbacks
    def _maybeExit(self, results):
        log.debug("results = {results!r}", results=results)
        if results[0][1] == False:
            log.critical("No EMA detected. Exiting gracefully")
            reactor.stop()
            return
        syncResult = yield self.syncRTCActivity(skipInternet = True)
        if not syncResult:
            log.critical("could not sync RTCs. Existing gracefully")
            reactor.stop()
            return
        self.webService.startService()
        self.mqttService.startService()
        self.schedulerService.startService()
        self.addActivities()


    def addActivities(self):
        '''
        Register all activities to the scheduler
        '''

        @inlineCallbacks
        def activityASAP(activeInterval, inactiveInterval):
            '''
            Synchronizes device parameters, then send MQTT registration
            '''
            where = self.schedulerService.findActiveInactive(datetime.datetime.utcnow())
            if where == self.schedulerService.INACTIVE:
                window = inactiveInterval
            else:
                window = activeInterval
            log.debug("At program start ({where} window {w})", where=where, w=window)
            self.logMQTTEvent(msg="At program start ({0} window {1})".format(where, window), kind='info')
            result = yield self.sync()
            if result:
                record = self.getParameters()
                self.queue['register'].append(record)


        @inlineCallbacks
        def activity10(activeInterval, inactiveInterval):
            '''
            Synchronizes device parameters, then send MQTT registration
            '''
            self.logMQTTEvent(msg="At 10% of active time window {0}".format(activeInterval), kind='info')
            result = yield self.sync()
            if result:
                record = self.getParameters()
                self.queue['register'].append(record)

        @inlineCallbacks
        def activity30(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 30% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.getDailyMinMaxDump()
                self.queue['minmax'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity50(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 50% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.get5MinAveragesDump()
                self.queue['ave5min'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')
    
        @inlineCallbacks
        def activity70(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 70% of active time window {0}".format(activeInterval), kind='info')
            try:
                if self.options['relay_shutdown']:
                    yield self.nextRelayCycle(inactiveInterval)
                    yield self.auxRelayTimer(True)
                else:
                    yield self.auxRelayTimer(False)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity90(activeInterval, inactiveInterval):
            self.logMQTTEvent(msg="At 90% of active time window {0}".format(activeInterval), kind='info')
            syncResult = yield self.syncRTC()
            if not syncResult:
                self.logMQTTEvent(msg="EMA RTC could not be synchronized", kind='info')
            if self.options['shutdown']:
                log.warn("EMAd program shutting down gracefully in 10 seconds")
                reactor.callLater(10+random.random(), reactor.stop)
            

        active, inactive = self.schedulerService.findCurrentInterval()
        d = activityASAP(active, inactive)
        self.schedulerService.addActivity(activity10, 10, active, inactive)
        self.schedulerService.addActivity(activity30, 30, active, inactive)
        self.schedulerService.addActivity(activity50, 50, active, inactive)
        self.schedulerService.addActivity(activity70, 70, active, inactive)
        self.schedulerService.addActivity(activity90, 90, active, inactive)

    # --------------------------
    # TEMPORARY Helper functions
    # --------------------------

    def buildDevices(self):
        self.rtc         = device.RealTimeClock(self, self.options['rtc'])
        self.voltmeter   = device.Voltmeter(self, self.options['voltmeter'],
                            upload_period=self.options['upload_period'], 
                            global_sync=self.options['sync'])
        self.anemometer  = device.Anemometer(self, self.options['anemometer'],
                            global_sync=self.options['sync'])
        self.barometer   = device.Barometer(self, self.options['barometer'],
                            global_sync=self.options['sync'])
        self.cloudsensor = device.CloudSensor(self, self.options['cloudsensor'],
                            global_sync=self.options['sync'])
        self.photometer  = device.Photometer(self, self.options['photometer'],
                            global_sync=self.options['sync'])
        self.pluviometer = device.Pluviometer(self, self.options['pluviometer'],
                            global_sync=self.options['sync'])
        self.pyranometer = device.Pyranometer(self, self.options['pyranometer'],
                            global_sync=self.options['sync'])
        self.rainsensor  = device.RainSensor(self, self.options['rainsensor'],
                            global_sync=self.options['sync'])
        self.thermometer = device.Thermometer(self, self.options['thermometer'],
                            global_sync=self.options['sync'])
        self.watchdog    = device.Watchdog(self, self.options['watchdog'],
                            global_sync=self.options['sync'])
        self.aux_relay   = device.AuxiliarRelay(self, self.options['aux_relay'],
                            global_sync=self.options['sync'])
        self.roof_relay  = device.RoofRelay(self, self.options['roof_relay'], global_sync=False)
        self.devices     = [self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.roof_relay]

    @inlineCallbacks
    def detectEMA(self, nretries=3):
        '''
        Returns True if EMA responds
        '''
        try:
            res = yield self.serialService.protocol.send(ema.command.Watchdog.GetPresence(), nretries)
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
                self.logMQTTEvent(msg="Synchronization error", kind="error")
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
        log.debug("PARAMETERS = {p}", p=mydict)
        return mydict
       

    def syncRTC(self):
        return self.rtc.sync()
        

    def syncHostRTC(self):
        return self.rtc.inverseSync()
        
    

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
            return self.aux_relay.mode('Timer/Off')
        

    def getDailyMinMaxDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        cmd = command.GetDailyMinMaxDump()
        return self.serialService.protocol.send(cmd)


    def get5MinAveragesDump(self):
        '''
        Get Daily Min Max accumulated measurements.
        Retuns a Deferred whose success callback returns a complex structure (see README.md).
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        cmd = command.Get5MinAveragesDump()
        return self.serialService.protocol.send(cmd)



    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        self.onEventExecute(event, *args)
    
    
       


        

__all__ = [ "EMAService" ]