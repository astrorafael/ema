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
import re

from ema.emaproto  import SATB, SATE, SRHB, SRHE, SDPB, SDPE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device
from ema.utils     import chop

log = logging.getLogger('thermomet')


def setLogLevel(level):
   log.setLevel(level)

THRESHOLD = {
   'name': 'Thermometer DeltaT Threshold',
   'logger' : 'thermomet',
   'mult' : 1.0,               # multiplier to internal value
   'unit' : 'deg C',               # degrees Celsius
   'get' : '(c)',              # string format for GET request
   'set' : '(C%03d)',          # string format for SET request
   'pat' : '\(C(\d{3})\)',     # pattern to recognize as response
   'grp' : 1,                  # group to extract value and compare
}


class Thermometer(Device):

   AMBIENT  = 'ambient'
   HUMIDITY = 'humidity'
   DEWPOINT = 'dewpoint'

   def __init__(self, ema, parser, N):
      lvl = parser.get("THERMOMETER", "thermo_log")
      log.setLevel(lvl)
      publish_where = chop(parser.get("THERMOMETER","thermo_publish_where"), ',')
      publish_what  = chop(parser.get("THERMOMETER","thermo_publish_what"), ',')
      thres   = parser.getfloat("THERMOMETER", "delta_thres")
      Device.__init__(self, publish_where, publish_what)
      self.thres    = Parameter(ema, thres, **THRESHOLD)
      self.ambient  = Vector(N)
      self.humidity = Vector(N)
      self.dewpoint = Vector(N)
      ema.addSync(self.thres)
      ema.subscribeStatus(self)
      ema.addCurrent(self)
      ema.addAverage(self)
      ema.addThreshold(self)


   def onStatus(self, message):
      self.ambient.append(int(message[SATB:SATE]))
      self.humidity.append(int(message[SRHB:SRHE]))
      self.dewpoint.append(int(message[SDPB:SDPE]))

   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return { 
         Thermometer.AMBIENT:  (self.ambient.last()  / 10.0 , 'deg C'),
         Thermometer.HUMIDITY: (self.humidity.last() / 10.0 , '%'),
         Thermometer.DEWPOINT: (self.dewpoint.last() / 10.0 , 'deg C')
         }

   @property
   def average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.ambient.sum()
      av1 = (accum/(10.0*n), 'deg C')
      accum, n = self.humidity.sum()
      av2 = (accum/(10.0*n), '%')
      accum, n = self.dewpoint.sum()
      av3 = (accum/(10.0*n), 'deg C')
      return { 
         Thermometer.AMBIENT: av1, 
         Thermometer.HUMIDITY: av2, 
         Thermometer.DEWPOINT: av3
         }

   @property
   def threshold(self):
      '''Return dictionary with thresholds'''
      return {
         Thermometer.AMBIENT: (self.thres.value / self.thres.mult, self.thres.unit)
      }
      
