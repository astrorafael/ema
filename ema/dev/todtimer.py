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
import datetime
import subprocess

from ema.server    import Server, Alarmable
from ema.device    import Device
from ema.intervals import Interval, Intervals

log = logging.getLogger('todtimer')

# =====================================
# Utility functions for Aux Relay Class
# =====================================


def now():
        return datetime.datetime.utcnow().replace(microsecond=0).time()

def adjust(time, minutes):
	''' adjust a datetime.time object by some integer minutes, 
	returning a new datetime.time object'''
	today  = datetime.date.today()
	tsnow  = datetime.datetime.combine(today, time)
	dur    = datetime.timedelta(minutes=minutes)
	return (tsnow + dur).time()

def durationFromNow(time):
	'''Retuns a datetime.timedelta object from given time to now'''
	today  = datetime.date.today()
	tsnow  = datetime.datetime.utcnow()
	tstime = datetime.datetime.combine(today, time)
	if tstime < tsnow:
		tstime += datetime.timedelta(hours=24)
	return tstime - tsnow

# =======================
# Time of Day Timer Class
# =======================


class TODTimer(Device, Alarmable):

	# Minimun active interval size in minutes
	MIN_DUR = 15

	INTERVALS = "Timer Active Intervals"
	ACTIVE   = "active"
	INACTIVE = "inactive"

	def __init__(self, ema, parser):
		lvl = parser.get("TOD_TIMER", "tod_log")
		log.setLevel(lvl)
		publish_where = parser.get("TOD_TIMER","tod_publish_where").split(',')
		publish_what  = parser.get("TOD_TIMER","tod_publish_what").split(',')
 		intervals     = parser.get("TOD_TIMER","tod_intervals")
 		poweroff      = parser.getboolean("TOD_TIMER","tod_poweroff")
                Device.__init__(self, publish_where, publish_what)
                Alarmable.__init__(self)
		self.ema      = ema
		self.poweroff = poweroff
		self.windows  = Intervals.parse(intervals, TODTimer.MIN_DUR)
		self.gaps     = ~ self.windows
		self.where    = None
		self.i        = None
		self.subscribedList = []
		ema.addParameter(self)
		ema.addCurrent(self)
		ema.addAverage(self)
		log.debug("processed %d active intervals and %d inactive intervals", len(self.windows), len(self.gaps))
		# Better in EMA, so the subscribers subscribe first before 
		# running a time window search process
		## self.onNewInterval()

	# --------------------------------
	# Offer the subscription Interface
	# --------------------------------

	def addSubscriber(self, obj):
        	'''Adds a object implementing the following methods:
        	onNewInterval()
        	'''
	        callable(getattr(obj,'onNewInterval'))
        	self.subscribedList.append(obj)


    	def delSubscriber(self, obj):
        	'''Removes subscribed object from the list.'''
        	self.subscribedList.pop(self.subscribedList.index(obj))

	# ----------------------------------
	# Implements the Alarmable interface
	# -----------------------------------

	def onTimeoutDo(self):
		log.debug("Triggered by Soft Alarm")
		self.onNewInterval()

	# ----------------------------------------
	# Implements the Signal SIGALARM interface
	# ----------------------------------------

	def onSigAlarmDo(self):
		log.debug("Triggered by SIGALRM")
		self.onNewInterval()

	# ----------
	# Properties
	# ----------

	@property
	def current(self):
		'''Return dictionary with current measured values'''
		i = self.i
		if self.where == TODTimer.ACTIVE:
			return { self.where: (self.windows[i] , 'UTC') }
		else:
			return { self.where: (self.gaps[i] , 'UTC') }

	@property
	def average(self):
		'''Return dictionary averaged values over a period of N samples'''
		return { self.where: ("N/A" , '') }


	@property
	def parameter(self):
		'''Return dictionary with calibration constants'''
		return {
			TODTimer.INTERVALS : ( str(self.windows) , 'UTC') ,
			}

	# ------------------
	# Intervals handling
	# ------------------

	def nextActiveIndex(self, i):
		return (i + 1) % len(self.windows)

	def getInterval(self, where, i):
		if where == TODTimer.ACTIVE:
			return self.windows[i]
		else:
			return self.gaps[i]
		

	def getActiveInterval(self, i):
		return self.windows[i]

	def onNewInterval(self):
		'''Executes the callbacks, triggered by alarms'''
		self.findCurrentInterval()
		for o in self.subscribedList:
			o.onNewInterval(self.where, self.i)
	
	def nextAlarm(self, tMID):
		'''Program next alarm'''
		t = int(durationFromNow(tMID).total_seconds())
		log.info("Next check at %s, %d seconds from now",tMID.strftime("%H:%M:%S"), t)
		self.ema.setSigAlarmHandler(self, t)
		self.resetAlarm()
		self.setTimeout(t / Server.TIMEOUT)
		self.ema.addAlarmable(self)

	def isShuttingDown(self):
		'''Find if a shutdown process is under way'''
		p1 = subprocess.Popen(["ps", "-ef"], stdout=subprocess.PIPE)
		p2 = subprocess.Popen(["grep", "shutdown"], stdin=p1.stdout, stdout=subprocess.PIPE)
		p3 = subprocess.Popen(["grep", "-v", "grep"], stdin=p2.stdout, stdout=subprocess.PIPE)
		output = p3.communicate()[0]
		if len(output) != 0:
			log.debug("Previous Shutdown under way")
			return True
		else:
			log.debug("No previous Shutdown under way")
			return False

	def shutdown(self, tSHU):
		'''Manages a possible shutdow request'''
		# WARNING !!!!! tSHU IS GIVEN AS UTC !!!!!!
		# AND SHUTDOWN REQUIRES LOCAL TIME !!!!!
		# This will only work if local time is UTC as well
		if self.poweroff and not self.isShuttingDown():
			if tSHU > now():
                                tSHUstr = tSHU.strftime("%H:%M")
                                log.warning("Calling shutdown at %s",tSHUstr)
                                subprocess.Popen(['sudo','shutdown','-k', tSHUstr])
			else:						
                                log.warning("Calling shutdown now")
                                subprocess.Popen(['sudo','shutdown','-k', 'now'])
			log.info("Programmed shutdown at %s",tSHU.strftime("%H:%M:%S"))


	def findCurrentInterval(self):
		'''Find the current interval'''		
        	tNow = now()
        	found, i = self.windows.find(tNow)
		if found:
			self.where = TODTimer.ACTIVE
			self.i    = i
                	log.info("now (%s) we are in the active window %s", tNow.strftime("%H:%M:%S"), self.windows[i])
			tSHU      = adjust(self.windows[i].t1, minutes=-2)
			tMID      = self.gaps[i].midpoint()
		else:
			self.where = TODTimer.INACTIVE
                	found, i = self.gaps.find(tNow)
                	log.info("now (%s) we are in the inactive window %s", tNow.strftime("%H:%M:%S"), self.gaps[i])
			self.i    = i
			i         = self.nextActiveIndex(i)
			tSHU      = adjust(self.windows[i].t1, minutes=-2)
			tMID      = self.windows[i].midpoint()

		# anyway sets an for the next self-check
		self.nextAlarm(tMID)	
		# Programs power off time		
		self.shutdown(tSHU)


     
