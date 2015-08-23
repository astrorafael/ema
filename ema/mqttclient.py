# ----------------------------------------------------------------------
# Copyright (c) 2015 Rafael Gonzalez.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ----------------------------------------------------------------------

# ========================== DESIGN NOTES ==============================
# An MQTT class implementing a MQTT client with a puere publishing-only
# behaviour. No disconnection requests are ever made.
#
# This class ingerits from Lazy to periodically execute a work() procedure
# whichi s responsible of most of the things, including keeping the connection alive
# The work() procedure eexectues twice as fast as the keepalive timeout specidied to
# the client MQTT library.
#
# This version publushes a 24h bulk dump to the MQTT broker
# by using an object of class Command and implementing the necessary callbacks.
# 
# ======================================================================

import logging
import paho.mqtt.client as mqtt
import socket
from datetime import datetime

from server import Lazy, Server
from emaproto  import SPSB, STATLEN
from command import Command, COMMAND
from dev.todtimer import Timer


# FLASH Pages where History data re stored
FLASH_START = 300
FLASH_END   = 300

# tog info every NPLUBLIS times (ticks) 
NPUBLISH = 60

# MQTT Connection Status
NOT_CONNECTED = 0
CONNECTING    = 1
CONNECTED     = 2
FAILED        = 3
DISCONNECTING = 4
	

log = logging.getLogger('mqtt')


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
   userdata.on_connect(flags, rc)

def on_disconnect(client, userdata, rc):
   userdata.on_disconnect(rc)

# The callback for when a PUBLISH message is received from the server.
# Not Needed. This is a pure 'publish type' client.
def on_message(client, userdata, msg):
    userdata.on_message(msg)

# Utility function 
def transform(message):
    '''Transform EMA status message into a pure ASCII string'''
    return "%s%03d%s" % (message[:SPSB], ord(message[SPSB]), message[SPSB+1:])



class BulkDumpCommand(Command):
   '''
   Commad subclass to handle bulk dump request and responses via callbacks
   '''

   def __init__(self, ema, retries, **kargs):
      Command.__init__(self,ema,retries,**kargs)

   # delegate to MQTT client object as it has all the needed context
   def onPartialCommand(self, message, userdata):
      '''
      Partial bulk dump handler
      '''
      self.ema.mqttclient.onPartialCommand(message,userdata)

   # delegate to MQTT client object as it has all he needed context
   def onCommandComplete(self, message, userdata):
      '''
      Bulk dump Command complete handler
      '''
      self.ema.mqttclient.onCommandComplete(message,userdata)




class MQTTClient(Lazy):

   # TOPIC Default vaules
   TOPIC_EVENTS         = "EMA/events"
   TOPIC_TOPICS         = "EMA/topics"
   TOPIC_HISTORY        = "EMA/history"
   TOPIC_CURRENT_STATUS = "EMA/current/status"


   def __init__(self, ema, parser, **kargs):
      lvl      = parser.get("MQTT", "mqtt_log")
      log.setLevel(lvl)
      id       = parser.get("MQTT", "mqtt_id")
      host     = parser.get("MQTT", "mqtt_host")
      port     = parser.getint("MQTT", "mqtt_port")
      period   = parser.getint("MQTT", "mqtt_period")
      histflag = parser.getboolean("MQTT", "mqtt_publish_history")
      publish_status = parser.getboolean("MQTT", "mqtt_publish_status")
      Lazy.__init__(self, period / 2.0 )
      MQTTClient.TOPIC_EVENTS         = "%s/events"  % id
      MQTTClient.TOPIC_TOPICS         = "%s/topics"  % id
      MQTTClient.TOPIC_HISTORY        = "%s/history" % id
      MQTTClient.TOPIC_CURRENT_STATUS = "%s/current/status" % id
      self.ema        = ema
      self.__id       = id
      self.__topics   = False
      self.__stats    = 0
      self.__count    = 0
      self.__histflag = histflag
      self.__state    = NOT_CONNECTED
      self.__host     = host
      self.__port     = port
      self.__period   = period
      self.__pubstat  = publish_status
      self.__emastat  = "()"
      self.__mqtt     =  mqtt.Client(client_id=id+'@'+socket.gethostname(), userdata=self)
      self.__mqtt.on_connect    = on_connect
      self.__mqtt.on_disconnect = on_disconnect
      ema.addLazy(self)
      ema.todtimer.addSubscriber(self)
      if publish_status:
         ema.subscribeStatus(self)
      log.info("MQTT client created")

   # ----------------------------------------
   # MQTT Callbacks
   # -----------------------------------------

   def on_connect(self, flags, rc):
     '''Send the initial event and set last will on unexpected diconnection'''
     if rc == 0:
       self.__state = CONNECTED
       self.__mqtt.publish(MQTTClient.TOPIC_EVENTS,  payload="EMA Server connected", qos=2, retain=True)
       self.__mqtt.will_set(MQTTClient.TOPIC_EVENTS, payload="EMA Server disconnected", qos=2, retain=True)
       self.__mqtt.will_set(MQTTClient.TOPIC_TOPICS, payload=MQTTClient.TOPIC_EVENTS, qos=2, retain=True)
       log.info("Conected successfully") 
     else:
       self.__state = FAILED
       log.error("Connection failed, rc =%d" % rc)

   def on_disconnect(self, rc):
     log.warning("Unexpected disconnection, rc =%d" % rc)
     self.__state  = NOT_CONNECTED
     self.__topics = False
     try:
       self.ema.delReadable(self)
     except ValueError as e:
       log.warning("Recovered from mqtt library 'double disconnection' bug")

   # ----------------------------------------
   # Implement the EMA Status Message calback
   # -----------------------------------------

   def onStatus(self, message):
	'''Pick up status message and transform it into pure ASCII string'''
        self.__emastat = transform(message)

   # ---------------------------------
   # Implement the Event I/O Interface
   # ---------------------------------

   def onInput(self):
      '''
      Read from message buffer and notify handlers if message complete.
      Called from Server object
      '''
      log.debug("onInput will use mqtt lib for reading")
      self.__mqtt.loop_read()
   
   def fileno(self):
      '''Implement this interface to be added in select() system call'''
      return self.__mqtt.socket().fileno()


   # -----------------------------------------------
   # Implement the TOD Timer onNewInterval interface
   # -----------------------------------------------

   def onNewInterval(self, where, i):
      if self.__state == CONNECTED:
         if self.__histflag:
            self.publishBulkDump()
      else:
         log.warn("Not connected to broker: can't publish 24h Bulk data")
	
   # ----------------------------------------
   # Implement The Lazy interface
   # -----------------------------------------


   def work(self):
      '''
      Writes data to serial port configured at init. 
      Called periodically from a Server object.
      Write blocking behaviour.
      '''
      log.debug("mqttclient.work()")
      if not self.ema.isSyncDone():
         return
	 
      if self.__state == NOT_CONNECTED:
         self.connect()
      	 return

      # Do this only once in server lifetime
      if self.__state == CONNECTED and not self.__topics:
         self.__topics = True
         self.publishTopics()
         if self.__histflag:
            self.publishBulkDump()

      self.__count = (self.__count + 1) % 2
      if self.__state == CONNECTED and self.__count == 0:
         self.publish()

      self.__mqtt.loop_misc()

   # ----------------------------------------
   # Implement Command callbacks
   # -----------------------------------------

   def onPartialCommand(self, message, userdata):
      '''
      Partial bulk dump request command handler
      '''
      if len(message) == STATLEN:
        self.bulkDump.append(transform(message))
      else:
        self.bulkDump.append(message)
     

   def onCommandComplete(self, message, userdata):
      '''
      Bulk dump request command complete handler
      '''
      log.debug("onCommandComplete => %s", message)
      self.bulkDump.append(message)
      if self.page < FLASH_END :
        self.page += 1
        self.requestPage(self.page)
      else:
        date = message[10:20]
        log.info("Uploading last 24h (%s) of hourly minmax history to %s", date, MQTTClient.TOPIC_HISTORY)
        self.__mqtt.publish(topic=MQTTClient.TOPIC_HISTORY, payload='\n'.join(self.bulkDump), qos=2, retain=True)
        log.info("Upload complete, processed %d lines", len(self.bulkDump))

   # --------------
   # Helper methods
   # --------------


   def connect(self):
      '''
      Connect to MQTT Broker with parameters passed at creation time.
      Add MQTT library to the (external) EMA I/O event loop. 
      '''
      try:
        log.info("Connecting to MQTT Broker %s:%s", self.__host, self.__port)
        self.__mqtt.connect(self.__host, self.__port, self.__period)
        self.__state = CONNECTING
        self.ema.addReadable(self)
      except Exception, e:
         log.error("Could not contact MQTT Broker %s: %s", self.__host, self.__port, e)
         self.__state = FAILED
         raise
   

   def publish(self):
      '''
      Publish real time individual readings to MQTT Broker
      '''
      # publish raw status line
      if self.__pubstat:
        self.__mqtt.publish(topic=MQTTClient.TOPIC_CURRENT_STATUS, payload=self.__emastat)
        self.__emastat = "()"

      # publish last current values
      for device in self.ema.currentList:
        if ('mqtt','current') in device.publishable:
          try:
            for key, value in device.current.iteritems():
              log.debug("%s publishing current %s => %s %s", device.name, key, value[0], value[1])
	      topic   = "%s/current/%s/%s" % (self.__id, device.name, key)
              payload = "%s %s" % value 
              self.__mqtt.publish(topic=topic, payload=payload)
          except IndexError as e:
            log.error("publish(current) Exception: %s reading device=%s", e, device.name)
      
      # Publish averages
      for device in self.ema.averageList:
        if ('mqtt','average') in device.publishable:
          try:
            for key, value in device.average.iteritems():
              log.debug("%s publishing average %s => %s %s", device.name, key, value[0], value[1])
	      topic   = "%s/average/%s/%s" % (self.__id, device.name, key)
              payload = "%s %s" % value 
              self.__mqtt.publish(topic=topic, payload=payload)
          except IndexError as e:
            log.error("publish(average) Exception: %s reading device=%s", e, device.name)

      if self.__stats % NPUBLISH == 0:
         log.info("Published %d measurements" % self.__stats)
      self.__stats += 1


   def publishTopics(self):
      '''
      Publish active topics
      '''
      topics = [MQTTClient.TOPIC_EVENTS, MQTTClient.TOPIC_HISTORY]
      if self.__pubstat:
        topics.append(MQTTClient.TOPIC_CURRENT_STATUS)

      for device in self.ema.currentList:
        if ('mqtt','current') in device.publishable:
          try:
            for key in device.current.iterkeys():
              topics.append('%s/current/%s/%s' % (self.__id, device.name, key))
          except IndexError as e:
            log.error("Exception: %s listing device key=%s", e, device.name)
            continue

      for device in self.ema.averageList:
        if ('mqtt','average') in device.publishable:
          try:
            for key in device.average.iterkeys():
              topics.append('%s/average/%s/%s' % (self.__id, device.name, key))
          except IndexError as e:
            log.error("Exception: %s listing device key=%s", e, device.name)
            continue
      self.__mqtt.publish(topic=MQTTClient.TOPIC_TOPICS, payload='\n'.join(topics), qos=2, retain=True)

      log.info("Sent active topics to %s", MQTTClient.TOPIC_TOPICS)
      

   def requestPage(self, page):
      '''
      Request current flash page to EMA
      '''
      log.debug("requesting page %d", page)
      cmd = BulkDumpCommand(self.ema, retries=0, **COMMAND[-1])
      cmd.request("(@H%04d)" % page, page)


   

   def publishBulkDump(self):
      '''
      Publish last 24h bulk dump
      '''
      self.bulkDump = []
      self.page = FLASH_START
      self.requestPage(self.page)
      log.debug("Request to publish 24h Bulk data")


if __name__ == "__main__":
      pass
