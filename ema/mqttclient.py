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


log = logging.getLogger('mqttclien')

def setLogLevel(level):
    log.setLevel(level)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
   userdata.on_connect(client, flags, rc)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    userdata.on_message(client, msg)


class MQTTClient(Lazy):

   NSTATS = 1000  # Print number of reads each NSTATs times
	
   def __init__(self, host, port, **kargs):
      Lazy.__init__(self)
      self.__host  = host
      self.__port  = port
      self.__timeout = 60
      self.__client =  mqtt.Client(client_id="EMA@crispi", userdata=self)
      self.__client.on_connect = on_connect
      self.__client.on_message = on_message
      
      # An EMA message, surronded by brackets
      try:
        self.__client.connect(host, port, self.__timeout)
      except Exception, e:
         log.error("Could not contact MQTT Server %s: %s", self.__host, self.__port, e)
         raise
      log.info("Connected to MQTT Server %s:%s", self.__host, self.__port)

   # ----------------------------------------
   # MQTT Callbacks
   # -----------------------------------------
   def on_connect(self, client, flags, rc):
     log.debug("Connected with result code "+str(rc))
     # Subscribing in on_connect() means that if we lose the connection and
     # reconnect then subscriptions will be renewed.
     client.subscribe("$SYS/#")
   
   def on_message(self, client, msg):
     log.debug("Topic: %s , Payload: %s" % (msg.topic, msg.payload))


   # ----------------------------------------
   # Public interface exposed to upper layers
   # -----------------------------------------


   def write(self, message):
      '''
      Enqueues message to output queue
      '''
      pass



   def addHandler(self, object):
      '''Registers an object implementing a handle(message) method'''
      pass

   # --------------
   # Helper methods
   # --------------

   def work(self):
      '''
      Writes data to serial port configured at init. 
      Called periodically from a Server object.
      Write blocking behaviour.
      '''
      pass


   def read(self):
      '''
      Reads from serial port. 
      Return all available data in buffer.
      '''
      try:
	return 0
      except Exception, e:
         log.error("%s:",  e)
         raise

      

   def onInput(self):
      '''
      Read from message buffer and notify handlers if message complete.
      Called from Server object
      '''
      pass


   def fileno(self):
      '''Implement this interface to be added in select() system call'''
      pass      



if __name__ == "__main__":
      pass



