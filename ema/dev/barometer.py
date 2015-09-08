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

from ema.emaproto  import SABB, SABE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device
from ema.utils     import chop

log = logging.getLogger('barometer')

def setLogLevel(level):
   log.setLevel(level)

HEIGHT = {
   'name': 'Barometer Height',
   'logger' : 'barometer' ,
   'mult' : 1.0,               # multiplier to internal value
   'unit' : 'm',               # meters
   'get' : '(m)',              # string format for GET request
   'set' : '(M%05d)',          # string format for SET request
   'pat' :  '\(M(\d{5})\)',    # pattern to recognize as response
   'grp'  : 1,                 # match group to extract value and compare
}

OFFSET = {
   'name': 'Barometer Offset',
   'logger' : 'barometer' ,
   'mult' : 1.0,              # multiplier to internal value
   'unit' : 'mBar',           # millibars
   'get' : '(b)',             # string format for GET request
   'set' : '(B%+03d)',        # string format for SET request
   'pat' : '\(B([+-]\d{2})\)',    # pattern to recognize as response
   'grp' : 1,                 # match group to extract value and compare
}



class Barometer(Device):

   PRESSURE     = 'abs_pressure'
   CAL_PRESSURE = 'cal_pressure'

   def __init__(self, ema, parser, N):
      lvl = parser.get("BAROMETER", "barom_log")
      log.setLevel(lvl)
      publish_where = chop(parser.get("BAROMETER","barom_publish_where"), ',')
      publish_what = chop(parser.get("BAROMETER","barom_publish_what"), ',')
      height  = parser.getfloat("BAROMETER", "barom_height")
      offset  = parser.getfloat("BAROMETER", "barom_offset")
      Device.__init__(self, publish_where, publish_what)
      self.height    = Parameter(ema, height, **HEIGHT)
      self.offset    = Parameter(ema, offset, **OFFSET)
      self.abspress  = Vector(N)
      self.calpress  = Vector(N)
      ema.addSync(self.height)
      ema.addSync(self.offset)
      ema.subscribeStatus(self)
      ema.addCurrent(self)
      ema.addAverage(self)
      ema.addParameter(self)


   def onStatus(self, message, timestamp):
      self.abspress.append(int(message[SABB:SABE]), timestamp)
      self.abspress.append(int(message[SCBB:SCBE]), timestamp)

   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return {
         Barometer.PRESSURE: (self.abspress.newest()[0] / 10.0 , "HPa"),
         Barometer.CAL_PRESSURE: (self.calpress.newest()[0] / 10.0 , "HPa"),
      }

   
   @property
   def raw_current(self):
      '''Return dictionary with current measured values'''
      return {
         Barometer.PRESSURE: self.abspress.newest()[0],
         Barometer.CAL_PRESSURE: self.calpress.newest()[0],
      }


   @property
   def average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.abspress.sum()
      abspres  = ( accum/(10.0*n), "HPa" )
      accum, n = self.calpress.sum()
      calpres  = ( accum/(10.0*n), "HPa" )
      return { 
         Barometer.PRESSURE:     abspres,
         Barometer.CAL_PRESSURE: calpres,
      }


   @property
   def raw_average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.abspress.sum()
      abspres  = float(accum)/n
      accum, n = self.calpress.sum()
      calpres  = float(accum)/n
      return { 
         Barometer.PRESSURE:     abspres,
         Barometer.CAL_PRESSURE: calpres, 
      }


   @property
   def parameter(self):
      '''Return dictionary with calibration constants'''
      ret = {}
      for param in [self.height, self.offset]:
         ret[param.name] = (param.value / param.mult, param.unit)
      return ret
