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

from emaproto  import SPSB, SMFB, SMFE, STATLEN, STRFTIME
from command import Command, COMMAND
from dev.todtimer import Timer

from utils import chop
from mqttpublisher import MQTTPublisher

# FLASH start Pages where historic data are stored
FLASH_MINMAX   = 300
FLASH_5MINAVER = 000

# tog info every NPLUBLIS times (ticks) 
NPUBLISH = 60


log = logging.getLogger('mqtt')



# Utility function 
def transform(message):
    '''
    Transform EMA status message into a pure ASCII string
    Voltage is not ASCII and it is formatted to a 3-digit value
    '''
    return "%s%03d%s" % (message[:SPSB], ord(message[SPSB]), message[SPSB+1:])

# =======================================
# HOURLY MINMAX BULK DUMP REQUEST COMMAND
# =======================================

class MinMaxCommand(Command):
   '''
   Commad subclass to handle bulk dump request and responses via callbacks
   '''

   # delegate to MQTT client object as it has all the needed context
   def onPartialCommand(self, message, userdata):
      '''
      Partial bulk dump handler
      '''
      self.ema.mqttclient.onMinMaxPartial(message,userdata)

   # delegate to MQTT client object as it has all he needed context
   def onCommandComplete(self, message, userdata):
      '''
      Bulk dump Command complete handler
      '''
      self.ema.mqttclient.onMinMaxComplete(message,userdata)


# =====================================
# AVERAGES 5m BULK DUMP REQUEST COMMAND
# ======================================

class AveragesCommand(Command):
   '''
   Commad subclass to handle bulk dump request and responses via callbacks
   '''

   # delegate to MQTT client object as it has all the needed context
   def onPartialCommand(self, message, userdata):
      '''
      Partial bulk dump handler
      '''
      self.ema.mqttclient.onAveragesPartial(message, userdata)

   # delegate to MQTT client object as it has all he needed context
   def onCommandComplete(self, message, userdata):
      '''
      Bulk dump Command complete handler
      '''
      self.ema.mqttclient.onAveragesComplete(message, userdata)

# =========================
# MQTT CLIENT CLASS FOR EMA
# =========================

class MQTTClient(MQTTPublisher):

   # TOPIC Default vaules
   TOPIC_EVENTS         = "EMA/events"
   TOPIC_TOPICS         = "EMA/topics"
   TOPIC_HISTORY_MINMAX = "EMA/history/minmax"
   TOPIC_CURRENT_STATUS = "EMA/current/status"
   TOPIC_AVERAGE_STATUS = "EMA/average/status"
   TOPIC_HISTORY_AVERAG = "EMA/history/average"

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
      self.__5m_tstamp = None
      ema.todtimer.addSubscriber(self)
      if publish_status:
         ema.subscribeStatus(self)
      MQTTClient.TOPIC_EVENTS         = "EMA/%s/events"          % self.id
      MQTTClient.TOPIC_TOPICS         = "EMA/%s/topics"          % self.id
      MQTTClient.TOPIC_HISTORY_MINMAX = "EMA/%s/history/minmax"  % self.id
      MQTTClient.TOPIC_HISTORY_AVERAG = "EMA/%s/history/average" % self.id
      MQTTClient.TOPIC_CURRENT_STATUS = "EMA/%s/current/status"  % self.id
      MQTTClient.TOPIC_AVERAGE_STATUS = "EMA/%s/average/status"  % self.id
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
            self.pubish5MinAver()
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
         self.publishAllBulkDumps()

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

   def onMinMaxPartial(self, message, userdata):
      '''
      Partial minmax bulk dump request command handler
      '''
      if self.minmax % 18 == 0:
         log.debug("onMinMaxPartial(%d)", self.minmax + 1)
      self.minmax += 1
      if len(message) == STATLEN:
         self.minmaxBulkDump.append(transform(message))
      else:
         self.minmaxBulkDump.append(message)
     

   def onMinMaxComplete(self, message, userdata):
      '''
      Minmax bulk dump request command complete handler
      '''
      self.minmaxBulkDump.append(message)
      date = message[10:20]
      log.info("Uploading (%s) hourly minmax history to %s", date, MQTTClient.TOPIC_HISTORY_MINMAX)
      self.mqtt.publish(topic=MQTTClient.TOPIC_HISTORY_MINMAX, 
                           payload='\n'.join(self.minmaxBulkDump), qos=2, retain=True)
      log.info("Upload complete, processed %d lines", len(self.minmaxBulkDump))


   def onAveragesPartial(self, message, userdata):
      '''
      Partial 5 min bulk dump request command handler
      '''
      if self.aver5min % 18 == 0:
         log.debug("onAveragesPartial(%d)", self.aver5min + 1)
      self.aver5min += 1
      minutes = int(message[SMFB:SMFE])*5
      hour = minutes // 60
      min  = minutes % 60
      ts = datetime.datetime.combine(datetime.date.today(), datetime.time(hour=hour, minute=min))
      self.averBulkDump.append( (transform(message), ts) )
           

   def onAveragesComplete(self, message, userdata):
      '''
      % min bulk dump request command complete handler
      '''
      minutes = int(message[SMFB:SMFE])*5
      hour = minutes // 60
      min  = minutes % 60
      ts = datetime.datetime.combine(datetime.date.today(), datetime.time(hour=hour, minute=min))
      self.averBulkDump.append( (transform(message), ts) )
      self.smartDump5min()

   # --------------
   # Publishing API
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
      if self.__pubstat and 'current' in self.__pubwhat:
         topics.append(MQTTClient.TOPIC_CURRENT_STATUS)
      if self.__pubstat and 'average' in self.__pubwhat:
         topics.append(MQTTClient.TOPIC_AVERAGE_STATUS)


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
             tNew.strftime(STRFTIME),
             tOld.strftime(STRFTIME),
             "(%d)" % N,
         ]
         payload = '\n'.join(payload)
         self.mqtt.publish(topic=MQTTClient.TOPIC_AVERAGE_STATUS, 
                           payload=payload)


   def publishAllBulkDumps(self):
      '''
      Publish last 24h min max
      '''
      self.averBulkDump = []
      self.minmaxBulkDump = []
      self.aver5min = 0
      self.minmax   = 0
      log.debug("Request to publish Bulk data")
      # Chain 2 commands.
      cmd1 = AveragesCommand(self.srv, "(@t%04d)" % FLASH_5MINAVER, retries=0, **COMMAND[-1])
      cmd2 = MinMaxCommand(self.srv, "(@H%04d)" % FLASH_MINMAX, next=cmd1, retries=0, **COMMAND[-2])
      cmd2.request()


   # --------------
   # Helper methods
   # --------------

   def smartDump5min(self):
      payload = [ msg[0] for msg in self.averBulkDump ]
      log.info("Uploading 5min averages history to %s", 
                  "EMA/emapi/history/average")
      self.mqtt.publish(topic=MQTTClient.TOPIC_HISTORY_AVERAG, payload='\n'.join(payload), qos=2, retain=True)
      log.info("Upload complete, processed %d lines", len(self.averBulkDump))
      

