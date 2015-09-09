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
#
# This version publushes :
# - real time EMA status message, sampled every 1 minute approx.
# - a 24h min max dump to the MQTT broker
# - a 5m avaerage bulk dump
#
# by using objects of class Command and implementing the necessary callbacks.
# 
# ======================================================================


import datetime
import logging

from emaproto  import SPSB, STATLEN, STRFTIME
from command import Command, COMMAND
from dev.todtimer import Timer

from utils import chop
from mqttpublisher import MQTTPublisher

# FLASH Pages where History data re stored
FLASH_START = 300
FLASH_END   = 300

# tog info every NPLUBLIS times (ticks) 
NPUBLISH = 60


log = logging.getLogger('mqtt')



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



class MQTTClient(MQTTPublisher):

   # TOPIC Default vaules
   TOPIC_EVENTS         = "EMA/events"
   TOPIC_TOPICS         = "EMA/topics"
   TOPIC_HISTORY_MINMAX = "EMA/history/minmax"
   TOPIC_CURRENT_STATUS = "EMA/current/status"
   TOPIC_AVERAGE_STATUS = "EMA/average/status"

   def __init__(self, ema, parser, **kargs):
      lvl      = parser.get("MQTT", "mqtt_log")
      log.setLevel(lvl)
      histflag = parser.getboolean("MQTT", "mqtt_publish_history")
      publish_status = parser.getboolean("MQTT", "mqtt_publish_status")
      publish_what   = chop(parser.get("MQTT", "mqtt_publish_what"), ',')
      MQTTPublisher.__init__(self, ema, parser, **kargs)
      self.ema        = ema
      self.__histflag = histflag
      self.__pubstat  = publish_status
      self.__pubwhat  = publish_what
      self.__emastat  = "()"
      self.__stats    = 0
      ema.todtimer.addSubscriber(self)
      if publish_status:
         ema.subscribeStatus(self)
      MQTTClient.TOPIC_EVENTS         = "EMA/%s/events"  % self.id
      MQTTClient.TOPIC_TOPICS         = "EMA/%s/topics"  % self.id
      MQTTClient.TOPIC_HISTORY_MINMAX = "EMA/%s/history/minmax" % self.id
      MQTTClient.TOPIC_CURRENT_STATUS = "EMA/%s/current/status" % self.id
      MQTTClient.TOPIC_AVERAGE_STATUS = "EMA/%s/average/status" % self.id
      log.info("MQTT client created")


   # ----------------------------------------
   # Implement the EMA Status Message calback
   # -----------------------------------------

   def onStatus(self, message, timestamp):
      '''Pick up status message and transform it into pure ASCII string'''
      self.__emastat = [transform(message), 
                        timestamp.strftime(STRFTIME)]


   # -----------------------------------------------
   # Implement the TOD Timer onNewInterval interface
   # -----------------------------------------------

   def onNewInterval(self, where, i):
      if self.connected():
         if self.__histflag:
            self.publishMinMax24h()
      else:
         log.warn("Not connected to broker: can't publish minmax history")
	
   # --------------------------------
   # Implement the MQTT Publisher API
   # --------------------------------

   def onConnect(self):
      '''Send the initial event and set last will on unexpected diconnection'''
      self.mqtt.publish(MQTTClient.TOPIC_EVENTS,  
                        payload="EMA Server connected", 
                        qos=2, retain=True)
      self.mqtt.will_set(MQTTClient.TOPIC_EVENTS, 
                         payload="EMA Server disconnected", 
                         qos=2, retain=True)
      self.mqtt.will_set(MQTTClient.TOPIC_TOPICS, 
                         payload=MQTTClient.TOPIC_EVENTS, 
                         qos=2, retain=True)


   def publishOnce(self):
      self.publishTopics()
      if self.__histflag:
         self.publishMinMax24h()


   def publish(self):
      '''
      Publish readings to MQTT Broker
      '''
         
      self.publishCurrentStatus()
      self.publishAverageStatus()
      self.publishCurrent()
      self.publishAverages()

      if self.__stats % NPUBLISH == 0:
         log.info("Published %d measurements" % self.__stats)
      self.__stats += 1



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
         log.info("Uploading (%s) hourly minmax history to %s", date, MQTTClient.TOPIC_HISTORY_MINMAX)
         self.mqtt.publish(topic=MQTTClient.TOPIC_HISTORY_MINMAX, 
                           payload='\n'.join(self.bulkDump), qos=2, retain=True)
         log.info("Upload complete, processed %d lines", len(self.bulkDump))

   # --------------
   # Helper methods
   # --------------


   def publishCurrent(self):
      '''Publish current individual readings'''
      for device in self.srv.currentList:
         if ('mqtt','current') in device.publishable:
            try:
               for key, value in device.current.iteritems():
                  log.debug("%s publishing current %s => %s %s", 
                                 device.name, key, value[0], value[1])
                  topic  = "%s/current/%s/%s" % (self.id, device.name, key)
                  payload = "%s %s" % value 
                  self.mqtt.publish(topic=topic, payload=payload)
            except IndexError as e:
               log.error("publish(current) Exception: %s reading device=%s", e, device.name)


   def publishAverages(self):
      '''Publish averages individual readings'''      
      # Publish averages
      for device in self.srv.averageList:
         if ('mqtt','average') in device.publishable:
            try:
               for key, value in device.average.iteritems():
                  log.debug("%s publishing average %s => %s %s", 
                                  device.name, key, value[0], value[1])
                  topic = "%s/average/%s/%s" % (self.id, device.name, key)
                  payload = "%s %s" % value 
                  self.mqtt.publish(topic=topic, payload=payload)
            except IndexError as e:
               log.error("publish(average) Exception: %s reading device=%s", e, device.name)



   def publishTopics(self):
      '''
      Publish active topics
      '''
      topics = [MQTTClient.TOPIC_EVENTS, MQTTClient.TOPIC_HISTORY_MINMAX]
      if self.__pubstat:
         topics.append(MQTTClient.TOPIC_CURRENT_STATUS)

      for device in self.srv.currentList:
         if ('mqtt','current') in device.publishable:
            try:
               for key in device.current.iterkeys():
                  topics.append('%s/current/%s/%s' % (self.id,device.name,key))
            except IndexError as e:
               log.error("Exception: %s listing device key=%s", e, device.name)
               continue

      for device in self.srv.averageList:
         if ('mqtt','average') in device.publishable:
            try:
               for key in device.average.iterkeys():
                  topics.append('%s/average/%s/%s' % (self.id,device.name,key))
            except IndexError as e:
               log.error("Exception: %s listing device key=%s", e, device.name)
               continue

      self.mqtt.publish(topic=MQTTClient.TOPIC_TOPICS, 
                        payload='\n'.join(topics), qos=2, retain=True)
      log.info("Sent active topics to %s", MQTTClient.TOPIC_TOPICS)
      

   def publishCurrentStatus(self):
      # publish current raw status line
      if self.__pubstat and 'current' in self.__pubwhat:
         payload = '\n'.join(self.__emastat)
         self.mqtt.publish(topic=MQTTClient.TOPIC_CURRENT_STATUS, 
                           payload=payload)
         self.__emastat = []


   def publishAverageStatus(self):
      # publish average raw status line
      if self.__pubstat and 'average' in self.__pubwhat:
         # Choose a timespan from any device (should be the same across all)
         tNew, tOld, N =  self.srv.voltmeter.timespan()
         payload = [
             self.srv.formatAverageStatus(),
             tNew,strftime(STRFTIME),
             tOld.strftime(STRFTIME),
             N,
         ]
         payload = '\n'.join(payload)
         self.mqtt.publish(topic=MQTTClient.TOPIC_AVERAGE_STATUS, 
                           payload=payload)





   def requestPage(self, page):
      '''
      Request current flash page to EMA
      '''
      log.debug("requesting page %d", page)
      cmd = BulkDumpCommand(self.srv, retries=0, **COMMAND[-1])
      cmd.request("(@H%04d)" % page, page)


   def publishMinMax24h(self):
      '''
      Publish last 24h bulk dump
      '''
      self.bulkDump = []
      self.page = FLASH_START
      self.requestPage(self.page)
      log.debug("Request to publish 24h Bulk data")

