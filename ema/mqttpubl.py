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
import datetime

from server import Lazy, Server


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

class MQTTPublisher(Lazy):
   '''Pure MQTT publisher client'''


   def __init__(self, ema, parser, **kargs):
      lvl      = parser.get("MQTT", "mqtt_log")
      log.setLevel(lvl)
      id       = parser.get("MQTT", "mqtt_id")
      host     = parser.get("MQTT", "mqtt_host")
      port     = parser.getint("MQTT", "mqtt_port")
      period   = parser.getint("MQTT", "mqtt_period")
      Lazy.__init__(self, period / 2.0 )
      self.TOPIC_EVENTS         = "EMA/%s/events"  % id
      self.TOPIC_TOPICS         = "EMA/%s/topics"  % id
      self.TOPIC_HISTORY_MINMAX = "EMA/%s/history/minmax" % id
      self.TOPIC_CURRENT_STATUS = "EMA/%s/current/status" % id
      self.srv        = ema
      self.topics     = []
      sefl.topicsdir  = ""
      self.topicsroot = ""
      self.id         = id
      self.__topics   = False
      self.__stats    = 0
      self.__count    = 0
      self.__state    = NOT_CONNECTED
      self.__host     = host
      self.__port     = port
      self.__period   = period
      self.__pubstat  = publish_status
      self.__mqtt     =  mqtt.Client(client_id=id+'@'+socket.gethostname(), 
                                     userdata=self, clean_session=False)
      self.__mqtt.on_connect    = on_connect
      self.__mqtt.on_disconnect = on_disconnect
      srv.addLazy(self)
      log.info("MQTT client created")

   # ----------------------------------------
   # Topics handling
   # -----------------------------------------

   def addTopics(self, root="", topicdir, lastwill=[], topics=[]):
      self.topics = topics
      self.topicsdir = topicdir
      self.lastwill = lastwill

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
         log.info("Conected sucessfully") 
      else:
         self.__state = FAILED
         log.error("Connection failed, rc =%d" % rc)

   def on_disconnect(self, rc):
      log.warning("Unexpected disconnection, rc =%d" % rc)
      self.__state  = NOT_CONNECTED
      self.__topics = False
      try:
         self.srv.delReadable(self)
      except ValueError as e:
         log.warning("Recovered from mqtt library 'double disconnection' bug")

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
      if not self.srv.isSyncDone():
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
         self.__state = CONNECTING
         self.__mqtt.connect(self.__host, self.__port, self.__period)
         self.srv.addReadable(self)
      except IOError, e:	
         log.error("%s",e)
         if e.errno == 101:
            log.warning("Trying to connect on the next cycle")
            self.__state = NOT_CONNECTED
         else:
            self.__state = FAILED
            raise
   

   def publish(self):
      '''
      Publish real time individual readings to MQTT Broker
      '''
      pass	

   def publishTopics(self):
      '''
      Publish active topics
      '''
      pass


if __name__ == "__main__":
      pass
