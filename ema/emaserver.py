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
#
# This object is the global server implementing the EMA daemon service
# It contains an amount of embedded to delegate responsibilities
# It acts as a mediator between these embedded objects too.
#
# Its main responsibilitioers are
#
# 1) Gobal initialization, mainly from a config file
# 2) Maintaining list of subscribed objects to certain events
# 3) Dispatchnig message events from Serial Port and UDP ports
#  to the proper embedded objects
#
# ======================================================================

import logging
import re
import os
import sys
import datetime
import errno

from server.logger import logToConsole, logToFile, sysLogInfo, sysLogError
from server import Server


import serdriver
import udpdriver
import mqttclient
import server
import notifier
import genpage
import command

from emaproto import STATLEN, MTCUR, SMTB, encodeFreq

import dev.rtc         as rtc
import dev.watchdog    as wdog
import dev.voltmeter   as volt
import dev.barometer   as barom
import dev.rain        as rain
import dev.cloudpelt   as cloud
import dev.pyranometer as pyran
import dev.photometer  as photom
import dev.thermometer as thermom
import dev.anemometer  as anemom
import dev.pluviometer as pluviom
import dev.thermopile  as thermop
import dev.relay       as relay
import dev.todtimer    as todtimer

# Only Python 2
import ConfigParser

log = logging.getLogger('emaserver')

from default import VERSION_STRING, CONFIG_FILE

class EMAServer(Server):
        
   PERIOD = 5

   # Unsolicited Responses Patterns
   URPAT = ( '\(\d{2}:\d{2}:\d{2} wait\)' ,            # Photometer 1
           '\(\d{2}:\d{2}:\d{2} mv:\d{2}\.\d{2}\)' , # Photometer 2
           '\(>10[01] ([+-]\d+\.\d+)\)',             # Thermopile I2C
           '\( \)',                                  # ping echo
         )

   def __init__(self, options):
      self.parseCmdLine(options)
      server.Server.__init__(self)
      self.pattern = [re.compile(p) for p in EMAServer.URPAT]
      self.syncDone = False
      self.responseHandlers   = []  # parameter object response list
      self.syncList           = []  # parameter object list for sync purposes
      self.statusList         = []    # device list handling status messages
      self.currentList        = []  # devices list holding current measurements
      self.averageList        = []  # devices list holding average measurements
      self.thresholdList      = []  # devices list containing thresholds
      self.parameterList      = []  # devices lists containing calibraton constants
      self.commandList        = []  # command list with active external commands
      self.build()
      self.sync()                # start the synchronization process

   def parseCmdLine(self, opts):
      '''Parses the comand line looking for the config file path 
      and optionally console output'''
      sysLogInfo("argv[] array is %s" % str(sys.argv)) 
      if opts.console:
         logToConsole()
      self.__poweroff = opts.poweroff
      self.__cfgfile = opts.config or CONFIG_FILE
      if not (self.__cfgfile != None and os.path.exists(self.__cfgfile)):
         raise IOError(errno.ENOENT,"No such file or directory",self.__cfgfile)


   def parseConfigFile(self):
      '''Parses the config file looking for its own options'''
      log.setLevel(self.__parser.get("GENERIC", "generic_log"))
      toFile = self.__parser.getboolean("GENERIC","log_to_file")
      if(toFile):
         filename = self.__parser.get("GENERIC","log_file")
         policy = self.__parser.get("GENERIC","log_policy")
         max_size = self.__parser.getint("GENERIC","log_max_size")
         by_size = policy == "size" if True else False
         logToFile(filename, by_size, max_size)


   def reload(self):
      '''Support on-line service reloading'''
      pass            # unimplemented for the time being


   def build(self):
      '''Buld children objects from configuration file'''

      self.__parser = ConfigParser.ConfigParser()
      self.__parser.optionxform = str
      self.__parser.read(self.__cfgfile)
      self.parseConfigFile()
      logging.getLogger().info("Starting %s, %s",VERSION_STRING, Server.FLAVOUR)
      log.info("Self power-off = %s", self.__poweroff)
      log.info("Loaded configuration from %s", self.__cfgfile)

      config = self.__parser

      self.syncNeeded = config.getboolean("GENERIC", "sync")
      self.uploadPeriod = config.getfloat("GENERIC", "upload_period")
      VECLEN =  int(round(self.uploadPeriod / EMAServer.PERIOD)) 
      lvl = config.get("GENERIC", "generic_log")
      command.log.setLevel(lvl)
      log.setLevel(lvl)

      # Serial Port object Building
      port = config.get("SERIAL", "serial_port")
      baud = config.getint("SERIAL", "serial_baud")
      opts = dict(config.items("SERIAL"))
      lvl = config.get("SERIAL", "serial_log")
      serdriver.log.setLevel(lvl)

      self.serdriver = serdriver.SerialDriver(port,baud,**opts)
      self.serdriver.addHandler(self)
      self.addLazy(self.serdriver)
      self.addReadable(self.serdriver)
            
      # Multicast UDP object building
      ip      = config.get("UDP", "mcast_ip")
      rx_port = config.getint("UDP", "udp_rx_port")
      tx_port = config.getint("UDP", "udp_tx_port")
      self.multicast = config.getboolean("UDP", "mcast_enabled")
      opts    = dict(config.items("UDP"))
      lvl = config.get("UDP", "udp_log")
      udpdriver.log.setLevel(lvl)

      self.udpdriver = udpdriver.UDPDriver(ip, rx_port, tx_port, **opts)
      self.udpdriver.addHandler(self)
      self.addReadable(self.udpdriver)

      # Builds Notifier object which executes scripts
      self.notifier = notifier.Notifier()

      # Build EMA HTML Page Generator object
      #self.genpage = genpage.HTML(self, config)

      # Time of Day Timer object 
      self.todtimer = todtimer.Timer(self, config, self.__poweroff)

      # MQTT Driver object 
      self.mqttclient = mqttclient.MQTTClient(self, config, **opts)

      # Builds RTC Object
      self.rtc = rtc.RTC(self, config)
      
      # Builds Watchdog object
      self.watchdog = wdog.WatchDog(self, config)

      # Build Auxiliar Relay Object
      self.auxRelay = relay.AuxRelay(self, config, VECLEN)

      # Build RoofRelay Object
      self.roofRelay  = relay.RoofRelay(self, config, VECLEN)

      # Builds Voltmeter object
      self.voltmeter = volt.Voltmeter(self, config, VECLEN)
   
      # Builds Photometer Sensor object
      self.photometer = photom.Photometer(self, config, int(round(self.uploadPeriod / 60))) 

      # Builds Barometer object
      self.barometer = barom.Barometer(self, config, VECLEN) 
      
      # Builds  Rain Detector Object
      self.rainsensor = rain.RainSensor(self, config, VECLEN)

      # Builds Cloud Sensor object
      self.clouds = cloud.CloudSensor(self, config, VECLEN)

      # Builds Pyranometer Sensor object
      self.pyranometer = pyran.Pyranometer(self, config, VECLEN)

      # Builds Thermometer Object
      self.thermometer = thermom.Thermometer(self, config, VECLEN)

      # Builds Anemometer Object
      self.anemometer = anemom.Anemometer(self, config, VECLEN)

      # Builds Pluviometer Object
      self.pluviometer = pluviom.Pluviometer(self, config, VECLEN)

      # Build objects without configuration values
      self.thermopile = thermop.Thermopile(self, config, VECLEN)
      

   # ----------------------------------
   # Synchronization at startup process
   # ----------------------------------

   def sync(self):
      '''Trigger configurable parameter syncronization with EMA hardware'''
      for obj in self.syncList:
         obj.sync()      


   def addRequest(self, obj):
      '''
      Add a parameter request to the lists of pending responses.
      Used by AbstractParameter.
      '''
      self.responseHandlers.append(obj)


   def delRequest(self, obj):
      '''
      Deleted a parameter request from the list of pending responses.
      Used by AbstractParameter.
      '''
      self.responseHandlers.pop(self.responseHandlers.index(obj))


   def addSync(self, obj):
      '''Add object with a sync() method for parameter sync at startup'''
      self.syncList.append(obj)


   def isSyncDone(self):
      if self.syncDone:
         return True
      accum = True
      for obj in self.syncList:
         accum &= obj.isDone()
      self.syncDone = accum
      return accum

   # ---------------------------------------------------
   # Management of rendering results to local HTML pages
   #----------------------------------------------------

   def addCurrent(self, obj):
      '''Add object implementing current @property'''
      self.currentList.append(obj)

   def addAverage(self, obj):
      '''Add object implementing average @property'''
      self.averageList.append(obj)

   def addThreshold(self, obj):
      '''Add object implementing threshold @property'''
      self.thresholdList.append(obj)

   def addParameter(self, obj):
      '''Add object implementing parameter @property'''
      self.parameterList.append(obj)

   # -------------------------------------------------
   # Specialied handlers from incoming Serial Messages
   # -------------------------------------------------

   def subscribeStatus(self, obj):
      '''Add object collecting measurements from 
      periodic status message, implementing onStatus()'''
      self.statusList.append(obj)


   def handleStatus(self,message):
      '''Handle EMA periodic status messages'''
      timestamp = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.5)
      flag = False
      # Only handles current value messages (type 'a')
      # if and only if al paramters are syncronized
      if len(message) == STATLEN and message[SMTB] == MTCUR and self.isSyncDone():
         # Loop to distribute to interested parties
         for obj in self.statusList:
            obj.onStatus(message, timestamp)
         self.broadcastUDP(message)
         flag = True
      return flag


   def handleUnsolicited(self, message):
      '''Handle most common unsolicited responses whose patterns are declared in URPAT'''
      flag = False
      for pat in self.pattern:
         matched = pat.search(message)
         if matched:
            index = self.pattern.index(pat)
            if   index == 0:  # start visual magnitude reading
               self.serdriver.hold(True)
            elif index == 1: # end visual magnitude reading
               self.serdriver.hold(False)
               self.photometer.add(message, matched)
            elif index == 2: # Thermopile reading
               self.thermopile.add(message, matched)
            # by default, we don't don't broadcast unsolicited responses 
            # self.udpdriver.write(message) 
            flag = True
            self.broadcastUDP(message)
            break
      return flag


   def handleRequest(self, message):
      '''Handler for internal requests like Parameter sync requests'''
      flag = False
      for handler in self.responseHandlers:
         if handler.onResponseDo(message):
            flag = True
            self.broadcastUDP(message)
            break
      return flag


   def handleCommand(self, message):
      '''Handler for requests from external hosts'''
      flag = False
      for handler in self.commandList:
         if handler.onResponseDo(message):
            flag = True
            break
      return flag


   # --------------------------
   # Handling commands from UDP
   # --------------------------

   def addCommand(self, obj):
      '''
      Add an external command request to the lists of pending commands.
      '''
      self.commandList.append(obj)


   def delCommand(self, obj):
      '''
      Delete an external command request from the lists of pending commands.
      '''
      self.commandList.pop(self.commandList.index(obj))


   def broadcastUDP(self, message):
      if self.multicast:
         log.debug("Serial => UDP: %s", message)
         self.udpdriver.write(message)

   # ------------------------------------------
   # Event handlers from Serial and UDP Drivers
   # ------------------------------------------

   def onSerialMessage(self, message):
      '''
      Generic message handler that dispatches to more specialized message 
      handlers in turn, by priority
      '''
      if self.handleStatus(message):
         log.debug("handled as ordinary Status Message")
         return
      # Commands should be handled before parameter syncs
      # as they are more short-lived and there is an overlap
      # between RTC parameter sync and MinMax command (@H0300)
      if self.handleCommand(message):
         log.debug("handled as Command")
         return
      if self.handleRequest(message):
         log.debug("handled as parameter sync request")
         return
      if self.handleUnsolicited(message):
         log.debug("handled as ordinary Status Message")
         return
      
      log.debug("unhandled message from EMA")



   def onUDPMessage(self, message, origin):
      '''
      Handle incoming commands from UDP driver.
      Only create and execute command objects for implemented commands.
      '''
      cmddesc = command.match(message)
      if cmddesc:
         cmd = ExternalCommand(self, message, **cmddesc)
         cmd.request(usedata = origin)
      else:
         self.serdriver.write(message)
      
   # --------------
   # Server Control
   # --------------

   def stop(self):
      log.info("Shutting down EMA server")
      logging.shutdown()


   # -------------------------------------
   # EMA Average Status Message Formatting
   # -------------------------------------

   # It makes no sense to pick averages from:
   # - Relay open/close state
   # - Accumulated rain
   # - Already averaged wind speed over 10m
   # In these cases, we pick up the newest sample

   def formatAverageStatus(self):
      '''Formats a similar status message but with averages'''

      roof  = self.roofRelay.raw_current[relay.RoofRelay.OPEN]
      aux   = self.auxRelay.raw_current[relay.AuxRelay.OPEN]
      pluAc = round(self.pluviometer.raw_current[pluviom.Pluviometer.ACCUMULATED])

      volti = round(self.voltmeter.raw_average[volt.Voltmeter.VOLTAGE])
      wet   = round(self.rainsensor.raw_average[rain.RainSensor.RAIN])
      clou  = round(self.clouds.raw_average[cloud.CloudSensor.CLOUD])
      plu   = round(self.pluviometer.raw_average[pluviom.Pluviometer.CURRENT])
      led   = round(self.pyranometer.raw_average[pyran.Pyranometer.IRRADIATION])
      freq = encodeFreq(self.photometer.raw_average[photom.Photometer.FREQUENCY])
      mydict = self.barometer.raw_average
      calp   = round(mydict[barom.Barometer.CAL_PRESSURE])
      absp   = round(mydict[barom.Barometer.PRESSURE])

      mydict = self.thermometer.raw_average
      tamb   = round(mydict[thermom.Thermometer.AMBIENT])
      hum    = round(mydict[thermom.Thermometer.HUMIDITY])
      dew    = round(mydict[thermom.Thermometer.DEWPOINT])

      mydict = self.anemometer.raw_current
      ane    = round(mydict[anemom.Anemometer.SPEED])
      ane10  = round(mydict[anemom.Anemometer.SPEED10])
      wind   = round(self.anemometer.raw_average[anemom.Anemometer.DIRECTION])

      values = {
         'roof':  roof,
         'aux':   aux,
         'volt':  volti,
         'wet':   wet,
         'clou':  clou,
         'calp':  calp,
         'absp':  absp,
         'plu':   plu,
         'pluAc': pluAc,
         'led':   led,
         'freq':  freq,
         'tamb':  tamb,
         'hum':   hum,
         'dew':   dew,
         'ane10': ane10,
         'ane':   ane,
         'wind':  wind
         }

      fmt = "(%(roof)c%(aux)c%(volt)03d %(wet)03d %(clou)03d %(calp)05d %(absp)05d %(plu)04d %(pluAc)04d %(led)03d %(freq)s %(tamb)+04d %(hum)03d %(dew)+04d +000 %(ane10)03d %(ane)04d %(wind)03d p0000)"
      return fmt % values

# ===========================================================================
# COMMAND CLASS FOR FORWARDING SERIAL => UDP
# ===========================================================================


class ExternalCommand(command.Command):
   '''Handles external commands comming from UDP messages'''

   def onPartialCommand(self, message, userdata):
      '''Forward it to UDP driver'''
      self.ema.udpdriver.write(message, userdata[0])

   def onCommandComplete(self, message, userdata):
      '''Forward it to UDP driver'''
      self.ema.udpdriver.write(message, userdata[0])



if __name__ == "__main__":
   import logger
   logger.logToConsole()
   server = EMAServer('../config')
   server.run()
   server.stop()
