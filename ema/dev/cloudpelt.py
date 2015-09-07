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

from ema.emaproto  import SCLB, SCLE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device
from ema.utils     import chop

log = logging.getLogger('peltier')

def setLogLevel(level):
   log.setLevel(level)


THRESHOLD = {
   'name': 'Cloud Sensor Threshold',
   'logger' : 'peltier',
   'mult' : 1.0,               # multiplier to internal value
   'unit' : '%',               # 
   'get' : '(n)',              # string format for GET request
   'set' : '(N%03d)',          # string format for SET request
   'pat' :  '\(N(\d{3})\)',    # pattern to recognize as response
   'grp'  : 1,                 # match group to extract value and compare
}


GAIN = {
   'name': 'Cloud Sensor Gain',
   'logger' : 'peltier',
   'mult' : 10.0,             # multiplier to internal value
   'unit' : 'none',           # 
   'get' : '(r)',             # string format for GET request
   'set' : '(R%03d)',         # string format for SET request
   'pat' : '\(R(\d{3})\)',    # pattern to recognize as response
   'grp' : 1,                 # match group to extract value and compare
}


class CloudSensor(Device):

   CLOUD = 'cloud'

   def __init__(self, ema, parser, N):
      lvl     = parser.get("CLOUD", "pelt_log")
      log.setLevel(lvl)
      publish_where = chop(parser.get("CLOUD","pelt_publish_where"), ',')
      publish_what  = chop(parser.get("CLOUD","pelt_publish_what"), ',')
      thres   = parser.getfloat("CLOUD", "pelt_thres")
      gain    = parser.getfloat("CLOUD", "pelt_gain")
      Device.__init__(self, publish_where, publish_what)
      self.thres       = Parameter(ema, thres, **THRESHOLD)
      self.gain        = Parameter(ema, gain,  **GAIN)
      self.cloud       = Vector(N)
      ema.addSync(self.thres)
      ema.addSync(self.gain)
      ema.subscribeStatus(self)
      ema.addCurrent(self)
      ema.addAverage(self)
      ema.addThreshold(self)
      ema.addParameter(self)


   def onStatus(self, message, timestamp):
      self.cloud.append(int(message[SCLB:SCLE]))


   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return { CloudSensor.CLOUD: (self.cloud.last() / 10.0 , '%') }


   @property
   def average(self):
      '''Return dictionary averaged values over a period of N samples'''
      accum, n = self.cloud.sum()
      return { CloudSensor.CLOUD: (accum/(10.0*n), '%') }


   @property
   def threshold(self):
      '''Return dictionary with thresholds'''
      return {
         CloudSensor.CLOUD: (self.thres.value / self.thres.mult, self.thres.unit)
      }
      
   @property
   def parameter(self):
      '''Return dictionary with calibration constants'''
      ret = {}
      for param in [self.gain]:
         ret[param.name] = (param.value / param.mult, param.unit)
      return ret
