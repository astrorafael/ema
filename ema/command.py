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
# This module implements available commands to be executed from 
# another entity, either a process in the ocal machine or 
# in the same LAN.
#
# The command list specified the request pattern received from an
# UDP mesage and its associated responses from EMA. 
# Some commands generates two responses.
#
# The global match function matches a given request message against
# the is of available commands. If mating is ok, returns the associated
# description of response data expected. This descriptor is used to
# build a command object that will send the request to EMA and handle 
# the responses from EMA.
#
# Responses are sent to the same origin IP. However, the Tx port is 
# fixed by UDP driver. 
#
# ======================================================================

# ====================================================================

# -----------------+-----------+------------------------------------
#      Command     | Request   | Response [example]
# -----------------+-----------+------------------------------------
# Force Roof Open  | (X007)    | (X007)(16:07:27 Abrir Obs. FORZADO)
# Force Roof Close | (X000)    | (X000)(16:08:11 Cerrar Obs.)
# Force Aux Open   | (S005)    | (S005)(16:12:46 Calentador on.)
# Force Aux  Close | (S004)    | (S004)(16:11:38 Calentador off.)
# Timer Mode On    | (S009)    | (S009)(16:17:05 06/03/2014 Timer ON)
# Timer mode Off   | (S008)    | (S008)(16:15:35 06/03/2014 Timer OFF)
# Hour On          | (SonHHMM) | (SonHHMM)
# Hour Off         | (SofHHMM) | (SofHHMM)
# Aux Relay Status | (s)       | (S009)(Son1900)(Sof2200)


import logging
import re

from server import Alarmable

log = logging.getLogger('command')

def setLogLevel(level):
	log.setLevel(level)

# List of allowed commands
COMMAND = [
	{
    'name'   : 'Roof Force Open',
    'reqPat' : '\(X007\)',            
    'resPat' : ['\(X007\)', '\(\d{2}:\d{2}:\d{2} Abrir Obs. FORZADO\)' ],
	},

	{
    'name'   : 'Roof Force Close',
    'reqPat' : '\(X000\)',            
    'resPat' : ['\(X000\)', '\(\d{2}:\d{2}:\d{2} Cerrar Obs.\)' ],	
	},

	{
    'name'   : 'Aux Relay Force Open',
    'reqPat' : '\(S005\)',            
    'resPat' : ['\(S005\)', '\(\d{2}:\d{2}:\d{2} Calentador on.\)' ],
	},

	{
    'name'   : 'Aux Relay Force Close',
    'reqPat' : '\(S004\)',            
    'resPat' : ['\(S004\)' , '\(\d{2}:\d{2}:\d{2} Calentador off.\)' ],
	},

	{
	'name'   : 'Aux Relay Timer Mode On',
    'reqPat' : '\(S009\)',            
    'resPat' : ['\(S009\)', '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer ON\)' ],
	},

	{
	'name'   : 'Aux Relay Timer Mode Off',
    'reqPat' : '\(S008\)',            
    'resPat' : ['\(S008\)', '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer OFF\)' ],
	},

	{
	'name'   : 'Aux Relay Timer On Hour Set',
    'reqPat' : '\(Son\d{4}\)',            
    'resPat' : ['\(Son\d{4}\)'],
	},

	{
	'name'   : 'Aux Relay Timer Off Hour Set',
    'reqPat' : '\(Sof\d{4}\)',            
    'resPat' : ['\(Sof\d{4}\)'],
	},

	{
	'name'   : 'Aux Relay Status',
    'reqPat' : '\(s\)',            
    'resPat' : ['\(S00\d\)', '\(Son\d{4}\)' , '\(Sof\d{4}\)'],
	},
]

REGEXP = [ re.compile(cmd['reqPat']) for cmd in COMMAND]

def match(message):
	'''Returns matched command descriptor or None'''
	for regexp in REGEXP:
		if regexp.search(message):
			return COMMAND[REGEXP.index(regexp)]
	return None

class Command(Alarmable):

	# Command retry
	RETRIES = 2
	TIMEOUT = 4


	def __init__(self, ema, **kargs):
		self.ema      = ema
		self.name     = kargs['name']
		self.resPat   = [ re.compile(p) for p in kargs['resPat'] ]
		self.indexRes = 0
		self.NRetries = Command.RETRIES

	# --------------
	# Helper methods
	# --------------

	def sendMessage(self, message):
		'''
		Do the actual sending of message to EMA and associated 
		timeout bookeeping
		'''
		n = self.ema.serdriver.queueDelay() + Command.TIMEOUT
		self.setTimeout(n)
		self.ema.addAlarmable(self)
		self.ema.serdriver.write(message)

	# --------------
	# Main interface
	# --------------

	def request(self, message, origin):
		'''Send a request to EMA on behalf of external origin'''
		log.info("executing external command %s", self.name)
		self.origin  = origin
		self.message = message
		self.retries = 0
		self.indexRes= 0
		self.resetAlarm()       
		self.ema.addExternal(self)
		self.sendMessage(message)
		
		
	def onResponseDo(self, message):
		'''Message event handler, handle response from EMA'''
		matched = self.resPat[self.indexRes].search(message)
		if matched:
			self.ema.udpdriver.write(message, self.origin[0])
			self.resetAlarm()
			self.retries = 0
			if (self.indexRes + 1) == len(self.resPat):
				log.debug("Matched command response, command complete")
				self.ema.delAlarmable(self)
				self.ema.delExternal(self)
			else:
				log.debug("Matched command response, awaiting for more")
				self.indexRes += 1
		return matched is not None


	def onTimeoutDo(self):
		'''Timeout event handler'''
		if self.retries < self.NRetries:
			self.retries += 1
			self.sendMessage(self.message)
			log.debug("Timeout waiting for command %s response, retrying", self.message)
		else:	# to END state
			self.ema.delExternal(self)
			log.error("Timeout: EMA not responding to %s command", self.message)
