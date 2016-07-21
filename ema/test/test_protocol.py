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

import ema.command

from ema.serial import EMAProtocol, EMAProtocolFactory
from ema.logger   import setLogLevel



class TestEMAProtocol1(unittest.TestCase):

    def setUp(self):
        setLogLevel(namespace='serial', levelStr='debug')
        setLogLevel(namespace='protoc', levelStr='debug')
        self.transport = proto_helpers.StringTransport()
        #self.clock     = task.Clock()
        self.factory   = EMAProtocolFactory()
        self.protocol  = self.factory.buildProtocol(0)
        self.transport.protocol = self.protocol
        #EMAProtocol.callLater   = self.clock.callLater
        self.protocol.makeConnection(self.transport)
       
    
    # ------------
    # EMA Watchdog
    # ------------

    def test_ping(self):
        d = self.protocol.execute(ema.command.Watchdog.GetPresence())
        self.assertEqual(self.transport.value(), '( )')
        self.transport.clear()
        self.protocol.dataReceived('( )')
        d.addCallback(self.assertEqual, '( )')
        return d

    def test_getWatchdogPeriod(self):
        d = self.protocol.execute(ema.command.Watchdog.GetPeriod())
        self.assertEqual(self.transport.value(), '(t)')
        self.transport.clear()
        self.protocol.dataReceived('(T200)')
        d.addCallback(self.assertEqual, 200)
        return d

    def test_setWatchdogPeriod(self):
        d = self.protocol.execute(ema.command.Watchdog.SetPeriod(200))
        self.assertEqual(self.transport.value(), '(T200)')
        self.transport.clear()
        self.protocol.dataReceived('(T200)')
        d.addCallback(self.assertEqual, 200)
        return d

    # -------
    # EMA RTC
    # -------

    def test_getRTCDateTime(self):
        d = self.protocol.execute(ema.command.RealTimeClock.GetDateTime())
        self.assertEqual(self.transport.value(), '(y)')
        self.transport.clear()
        self.protocol.dataReceived('(00:07:35 20/06/2016)')
        d.addCallback(self.assertEqual, datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35))
        return d

    def test_setRTCDateTime(self):
        d = self.protocol.execute(ema.command.RealTimeClock.SetDateTime(datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35)))
        self.assertEqual(self.transport.value(), '(Y200616000735)')
        self.transport.clear()
        self.protocol.dataReceived('(00:07:35 20/06/2016)')
        d.addCallback(self.assertEqual, datetime.datetime(year=2016, month=6, day=20, hour=0, minute=7, second=35))
        return d

    # --------------
    # EMA Anemometer
    # --------------
        
    def test_getCurrentWindSpeedThreshold(self):
        d = self.protocol.execute(ema.command.Anemometer.GetCurrentWindSpeedThreshold())
        self.assertEqual(self.transport.value(), '(w)')
        self.transport.clear()
        self.protocol.dataReceived('(W020)')
        d.addCallback(self.assertEqual, 20)
        return d

    def test_setCurrentWindSpeedThreshold(self):
        d = self.protocol.execute(ema.command.Anemometer.SetCurrentWindSpeedThreshold(66))
        self.assertEqual(self.transport.value(), '(W066)')
        self.transport.clear()
        self.protocol.dataReceived('(W066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_getAverageWindSpeedThreshold(self):
        d = self.protocol.execute(ema.command.Anemometer.GetAverageWindSpeedThreshold())
        self.assertEqual(self.transport.value(), '(o)')
        self.transport.clear()
        self.protocol.dataReceived('(O066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_setAverageWindSpeedThreshold(self):
        d = self.protocol.execute(ema.command.Anemometer.SetAverageWindSpeedThreshold(66))
        self.assertEqual(self.transport.value(), '(O066)')
        self.transport.clear()
        self.protocol.dataReceived('(O066)')
        d.addCallback(self.assertEqual, 66)
        return d

    def test_getAnemometerCalibrationFactor(self):
        d = self.protocol.execute(ema.command.Anemometer.GetCalibrationFactor())
        self.assertEqual(self.transport.value(), '(a)')
        self.transport.clear()
        self.protocol.dataReceived('(A070)')
        d.addCallback(self.assertEqual, 70)
        return d
    
    def test_setAnemometerCalibrationFactor(self):
        d = self.protocol.execute(ema.command.Anemometer.SetCalibrationFactor(70))
        self.assertEqual(self.transport.value(), '(A070)')
        self.transport.clear()
        self.protocol.dataReceived('(A070)')
        d.addCallback(self.assertEqual, 70)
        return d

    def test_getAnemometerModel(self):
        d = self.protocol.execute(ema.command.Anemometer.GetModel())
        self.assertEqual(self.transport.value(), '(z)')
        self.transport.clear()
        self.protocol.dataReceived('(Z000)')
        d.addCallback(self.assertEqual, 'Simple')
        return d
    
    def test_setAnemometerModel(self):
        d = self.protocol.execute(ema.command.Anemometer.SetModel('Simple'))
        self.assertEqual(self.transport.value(), '(Z000)')
        self.transport.clear()
        self.protocol.dataReceived('(Z000)')
        d.addCallback(self.assertEqual, 'Simple')
        return d

    # -------------
    # EMA Barometer
    # -------------

    def test_getBarometerHeight(self):
        d = self.protocol.execute(ema.command.Barometer.GetHeight())
        self.assertEqual(self.transport.value(), '(m)')
        self.transport.clear()
        self.protocol.dataReceived('(M00711)')
        d.addCallback(self.assertEqual, 711)
        return d
    
    def test_setBarometerHeight(self):
        d = self.protocol.execute(ema.command.Barometer.SetHeight(711))
        self.assertEqual(self.transport.value(), '(M00711)')
        self.transport.clear()
        self.protocol.dataReceived('(M00711)')
        d.addCallback(self.assertEqual, 711)
        return d

    def test_getBarometerOffset(self):
        d = self.protocol.execute(ema.command.Barometer.GetOffset())
        self.assertEqual(self.transport.value(), '(b)')
        self.transport.clear()
        self.protocol.dataReceived('(B-10)')
        d.addCallback(self.assertEqual, -10)
        return d
    
    def test_setBarometerOffset(self):
        d = self.protocol.execute(ema.command.Barometer.SetOffset(-10))
        self.assertEqual(self.transport.value(), '(B-10)')
        self.transport.clear()
        self.protocol.dataReceived('(B-10)')
        d.addCallback(self.assertEqual, -10)
        return d
   
    # ------------------
    # EMA Cloud Detector
    # ------------------

    def test_getCloudSensorThreshold(self):
        d = self.protocol.execute(ema.command.CloudSensor.GetThreshold())
        self.assertEqual(self.transport.value(), '(n)')
        self.transport.clear()
        self.protocol.dataReceived('(N067)')
        d.addCallback(self.assertEqual, 67)
        return d
    
    def test_setCloudSensorThreshold(self):
        d = self.protocol.execute(ema.command.CloudSensor.SetThreshold(67))
        self.assertEqual(self.transport.value(), '(N067)')
        self.transport.clear()
        self.protocol.dataReceived('(N067)')
        d.addCallback(self.assertEqual, 67)
        return d

    def test_getCloudSensorGain(self):
        d = self.protocol.execute(ema.command.CloudSensor.GetGain())
        self.assertEqual(self.transport.value(), '(r)')
        self.transport.clear()
        self.protocol.dataReceived('(R010)')
        d.addCallback(self.assertEqual, 1.0)
        return d
    
    def test_setCloudSensorGain(self):
        d = self.protocol.execute(ema.command.CloudSensor.SetGain(1.0))
        self.assertEqual(self.transport.value(), '(R010)')
        self.transport.clear()
        self.protocol.dataReceived('(R010)')
        d.addCallback(self.assertEqual, 1.0)
        return d

    # --------------
    # EMA Photometer
    # --------------

    def test_getPhotometerThreshold(self):
        d = self.protocol.execute(ema.command.Photometer.GetThreshold())
        self.assertEqual(self.transport.value(), '(i)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        self.protocol.dataReceived('(I+00)')
        self.protocol.dataReceived('(I00100)')
        d.addCallback(self.assertEqual, 10.5)
        return d
    
    def test_setPhotometerThreshold(self):
        d = self.protocol.execute(ema.command.Photometer.SetThreshold(10.5))
        self.assertEqual(self.transport.value(), '(I105)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        d.addCallback(self.assertEqual, 10.5)
        return d

    def test_getPhotometerOffset(self):
        d = self.protocol.execute(ema.command.Photometer.GetOffset())
        self.assertEqual(self.transport.value(), '(i)')
        self.transport.clear()
        self.protocol.dataReceived('(I105)')
        self.protocol.dataReceived('(I+00)')
        self.protocol.dataReceived('(I00100)')
        d.addCallback(self.assertEqual, 0.0)
        return d
    
    def test_setPhotometerOffset(self):
        d = self.protocol.execute(ema.command.Photometer.SetOffset(0.0))
        self.assertEqual(self.transport.value(), '(I+00)')
        self.transport.clear()
        self.protocol.dataReceived('(I+00)')
        d.addCallback(self.assertEqual, 0.0)
        return d

    # ---------------
    # EMA Pluviometer
    # ---------------

    def test_getPluviometerCalibration(self):
        d = self.protocol.execute(ema.command.Pluviometer.GetCalibrationFactor())
        self.assertEqual(self.transport.value(), '(p)')
        self.transport.clear()
        self.protocol.dataReceived('(P124)')
        d.addCallback(self.assertEqual, 124)
        return d
    
    def test_setPluviometerCalibration(self):
        d = self.protocol.execute(ema.command.Pluviometer.SetCalibrationFactor(124))
        self.assertEqual(self.transport.value(), '(P124)')
        self.transport.clear()
        self.protocol.dataReceived('(P124)')
        d.addCallback(self.assertEqual, 124)
        return d

    # ---------------
    # EMA Pyranometer
    # ---------------

    def test_getPyranometerGain(self):
        d = self.protocol.execute(ema.command.Pyranometer.GetGain())
        self.assertEqual(self.transport.value(), '(j)')
        self.transport.clear()
        self.protocol.dataReceived('(J140)')
        d.addCallback(self.assertEqual, 14.0)
        return d
    
    def test_setPyranometerGain(self):
        d = self.protocol.execute(ema.command.Pyranometer.SetGain(14.0))
        self.assertEqual(self.transport.value(), '(J140)')
        self.transport.clear()
        self.protocol.dataReceived('(J140)')
        d.addCallback(self.assertEqual, 14.0)
        return d

    def test_getPyranometerOffset(self):
        d = self.protocol.execute(ema.command.Pyranometer.GetOffset())
        self.assertEqual(self.transport.value(), '(u)')
        self.transport.clear()
        self.protocol.dataReceived('(U000)')
        d.addCallback(self.assertEqual, 0)
        return d
    
    def test_setPyranometerOffset(self):
        d = self.protocol.execute(ema.command.Pyranometer.SetOffset(0))
        self.assertEqual(self.transport.value(), '(U000)')
        self.transport.clear()
        self.protocol.dataReceived('(U000)')
        d.addCallback(self.assertEqual, 0)
        return d

    # ---------------
    # EMA Rain Sensor
    # ---------------

    def test_getRainSensorThreshold(self):
        d = self.protocol.execute(ema.command.RainSensor.GetThreshold())
        self.assertEqual(self.transport.value(), '(l)')
        self.transport.clear()
        self.protocol.dataReceived('(L001)')
        d.addCallback(self.assertEqual, 1)
        return d
    
    def test_setRainSensorThreshold(self):
        d = self.protocol.execute(ema.command.RainSensor.SetThreshold(1))
        self.assertEqual(self.transport.value(), '(L001)')
        self.transport.clear()
        self.protocol.dataReceived('(L001)')
        d.addCallback(self.assertEqual, 1)
        return d
  
    # ---------------
    # EMA Thermometer
    # ---------------

    def test_getThermometerDeltaTempThreshold(self):
        d = self.protocol.execute(ema.command.Thermometer.GetThreshold())
        self.assertEqual(self.transport.value(), '(c)')
        self.transport.clear()
        self.protocol.dataReceived('(C005)')
        d.addCallback(self.assertEqual, 5)
        return d
    
    def test_setThermometerDeltaTempThreshold(self):
        d = self.protocol.execute(ema.command.Thermometer.SetThreshold(5))
        self.assertEqual(self.transport.value(), '(C005)')
        self.transport.clear()
        self.protocol.dataReceived('(C005)')
        d.addCallback(self.assertEqual, 5)
        return d

    # -------------
    # EMA Voltmeter
    # -------------

    def test_getVoltmeterThreshold(self):
        d = self.protocol.execute(ema.command.Voltmeter.GetThreshold())
        self.assertEqual(self.transport.value(), '(f)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, 0.0)
        return d
    
    def test_setVoltmeterThreshold(self):
        d = self.protocol.execute(ema.command.Voltmeter.SetThreshold(0.0))
        self.assertEqual(self.transport.value(), '(F000)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        d.addCallback(self.assertEqual, 0.0)
        return d

    def test_getVoltmeterOffset(self):
        d = self.protocol.execute(ema.command.Voltmeter.GetOffset())
        self.assertEqual(self.transport.value(), '(f)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, -1.4)
        return d
    
    def test_setVoltmeterOffset(self):
        d = self.protocol.execute(ema.command.Voltmeter.SetOffset(-1.4))
        self.assertEqual(self.transport.value(), '(F-14)')
        self.transport.clear()
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, -1.4)
        return d

    # ------------------
    # EMA Auxiliar Relay
    # ------------------

    def test_getAuxiliarRelaySwitchOnTime(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.GetSwitchOnTime())
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=6, minute=0))
        return d
    
    def test_setAuxiliarRelaySwitchOnTime(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetSwitchOnTime(datetime.time(hour=6, minute=0)))
        self.assertEqual(self.transport.value(), '(Son0600)')
        self.transport.clear()
        self.protocol.dataReceived('(Son0600)')
        d.addCallback(self.assertEqual, datetime.time(hour=6, minute=0))
        return d

    def test_getAuxiliarRelaySwitchOffTime(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.GetSwitchOffTime())
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=9, minute=0))
        return d
    
    def test_setAuxiliarRelaySwitchOffTime(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetSwitchOffTime(datetime.time(hour=9, minute=0)))
        self.assertEqual(self.transport.value(), '(Sof0900)')
        self.transport.clear()
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, datetime.time(hour=9, minute=0))
        return d

    def test_getAuxiliarRelayMode(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.GetMode())
        self.assertEqual(self.transport.value(), '(s)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(Son0600)')
        self.protocol.dataReceived('(Sof0900)')
        d.addCallback(self.assertEqual, 'Timer/On')
        return d
    
    def test_setAuxiliarRelayMode1(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetMode('Auto'), nretries=0)
        self.assertEqual(self.transport.value(), '(S000)')
        self.transport.clear()
        self.protocol.dataReceived('(S000)')
        d.addCallback(self.assertEqual, 'Auto')
        return d

    def test_setAuxiliarRelayMode2(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetMode('Closed'))
        self.assertEqual(self.transport.value(), '(S004)')
        self.transport.clear()
        self.protocol.dataReceived('(S004)')
        self.protocol.dataReceived('(12:34:56 Calentador off.)')
        d.addCallback(self.assertEqual, 'Closed')
        return d

    def test_setAuxiliarRelayMode3(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetMode('Open'))
        self.assertEqual(self.transport.value(), '(S005)')
        self.transport.clear()
        self.protocol.dataReceived('(S005)')
        self.protocol.dataReceived('(12:34:56 Calentador on.)')
        d.addCallback(self.assertEqual, 'Open')
        return d

    def test_setAuxiliarRelayMode4(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetMode('Timer/Off'))
        self.assertEqual(self.transport.value(), '(S008)')
        self.transport.clear()
        self.protocol.dataReceived('(S008)')
        self.protocol.dataReceived('(12:34:56 20/06/2016 Timer OFF)')
        d.addCallback(self.assertEqual, 'Timer/Off')
        return d

    def test_setAuxiliarRelayMode5(self):
        d = self.protocol.execute(ema.command.AuxiliarRelay.SetMode('Timer/On'))
        self.assertEqual(self.transport.value(), '(S009)')
        self.transport.clear()
        self.protocol.dataReceived('(S009)')
        self.protocol.dataReceived('(12:34:56 20/06/2016 Timer ON)')
        d.addCallback(self.assertEqual, 'Timer/On')
        return d

    # --------------
    # EMA Roof Relay
    # --------------

    def test_setRoofRelayMode1(self):
        d = self.protocol.execute(ema.command.RoofRelay.SetMode('Open'))
        self.assertEqual(self.transport.value(), '(X007)')
        self.transport.clear()
        self.protocol.dataReceived('(X007)')
        self.protocol.dataReceived('(12:34:56 Abrir Obs. FORZADO)')
        d.addCallback(self.assertEqual, 'Open')
        return d

    def test_setRoofRelayMode2(self):
        d = self.protocol.execute(ema.command.RoofRelay.SetMode('Closed'))
        self.assertEqual(self.transport.value(), '(X000)')
        self.transport.clear()
        self.protocol.dataReceived('(X000)')
        self.protocol.dataReceived('(12:34:56 Cerrar Obs.)')
        d.addCallback(self.assertEqual, 'Closed')
        return d
