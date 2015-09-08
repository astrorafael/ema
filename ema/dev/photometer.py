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


from ema.emaproto  import MVI, MVD
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device
from ema.utils     import chop

log = logging.getLogger('photomete')

THRESHOLD = {
   'name': 'Photometer Threshold',
   'logger' : 'photomete',
   'mult': 10.0,              # multiplier to internal value
   'unit': 'Mv/arcsec^2',     # 
   'get' : '(i)',             # string format for GET request
   'set' : '(I%03d)',         # string format for SET request
   'pat' : '\(I(\d{3})\)',    # pattern to recognize as response
   'grp' : 1,                 # match group to extract value and compare
}


OFFSET = {
   'name': 'Photometer Offset',
   'logger' : 'photomete',
   'mult': 10.0,              # multiplier to internal value
   'unit': 'Mv/arcsec^2',     # Visual Magnitude
   'get' : '(i)',             # string format for GET request
   'set' : '(I%+03d)',        # string format for SET request
   'pat' : '\(I([+-]\d{2})\)', # pattern to recognize as response
   'grp' : 1,                 # match group to extract value and compare
}

# inheriting from alarmable is a kludge to solve the two message respones issue
# in photometer adjustments

# Photometer values (in magnitudes) do not come in status messages
# but in an independent message so there is no onStatus() method

# This is a hack. It should go away
from datetime import datetime

def xtFrequency(message):
   '''Extract and Transform into Instrumental Magnitude in Hz'''
   exp  = int(message[SPHB]) - 3      
   mant = int(message[SPHB+1:SPHE])
   return mant*pow(10, exp)


class Photometer(Device):

   MAGNITUDE = 'magnitude'
   FREQUENCY = 'frequency'

   def __init__(self, ema, parser, N):
      lvl     = parser.get("PHOTOMETER", "phot_log")
      log.setLevel(lvl)
      publish_where = chop(parser.get("PHOTOMETER","phot_publish_where"), ',')
      publish_what = chop(parser.get("PHOTOMETER","phot_publish_what"), ',')
      offset  = parser.getfloat("PHOTOMETER", "phot_offset")
      thres   = parser.getfloat("PHOTOMETER", "phot_thres")
      Device.__init__(self,publish_where,publish_what)
      self.offset      = Parameter(ema, offset, **OFFSET)
      self.thres       = Parameter(ema, thres,  self.offset, **THRESHOLD)
      self.photom      = Vector(N)
      self.freq        = Vector(N)
      ema.addSync(self.thres)
      ema.subscribeStatus(self)
      ema.addCurrent(self)
      ema.addAverage(self)
      ema.addThreshold(self)
      ema.addParameter(self)

   def onStatus(self, message, timestamp):
      '''Dummy onStatus() implementation'''
      self.freq.append( (xtFrequency(message) ,timestamp) )


   def add(self, message, matchobj):
      self.photom.append(int(message[MVI:MVI+2])*100 + int(message[MVD:MVD+2]),
                         datetime.utcnow())
      

   @property
   def current(self):
      '''Return dictionary with current measured values'''
      return {  
         Photometer.MAGNITUDE: (self.photom.newest()[0]/100.0 , 'Mv/arcsec^2'),
         Photometer.FREQUENCY:  (self.freq.newest()[0], 'Hz'),
      }

   @property
   def raw_current(self):
      '''Return dictionary with current measured values'''
      return {  
         Photometer.MAGNITUDE:  self.photom.newest()[0],
         Photometer.FREQUENCY:  self.freq.newest()[0],
      }


   @property
   def average(self):
      '''Return dictionary of averaged values over a period of N samples'''
      accum, n = self.photom.sum()
      mv = accum/(100.0*n)
      accum, n = self.freq.sum()
      freq = float(accum)/n

      return { 
         Photometer.MAGNITUDE: (mv, 'Mv/arcsec^2' ), 
         Photometer.FREQUENCY: (freq, 'Hz' ), 
      }

   @property
   def raw_average(self):
      '''Return dictionary of averaged values over a period of N samples'''
      accum, n = self.photom.sum()
      mv = float(accum)/n  
      accum, n = self.freq.sum()
      freq = float(accum)/n
      return { 
         Photometer.MAGNITUDE: mv,  
         Photometer.FREQUENCY: freq, 
      }


   @property
   def threshold(self):
      '''Return dictionary with thresholds'''
      return {
         Photometer.MAGNITUDE: (self.thres.value / self.thres.mult, self.thres.unit)
      }

   @property
   def parameter(self):
      '''Return dictionary with calibration constants'''
      ret = {}
      for param in [self.offset]:
         ret[param.name] = (param.value / param.mult, param.unit)
      return ret
