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
from ema.utils     import chop

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
      publish_where = chop(parser.get("ROOF_RELAY","roof_relay_publish_where"), ',')
      publish_what  = chop(parser.get("ROOF_RELAY","roof_relay_publish_what"), ',')
      scripts       = chop(parser.get("ROOF_RELAY","roof_relay_script"), ',')
      relay_mode    = parser.get("ROOF_RELAY","roof_relay_mode")
      Device.__init__(self, publish_where, publish_what)
      self.relay    = Vector(N)
      self.rawrelay = Vector(N)
      self.ema   = ema
      ema.subscribeStatus(self)
      ema.addCurrent(self)
      ema.addAverage(self)
      for script in scripts:
         ema.notifier.addScript('RoofRelaySwitch', relay_mode, script)
      

   def toBoolean(self, c):
      return False if c == 'C' else True

   def onStatus(self, message, timestamp):
      '''Roof Relay, accumulate open (True) /close (False) readings'''
      c = message[SRRB]
      openFlag = self.toBoolean(c)
      val = ord(c)

      # Handle initial feed
      if self.relay.len() == 0:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         return

      # Detects Open -> Close transitions and notify
      if self.relay.newest()[0] and not openFlag:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         self.ema.notifier.onEventExecute('RoofRelaySwitch', "--status" , OFF, "--reason", c)

      # Detects Close-> Open transitions and notify
      elif not self.relay.newest()[0] and openFlag:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         self.ema.notifier.onEventExecute('RoofRelaySwitch', "--status" , ON, "--reason", c)
      else:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)


   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return { RoofRelay.OPEN: (self.relay.newest()[0] , '') }

   @property
   def raw_current(self):
      '''Return dictionary with current measured values'''
      return { RoofRelay.OPEN: chr(self.rawrelay.newest()[0]) }


   @property
   def average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.relay.sum()
      return { RoofRelay.OPEN: ((accum*100.0)/n, '%') }

   #@property
   #def raw_average(self):


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
      self.aux_mode = parser.get("AUX_RELAY", "aux_mode")
      scripts       = chop(parser.get("AUX_RELAY","aux_relay_script"), ',')
      script_mode   = parser.get("AUX_RELAY","aux_relay_mode")
      publish_where = chop(parser.get("AUX_RELAY","aux_relay_publish_where"), ',')
      publish_what  = chop(parser.get("AUX_RELAY","aux_relay_publish_what"), ',')
      sync          = parser.getboolean("AUX_RELAY","aux_sync")
      Device.__init__(self, publish_where, publish_what)
      self.ema      = ema
      self.ton      = None
      self.toff     = None
      self.mode     = None
      self.relay    = Vector(N)
      self.rawrelay = Vector(N)
      self.sync     = sync
      #ema.addSync(self.mode)
      ema.subscribeStatus(self)
      ema.addParameter(self)
      for script in scripts:
         ema.notifier.addScript('AuxRelaySwitch', script_mode, script)
      if AuxRelay.MAPPING[self.mode] == AuxRelay.TIMED:
         ema.todtimer.addSubscriber(self)

   def toBoolean(self, c):
      return True if c == 'E' or c == 'e' else False

   # -------------------------------------------
   # Implements the EMA status message interface
   # -------------------------------------------

   def onStatus(self, message, timestamp):
      '''Aux Relay, accumulate open/close readings'''
      c = message[SARB]
      openFlag = self.toBoolean(c)
      val = ord(c)                # convert to an integer

      # Handle initial feed
      if self.relay.len() == 0:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         return

      # Detects Open -> Close transitions and notify
      if self.relay.newest()[0] and not openFlag:
         log.warning("Aux Relay Switch Off: %s", AuxRelay.REASON[c])
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , OFF, "--reason", c)
      # Detects Close-> Open transitions and notify
      elif not self.relay.newest()[0] and openFlag:
         log.warning("Aux Relay Switch On: %s", AuxRelay.REASON[c])
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)
         self.ema.notifier.onEventExecute('AuxRelaySwitch', "--status" , ON, "--reason", c)
      else:
         self.relay.append(openFlag, timestamp)
         self.rawrelay.append(val, timestamp)

   # ----------
   # Properties
   # ----------

   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return { AuxRelay.OPEN: (self.relay.newest()[0], '') }

   @property
   def raw_current(self):
      '''Return dictionary with current measured values'''
      return { AuxRelay.OPEN: self.rawrelay.newest()[0] }

   @property
   def average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.relay.sum()
      return { AuxRelay.OPEN: ((accum*100.0)/n, '%') }

   #@property
   #def raw_average(self):

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
      self.toff = Parameter(self.ema, tOFF, sync=self.sync, **TOFF)
      self.ton  = Parameter(self.ema, tON, self.toff, sync=self.sync, **TON)
      self.mode = Parameter(self.ema, AuxRelay.MAPPING[self.aux_mode], self.ton, sync=self.sync, **MODE) 
      self.ton.sync()
