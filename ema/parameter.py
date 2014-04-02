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
# Parameter = Either a Calibration Constant or a Threshold. 
# Parameters are stored in EMA's EEPROM.
#
# I wanted to address the requirement of proper EMA parameter setup with
# minimun EEPROM R/W cycles. This means designing a process in which a 
# a parameter value is first queried and then set to a new value if 
# not equal to the value set in the configuration file. And all this 
# using EMA commands, which sometimes was not easy: messages sent to EMA
# are lost now and then, so a timeout & retry procedure was introduced. 
#
# The AbstractParameter class implements the whole get/set workflow. 
# It is a Finite State Machine that delegates to subclasses 
# the specific actions, leaving the FSM bookeeping in 
# the AbstractParameter class.
#
# After coding the get/set process for some calibration constants, 
# I realized that all actions to be subclassed could be really coded
# in a generic way. This is the Paranmeter class. The only exception
# is setting/getting te EMA Real Time Clock (see its desig notes).
#
# A parameter descriptor is a dictionary which specifies configuration 
# for a specific Parameter. This dictionary is passed at Parameter 
# construction time.Some parameters' values are encoded in EMA responses
# with a x10 multiplier, others with x1 multipier, so we introduced a 
# multiplier in he parameter descriptor.
#
# These two classes makes heavy use of regular rxpressions, which 
# greatly simplify the process of parsing EMA responses. 
# In the end, there was no need to distinghish a 'get' regular 
# expression from a 'set' regular expression. However, they are still
# in the code (who knows ...)
#
# ======================================================================

import re
import logging
from abc import ABCMeta, abstractmethod

from server import Alarmable

# Note that AbstractClass also uses ABCMetaclass, inherited from Alarmable
class AbstractParameter(Alarmable):


	# Default constanst
	TIMEOUT = 5                 # timeout cycles
	RETRIES = 2                 # retries (0 = no retry)

	# States
	BEGIN = 0
	GET   = 1
	SET   = 2
	END   = 3

	def __init__(self, ema, T, getPat, setPat, nretries = 0):
		Alarmable.__init__(self,T)
		self.ema    = ema
		self.getPat = re.compile(getPat)
		self.setPat = re.compile(setPat)
		self.state  = AbstractParameter.BEGIN
		self.NRetries = nretries


	def sync(self):
		'''First Event'''
		self.retries = 0
		self.resetAlarm()       # maybe not necessary
		self.ema.addAlarmable(self)
		self.ema.addRequest(self)
		self.actionStart()                 # overriden in subclass
		self.state = AbstractParameter.GET   # next state


	def onResponseDo(self, message):
		'''Input message handler'''
		if self.state == AbstractParameter.GET:
			matched = self.getPat.search(message)
			if matched:
				self.resetAlarm()
				self.retries = 0
				syncNeeded = self.actionGet(message, matched) # overriden in subclass
				if syncNeeded:
					self.state = AbstractParameter.SET # transition to next state
				else:
					self.state = AbstractParameter.END # or to END state
					self.ema.delRequest(self)
					self.ema.delAlarmable(self)
					self.actionEnd()   # overriden in subclass
			return matched is not None

		elif self.state == AbstractParameter.SET:
			matched = self.setPat.search(message)
			if matched:
				self.resetAlarm()
				self.retries = 0
				self.actionSet(message, matched) # overriden in subclass
				self.state = AbstractParameter.END # transtition to next state
				self.ema.delRequest(self)
				self.ema.delAlarmable(self)
				self.actionEnd() # overriden in subclass
			return matched is not None

		else:
			return False
		

	def onTimeoutDo(self):
		'''Timeout event handler'''
		if self.retries < self.NRetries:
			if self.state == AbstractParameter.GET:
				self.retryGet()     # overriden in subclass
			elif self.state == AbstractParameter.SET:
				self.retrySet()      # overriden in subclass
			else:
				return
			self.retries += 1
			self.ema.addAlarmable(self)
		else:	# to END state
			self.state = AbstractParameter.END 
			self.ema.delRequest(self)
			self.actionTimeout() # overriden in subclass
			

	def isDone(self):
		'''Returns true if syncronization process ended'''
		return self.state == AbstractParameter.END
	
	
	def getRetries(self):
		'''Returns tuple with the retry count and retry limit'''
		return (self.retries, self.NRetries)

	@abstractmethod
	def actionStart(self):
		'''
		Called by Sync and also by retrying a GET message
		To be subclassed. Delegated reponsibilites:
		1) Send a GET message to EMA
		Returns:
		Nothing
		'''
		pass

	@abstractmethod
	def actionGet(self, message, matchobj):
		'''
		To be subclassed. Delegated responsibilites.
		1) Parse the GET response message and extract appropriate values, 
		using matchobj if needed. 
		2) Detect if a sync is needed
		3) Send SET message to EMA if needs sync. 
		Returns:
		True if needs sync, False otherwise.
		'''
		return False

	@abstractmethod
	def actionSet(self, message, matchobj):
		'''
		To be subclassed. Delegated responsibilities:
		1) Parse SET response message (only if needed, normally not).
		2) Verify that value returned is the desired.
		3) Log a warning if not the same.
		Returns:
		Nothing
		'''
		pass

	@abstractmethod
	def actionEnd(self):
		'''
		To be subclassed. Delegated responsibilities:
		1) Kick off new processes, like Idle object registering
		Returns:
		Nothing
		'''
		pass


	@abstractmethod
	def retryGet(self):
		'''
		To be subclassed if retries are desired. Delegated responsibilities:
		1) resend a GET message (usually same as actionSync() )
		2) Log this retry
		Returns:
		Nothing
		'''
		pass

	@abstractmethod
	def retrySet(self):
		'''
		To be subclassed if retries are desired. Delegated responsibilities:
		1) resend a SET message
		2) Log this retry
		Returns:
		Nothing
		'''
		pass

	@abstractmethod
	def actionTimeout(self):
		'''
		Called when the requests times out and retry limits are reached 
		To be subclassed. Delegated responsibilities:
		1) Log an error message with details
		'''
		pass

   


'''
Sample Descriptor
#LOFFSET = {
	'name': 'Cloud Sensor Offset',
	'logger' : 'cloudpel',
	'mult' : 1.0,               # multiplier to internal value
	'unit' : none               # parameter units
	'get' : '(n)',              # string format for GET request
	'set' : '(N%03d)',          # string format for SET request
	'pat' :  '\(N(\d{3})\)',    # pattern to recognize as response
	'grp'  : 1,                 # pat. group to extract value & compare
}
'''


class Parameter(AbstractParameter):

	def __init__(self, ema, parent, value, **kargs):
		AbstractParameter.__init__(self, ema, 
									   AbstractParameter.TIMEOUT, 
									   kargs['pat'], 
									   kargs['pat'], 
									   AbstractParameter.RETRIES)
		self.name = kargs['name']
		self.log  = logging.getLogger(kargs['logger'])
		self.mult = kargs['mult']
		self.unit = kargs['unit']
		self.get  = kargs['get']
		self.set  = kargs['set']
		self.pat  = kargs['pat']
		self.grp  = kargs['grp']
		self.value = int(round(value * self.mult))
		self.parent = parent
		
		self.log.debug("created Parameter %s = %d", self.name, self.value)


	def sendValue(self):
		n = self.ema.serdriver.queueDelay()
		n += AbstractParameter.TIMEOUT
		self.setTimeout(n)      # adjust for queue length
		self.ema.serdriver.write(self.set % self.value)


	def actionStart(self):
		n = self.ema.serdriver.queueDelay()
		n += AbstractParameter.TIMEOUT
		self.setTimeout(n)      # adjust for queue length
		self.ema.serdriver.write(self.get)
		

	def actionGet(self, message, matchobj):
		self.log.debug("matched GET message %s", message)
		value = int(matchobj.group(self.grp))
		if value != self.value:
			self.sendValue()
			needsSync = True
		else:
			self.log.debug("No need to sync %s value", self.name)
			needsSync = False
		return needsSync


	def actionSet(self, message, matchobj):
		self.log.debug("matched SET message %s", message)
		value = int(matchobj.group(self.grp))
		if value != self.value:
			self.log.warning("EMA %s value is still not synchronized", self.name)


	def actionEnd(self):
		self.log.debug("Parameter %s succesfully synchronized", self.name)
		# kludge: schedule an alarm on the parent 
		# whose timeout will trigger next thing
		if(self.parent):
			self.log.debug("Triggering another parameter sync")
			self.ema.addAlarmable(self.parent) 


	def retryGet(self):
		self.log.debug("Retry a GET message (%d/%d)" % self.getRetries() )
		self.actionStart()


	def retrySet(self):
		self.log.debug("Retry a SET message (%d/%d)" % self.getRetries() )
		self.sendValue()


	def actionTimeout(self):
		self.log.error("Timeout: EMA not responding to %s sync request", self.name)
