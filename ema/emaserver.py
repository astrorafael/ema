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


import logger
import serdriver
import udpdriver
import mqttclient
import server
import notifier
import genpage
import command

from emaproto import STATLEN, MTCUR, SMTB

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



log = logging.getLogger('emaserver')

def setLogLevel(level):
	log.setLevel(level)


def parseLogLevel(levelstring):
	lvl = 'logging.' + levelstring
	try:
		return eval(lvl)
	except:
		return logging.NOTSET


# Only Python 2
import ConfigParser as parser

class EMAServer(server.Server):

	PERIOD = 5

	# Unsolicited Responses Patterns
	URPAT = ( '\(\d{2}:\d{2}:\d{2} wait\)' ,            # Photometer 1
			  '\(\d{2}:\d{2}:\d{2} mv:\d{2}\.\d{2}\)' , # Photometer 2
			  '\(>10[01] ([+-]\d+\.\d+)\)',             # Thermopile I2C
			  '\( \)',                                  # ping echo
		   )

	def __init__(self, configfile=None):
		server.Server.__init__(self)
		self.pattern = [re.compile(p) for p in EMAServer.URPAT]
		self.syncDone = False
		self.responseHandlers   = []	# parameter object response list
		self.syncList           = []	# parameter object list for sync purposes
		self.statusList         = []    # device list handling status messages
		self.currentList        = []	# devices list holding current measurements
		self.averageList        = []	# devices list holding average measurements
		self.thresholdList      = []	# devices list containing thresholds
		self.parameterList      = []	# devices lists containing calibraton constants
		self.commandList        = []	# command list with active external commands
		self.buildFrom(configfile)
		self.sync()						# start the synchronization process


	def buildFrom(self, configfile):
		'''Buld children objects from configuration file'''

		if not (configfile != None and os.path.exists(configfile)):
			log.error("No configuration is given. Exiting ...")
			return

		log.info("Loading configuration from %s" % configfile)
		config = parser.ConfigParser()
		config.optionxform = str
		config.read(configfile)

		self.syncNeeded = config.getboolean("GENERIC", "sync")
		self.uploadPeriod = config.getfloat("GENERIC", "upload_period")
		VECLEN =  int(round(self.uploadPeriod / EMAServer.PERIOD)) 
		lvl = config.get("GENERIC", "generic_log")
		lvl = parseLogLevel(lvl)
		command.setLogLevel(lvl)
		genpage.setLogLevel(lvl)
		setLogLevel(lvl)

		# Serial Port object Building
		port = config.get("SERIAL", "serial_port")
		baud = config.getint("SERIAL", "serial_baud")
		opts = dict(config.items("SERIAL"))
		lvl = config.get("SERIAL", "serial_log")
		serdriver.setLogLevel(parseLogLevel(lvl))

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
		udpdriver.setLogLevel(parseLogLevel(lvl))

		self.udpdriver = udpdriver.UDPDriver(ip, rx_port, tx_port, **opts)
		self.udpdriver.addHandler(self)
		self.addReadable(self.udpdriver)

		# Builds Notifier object which executes scripts
		self.notifier = notifier.Notifier()

		# MQTT Driver object 
 		mqtt_id     = config.get("MQTT", "mqtt_id")
		mqtt_host   = config.get("MQTT", "mqtt_host")
        	mqtt_port   = config.getint("MQTT", "mqtt_port")
		mqtt_period = config.getint("MQTT", "mqtt_period")
		mqtt_historic = config.getint("MQTT", "mqtt_period_historic")
		mqtt_publish_status = config.getboolean("MQTT", "mqtt_publish_status")
		mqtt_poweroff = config.getboolean("MQTT", "mqtt_energy_savings")
		lvl = config.get("MQTT", "mqtt_log")
                mqttclient.setLogLevel(parseLogLevel(lvl))
		self.mqttclient = mqttclient.MQTTClient(self, mqtt_id, mqtt_host, mqtt_port, mqtt_period, mqtt_historic, mqtt_publish_status, mqtt_poweroff, **opts)

		# Builds RTC Object
		deltaT = config.getint("RTC", "rtc_delta")   
		N = config.getfloat("RTC", "rtc_period")
		N =  int(round(N / EMAServer.PERIOD))  
		lvl = config.get("RTC", "rtc_log")
		rtc.setLogLevel(parseLogLevel(lvl))    
		self.rtc = rtc.RTC(self, deltaT, N)
		

		# Builds Watchdog object
		keepalive = config.getint("WATCHDOG", "keepalive")
		lvl = config.get("WATCHDOG", "wdog_log")
		wdog.setLogLevel(parseLogLevel(lvl))
		self.watchdog = wdog.WatchDog(self,keepalive)

		# Build Auxiliar Relay Object
		if config.has_section("AUX_RELAY"):
			aux_mode = config.get("AUX_RELAY", "aux_mode")
			aux_on   = config.get("AUX_RELAY", "aux_on") 
			aux_off  = config.get("AUX_RELAY", "aux_off")
			aux_relay_script = config.get("AUX_RELAY","aux_relay_script")
			aux_relay_mode  = config.get("AUX_RELAY","aux_relay_mode")
			aux_relay_publish = config.get("AUX_RELAY","aux_relay_publish").split(',')
			lvl = config.get("AUX_RELAY", "aux_relay_log")
			relay.setLogLevel(parseLogLevel(lvl))       
			self.auxRelay = relay.AuxRelay(self, 
									aux_mode, aux_on, aux_off, VECLEN,aux_relay_publish) 

		# Build RoofRelay Object
		if config.has_section("ROOF_RELAY"):
			roof_relay_publish = config.get("ROOF_RELAY","roof_relay_publish").split(',')
			roof_relay_script = config.get("ROOF_RELAY","roof_relay_script")
			roof_relay_mode = config.get("ROOF_RELAY","roof_relay_mode")

		self.roofRelay  = relay.RoofRelay(self,VECLEN,roof_relay_publish)

		# Builds Voltmeter object
		self.voltmeter = volt.Voltmeter(self, config, VECLEN)
	
		# Builds (optional) Photometer Sensor object
		# Photometer is updated every 60 seconds
		if config.has_section("PHOTOMETER"):
			phot_publish = config.get("PHOTOMETER","phot_publish").split(',')
			phot_offset  = config.getfloat("PHOTOMETER", "phot_offset")
			phot_thres   = config.getfloat("PHOTOMETER", "phot_thres")
			lvl = config.get("PHOTOMETER", "phot_log")
			photom.setLogLevel(parseLogLevel(lvl))
			self.photometer = photom.Photometer(self, 
												phot_thres, 
												phot_offset,
												int(round(self.uploadPeriod / 60)),phot_publish)

		# Builds (optional) Barometer object
		if config.has_section("BAROMETER"):
			baro_publish = config.get("BAROMETER","barom_publish").split(',')
			baro_height = config.getfloat("BAROMETER", "barom_height")
			baro_offset = config.getfloat("BAROMETER", "barom_offset")
			lvl = config.get("BAROMETER", "barom_log")
			barom.setLogLevel(parseLogLevel(lvl))
			self.barometer = barom.Barometer(self, 
								baro_height, baro_offset, VECLEN, baro_publish)
			
		
		# Builds (optional) Rain Detector Object
		if config.has_section("RAIN"):
			rain_publish = config.get("RAIN","rain_publish").split(',')
			thres = config.getfloat("RAIN", "rain_thres")  
			lvl = config.get("RAIN", "rain_log")
			rain.setLogLevel(parseLogLevel(lvl))      
			self.rainsensor = rain.RainSensor(self, thres, VECLEN, rain_publish)
			

		# Builds (optional) Cloud Sensor object
		if config.has_section("CLOUD"):
			pelt_publish = config.get("CLOUD","pelt_publish").split(',')
			pelt_thres  = config.getfloat("CLOUD", "pelt_thres")
			pelt_gain   = config.getfloat("CLOUD", "pelt_gain")
			lvl = config.get("CLOUD", "pelt_log")
			cloud.setLogLevel(parseLogLevel(lvl))
			self.clouds = cloud.CloudSensor(self, pelt_thres, 
											pelt_gain, VECLEN,pelt_publish)
			

		# Builds (optional) Pyranometer Sensor object
		if config.has_section("PYRANOMETER"):
			pyr_publish = config.get("PYRANOMETER","pyr_publish").split(',')
			pyr_offset  = config.getfloat("PYRANOMETER", "pyr_offset")
			pyr_gain    = config.getfloat("PYRANOMETER", "pyr_gain")
			lvl = config.get("PYRANOMETER", "pyr_log")
			pyran.setLogLevel(parseLogLevel(lvl))
			self.pyranometer = pyran.Pyranometer(self, 
												pyr_gain, 
												pyr_offset,
												VECLEN,
												pyr_publish)

		# Builds (optional) Thermometer Object
		if config.has_section("THERMOMETER"):
			thermo_publish = config.get("THERMOMETER","thermo_publish").split(',')
			thres = config.getfloat("THERMOMETER", "delta_thres") 
			lvl = config.get("THERMOMETER", "thermo_log")
			thermom.setLogLevel(parseLogLevel(lvl))       
			self.thermometer = thermom.Thermometer(self, thres, VECLEN, thermo_publish)

		# Builds (optional) Anemometer Object
		if config.has_section("ANEMOMETER"):
			anem_publish = config.get("ANEMOMETER","anem_publish").split(',')
			w_th   = config.getfloat("ANEMOMETER", "wind_thres")        
			w_th10 = config.getfloat("ANEMOMETER", "wind_thres10")        
			a_calib   = config.getfloat("ANEMOMETER", "anem_calib")        
			a_type    = config.get("ANEMOMETER", "anem_type")
			a_model = 1 if a_type == "TX20" else 0
			lvl = config.get("ANEMOMETER", "anem_log")
			anemom.setLogLevel(parseLogLevel(lvl))
			self.anemometer = anemom.Anemometer(self,
												w_th, 
												w_th10, 
												a_calib, 
												a_model,
												VECLEN,
												anem_publish)
		# Builds (optional) Pluviometer Object
		if config.has_section("PLUVIOMETER"):
			pluv_publish = config.get("PLUVIOMETER","pluv_publish").split(',')
			calib = config.getfloat("PLUVIOMETER", "pluv_calib") 
			lvl = config.get("PLUVIOMETER", "pluv_log")
			pluviom.setLogLevel(parseLogLevel(lvl))       
			self.pluviometer = pluviom.Pluviometer(self, calib,VECLEN,pluv_publish)

		# Build objects without configuration values
		lvl = config.get("THERMOPILE", "thermop_log")
		thermop_publish = config.get("THERMOPILE","thermop_publish").split(',')
		thermop.setLogLevel(parseLogLevel(lvl))     
		self.thermopile = thermop.Thermopile(self,VECLEN,thermop_publish)
		

		# Build EMA Page Generator object
		html_file     = config.get("HTML", "html_file")
		html_period   = config.getfloat("HTML", "html_period")
		lvl = config.get("HTML", "html_log")
		genpage.setLogLevel(parseLogLevel(lvl)) 
		N   =  int(round(html_period / server.Server.TIMEOUT) )
		self.genpage = genpage.HTML(self, html_file, N)


	# ----------------------------------
	# Synchroniztaion at startup process
	# ----------------------------------

	def sync(self):
		'''Trigger configurable parameter syncronization with EMA hardware'''
		if self.syncNeeded:
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
		flag = False
		# Only handles current value messages (type 'a')
		# if and only if al paramters are syncronized
		if len(message) == STATLEN and message[SMTB] == MTCUR and self.isSyncDone():
			# Loop to distribute to interested parties
			for obj in self.statusList:
				obj.onStatus(message)
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
		if self.handleRequest(message):
			log.debug("handled as parameter sync request")
			return
		if self.handleUnsolicited(message):
			log.debug("handled as ordinary Status Message")
			return
		if self.handleCommand(message):
			log.debug("handled as Command")
			return
		log.debug("unhandled message from EMA")



	def onUDPMessage(self, message, origin):
		'''
		Handle incoming commands from UDP driver.
		Only create and execute command objects for implemented commands.
		'''
		cmddesc = command.match(message)
		if cmddesc:
			cmd = ExternalCommand(self, **cmddesc)
			cmd.request(message, origin)
		else:
			self.serdriver.write(message)
		

	# ---------------------------
	# Event handlers from Devices
	# ---------------------------

	def onRoofRelaySwitch(self, mode, reason):
		'''
		Roof Relay Open Event handler.
		'mode' is either 'ON' or 'OFF'
		'reason' is the reason code in EMA status message.
		'''
		self.notifier.onRoofRelaySwitch(mode, reason)


	def onAuxRelaySwitch(self, mode, reason):
		'''
		Aux Relay Close Event handler.
		'reason' is the reason code in EMA status message.
		'''
		self.notifier.onAuxRelaySwitch(mode, reason)


	def onVoltageLow(self, voltage, threshold, n):
		'''
		Voltmeter low event handler.
		'vltage' is the actual voltage in EMA status message.
		'threshold' is the low threshold
		'n' is the sampe size on which the average was made
		'''
		self.notifier.onVoltageLow(voltage, threshold, n)

	# --------------
	# Server Control
	# --------------

	def stop(self):
		log.info("Shutting down EMA server")
		logging.shutdown()


class ExternalCommand(command.Command):
	'''Handles external commands comming from UDP messages'''
        def __init__(self, ema, retries=command.Command.RETRIES, **kargs):
                command.Command.__init__(self,ema,retries,**kargs)

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
