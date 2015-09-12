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
# The v1.0 implemnentation  handled command response as simply writtimg
# back to the UDP port with the same originating IP.
#
# Version v2.0 generalizes the command response by introducing 2 callback methods:
#  - onPartialCommand(message, userdata)
#  - on CommandComplete(message, userdata)
#
# Verion v2.0 also generalized the response string expected from EMA to handle
# the bulk dum responses from EMA, where response messages are organized 
# in a 3 x 24 pattern
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
# 24h Bulk Dump    | (@H0000)  | (<EMA STATUS LINE>)(<EMA STATUS LINE>)(16:17:05 06/03/2014) x 24 times


import logging
import re
from   abc import abstractmethod


from server   import Server, Alarmable
from emaproto import STATLENEXT

log = logging.getLogger('command')

# List of allowed commands
COMMAND = [
   {
    'name'   : 'Roof Force Open',
    'reqPat' : '\(X007\)',            
    'resPat' : ['\(X007\)', '\(\d{2}:\d{2}:\d{2} Abrir Obs. FORZADO\)' ],
    'iterations'   : 1,
   },

   {
    'name'   : 'Roof Force Close',
    'reqPat' : '\(X000\)',            
    'resPat' : ['\(X000\)', '\(\d{2}:\d{2}:\d{2} Cerrar Obs.\)' ],   
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Force Open',
    'reqPat' : '\(S005\)',            
    'resPat' : ['\(S005\)', '\(\d{2}:\d{2}:\d{2} Calentador on.\)' ],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Force Close',
    'reqPat' : '\(S004\)',            
    'resPat' : ['\(S004\)' , '\(\d{2}:\d{2}:\d{2} Calentador off.\)' ],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Timer Mode On',
    'reqPat' : '\(S009\)',            
    'resPat' : ['\(S009\)', '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer ON\)' ],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Timer Mode Off',
    'reqPat' : '\(S008\)',            
    'resPat' : ['\(S008\)', '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4} Timer OFF\)' ],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Timer On Hour Set',
    'reqPat' : '\(Son\d{4}\)',            
    'resPat' : ['\(Son\d{4}\)'],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Timer Off Hour Set',
    'reqPat' : '\(Sof\d{4}\)',            
    'resPat' : ['\(Sof\d{4}\)'],
    'iterations'   : 1,
   },

   {
    'name'   : 'Aux Relay Status',
    'reqPat' : '\(s\)',            
    'resPat' : ['\(S00\d\)', '\(Son\d{4}\)' , '\(Sof\d{4}\)'],
    'iterations'   : 1,
   },

   {
    'name'   : '24h Hourly MinMax Bulk Dump',
    'reqPat' : '\(@H\d{4}\)',            
    'resPat' : ['\(.{76}M\d{4}\)', '\(.{76}m\d{4}\)', '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)'],
    'iterations'   : 24,
   },

   {
    'name'   : '24h 5m Averages Bulk Dump',
    'reqPat' : '\(@t\d{4}\)',            
    'resPat' : ['\(.{76}t\d{4}\)'],
    'iterations'   : 288,
   },

]

REGEXP = [ re.compile(cmd['reqPat']) for cmd in COMMAND]

def match(message):
   '''Returns matched command descriptor or None'''
   for regexp in REGEXP:
      if regexp.search(message):
         return COMMAND[REGEXP.index(regexp)]
   return None

# Note that command inherits form Alarmable, which already has
# ABMeta as its metaclass 
class Command(Alarmable):

   # Command retry
   RETRIES = 2
   TIMEOUT = 4


   def __init__(self, ema, retries =RETRIES, **kargs):
      Alarmable.__init__(self, Command.TIMEOUT)
      self.ema      = ema
      self.name     = kargs['name']
      self.resPat   = [ re.compile(p) for p in kargs['resPat'] ]
      self.indexRes        = 0
      self.NRetries        = retries
      self.NIterations     = kargs['iterations']
      self.iteration       = 1
      self.partialHandler  = None
      self.completeHandler = None

   # --------------
   # Helper methods
   # --------------

   def sendMessage(self, message):
      '''
      Do the actual sending of message to EMA and associated 
      timeout bookeeping
      '''
      t = self.ema.serdriver.queueDelay()*Server.TIMEOUT + Command.TIMEOUT*self.NIterations
      self.setTimeout(t)
      self.resetAlarm()
      self.ema.addAlarmable(self)
      self.ema.serdriver.write(message)

   # --------------
   # Main interface
   # --------------

   def request(self, message, userdata):
      '''Send a request to EMA on behalf of external origin'''
      log.debug("executing external command %s", self.name)
      self.userdata  = userdata
      self.message   = message
      self.retries   = 0
      self.indexRes  = 0
      self.iteration = 1
      self.resetAlarm()       
      self.ema.addCommand(self)
      self.sendMessage(message)
      
      
   def onResponseDo(self, message):
      '''Message event handler, handle response from EMA'''
      log.debug("trying to match %s", message)
      matched = self.resPat[self.indexRes].search(message)
      if matched:
         self.resetAlarm()
         self.retries = 0
         if (self.indexRes + 1) == len(self.resPat) and self.iteration == self.NIterations:
            log.debug("Matched command response, command complete")
            self.ema.delAlarmable(self)
            self.ema.delCommand(self)
            self.onCommandComplete(message, self.userdata)
         elif (self.indexRes + 1) == len(self.resPat) and self.iteration < self.NIterations:
            log.debug("Matched command response, iteration complete")
            self.iteration += 1
            self.indexRes = 0
            self.onPartialCommand(message, self.userdata)
         else:
            log.debug("Matched command response (iteration %d), awaiting for more", self.iteration)
            self.indexRes += 1
            self.onPartialCommand(message, self.userdata)
      return matched is not None


   def onTimeoutDo(self):
      '''Timeout event handler'''
      if self.retries < self.NRetries:
         self.retries += 1
         self.sendMessage(self.message)
         log.debug("Timeout waiting for command %s response, retrying", self.message)
      else: # to END state
         self.ema.delCommand(self)
         log.error("Timeout: EMA not responding to %s command", self.message)
   
   # ----------------------------------------------
   # Abstract methods to be overriden in subclasses
   # ----------------------------------------------

   @abstractmethod
   def onPartialCommand(self, message, userdata):
      '''To be subclassed and overriden'''
      pass

   @abstractmethod
   def onCommandComplete(self, message, userdata):
      '''To be subclassed and overriden'''
      pass



