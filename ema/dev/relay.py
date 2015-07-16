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

from ema.server    import Alarmable
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.emaproto  import SRRB, SARB
from ema.device    import Device

log = logging.getLogger('relays')

# On/Off flags as string constants
ON  = 'ON'
OFF = 'OFF'


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

def timeFromString(stime):
	'''Conversion from HH:MM to EMA tiem string HHMM'''
	return int(stime[0:2]  + stime[3:5])


def timeToString(itime):
	'''Conversion fromr EMA integer HHMM value to HH:MM string'''
	return '%02d:%02d' % (itime // 100, itime % 100) 

def toMinutes(hhmm):
	'''Converts an HH:MM sttring to minutes'''
	minutes = int(hhmm[0:2])*60  + int(hhmm[3:5])
	log.debug ("hh:mm => %d minutes", minutes)
	return minutes

def analiza(w):
	'''Analyzes a  series of time windows'''
	for i in range(0,len(w)):
		log.debug("w[%i]= %s", i, w[i])		

	# Start Time[i] must be less than End Time[i]
	# except for the last window which could wrap around		
	log.debug("checking each start/end time window")
	for i in range(0,len(w)-1):
		log.debug("w[%d][start] (%s) < w[%d][end] (%s)", i, w[i][0], i,  w[i][1])		
		if not toMinutes(w[i][0]) < toMinutes(w[i][1]):
			raise IndexError
	
	# End Time[i] must be less than Start Time[i+1]
	# except for the last window which could wrap around		
	log.debug("checking concatenated end/start time window")
	for i in range(0,len(w)-1):
		log.debug("w[%d][end] (%s) < w[%d][start] (%s)", i, w[i][1], i+1, w[i+1][0])		
		if not  toMinutes(w[i][1]) < toMinutes(w[i+1][0]):
			raise IndexError

	if not toMinutes(w[-1][0]) < toMinutes(w[-1][1]):
		log.debug("detected last time window wrap around")



class AuxRelay(Alarmable, Device):

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
		mode         = parser.get("AUX_RELAY", "aux_mode")
		tON          = parser.get("AUX_RELAY", "aux_on")
		tOFF         = parser.get("AUX_RELAY", "aux_off")
		scripts      = parser.get("AUX_RELAY","aux_relay_script").split(',')
		script_mode  = parser.get("AUX_RELAY","aux_relay_mode")
		publish      = parser.get("AUX_RELAY","aux_relay_publish").split(',')
		Alarmable.__init__(self,3)
		Device.__init__(self, publish)
		myself = self if AuxRelay.MAPPING[mode] == AuxRelay.TIMED else None
		self.mode = Parameter(ema, myself, AuxRelay.MAPPING[mode], **MODE)	
		# get rid of : in   HH:MM   and transform it to a number
		tON        =  timeFromString(tON)
		tOFF       =  timeFromString(tOFF)
		self.ton   = Parameter(ema, myself, tON,  **TON)
		self.toff  = Parameter(ema, None,   tOFF, **TOFF)
		self.relay = Vector(N)
		self.ema   = ema
		ema.addSync(self.mode)
		ema.subscribeStatus(self)
		ema.addParameter(self)
		for script in scripts:
			ema.notifier.addAuxRelayScript(script_mode, script)
		# ESTO ES NUEVO
		window = parser.get("AUX_RELAY", "aux_window")
		self.window =[ time.split('-') for time in window.split(',')  ]
		analiza(self.window)


	def onTimeoutDo(self):
		if self.mode.value != AuxRelay.TIMED :
			return
		#if self.ton.isDone() : 
			#self.toff.sync()
		#else: 
			#self.ton.sync()


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
			self.ema.onAuxRelaySwitch(OFF, c)
		# Detects Close-> Open transitions and notify
		elif not self.relay.last() and openFlag:
			log.warning("Aux Relay Switch On: %s", AuxRelay.REASON[c])
			self.relay.append(openFlag)
			self.ema.onAuxRelaySwitch(ON, c)
		else:
			self.relay.append(openFlag)

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
		return {
			self.mode.name : (AuxRelay.MAPPING[self.mode.value] , self.mode.unit) ,
			self.ton.name  : ( timeToString(self.ton.value), self.ton.unit) ,
			self.toff.name : ( timeToString(self.toff.value), self.toff.unit) ,
			}
	
		


class RoofRelay(Device):

	OPEN = 'open'

	REASON = {
		'A' : 'Manual switch on' ,
		'a' : 'Manual switch on, overriding thresholds' ,
	}

	def __init__(self, ema,  parser, N):
		publish    = parser.get("ROOF_RELAY","roof_relay_publish").split(',')
		scripts    = parser.get("ROOF_RELAY","roof_relay_script").split(',')
		relay_mode = parser.get("ROOF_RELAY","roof_relay_mode")
                Device.__init__(self, publish)
		self.relay = Vector(N)
		self.ema   = ema
		ema.subscribeStatus(self)
		ema.addCurrent(self)
		ema.addAverage(self)
		for script in scripts:
			ema.notifier.addRoofRelayScript(relay_mode, script)
		

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
			self.ema.onRoofRelaySwitch(OFF, c)
		# Detects Close-> Open transitions and notify
		elif not self.relay.last() and openFlag:
			self.relay.append(openFlag)
			self.ema.onRoofRelaySwitch(ON, c)
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
