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
# The EMA hardware is quite smart. It does many things on its own:
# if any of its various thresholds are reached it opens or closes relays
# Threshold caluclations are done inside the EMA.
# But there may be other actions that could be triggered
# when the roof or aux relay or change state, like sending an SMS.
#
# Also, in my current setup, the battery voltage should be carefully 
# controled. If volage falls below a threshold, we should start 
# switching off all devices except EMAitself.
#
# This module is the real added value of this EMA Python server 
# to this excellent hardware.
#
# It allows you to trigger scripts that do interesting things like
# sendimg SMS or switching off its own computer (a Raspberry Pi)
#
# Scripts can be written in any language you like, of course. This
# project includes scripts to send SMS using the python-gammu 
# binding to gammu project.
#
# I have preferred to trigger arbitrary scripts rather than a tight
# integration to this EMA server. Loosely couple modules evolve better 
# over time.
#
# Scripts are forked in background and can be triggered each time 
# the event takes places or just once. There will be only one script 
# process running. If a recurring event takes place and the script is 
# still active, the new script is not launched.
#
# Notifier Class responsibilities:
# 1)  capture Voltage Low , Roff Relay on/off  
# and Aux Relay off/on events
# 2) Hold Script objects to run
# 3) Run them when the event comes.
#
# Script Class responsibilities
# 1) Hold a path to the external script file
# 2) Knows what its execution mode is (run once, run many times)
# 3) Forks the script in background and does not wait for its completion
#
# We use an exception to signal notifier about an porcess already being
# executed. I think this is cleaner than carrying return information 
# across two levels.
#
# ======================================================================


import logging
import subprocess
import os

log = logging.getLogger('notifier')

def setLogLevel(level):
	log.setLevel(level)



class ExecutedScript(Exception):
	'''Signals a script has executed'''
	def __init__(self, name, *args):
		self.name = name
		self.args = args

	def  __str__(self):
		'''Prints useful information'''
		tmp = ''
		for arg in self.args:
			tmp += ' ' + arg
		return self.name + ' ' + tmp



class Script(object):
	'''Notifier creates Script wrapper objects, representing
	scripts to be launched'''

	# modes as constants
	NEVER = 0
	ONCE  = 1
	MANY  = 2

	# mappping from strings to numbers
	MODES = { 'Never' : NEVER, 'Once' : ONCE, 'Many' : MANY }

	def __init__(self,  cfg):
		self.mode  = Script.MODES[cfg[1]]
		self.path  = cfg[0]
		self.name  = os.path.basename(self.path)
		self.child = None
		self.executed  = False


	def runOnce(self, *args):
		'''run only once in the whole server lifetime'''
		# skip if already run
		# otherwise, spawn it
		if self.executed:
			return False
		# If not running, spawn it
		try:
			self.child = subprocess.Popen((self.path,) + args)
		except (OSError, ValueError) as e:
			log.error("runOnce(%s): %s", self.path, e)
		else:
			self.executed = True
			raise ExecutedScript(self.name, *args)


	def runMany(self, *args):
		'''Run one more time, if previous run completed'''
		# Check existing script already running
		# If running we don't go any further and return.
		# otherwise, spawn it.
		if self.child:
			self.child.poll()
			if self.child.returncode is None:
				log.warning("script %s has not finished. Can't launch it again", self.name)
				return
		try:
			self.child = subprocess.Popen((self.path,) + args)
		except (OSError, ValueError) as e:
			log.error("runMany(%s): %s", self.path, e)
		else:
			raise ExecutedScript(self.name, *args)
		return


	def run(self, *args):
		'''Launch a script, depending on the launch mode'''
		# Skip if no script is configured
		if not self.path:
			return
		if self.mode == Script.ONCE:
			self.runOnce(*args)
		elif self.mode == Script.MANY:
			self.runMany(*args)

		



class Notifier(object):
	'''Notifies EMA events to third parties by executing scripts'''

	# Modes as a set text strings to be used in config file
	MODES = {'Never', 'Once', 'Many'}

	def __init__(self):
		pass
		self.lowVoltScript   = []
		self.auxRelayScript  = []
		self.roofRelayScript = []

	# ---------------------------								
	# Adding scripts to notifier
	# ---------------------------

	def addVoltScript(self, mode, script):
		''' *_script are tuples of (path, mode)'''
		self.lowVoltScript.append(Script((script,mode)))
		
	def addAuxRelayScript(self, mode, script):
		''' *_script are tuples of (path, mode)'''
		self.auxRelayScript.append(Script((script,mode)))

	def addRoofRelayScript(self, mode, script):
		''' *_script are tuples of (path, mode)'''
		self.roofRelayScript.append(Script((script,mode))) 

	# ---------------------------
	# Event handlers from Devices
	# ---------------------------

	def onVoltageLow(self, voltage, threshold, n):
		try:
			for script in self.lowVoltScript:
				script.run("--voltage", voltage, "--threshold", threshold, "--size", n)
		except ExecutedScript as e:
			log.critical("Executed a Low Voltage script: %s ", e)


	def onRoofRelaySwitch(self, on_off, reason):
		try:
			for script in self.roofRelayScript:
				script.run("--status", on_off, "--reason", reason)
		except ExecutedScript as e:
			log.warning("Executed a Roof Relay script: %s ", e)


	def onAuxRelaySwitch(self, on_off, reason):
		try:
			for script in self.auxRelayScript:
				script.run("--status", on_off, "--reason", reason)
		except ExecutedScript as e:
			log.warning("Executed an Aux Relay script: %s ", e)
