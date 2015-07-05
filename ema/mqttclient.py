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

from server import Lazy


log = logging.getLogger('mqttadapt')

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


class MQTTClient(Lazy):

   NOT_CONNECTED = 0
   CONNECTING    = 1
   CONNECTED     = 2
   FAILED        = 3
   DISCONNECTING = 4
	
   def __init__(self, ema, host, port, **kargs):
      Lazy.__init__(self,5)
      self.__state = MQTTClient.NOT_CONNECTED
      self.ema   = ema
      self.__host  = host
      self.__port  = port
      self.__timeout = 60
      self.__mqtt =  mqtt.Client(client_id="EMA@crispi", userdata=self)
      self.__mqtt.on_connect    = on_connect
      self.__mqtt.on_disconnect = on_disconnect
      self.__mqtt.on_message    = on_message
      ema.addLazy(self)
      log.info("MQTT client created")

   # ----------------------------------------
   # MQTT Callbacks
   # -----------------------------------------

   def on_connect(self, flags, rc):
     if rc == 0:
       self.__state = MQTTClient.CONNECTED
       log.info("MQTT client conected successfully") 
       # Subscribing in on_connect() means that if we lose the connection and
       # reconnect then subscriptions will be renewed.
       #self.__mqtt.subscribe("$SYS/#")
     else:
       self.__state = MQTTClient.FAILED
       log.error("MQTT client connection failed, rc =%d" % rc)

   def on_disconnect(self, rc):
     self.__state = MQTTClient.NOT_CONNECTED
     self.ema.delReadable(self)
     self.ema.delWritable(self)
     if rc == 0:
       log.info("MQTT client disconected successfully") 
     else:
       log.error("MQTT client unexpected disconnection, rc =%d" % rc)

   # Currently unusued
   def on_message(self,  msg):
     log.debug("Topic: %s , Payload: %s" % (msg.topic, msg.payload))


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
   
   def onOutput(self):
      '''
      Write Event handler
      '''
      log.debug("onOutput will use test mqtt lib for writting")
      if self.__mqtt.want_write():
         log.debug("onOutput will use mqtt lib for writting")
         self.__mqtt.loop_write()

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
      if not self.ema.isSyncDone():
         return
	 
      if self.__state == MQTTClient.NOT_CONNECTED:
         self.connect()
      	 return

      if self.__state == MQTTClient.CONNECTED:
         self.publish()
      	 return

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
        self.__mqtt.connect(self.__host, self.__port, self.__timeout)
        self.__state = MQTTClient.CONNECTING
      except Exception, e:
         log.error("Could not contact MQTT Broker %s: %s", self.__host, self.__port, e)
         self.__state = MQTTClient.FAILED
         raise
      self.ema.addReadable(self)
      self.ema.addWritable(self)
   
   def disconect(self):
      '''
      Disconnect from the MQTT Broker.
      '''
      self.__mqtt.disconnect()

   def publish(self):
      '''
      Publish real time individual readings to MQTT Broker
      '''
      log.debug("Publish Individual readings")
      for device in self.ema.currentList:
        for key, value in device.current.iteritems():
          log.debug("%s publishing current %s => %s %s", device.name, key, value[0], value[1])
	  topic   = "EMA/current/%s" % key
          payload = "%s %s" % value 
          self.__mqtt.publish(topic=topic, payload=payload)



if __name__ == "__main__":
      pass
