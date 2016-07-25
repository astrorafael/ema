# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import os
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

from twisted.logger import Logger, LogLevel
from twisted.internet import reactor, task
from twisted.application.service import Service
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet.endpoints import clientFromString
from twisted.internet.defer import inlineCallbacks, returnValue

from mqtt import v311
from mqtt.error  import MQTTStateError
from mqtt.client.factory import MQTTFactory

#--------------
# local imports
# -------------

from .logger import setLogLevel
from .utils  import chop

# ----------------
# Module constants
# ----------------

# Reconencting Service. Default backoff policy parameters

INITIAL_DELAY = 4   # seconds
FACTOR        = 2
MAX_DELAY     = 600 # seconds

# Sequence of possible timestamp formats comming from the Publishers
TSTAMP_FORMAT = [ "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",]

# Max Timestamp Ouf-Of-Sync difference, in seconds
MAX_TSTAMP_OOS = 60

PROTOCOL_REVISION = 1

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='mqtt')



class DateTimeEncoder(json.JSONEncoder):
    '''Helper class to encode datetime objets in JSON'''
    def default(self, o):
        if  isinstance(o, datetime.datetime):
            return o.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


class MQTTService(ClientService):

    # Default subscription QoS
    
    NAME = 'MQTTService'
    QoS = 2
    T  = 1
    

    def __init__(self, options):
        self.options    = options
        self.topics     = []
        setLogLevel(namespace='mqtt', levelStr=options['log_level'])
        setLogLevel(namespace='mqtt.client.factory.MQTTFactory', levelStr='error')
        self.factory  = MQTTFactory(profile=MQTTFactory.PUBLISHER)
        self.endpoint = clientFromString(reactor, self.options['broker'])
        if self.options['username'] == "":
            self.options['username'] = None
            self.options['password'] = None
        ClientService.__init__(self, self.endpoint, self.factory, 
            retryPolicy=backoffPolicy(initialDelay=INITIAL_DELAY, factor=FACTOR, maxDelay=MAX_DELAY))
        self.topic = {
            'register' : 'EMA/register',
            'events'   : 'EMA/{0}/events'.format(options['channel']),
            'state'    : 'EMA/{0}/current/state'.format(options['channel']),
            'minmax'   : 'EMA/{0}/historic/minmax'.format(options['channel']),
            'averages' : 'EMA/{0}/historic/average'.format(options['channel']),
        }
   

    def startService(self):
        log.info("starting MQTT Client Service")
        self.whenConnected().addCallback(self.connectToBroker)
        ClientService.startService(self)


    @inlineCallbacks
    def stopService(self):
        try:
            yield ClientService.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)
        
    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='mqtt', levelStr=new_options['log_level'])
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        self.options = new_options
        

    def pauseService(self):
        pass

    def resumeService(self):
        pass

   
    # --------------
    # Helper methods
    # ---------------
   
    @inlineCallbacks
    def connectToBroker(self, protocol):
        '''
        Connect to MQTT broker
        '''
        self.protocol = protocol
        try:
            self.protocol.setTimeout(self.options['timeout'])
            self.protocol.setBandwith(self.options['bandwidth'])
            self.protocol.setWindowSize(4)
            yield self.protocol.connect("TwistedMQTT-pub", 
                username=self.options['username'], password=self.options['password'], 
                keepalive=self.options['keepalive'])
        except Exception as e:
            log.failure("Connecting to {broker} raised {excp!s}", 
               broker=self.options['broker'], excp=e)
        else:
            log.info("Connected to {broker}", broker=self.options['broker'])
            self.periodicTask = task.LoopingCall(self._publish)
            self.periodicTask.start(self.T, now=False) # call every T seconds
       

    #@inlineCallbacks
    def _publish(self):
        '''
        Runs a publish cycle.
        '''
        # NOTA: DEPURAR EL JSON HASTA QURE ESTE CONFORME
        # A LA ESPECIFICACION Y PUBLICAR VIA MQTT
        def logError(failure, topic):
            log.error("MQTT publishig failed in {topic}", topic=topic)
            log.failure("{excp!s}", excp=failure)

        if len(self.parent.queue['register']):
            msg = self.parent.queue['register'].popleft()
            msg['who'] = self.options['id']
            msg['rev'] = PROTOCOL_REVISION
            flat = json.dumps(msg, cls=DateTimeEncoder)
            log.debug("MQTT Payload => {flat}", flat=flat)
            d1 = self.protocol.publish(topic=self.topic['register'], qos=2, message=flat)
            d1.addErrback(logError, self.topic['register'])

        if len(self.parent.queue['log']):
            msg = self.parent.queue['log'].popleft()
            msg['who'] = self.options['id']
            msg['rev'] = PROTOCOL_REVISION
            flat = json.dumps(msg, cls=DateTimeEncoder)
            log.debug("MQTT Payload => {flat}", flat=flat)
            d2 = self.protocol.publish(topic=self.topic['events'], qos=0, message=flat, retain=True)
            d2.addErrback(logError, self.topic['events'])

        if len(self.parent.queue['status']):
            status, tstamp = self.parent.queue['status'].popleft()
            msg = {}
            msg['who'] = self.options['id']
            msg['rev'] = PROTOCOL_REVISION
            msg['tstamp'] = tstamp
            msg['current'] = status
            flat = json.dumps(msg, cls=DateTimeEncoder)
            log.debug("MQTT Payload => {flat}", flat=flat)
            d3 = self.protocol.publish(topic=self.topic['state'], qos=0, message=flat)
            d3.addErrback(logError, self.topic['state'])

        if len(self.parent.queue['minmax']):
            dump = self.parent.queue['minmax'].popleft()
            msg = {}
            msg['who'] = self.options['id']
            msg['rev'] = PROTOCOL_REVISION
            msg['minmax'] = dump
            flat = json.dumps(msg, cls=DateTimeEncoder)
            log.debug("MQTT Payload => {flat}", flat=flat)
            d4 = self.protocol.publish(topic=self.topic['minmax'], qos=2, message=flat)
            d4.addErrback(logError, self.topic['minmax'])

        if len(self.parent.queue['ave5min']):
            dump = self.parent.queue['ave5min'].popleft()
            msg = {}
            msg['who'] = self.options['id']
            msg['rev'] = PROTOCOL_REVISION
            msg['averages'] = dump
            flat = json.dumps(msg, cls=DateTimeEncoder)
            log.debug("MQTT Payload => {flat}", flat=flat)
            d5 = self.protocol.publish(topic=self.topic['averages'], qos=2, message=flat)
            d5.addErrback(logError, self.topic['averages'])