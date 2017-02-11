# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import sys
import datetime
import random
import os
from collections import deque

# ---------------
# Twisted imports
# ---------------

from twisted          import __version__ as __twisted_version__
from twisted.logger   import Logger, LogLevel
from twisted.internet import task, reactor, defer
from twisted.internet.defer  import inlineCallbacks, returnValue, DeferredList
from twisted.internet.threads import deferToThread

#--------------
# local imports
# -------------

from ema import __version__
from ema.config import VERSION_STRING, loadCfgFile
from ema.logger import setLogLevel

from ema.service.reloadable import MultiService

from ema.device         import EMARangeError
from ema.command        import PERIOD as EMA_PERIOD
from ema.serial         import SerialService, EMATimeoutError
from ema.scripts        import ScriptsService, AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from ema.scheduler      import SchedulerService
from ema.probe          import ProbeService
from ema.mqttpub        import MQTTService
from ema.web            import WebService

import ema.command as command
import ema.device  as device

# ----------------
# Module constants
# ----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='ema')

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------    
# -----------------------------------------------------------------------------  

class DumpFilter(object):

    ONE_DAY  = datetime.timedelta(days=1)
    STRFTIME = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, overlap):
        self.overlap      = overlap/100

    def toPage(self, time):
        '''
        Computes the flash page corresponding to a given time.
        To be overriden
        '''
        pass

    def toTime(self, page):
        '''
        Computes the end time coresponding to a given page.
        To be overriden.
        '''
        pass

    def updateCache(self):
      with open(self.PATH,'w') as f:
         f.write(self.today.strftime(self.STRFTIME) + '\n')

    def begin(self):
        log.debug("prepare to filter dump, overlap factor is {overlap}", overlap=self.overlap)
        self.today     = datetime.datetime.utcnow()
        self.yesterday = self.today - self.ONE_DAY
        self.todayPage = self.toPage(self.today.time())
        self.lastDay   = None

        if os.path.isfile(self.PATH):
            with open(self.PATH, 'r') as f:
                self.lastDay  = datetime.datetime.strptime(f.readline()[:-1],
                                                       self.STRFTIME)

        # If unknown of a long time ago, set the last page to the oldest
        # possible page so that we do a full dump
        if not self.lastDay or (self.today - self.lastDay) >= self.ONE_DAY:
            self.lastPage = self.todayPage
            log.debug("lastPage is unknown or very old, setting to {today}", today=self.todayPage)
        else:
            self.lastPage = self.toPage(self.lastDay.time())
            log.debug("lastPage = {lastPage} computed from timestamp in file", lastPage=self.todayPage)


    def filter(self, data):
        '''Filter the result array, taking into account an overlap factor'''
        log.debug("filtering dump")
        self.updateCache()
        distance = (self.lastPage - self.todayPage) % self.NPAGES
        overlap  = int(round(distance * self.overlap))
        lastPage = (self.lastPage - overlap) % self.NPAGES
        log.debug("last page[before]={bef}, [after]={aft} today={tod}", 
            bef=self.lastPage, 
            aft=lastPage, 
            tod=self.todayPage)
        i = lastPage
        j = self.todayPage
        if self.todayPage > lastPage:
            log.debug("Adding results of today only")
            log.debug("Trimminng data to [{i}:{j}] section", i=i, j=j)
            return data[i:j]
        else:
            log.debug("Adding yesterday's and today's results")
            log.debug("Trimminng data to [0:{j}] and [{i}:-] section", j=j, i=i)
            subset1 = data[0:j]
            subset2 = data[i:]
            return subset1 + subset2

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------    
# -----------------------------------------------------------------------------  

class MinMaxDumpFilter(DumpFilter):

    PATH   = '/var/cache/ema/his1h.txt'
    NPAGES = 24


    def toPage(self, time):
        '''Computes the flash page corresponding to a given time'''
        return time.hour


    def toTime(self, page):
        '''Compues the end time coresponding to a given page'''
        return datetime.time(hour=page)

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------    
# -----------------------------------------------------------------------------  

class Average5MinDumpFilter(DumpFilter):
  
    PATH = '/var/cache/ema/his5min.txt'
    NPAGES = 288


    def toPage(self, time):
        '''Computes the flash page corresponding to a given time'''
        return (time.hour*60 + time.minute)//5


    def toTime(self, page):
        '''Computes the end time coresponding to a given page'''
        minutes = page*5 + 5
        hour = (minutes//60) % 24
        return datetime.time(hour=hour, minute=minutes%60)


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------    
# -----------------------------------------------------------------------------    

class EMAService(MultiService):

    # Service name
    NAME = 'EMA'
    # Queue names, by priority
    QNAMES = ['register','log','status', 'minmax', 'ave5min' ]
    # Queue sizes
    QSIZES = [ 10, 1000, 10, 10*24*60, 10*24*60]


    def __init__(self, options, cfgFilePath):
        MultiService.__init__(self)
        setLogLevel(namespace='ema', levelStr=options['log_level'])
        self.cfgFilePath = cfgFilePath
        self.options     = options
        self.samplingCounter = 0
        self.NSAMPLES    = self.options['period'] // EMA_PERIOD
        self.queue       = { 
            'status'  : deque(), 
            'ave5min' : deque(), 
            'minmax'  : deque(),
            'log'     : deque(),
            'register': deque(), 
        }
        self.devices       = []
        self.minmaxFilter  = MinMaxDumpFilter(options['overlap'])
        self.averageFilter = Average5MinDumpFilter(options['overlap'])
        

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
        log.info('starting {name} {version} using Twisted {tw_version}', 
            name=self.name,
            version=__version__, 
            tw_version=__twisted_version__)
        self.scriptsService   = self.getServiceNamed(ScriptsService.NAME)
        self.probeService     = self.getServiceNamed(ProbeService.NAME)
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
            log.failure("{excp!s}", excp=e)
            log.critical("Problems initializing {name}. Exiting gracefully", name=self.serialService.name)
            reactor.callLater(0,reactor.stop)
        else:
            self.probeService.startService()
            d1 = self.detectEMA(nretries=self.options['nretries'])
            d2 = self.probeService.hasConnectivity()
            dl = DeferredList([d1,d2], consumeErrors=True)
            dl.addCallback(self._maybeExit)
       

    def buildDevices(self):
        '''
        Build the virtual devices as soon as the service is started
        ''' 
        self.rtc         = device.RealTimeClock(self, self.options['rtc'])
        self.voltmeter   = device.Voltmeter(self, self.options['voltmeter'],
                            upload_period=self.options['period'])
        self.anemometer  = device.Anemometer(self, self.options['anemometer'])
        self.barometer   = device.Barometer(self, self.options['barometer'])
        self.cloudsensor = device.CloudSensor(self, self.options['cloudsensor'])
        self.photometer  = device.Photometer(self, self.options['photometer'])
        self.pluviometer = device.Pluviometer(self, self.options['pluviometer'])
        self.pyranometer = device.Pyranometer(self, self.options['pyranometer'])
        self.rainsensor  = device.RainSensor(self, self.options['rainsensor'])
        self.thermometer = device.Thermometer(self, self.options['thermometer'])
        self.watchdog    = device.Watchdog(self, self.options['watchdog'])
        self.aux_relay   = device.AuxiliarRelay(self, self.options['aux_relay'])
        self.roof_relay  = device.RoofRelay(self, self.options['roof_relay'])
        self.devices     = [self.voltmeter, self.anemometer, self.barometer, self.cloudsensor,
                            self.photometer,self.pluviometer,self.pyranometer,self.rainsensor,
                            self.watchdog, self.aux_relay, self.roof_relay]       
    
    # ----------------
    # Dispatching APIs
    # ----------------

    def logMQTTEvent(self, msg, kind='info'):
        '''Logs important evento to MQTT'''
        record = { 'tstamp': datetime.datetime.utcnow(), 'type': kind, 'msg': msg}
        # aqui que el MQTT service le ponga el who
        self.queue['log'].append(record)
       

    def onEventExecute(self, event, *args):
        '''
        Event Handler coming from the Voltmeter
        '''
        self.scriptsService.onEventExecute(event, *args)


    def onStatus(self, status, tstamp):
        '''
        Decimate EMA status message and enqueue
        '''
        if self.samplingCounter == 0:
            self.queue['status'].append( (status, tstamp) )
        # Increments with modulo
        self.samplingCounter += 1
        # Esto es ilogico, mi capitan pero parece que 
        # se cuela 1 muestra de mas
        self.samplingCounter %= self.NSAMPLES-1 
        

    def gotProtocol(self, protocol):
        '''
        Called from serial service as soon as it gets a new protocol.
        '''
        device.Attribute.bind(protocol)


    def addStatusCallback(self, callback):
        '''
        Register other services/components interest in EMA status messages
        '''
        self.serialService.protocol.addStatusCallback(callback)
    

    
    # --------------------
    # Scheduler Activities
    # --------------------

    @inlineCallbacks
    def getDailyMinMaxDump(self):
        self.minmaxFilter.begin()
        cmd  = command.GetDailyMinMaxDump()
        dump = yield self.serialService.protocol.execute(cmd)
        dump = self.minmaxFilter.filter(dump)
        returnValue(dump)

    @inlineCallbacks
    def get5MinAveragesDump(self):
        self.averageFilter.begin()
        cmd  = command.Get5MinAveragesDump()
        dump = yield self.serialService.protocol.execute(cmd)
        dump = self.averageFilter.filter(dump)
        returnValue(dump)


    @inlineCallbacks
    def syncRTCActivity(self, skipInternet = False):
        '''
        Sync RTC activity to be programmed under the scheduler.
        '''
        if not skipInternet:
            internet = yield self.probeService.hasConnectivity()
        else:
            internet = True

        if not internet and not self.options['host_rtc']:
            syncResult = yield self.rtc.inverseSync()
        else:
            syncResult = yield self.rtc.sync()

        returnValue(syncResult)


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
            log.info("Starting a cycle in {where} window {w})", where=where, w=window)
            self.logMQTTEvent(msg="Starting a cycle in {0} window {1}".format(where, window), 
                kind='info')
            result = yield self.sync()
            if result:
                record = yield self.getParameters()
                self.queue['register'].append(record)


        @inlineCallbacks
        def activity10(activeInterval, inactiveInterval):
            '''
            Synchronizes device parameters, then send MQTT registration
            '''
            log.info("At 10% of active time window {w}",w=activeInterval)
            self.logMQTTEvent(msg="At 10% of active time window {0}".format(activeInterval), 
                kind='info')
            result = yield self.sync()
            if result:
                record = yield self.getParameters()
                self.queue['register'].append(record)

        @inlineCallbacks
        def activity30(activeInterval, inactiveInterval):
            log.info("At 10% of active time window {w}",w=activeInterval)
            self.logMQTTEvent(msg="At 30% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.getDailyMinMaxDump()
                self.queue['minmax'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity50(activeInterval, inactiveInterval):
            log.info("At 50% of active time window {w}",w=activeInterval)
            self.logMQTTEvent(msg="At 50% of active time window {0}".format(activeInterval), kind='info')
            try:
                dump = yield self.get5MinAveragesDump()
                self.queue['ave5min'].append(dump)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')
    
        @inlineCallbacks
        def activity70(activeInterval, inactiveInterval):
            log.info("At 70% of active time window {w}",w=activeInterval)
            self.logMQTTEvent(msg="At 70% of active time window {0}".format(activeInterval), kind='info')
            try:
                aux_mode = yield self.aux_relay.mode
                if aux_mode == 'Timer/On':
                    yield self.aux_relay.nextRelayCycle(inactiveInterval)
            except Exception as e:
                self.logMQTTEvent(msg=str(e), kind='error')

        @inlineCallbacks
        def activity90(activeInterval, inactiveInterval):
            log.info("At 90% of active time window {w}",w=activeInterval)
            self.logMQTTEvent(msg="At 90% of active time window {0}".format(activeInterval), kind='info')
            syncResult = yield self.rtc.sync()
            if not syncResult:
                self.logMQTTEvent(msg="EMA RTC could not be synchronized", kind='info')
            aux_mode = yield self.aux_relay.mode
            if aux_mode == 'Timer/On' and self.options['shutdown']:
                log.warn("EMAd program shutting down gracefully in 10 seconds")
                reactor.callLater(10+random.random(), reactor.stop)
            

        active, inactive = self.schedulerService.findCurrentInterval()
        d = activityASAP(active, inactive)
        self.schedulerService.addActivity(activity10, 10, active, inactive)
        self.schedulerService.addActivity(activity30, 30, active, inactive)
        self.schedulerService.addActivity(activity50, 50, active, inactive)
        self.schedulerService.addActivity(activity70, 70, active, inactive)
        self.schedulerService.addActivity(activity90, 90, active, inactive)

    
  


    # ----------------------
    # Other Helper functions
    # ----------------------

    @inlineCallbacks
    def _maybeExit(self, results):
        '''
        Starts all services or exit gracefully on either these two conditions:
        1) No EMA has been detected
        2) No RTC synchronization took place
        '''
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


    def detectEMA(self, nretries=3):
        '''
        Returns a deferred with True if detected, false otherwise
        '''
        def noEma(failure):
            return False
        cmd = command.Watchdog.GetPresence()
        d = self.serialService.protocol.execute(cmd, nretries)
        d.addErrback(noEma)
        return d


    @inlineCallbacks
    def sync(self):
        '''
        Devices synchronization.
        Cannot send EMA MQTT registration until not sucessfully synchronized
        '''
        ok = True
        for dev in self.devices:
            try:
                yield dev.sync()
            except (EMARangeError, EMATimeoutError) as e:
                log.error("Synchronization error => {error}", error=e)
                self.logMQTTEvent(msg="Synchronization error", kind="error")
                ok = False
                break
        returnValue(ok)


    @inlineCallbacks
    def getParameters(self):
        '''
        Get all parameters once al devices synchronized
        '''
        with open("/sys/class/net/eth0/address",'r') as fd:
            mac = fd.readline().rstrip('\r\n')
        mydict = { 'mac': mac }
        for dev in self.devices:
            anotherDict = yield dev.parameters()
            mydict.update(anotherDict)
        log.debug("PARAMETERS = {p}", p=mydict)
        returnValue(mydict)
       

   
       


        

__all__ = [ "EMAService" ]