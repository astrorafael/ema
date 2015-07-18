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
		publish_where = parser.get("AUX_RELAY","aux_relay_publish_where").split(',')
		publish_what  = parser.get("AUX_RELAY","aux_relay_publish_what").split(',')
		Alarmable.__init__(self,3)
                Device.__init__(self, publish_where, publish_what)
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
			ema.notifier.addScript('AuxRelaySwitch', script_mode, script)
		# ESTO ES NUEVO
		self.scheduler = TimeScheduler(self, parser)

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
			self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , OFF, "--reason", c)
		# Detects Close-> Open transitions and notify
		elif not self.relay.last() and openFlag:
			log.warning("Aux Relay Switch On: %s", AuxRelay.REASON[c])
			self.relay.append(openFlag)
			self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , ON, "--reason", c)
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
		publish_where = parser.get("ROOF_RELAY","roof_relay_publish_where").split(',')
		publish_what  = parser.get("ROOF_RELAY","roof_relay_publish_what").split(',')
		scripts    = parser.get("ROOF_RELAY","roof_relay_script").split(',')
		relay_mode = parser.get("ROOF_RELAY","roof_relay_mode")
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


# ============================================================================
# ============================================================================
# ============================================================================

import datetime

def now():
	return datetime.datetime.utcnow().replace(microsecond=0).time()

def toTime(hhmm):
	'''Converts HH:MM strings into time objects'''
	return datetime.time(hour=int(hhmm[0:2]), minute=int(hhmm[3:5]))

def reversed(w):
	'''Detects time wrap around in a time window w 0=start, 1=end'''
	return not (w[0] < w[1])

def inInterval(time, w):
	'''Returns whether a given itme is in a given window'''
	return time >= w[0] and time <= w[1]

def strfwin(w):
	'''return formatted string for an interval w'''
	return "[%s-%s]" % (w[0].strftime("%H:%M"), w[1].strftime("%H:%M"))

def windows(winstr):
	'''Build a window list from a windows list spec string 
	taiking the following format HH:MM-HH:MM,HH:MM-HH:MM,etc
	Window interval (Start % end time) separated by dashes
	Window ist separated by commands'''
	return [ map(toTime, t.split('-')) for t in winstr.split(',')  ]

def gaps(windows):
	'''Build the complementary windows with the gaps in the original windows'''
	aList = []
	if reversed(windows[-1]):
		aList.append([ windows[-1][1], windows[0][0] ])
		for i in range(0,len(windows)-1):
			aList.append([ windows[i][1], windows[i+1][0] ])
	else:
		for i in range(0,len(windows)-1):
			aList.append([ windows[i][1], windows[i+1][0] ])
		aList.append([ windows[-1][1], windows[0][0] ])
	return aList

def positive(windows):
	'''Returns true if individual window lengths are positive'''
	log.debug("checking each start/end time window")
	if not reversed(windows[-1]):
		for i in range(0,len(windows)):
                	if reversed(windows[i]):
                        	return False, i
		log.debug("checking positive window ok.")
		return True, -1
	else:
		return positive(gaps(windows))


def monotonic(windows):
	'''Returns true if monotonic window sequence'''
	log.debug("checking monotonic time windows series")
	if not reversed(windows[-1]):
		for i in range(0,len(windows)-1):
			if not (windows[i][1] < windows[i+1][0]):
				return False, i
		log.debug("checking monotonic windows ok.")
		return True, -1
	else:
		return monotonic(gaps(windows))

	
def curWindow(windows, tNow):
	if not reversed (windows[-1]):
		for i in range(0,len(windows)):
			if inInterval(tNow, windows[i]):
				return True, i
		return False, -1
	else:
		for i in range(0, len(windows)-1):
			if inInterval(tNow, windows[i]):
				return True, i
		if inInterval(tNow, [windows[-1][0], datetime.time.max]) or inInterval(tNow, [datetime.time.min, windows[-1][1]]):
			return True, len(windows)-1
		return False, -1


def where(windows):
	log.debug("Finding current relay window")
	tNow = now()
	found, i = curWindow(windows, tNow)
	if found:
		log.debug("current relay window is %s", strfwin(windows[i]))
	else:
		log.debug("No current relay window active, finding gap")
		g = gaps(windows) 
		found, i = curWindow(g, tNow)
		log.debug("now() is in gap %s", strfwin(g[i]))


def verify(windows):
	'''Verify a  series of time windows'''
	positive_flag, i = positive(windows)
	if not positive_flag:
		log.error("Window with negative length => %s", strfwin(windows[i]))
		raise InvalidTimeWindow(windows[i])
	monotonic_flag, i = monotonic(windows)
	if not monotonic_flag:
		log.error("Window series not monotonic starting at => %s", strfwin(windows[i]))
		raise InvalidTimeWindow(windows[i])


class InvalidTimeWindow(Exception):
	'''Signals a script has executed'''
	def __init__(self, w):
		self.win = w
	def  __str__(self):
		'''Prints useful information'''
		return "[%s-%s]" % (self.w[0].strftime("%H:%M"), self.w[1].strftime("%H:%M"))


class TimeScheduler(object):

	def __init__(self, relay, parser):
		self.relay = relay
		winstr = parser.get("AUX_RELAY", "aux_window")
		self.windows = windows(winstr)
		verify(self.windows)
		where(self.windows)
