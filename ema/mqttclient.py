# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
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
# ======================================================================

import logging
import paho.mqtt.client as mqtt
import socket

from server import Lazy, Server
from ema.emaproto  import SPSB, STATLEN
import command


# TOPIC Default vaules
TOPIC_EVENTS         = "EMA/events"
TOPIC_TOPICS         = "EMA/topics"
TOPIC_HISTORY        = "EMA/history"
TOPIC_CURRENT_STATUS = "EMA/current/status"

# FLASH PAges where History data re stored
FLASH_START = 300
FLASH_END   = 300

log = logging.getLogger('mqtt')

def setLogLevel(level):
    log.setLevel(level)


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


class MQTTClient(Lazy):


   # tog info every NPLUBLIS times 
   NPUBLISH = 60

   # MQTT Connection Status
   NOT_CONNECTED = 0
   CONNECTING    = 1
   CONNECTED     = 2
   FAILED        = 3
   DISCONNECTING = 4
	
   def __init__(self, ema, id, host, port, period, mqtt_publish_status, **kargs):
      Lazy.__init__(self, period / ( 2 * Server.TIMEOUT))
      TOPIC_EVENTS         = "%s/events"  % id
      TOPIC_TOPICS         = "%s/topics"  % id
      TOPIC_HISTORY        = "%s/history" % id
      TOPIC_CURRENT_STATUS = "%s/current/status" % id
      self.ema       = ema
      self.__id      = id
      self.__topics  = False
      self.__count   = 0
      self.__state   = MQTTClient.NOT_CONNECTED
      self.__work    = 0
      self.__host    = host
      self.__port    = port
      self.__period  = period
      self.__pubstat = mqtt_publish_status
      self.__emastat = "()"
      self.__mqtt    =  mqtt.Client(client_id=id+'@'+socket.gethostname(), userdata=self)
      self.__mqtt.on_connect    = on_connect
      self.__mqtt.on_disconnect = on_disconnect
      ema.addLazy(self)
      if mqtt_publish_status:
        ema.subscribeStatus(self)
      log.info("MQTT client created")

   # ----------------------------------------
   # MQTT Callbacks
   # -----------------------------------------

   def on_connect(self, flags, rc):
     '''Send the initial event and set last will on unexpected diconnection'''
     if rc == 0:
       self.__state = MQTTClient.CONNECTED
       self.__mqtt.publish(TOPIC_EVENTS,  payload="EMA Server connected", qos=2, retain=True)
       self.__mqtt.will_set(TOPIC_EVENTS, payload="EMA Server disconnected", qos=2, retain=True)
       self.__mqtt.will_set(TOPIC_TOPICS, payload="EMA/events", qos=2, retain=True)
       log.info("MQTT client conected successfully") 
     else:
       self.__state = MQTTClient.FAILED
       log.error("MQTT client connection failed, rc =%d" % rc)

   def on_disconnect(self, rc):
     self.__state  = MQTTClient.NOT_CONNECTED
     self.__topics = False
     self.ema.delReadable(self)
     if rc == 0:
       log.warning("MQTT client disconected successfully") 
     else:
       log.warning("MQTT client unexpected disconnection, rc =%d" % rc)


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
	 
      if self.__state == MQTTClient.NOT_CONNECTED:
         self.connect()
      	 return

      if self.__state == MQTTClient.CONNECTED and not self.__topics:
         self.__topics = True
         self.publishTopics()
         self.publishBulkDump()

      self.__work = (self.__work + 1) % 2
      if self.__state == MQTTClient.CONNECTED and self.__work == 0:
         self.publish()

      self.__mqtt.loop_misc()

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
        self.__state = MQTTClient.CONNECTING
        self.ema.addReadable(self)
      except Exception, e:
         log.error("Could not contact MQTT Broker %s: %s", self.__host, self.__port, e)
         self.__state = MQTTClient.FAILED
         raise
   

   def publish(self):
      '''
      Publish real time individual readings to MQTT Broker
      '''
      if self.__pubstat:
        self.__mqtt.publish(topic=TOPIC_CURRENT_STATUS, payload=self.__emastat)
        self.__emastat = "()"

      for device in self.ema.currentList:
        if 'mqtt' in device.publishable:
          try:
            for key, value in device.current.iteritems():
              log.debug("%s publishing current %s => %s %s", device.name, key, value[0], value[1])
	      topic   = "%s/current/%s-%s" % (self.__id, device.name, key)
              payload = "%s %s" % value 
              self.__mqtt.publish(topic=topic, payload=payload)
          except IndexError as e:
            log.error("Exception: %s reading device=%s", e, device.name)
      self.__count += 1
      if self.__count % MQTTClient.NPUBLISH == 1:
         log.info("Published %d measurements" % self.__count)


   def publishTopics(self):
      '''
      Publish active topics
      '''
      topics = [TOPIC_EVENTS, TOPIC_HISTORY]
      if self.__pubstat:
        topics.append(TOPIC_CURRENT_STATUS)

      for device in self.ema.currentList:
        if 'mqtt' in device.publishable:
          try:
            for key in device.current.iterkeys():
              topics.append('%s/current/%s-%s' % (self.__id, device.name, key))
          except IndexError as e:
            log.error("Exception: %s listing device key=%s", e, device.name)
            continue
      self.__mqtt.publish(topic=TOPIC_TOPICS, payload='\n'.join(topics), qos=2, retain=True)
      log.info("Sent active topics to %s",TOPIC_TOPICS)
      

   def requestPage(self, page):
      '''
      Request current flash page to EMA
      '''
      log.debug("requesting page %d", page)
      cmd = command.Command(self.ema, retries=0, **command.COMMAND[-1])
      cmd.setCommandHandler(self)
      cmd.request("(@H%04d)" % page, page)


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
        date = message[10:19]
        log.debug("Collectd %d lines", len(self.bulkDump))
        log.info("Uploading %d days of 24h history (%s) to %s", FLASH_END + 1 - FLASH_START, date, TOPIC_HISTORY)
        self.__mqtt.publish(topic=TOPIC_HISTORY, payload='\n'.join(self.bulkDump), qos=2, retain=True)


   def publishBulkDump(self):
      '''
      Publish last 24h bulk dump
      '''
      self.bulkDump = []
      self.page = FLASH_START
      self.requestPage(self.page)

if __name__ == "__main__":
      pass
