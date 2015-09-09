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
# An MQTT class implementing a MQTT client with a pere publishing-only
# behaviour. This is an stubborn client, it tries to reciver from network 
# errors and no disconnection requests are ever issued.
#
# This class ingerits from Lazy to periodically execute a work() procedure
# whichi s responsible of most of the things, including keeping the 
# connection alive
# The work() procedure exectues twice as fast as the keepalive timeout 
# specidied in the client MQTT library.
#
# ======================================================================

import logging
import paho.mqtt.client as paho
import socket
import datetime

from server import Lazy


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

class MQTTPublisher(Lazy):
   '''Pure MQTT publisher client'''

   # Maximun retry period
   MAX_PERIOD = 2*60*60

   def __init__(self, ema, parser, **kargs):
      lvl      = parser.get("MQTT", "mqtt_log")
      log.setLevel(lvl)
      ident            = parser.get("MQTT", "mqtt_id")
      host             = parser.get("MQTT", "mqtt_host")
      port             = parser.getint("MQTT", "mqtt_port")
      period           = parser.getint("MQTT", "mqtt_period")
      self.srv         = ema
      self.__id        = ident
      self.__once      = False
      self.__count     = 0
      self.__state     = NOT_CONNECTED
      self.__host      = host
      self.__port      = port
      self.__keepalive = period
      self.__initial_T = self.__keepalive / 2
      self.__period    = self.__initial_T
      self.__paho      =  paho.Client(client_id=ident+'@'+socket.gethostname(), 
                                     userdata=self, clean_session=False)
      self.__paho.on_connect    = on_connect
      self.__paho.on_disconnect = on_disconnect
      Lazy.__init__(self, self.__initial_T )
      ema.addLazy(self)

   # -----------------
   # API to subclasses
   # -----------------
   
   def connected(self):
      '''True if connected'''
      return self.__state == CONNECTED

   @property
   def id(self):
      '''return mqtt id'''
      return self.__id

   @property
   def mqtt(self):
      '''return mqtt object'''
      return self.__paho

   def onConnect(self):
      pass
   
   def publish(self):
      '''Called periodically'''
      pass

   def publishOnce(self):
      '''Called only once'''
      pass

   # ----------------------------------------
   # MQTT Callbacks
   # -----------------------------------------

   def on_connect(self, flags, rc):
      '''Send the initial event and set last will on unexpected diconnection'''
      if rc == 0:
         self.__period = self.__initial_T
         self.setPeriod(self.__initial_T)
         self.__state = CONNECTED
         self.onConnect()
         log.info("Connected sucessfully") 
      else:
         self.handleConnErrors()


   def on_disconnect(self, rc):
      log.warning("Unexpected disconnection, rc =%d" % rc)
      self.__state  = NOT_CONNECTED
      self.__once = False
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
      self.__paho.loop_read()
   
   def fileno(self):
      '''Implement this interface to be added in select() system call'''
      return self.__paho.socket().fileno()


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

      # Do this only once pero open conection
      if self.__state == CONNECTED and not self.__once:
         self.__once = True
         self.publishOnce()

      # Do this periodically
      self.__count = (self.__count + 1) % 2
      if self.__state == CONNECTED and self.__count == 0:
         self.publish()

      self.__paho.loop_misc()

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
         self.__paho.connect(self.__host, self.__port, self.__keepalive)
         self.srv.addReadable(self)
      except IOError as e:	
         log.error("%s",e)
         self.handleConnErrors()


   def handleConnErrors(self):
      self.__state = NOT_CONNECTED
      self.__period *= 2
      self.__period = min(self.__period, MQTTPublisher.MAX_PERIOD)
      self.setPeriod(self.__period)
      log.info("Connection failed, next try in %d sec.", self.__period)

