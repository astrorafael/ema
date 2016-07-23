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

from ema.serial   import EMAProtocol, EMAProtocolFactory, EMATimeoutError
from ema.logger   import setLogLevel
from ema.device   import EMARangeError, EMATypeError, EMAAttributeError, EMARuntimeError, EMADeleteAttributeError



class TestGeneric(unittest.TestCase):

    def setUp(self):
        
        setLogLevel(namespace='serial', levelStr='debug')
        setLogLevel(namespace='protoc', levelStr='debug')
        setLogLevel(namespace='ema',    levelStr='debug')
        self.transport = proto_helpers.StringTransport()
        self.clock     = task.Clock()
        self.factory   = EMAProtocolFactory()
        self.protocol  = self.factory.buildProtocol(0)
        self.transport.protocol = self.protocol
        EMAProtocol.callLater   = self.clock.callLater
        self.protocol.makeConnection(self.transport)
        device.Attribute.bind(self.protocol)
        


class TestVReadWriteAttribute(TestGeneric):

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

    def test_nominalRead(self):
        d = self.voltmeter.threshold
        self.assertEqual(self.transport.value(), '(f)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        self.protocol.dataReceived('(F-14)')
        d.addCallback(self.assertEqual, 0.0)
        return d
    
    def test_nominalWrite(self):
        self.voltmeter.threshold = 0.0
        d = self.voltmeter.threshold
        self.assertEqual(self.transport.value(), '(F000)')
        self.transport.clear()
        self.protocol.dataReceived('(F000)')
        d.addCallback(self.assertEqual, 0.0)
        return d

    def test_delete1(self):
        '''Assign to None is not attribute deletion'''
        error = None
        try:
            self.voltmeter.threshold = None
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMATypeError)


    def test_delete2(self):
        '''Attribute deletion is not supported'''
        error = None
        try:
            del self.voltmeter.threshold
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMADeleteAttributeError)


    
    def test_typeMismatch(self):
        error = None
        try:
            self.voltmeter.offset = -2
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMATypeError)


    def test_rangeError(self):
        error = None
        try:
            self.voltmeter.offset = 200.0
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMARangeError)


    def test_noProtocol(self):
        device.Attribute.bind(None)
        error = None
        try:
            self.voltmeter.offset = -1.4
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMARuntimeError)
        

    def test_twoReads(self):
        '''
        Two reads in a row will return the same deferred
        as log as it is not completed.
        '''
        self.voltmeter.offset = -1.4
        d1 = self.voltmeter.offset
        d2 = self.voltmeter.offset
        self.assertEqual(d1, d2)
       

    def test_twoWrites(self):
        '''
        Two writes in a row are not allowed
        because we want to return the last generated deferred 
        in a subsequent read
        '''
        try:
            self.voltmeter.offset = -1.4
            self.voltmeter.offset = -1.4
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMARuntimeError)



class TestVReadOnlyAttribute(TestGeneric):

    def setUp(self):
        TestGeneric.setUp(self)
        self.options             = {}
        self.options['watchdog'] = {}
        self.options['watchdog']['sync']   = True 
        self.options['watchdog']['period'] = 60
        self.watchdog = device.Watchdog(self, 
            self.options['watchdog'],
            global_sync=True)


    def addStatusCallback(self, callback):
        '''Needed for the device registration'''
        pass


    def test_nominalRead(self):
        d = self.watchdog.presence
        self.assertEqual(self.transport.value(), '( )')
        self.transport.clear()
        self.protocol.dataReceived('( )')
        d.addCallback(self.assertEqual, '( )')
        return d

    
    def test_failedWrite(self):
        '''R/O attribute exception takes precendece'''
        error = None
        try:
            self.watchdog.presence = 0.0
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)
    

    def test_typeMismatch(self):
        error = None
        try:
            self.watchdog.presence = -2
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)


    def test_rangeError(self):
        '''R/O attribute exception takes precendece'''
        error = None
        try:
            self.watchdog.presence = 200.0
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)


    def test_noProtocol(self):
        '''R/O attribute exception takes precendece'''
        error = None
        device.Attribute.bind(None)
        try:
            self.watchdog.presence = -1.4
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)
        

    def test_twoReads(self):
        d1 = self.watchdog.presence
        d2 = self.watchdog.presence
        self.assertEqual(d1, d2)
       

    def test_twoWrites(self):
        '''R/O attribute exception takes precendece'''
        try:
            self.watchdog.presence = -1.4
            self.watchdog.presence = -1.4
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)



class TestVWriteOnlyAttribute(TestGeneric):


    def setUp(self):
        TestGeneric.setUp(self)
        self.options               = {}
        self.options['roof_relay'] = {}
        self.options['roof_relay']['sync']   = False
        self.roof_relay = device.RoofRelay(self, 
            self.options['roof_relay'], 
            global_sync=False)


    def addStatusCallback(self, callback):
        '''Needed for the device registration'''
        pass

    def test_nominalWrite(self):
        self.roof_relay.mode = 'Open'
        d = self.roof_relay.mode
        self.assertEqual(self.transport.value(), '(X007)')
        self.transport.clear()
        self.protocol.dataReceived('(X007)')
        self.protocol.dataReceived('(12:34:56 Abrir Obs. FORZADO)')
        d.addCallback(self.assertEqual, 'Open')
        return d


    def test_failedRead(self):
        '''isolated read cause a W/O attribute exception''' 
        error = None
        try:
            d = self.roof_relay.mode
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)

    def test_notFailedRead(self):
        '''W/O attributes gets a chance of getting the deferred 
        in order to follow pending operation
        ''' 
        error = None
        try:
            self.roof_relay.mode = 'Auto'
            d = self.roof_relay.mode
        except Exception as e:
            error = e
        self.assertEqual(type(error), type(None))
        

    def test_typeMismatch(self):
        error = None
        try:
            self.roof_relay.mode = -2
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMATypeError)


    def test_rangeError(self):
        error = None
        try:
            self.roof_relay.mode = 'Foo'
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMARangeError)


    def test_noProtocol(self):
        '''Missing Protocol does not takes precedence'''
        error = None
        device.Attribute.bind(None)
        try:
            self.roof_relay.mode = -1.4
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMATypeError)
        

    def test_twoReads1(self):
        '''
        W/O attributes gets a chance of getting the deferred 
        in order to follow write pending operation
        ''' 
        error = None
        try:
            self.roof_relay.mode = 'Auto'
            d1 = self.roof_relay.mode
            d2 = self.roof_relay.mode
        except Exception as e:
            error = e
        self.assertEqual(d1, d2)

    def test_twoReads2(self):
        '''
        W/O attribute. A read cannot appear without a write first.
        ''' 
        error = None
        try:
            d1 = self.roof_relay.mode
            d2 = self.roof_relay.mode
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMAAttributeError)
       

    def test_twoWrites(self):
        '''Two writes in a row are not allowed.
        First get the deferred and wait for the callback
        '''
        try:
            self.roof_relay.mode = 'Open'
            self.roof_relay.mode = 'Auto'
        except Exception as e:
            error = e
        self.assertEqual(type(error), EMARuntimeError)

  