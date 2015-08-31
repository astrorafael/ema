# -*- coding: iso-8859-15 -*-

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

from ema.emaproto  import THERMOINF
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('thermopil')

def setLogLevel(level):
   log.setLevel(level)


# Thermopile values (in magnitudes) do not come in status messages
# but in an independent message so there is no onStatus() method

class Thermopile(Device):

   SKY     = 'sky'
   AMBIENT = 'ambient'

   def __init__(self, ema, parser, N):
      lvl = parser.get("THERMOPILE", "thermop_log")
      log.setLevel(lvl)
      publish_where = parser.get("THERMOPILE","thermop_publish_where").split(',')
      publish_what = parser.get("THERMOPILE","thermop_publish_what").split(',')
      Device.__init__(self, publish_where, publish_what)
      self.infrared = Vector(N)
      self.capsule  = Vector(N)
      ema.addCurrent(self)
      ema.addAverage(self)


   def add(self, message, matchobj):
      log.debug("themopile.add(%s)", message)
      temp = float(matchobj.group(1))
      if message[THERMOINF] == '0':
         self.infrared.append(temp) 
      else:
         self.capsule.append(temp)

   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return { 
         Thermopile.SKY:     (self.infrared.last() , ' deg C'),
         Thermopile.AMBIENT: (self.capsule.last()  , ' deg C')
         }

   @property
   def average(self):
      '''Return dictionary of averaged values over a period of N samples'''
      accum, n = self.infrared.sum()
      av1  = (accum / n, ' deg C')
      accum, n = self.capsule.sum()
      av2 = (accum / n, ' deg C')
      return {  Thermopile.SKY: av1 , Thermopile.AMBIENT: av2 }

   
