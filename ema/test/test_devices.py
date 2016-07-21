# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------

from __future__ import division, absolute_import


#--------------------
# System wide imports
# -------------------

import datetime

# ---------------
# Twisted imports
# ---------------

from twisted.trial    import unittest
from twisted.test     import proto_helpers
from twisted.internet import task, error
from twisted.logger   import Logger, LogLevel
from twisted.internet.defer import inlineCallbacks


#--------------
# local imports
# -------------

import ema.device as device

from ema.serial   import EMAProtocol, EMAProtocolFactory
from ema.logger   import setLogLevel



# self.options['voltmeter'] = {}
# self.options['voltmeter']['sync']            = False
# self.options['voltmeter']['offset']          = 0.0
# self.options['voltmeter']['threshold']       = 11.8
# self.options['voltmeter']['delta']           = 0.2










# self.options['thermometer'] = {}
# self.options['thermometer']['sync']            = 
# self.options['thermometer']['threshold']      = 


# self.options['rtc'] = {}
# self.options['rtc']['max_drift']          = 





class TestGeneric(unittest.TestCase):

    def setUp(self):
        
        setLogLevel(namespace='serial', levelStr='debug')
        setLogLevel(namespace='protoc', levelStr='debug')
        setLogLevel(namespace='ema',    levelStr='debug')
        self.transport = proto_helpers.StringTransport()
        #self.clock     = task.Clock()
        self.factory   = EMAProtocolFactory()
        self.protocol  = self.factory.buildProtocol(0)
        self.transport.protocol = self.protocol
        #EMAProtocol.callLater   = self.clock.callLater
        self.protocol.makeConnection(self.transport)
        device.DeferredAttribute.bind(self.protocol)


class TestWatchdog(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options             = {}
        self.options['watchdog'] = {}
        self.options['watchdog']['sync']   = True 
        self.options['watchdog']['period'] = 60
        self.watchdog = device.Watchdog(self, 
            self.options['watchdog'],
            global_sync=True)

    def test_ping(self):
        d = self.watchdog.presence
        self.assertEqual(self.transport.value(), '( )')
        self.transport.clear()
        self.protocol.dataReceived('( )')
        d.addCallback(self.assertEqual, '( )')
        return d

    def test_getWatchdogPeriod(self):
        d = self.watchdog.period
        self.assertEqual(self.transport.value(), '(t)')
        self.transport.clear()
        self.protocol.dataReceived('(T200)')
        d.addCallback(self.assertEqual, 200)
        return d

    def test_setWatchdogPeriod(self):
        self.watchdog.period = 200
        d = self.watchdog.period
        self.assertEqual(self.transport.value(), '(T200)')
        self.transport.clear()
        self.protocol.dataReceived('(T200)')
        d.addCallback(self.assertEqual, 200)
        return d

class TestRealTimeClock(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options        = {}
        self.options['rtc'] = {}
        self.options['rtc']['max_drift'] = 2
        self.rtc = device.RealTimeClock(self, 
            self.options['rtc'], 
            global_sync=False)

    def test_getRTCDateTime(self):
        d = self.rtc.dateTime
        self.assertEqual(self.transport.value(), '(y)')
        self.transport.clear()
        self.protocol.dataReceived('(00:07:35 20/06/2016)')
        d.addCallback(self.assertEqual, datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35))
        return d

    def test_setRTCDateTime(self):
        self.rtc.dateTime = datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35)
        d = self.rtc.dateTime
        self.assertEqual(self.transport.value(), '(Y200616000735)')
        self.transport.clear()
        self.protocol.dataReceived('(00:07:35 20/06/2016)')
        d.addCallback(self.assertEqual, datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35))
        return d

class TestAnemometer(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options               = {}
        self.options['anemometer'] = {}
        self.options['anemometer']['sync']            = False
        self.options['anemometer']['calibration']     = 36
        self.options['anemometer']['model']           = "TX20"
        self.options['anemometer']['threshold']       = 20
        self.options['anemometer']['ave_threshold']   = 66
        self.anemometer = device.Anemometer(self, 
            self.options['anemometer'], 
            global_sync=False)

    def test_getCurrentWindSpeedThreshold(self):
        d = self.anemometer.threshold
        self.assertEqual(self.transport.value(), '(w)')
        self.transport.clear()
        self.protocol.dataReceived('(W020)')
        d.addCallback(self.assertEqual, 20)
        return d

    def test_setCurrentWindSpeedThreshold(self):
        self.anemometer.threshold = 66
        d = self.anemometer.threshold
        self.assertEqual(self.transport.value(), '(W066)')
        self.transport.clear()
        self.protocol.dataReceived('(W066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_getAverageWindSpeedThreshold(self):
        d = self.anemometer.ave_threshold
        self.assertEqual(self.transport.value(), '(o)')
        self.transport.clear()
        self.protocol.dataReceived('(O066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_setAverageWindSpeedThreshold(self):
        self.anemometer.ave_threshold = 66
        d = self.anemometer.ave_threshold
        self.assertEqual(self.transport.value(), '(O066)')
        self.transport.clear()
        self.protocol.dataReceived('(O066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_getAnemometerCalibrationFactor(self):
        d = self.anemometer.calibration
        self.assertEqual(self.transport.value(), '(a)')
        self.transport.clear()
        self.protocol.dataReceived('(A070)')
        d.addCallback(self.assertEqual, 70)
        return d
    
    def test_setAnemometerCalibrationFactor(self):
        self.anemometer.calibration = 70
        d = self.anemometer.calibration
        self.assertEqual(self.transport.value(), '(A070)')
        self.transport.clear()
        self.protocol.dataReceived('(A070)')
        d.addCallback(self.assertEqual, 70)
        return d

    def test_getAnemometerModel(self):
        d = self.anemometer.model
        self.assertEqual(self.transport.value(), '(z)')
        self.transport.clear()
        self.protocol.dataReceived('(Z000)')
        d.addCallback(self.assertEqual, 'Simple')
        return d
    
    def test_setAnemometerModel(self):
        self.anemometer.model = 'Simple'
        d = self.anemometer.model
        self.assertEqual(self.transport.value(), '(Z000)')
        self.transport.clear()
        self.protocol.dataReceived('(Z000)')
        d.addCallback(self.assertEqual, 'Simple')
        return d

class TestBarometer(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options              = {}
        self.options['barometer'] = {}
        self.options['barometer']['sync']            = False
        self.options['barometer']['height']          = 700
        self.options['barometer']['offset']          = -19
        self.barometer = device.Barometer(self, 
            self.options['barometer'], 
            global_sync=False)

    def test_getBarometerHeight(self):
        d = self.barometer.height
        self.assertEqual(self.transport.value(), '(m)')
        self.transport.clear()
        self.protocol.dataReceived('(M00711)')
        d.addCallback(self.assertEqual, 711)
        return d
    
    def test_setBarometerHeight(self):
        self.barometer.height = 711
        d = self.barometer.height
        self.assertEqual(self.transport.value(), '(M00711)')
        self.transport.clear()
        self.protocol.dataReceived('(M00711)')
        d.addCallback(self.assertEqual, 711)
        return d

    def test_getBarometerOffset(self):
        d = self.barometer.offset
        self.assertEqual(self.transport.value(), '(b)')
        self.transport.clear()
        self.protocol.dataReceived('(B-10)')
        d.addCallback(self.assertEqual, -10)
        return d
    
    def test_setBarometerOffset(self):
        self.barometer.offset = -10
        d = self.barometer.offset
        self.assertEqual(self.transport.value(), '(B-10)')
        self.transport.clear()
        self.protocol.dataReceived('(B-10)')
        d.addCallback(self.assertEqual, -10)
        return d

class TestCloudSensor(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options              = {}
        self.options['cloudsensor'] = {}
        self.options['cloudsensor']['sync']            = False
        self.options['cloudsensor']['threshold']       = 23
        self.options['cloudsensor']['gain']            = 2
        self.cloudsensor = device.CloudSensor(self, 
            self.options['cloudsensor'], 
            global_sync=False)

    def test_getCloudSensorThreshold(self):
        d = self.cloudsensor.threshold 
        self.assertEqual(self.transport.value(), '(n)')
        self.transport.clear()
        self.protocol.dataReceived('(N067)')
        d.addCallback(self.assertEqual, 67)
        return d
    
    def test_setCloudSensorThreshold(self):
        self.cloudsensor.threshold  = 67
        d = self.cloudsensor.threshold 
        self.assertEqual(self.transport.value(), '(N067)')
        self.transport.clear()
        self.protocol.dataReceived('(N067)')
        d.addCallback(self.assertEqual, 67)
        return d

    def test_getCloudSensorGain(self):
        d = self.cloudsensor.gain 
        self.assertEqual(self.transport.value(), '(r)')
        self.transport.clear()
        self.protocol.dataReceived('(R010)')
        d.addCallback(self.assertEqual, 1.0)
        return d
    
    def test_setCloudSensorGain(self):
        self.cloudsensor.gain = 1.0
        self.assertEqual(self.transport.value(), '(R010)')
        d = self.cloudsensor.gain 
        self.transport.clear()
        self.protocol.dataReceived('(R010)')
        d.addCallback(self.assertEqual, 1.0)
        return d

class TestPhotometer(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                = {}
        self.options['photometer'] = {}
        self.options['photometer']['sync']            = False
        self.options['photometer']['threshold']       = 10.2
        self.options['photometer']['offset']          = 12.0
        self.photometer = device.Photometer(self, 
            self.options['photometer'], 
            global_sync=False)

    def test_getPhotometerThreshold(self):
        d = self.photometer.threshold
        self.assertEqual(self.transport.value(), '(i)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        self.protocol.dataReceived('(I+00)')
        self.protocol.dataReceived('(I00100)')
        d.addCallback(self.assertEqual, 10.5)
        return d
    
    def test_setPhotometerThreshold(self):
        self.photometer.threshold = 10.5
        d = self.photometer.threshold
        self.assertEqual(self.transport.value(), '(I105)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        d.addCallback(self.assertEqual, 10.5)
        return d

    def test_getPhotometerOffset(self):
        d = self.photometer.offset
        self.assertEqual(self.transport.value(), '(i)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        self.protocol.dataReceived('(I+00)')
        self.protocol.dataReceived('(I00100)')
        d.addCallback(self.assertEqual, 0.0)
        return d
    
    def test_setPhotometerOffset(self):
        self.photometer.offset = 0.0
        d = self.photometer.offset
        self.assertEqual(self.transport.value(), '(I+00)')
        self.transport.clear()
        self.protocol.dataReceived('(I+00)')
        d.addCallback(self.assertEqual, 0.0)
        return d

class TestPluviometer(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                               = {}
        self.options['pluviometer']                = {}
        self.options['pluviometer']['sync']        = False
        self.options['pluviometer']['calibration'] = 36
        self.pluviometer = device.Pluviometer(self, 
            self.options['pluviometer'], 
            global_sync=False)


    def test_getPluviometerCalibration(self):
        d = self.pluviometer.calibration
        self.assertEqual(self.transport.value(), '(p)')
        self.transport.clear()
        self.protocol.dataReceived('(P124)')
        d.addCallback(self.assertEqual, 124)
        return d
    
    def test_setPluviometerCalibration(self):
        self.pluviometer.calibration = 124
        d = self.pluviometer.calibration
        self.assertEqual(self.transport.value(), '(P124)')
        self.transport.clear()
        self.protocol.dataReceived('(P124)')
        d.addCallback(self.assertEqual, 124)
        return d

class TestPyranometer(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                               = {}
        self.options['pyranometer'] = {}
        self.options['pyranometer']['sync']            = False
        self.options['pyranometer']['gain']            = 1
        self.options['pyranometer']['offset']          = 2
        self.pyranometer = device.Pyranometer(self, 
            self.options['pyranometer'], 
            global_sync=False)

    def test_getPyranometerGain(self):
        d = self.pyranometer.gain
        self.assertEqual(self.transport.value(), '(j)')
        self.transport.clear()
        self.protocol.dataReceived('(J140)')
        d.addCallback(self.assertEqual, 14.0)
        return d
    
    def test_setPyranometerGain(self):
        self.pyranometer.gain = 14.0
        d = self.pyranometer.gain
        self.assertEqual(self.transport.value(), '(J140)')
        self.transport.clear()
        self.protocol.dataReceived('(J140)')
        d.addCallback(self.assertEqual, 14.0)
        return d

    def test_getPyranometerOffset(self):
        d = self.pyranometer.offset
        self.assertEqual(self.transport.value(), '(u)')
        self.transport.clear()
        self.protocol.dataReceived('(U000)')
        d.addCallback(self.assertEqual, 0)
        return d
    
    def test_setPyranometerOffset(self):
        self.pyranometer.offset = 0
        d = self.pyranometer.offset
        self.assertEqual(self.transport.value(), '(U000)')
        self.transport.clear()
        self.protocol.dataReceived('(U000)')
        d.addCallback(self.assertEqual, 0)
        return d

class TestRainSensor(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                               = {}
        self.options['rainsensor'] = {}
        self.options['rainsensor']['sync']            = False
        self.options['rainsensor']['threshold']       = 1
        self.rainsensor = device.RainSensor(self, 
            self.options['rainsensor'], 
            global_sync=False)

    def test_getRainSensorThreshold(self):
        d = self.rainsensor.threshold
        self.assertEqual(self.transport.value(), '(l)')
        self.transport.clear()
        self.protocol.dataReceived('(L001)')
        d.addCallback(self.assertEqual, 1)
        return d
    
    def test_setRainSensorThreshold(self):
        self.rainsensor.threshold = 1
        d = self.rainsensor.threshold
        self.assertEqual(self.transport.value(), '(L001)')
        self.transport.clear()
        self.protocol.dataReceived('(L001)')
        d.addCallback(self.assertEqual, 1)
        return d

class TestVoltmeter(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                               = {}
        self.options['voltmeter'] = {}
        self.options['voltmeter']['sync']            = False
        self.options['voltmeter']['threshold']       = 1
        self.voltmeter = device.Voltmeter(self, 
            self.options['voltmeter'], 
            upload_period = 60,
            global_sync=False)

    def addStatusCallback(self, callback):
        '''Needed for the device registration'''
        pass

    def test_getVoltmeterThreshold(self):
        d = self.voltmeter.threshold
        self.assertEqual(self.transport.value(), '(f)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, 0.0)
        return d
    
    def test_setVoltmeterThreshold(self):
        self.voltmeter.threshold = 0.0
        d = self.voltmeter.threshold
        self.assertEqual(self.transport.value(), '(F000)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        d.addCallback(self.assertEqual, 0.0)
        return d

    def test_getVoltmeterOffset(self):
        d = self.voltmeter.offset
        self.assertEqual(self.transport.value(), '(f)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, -1.4)
        return d
    
    def test_setVoltmeterOffset(self):
        self.voltmeter.offset = -1.4
        d = self.voltmeter.offset
        self.assertEqual(self.transport.value(), '(F-14)')
        self.transport.clear()
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, -1.4)
        return d

class TestRoofRelay(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                                  = {}
        self.options['roof_relay'] = {}
        self.options['roof_relay']['sync']          = False
        self.roof_relay = device.RoofRelay(self, 
            self.options['roof_relay'], 
            global_sync=False)

    def addStatusCallback(self, callback):
        '''Needed for the device registration'''
        pass

    def test_setRoofRelayMode1(self):
        self.roof_relay.mode = 'Open'
        d = self.roof_relay.mode
        self.assertEqual(self.transport.value(), '(X007)')
        self.transport.clear()
        self.protocol.dataReceived('(X007)')
        self.protocol.dataReceived('(12:34:56 Abrir Obs. FORZADO)')
        d.addCallback(self.assertEqual, 'Open')
        return d

    def test_setRoofRelayMode2(self):
        self.roof_relay.mode = 'Closed'
        d = self.roof_relay.mode
        self.assertEqual(self.transport.value(), '(X000)')
        self.transport.clear()
        self.protocol.dataReceived('(X000)')
        self.protocol.dataReceived('(12:34:56 Cerrar Obs.)')
        d.addCallback(self.assertEqual, 'Closed')
        return d

    def test_setRoofRelayMode3(self):
        self.roof_relay.mode = 'Auto'
        d = self.roof_relay.mode
        self.assertEqual(self.transport.value(), '(X001)')
        self.transport.clear()
        self.protocol.dataReceived('(X001)')
        self.protocol.dataReceived('(12:34:56 Abrir Obs.)')
        d.addCallback(self.assertEqual, 'Auto')
        return d

class TestAuxiliarfRelay(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options                                  = {}
        self.options['aux_relay'] = {}
        self.options['aux_relay']['sync']          = False
        self.options['aux_relay']['mode']          = 'Timer/On'
        self.aux_relay = device.AuxiliarRelay(self, 
            self.options['aux_relay'], 
            global_sync=False)

    def addStatusCallback(self, callback):
        '''Needed for the device registration'''
        pass

    def test_getAuxiliarRelaySwitchOnTime(self):
        d = self.aux_relay.switchOnTime 
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=6, minute=0))
        return d
    
    def test_setAuxiliarRelaySwitchOnTime(self):
        self.aux_relay.switchOnTime = datetime.time(hour=6, minute=0)
        d = self.aux_relay.switchOnTime 
        self.assertEqual(self.transport.value(), '(Son0600)')
        self.transport.clear()
        self.protocol.dataReceived('(Son0600)')
        d.addCallback(self.assertEqual, datetime.time(hour=6, minute=0))
        return d

    def test_getAuxiliarRelaySwitchOffTime(self):
        d = self.aux_relay.switchOffTime 
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=9, minute=0))
        return d
    
    def test_setAuxiliarRelaySwitchOffTime(self):
        self.aux_relay.switchOffTime = datetime.time(hour=9, minute=0)
        d = self.aux_relay.switchOffTime 
        self.assertEqual(self.transport.value(), '(Sof0900)')
        self.transport.clear()
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=9, minute=0))
        return d

    def test_getAuxiliarRelayMode(self):
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, 'Timer/On')
        return d
    
    def test_setAuxiliarRelayMode1(self):
        self.aux_relay.mode = 'Auto'
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(S000)')
        self.transport.clear()
        self.protocol.dataReceived('(S000)')
        d.addCallback(self.assertEqual, 'Auto')
        return d

    def test_setAuxiliarRelayMode2(self):
        self.aux_relay.mode = 'Closed'
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(S004)')
        self.transport.clear()
        self.protocol.dataReceived('(S004)')
        self.protocol.dataReceived('(12:34:56 Calentador off.)')
        d.addCallback(self.assertEqual, 'Closed')
        return d

    def test_setAuxiliarRelayMode3(self):
        self.aux_relay.mode = 'Open'
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(S005)')
        self.transport.clear()
        self.protocol.dataReceived('(S005)')
        self.protocol.dataReceived('(12:34:56 Calentador on.)')
        d.addCallback(self.assertEqual, 'Open')
        return d

    def test_setAuxiliarRelayMode4(self):
        self.aux_relay.mode = 'Timer/Off'
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(S008)')
        self.transport.clear()
        self.protocol.dataReceived('(S008)')
        self.protocol.dataReceived('(12:34:56 20/06/2016 Timer OFF)')
        d.addCallback(self.assertEqual, 'Timer/Off')
        return d

    def test_setAuxiliarRelayMode5(self):
        self.aux_relay.mode = 'Timer/On'
        d = self.aux_relay.mode
        self.assertEqual(self.transport.value(), '(S009)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(12:34:56 20/06/2016 Timer ON)')
        d.addCallback(self.assertEqual, 'Timer/On')
        return d