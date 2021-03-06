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

import logging
import re
import datetime

from ema.server    import Server, Alarmable
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.emaproto  import SRRB, SARB
from ema.device    import Device
from ema.intervals import Interval, Intervals
from todtimer      import Timer

# On/Off flags as string constants
ON  = 'ON'
OFF = 'OFF'


log = logging.getLogger('relays')

# ================
# Rool Relay Class
# ================


class RoofRelay(Device):

	OPEN = 'open'

	REASON = {
		'A' : 'Manual switch on' ,
		'a' : 'Manual switch on, overriding thresholds' ,
	}

	def __init__(self, ema,  parser, N):
		publish_where = parser.get("ROOF_RELAY","roof_relay_publish_where").split(',')
		publish_what  = parser.get("ROOF_RELAY","roof_relay_publish_what").split(',')
		scripts       = parser.get("ROOF_RELAY","roof_relay_script").split(',')
		relay_mode    = parser.get("ROOF_RELAY","roof_relay_mode")
                Device.__init__(self, publish_where, publish_what)
		self.relay = Vector(N)
		self.ema   = ema
		ema.subscribeStatus(self)
		ema.addCurrent(self)
		ema.addAverage(self)
		for script in scripts:
			ema.notifier.addScript('RoofRelaySwitch', relay_mode, script)
		

	def onStatus(self, message):
		'''Roof Relay, accumulate open (True) /close (False) readings'''
		c = message[SRRB]
		openFlag = False if c == 'C' else True

		# Handle initial feed
		if self.relay.len() == 0:
			self.relay.append(openFlag)
			return

		# Detects Open -> Close transitions and notify
		if self.relay.last() and not openFlag:
			self.relay.append(openFlag)
			self.ema.notifier.onEventExecute('RoofRelaySwitch', "--status" , OFF, "--reason", c)

		# Detects Close-> Open transitions and notify
		elif not self.relay.last() and openFlag:
			self.relay.append(openFlag)
			self.ema.notifier.onEventExecute('RoofRelaySwitch', "--status" , ON, "--reason", c)
		else:
			self.relay.append(openFlag)


	@property
	def current(self):
		'''Return dictionary with current measured values'''
		return { RoofRelay.OPEN: (self.relay.last() , '') }


	@property
	def average(self):
		'''Return dictionary averaged values over a period of N samples'''
		accum, n = self.relay.sum()
		return { RoofRelay.OPEN: ((accum*100.0)/n, '%') }


# =======================================
# Parameter definition for AuxRelay class
# =======================================

MODE = {
	'name': 'Aux Relay mode',
	'logger': 'relays',
	'mult': 1.0,               # multiplier to internal value
	'unit': '',                # 
	'get' : '(s)',             # string format for GET request
	'set' : '(S%03d)',         # string format for SET request
	'pat' : '\(S(\d{3})\)',    # pattern to recognize as response
	'grp' : 1,                 # match group to extract value and compare
}

TON = {
	'name': 'Aux Relay Switch on Time',
	'logger': 'relays',
	'mult': 1.0,               # multiplier to internal value
	'unit': 'HH:MM',           # 
	'get' : '(s)',             # string format for GET request
	'set' : '(Son%04d)',       # string format for SET request
	'pat' : '\(Son(\d{4})\)',  # pattern to recognize as response
	'grp' : 1,                 # match group to extract value and compare
}

TOFF = {
	'name': 'Aux Relay Switch off Time',
	'logger': 'relays',
	'mult': 1.0,               # multiplier to internal value
	'unit': 'HH:MM',           # 
	'get' : '(s)',             # string format for GET request
	'set' : '(Sof%04d)',       # string format for SET request
	'pat' : '\(Sof(\d{4})\)',  # pattern to recognize as response
	'grp' : 1,                 # match group to extract value and compare
}


# =====================================
# Utility functions for Aux Relay Class
# =====================================


def timeFromString(stime):
	'''Conversion from HH:MM to EMA time string HHMM'''
	return int(stime[0:2]  + stime[3:5])


def timeToString(itime):
	'''Conversion fromr EMA integer HHMM value to HH:MM string'''
	return '%02d:%02d' % (itime // 100, itime % 100) 


# ====================
# Auxiliar Relay Class
# ====================


class AuxRelay(Device):

	OPEN = 'open'

	# Aux Relay Mode constants
	AUTO   = 0
	MANUAL = 5 # Manual mode, state ON by default.
	TIMED  = 9

	# Mapping from strings to constants and viceversa
	MAPPING = {
		'Auto'  : AUTO ,
		'Manual': MANUAL ,
		'Timed' : TIMED,
		AUTO    : 'AUTO',
		MANUAL  : 'MANUAL',
		TIMED   : 'Timed' ,
	}

	REASON = {
		'A' : 'Automatic switch off (heaters off)' ,
		'a' : 'Manual or timed mode switch off' ,
		'!' : 'Automatic switch off by humidity sensor read error' ,
		'E' : 'Automatic switch on (heaters on)' ,
		'e' : 'Manual or timed switch on' ,
	}


	def __init__(self, ema, parser, N):
		lvl = parser.get("AUX_RELAY", "aux_relay_log")
		log.setLevel(lvl)
		mode          = parser.get("AUX_RELAY", "aux_mode")
		scripts       = parser.get("AUX_RELAY","aux_relay_script").split(',')
		script_mode   = parser.get("AUX_RELAY","aux_relay_mode")
		publish_where = parser.get("AUX_RELAY","aux_relay_publish_where").split(',')
		publish_what  = parser.get("AUX_RELAY","aux_relay_publish_what").split(',')
                Device.__init__(self, publish_where, publish_what)
		self.ema      = ema
		self.mode     = Parameter(ema, AuxRelay.MAPPING[mode], **MODE)	
		self.ton      = None
		self.toff     = None
		self.relay    = Vector(N)
		ema.addSync(self.mode)
		ema.subscribeStatus(self)
		ema.addParameter(self)
		for script in scripts:
			ema.notifier.addScript('AuxRelaySwitch', script_mode, script)
		if AuxRelay.MAPPING[mode] == AuxRelay.TIMED:
			ema.todtimer.addSubscriber(self)

	# -------------------------------------------
	# Implements the EMA status message interface
	# -------------------------------------------

	def onStatus(self, message):
		'''Aux Relay, accumulate open/close readings'''
		c = message[SARB]
		openFlag = True if c == 'E' or c == 'e' else False

		# Handle initial feed
		if self.relay.len() == 0:
			self.relay.append(openFlag)
			return

		# Detects Open -> Close transitions and notify
		if self.relay.last() and not openFlag:
			log.warning("Aux Relay Switch Off: %s", AuxRelay.REASON[c])
			self.relay.append(openFlag)
			self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , OFF, "--reason", c)
		# Detects Close-> Open transitions and notify
		elif not self.relay.last() and openFlag:
			log.warning("Aux Relay Switch On: %s", AuxRelay.REASON[c])
			self.relay.append(openFlag)
			self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , ON, "--reason", c)
		else:
			self.relay.append(openFlag)

	# ----------
	# Properties
	# ----------

	@property
	def current(self):
		'''Return dictionary with current measured values'''
		return { AuxRelay.OPEN: (self.relay.last() , '') }

	@property
	def average(self):
		'''Return dictionary averaged values over a period of N samples'''
		accum, n = self.relay.sum()
		return { AuxRelay.OPEN: ((accum*100.0)/n, '%') }


	@property
	def parameter(self):
		'''Return dictionary with calibration constants'''
		if self.ton is not None:
			return {
				self.mode.name : (AuxRelay.MAPPING[self.mode.value] , self.mode.unit) ,
				self.ton.name  : ( timeToString(self.ton.value), self.ton.unit) ,
				self.toff.name : ( timeToString(self.toff.value), self.toff.unit) ,
				}
		else:
			return {
				self.mode.name : (AuxRelay.MAPPING[self.mode.value] , self.mode.unit) ,
				}
	# --------------------------------------
	# Implement the onNewIntervalDo interface
	# ---------------------------------------

	def onNewInterval(self, where, i):
		'''Program Aux Relay tON and tOFF times'''
		if where == Timer.INACTIVE:
			i         = self.ema.todtimer.nextActiveIndex(i)
			interval  = self.ema.todtimer.getInterval(Timer.ACTIVE,i) 
			tON       = int(interval.t0.strftime("%H%M"))
			tOFF      = int(interval.t1.strftime("%H%M"))
			log.info("Programming next active window (tON-tOFF) to %s",interval)
		else:
			interval  = self.ema.todtimer.getInterval(Timer.INACTIVE,i) 
			tOFF      = int(interval.t0.strftime("%H%M"))
			tON       = int(interval.t1.strftime("%H%M"))
			log.info("Programming next inactive window (tOFF-tON) to %s", interval)
		self.ton  = Parameter(self.ema, tON,  **TON)
		self.toff = Parameter(self.ema, tOFF, self.ton, **TOFF)
		self.toff.sync()
