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

from ema.emaproto  import SAAB, SAAE, SACB, SACE, SWDB, SWDE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('anemomete')

def setLogLevel(level):
    log.setLevel(level)

THRESHOLD_I = {
    'name': 'Current Wind Speed Threshold',
    'logger' : 'anemomete',
    'mult' : 1.0,              # multiplier to internal value
    'unit' : 'Km/h',            # 
    'get' : '(w)',              # string format for GET request
    'set' : '(W%03d)',          # string format for SET request
    'pat' :  '\(W(\d{3})\)',    # pattern to recognize as response
    'grp'  : 1,                 # match group to extract value and compare
}

THRESHOLD_M = {
    'name': 'Average (10m.) Wind Speed Threshold',
    'logger' : 'anemomete',
    'mult' : 1.0,              # multiplier to internal value
    'unit' : 'Km/h',           # 
    'get' : '(o)',             # string format for GET request
    'set' : '(O%03d)',         # string format for SET request
    'pat' : '\(O(\d{3})\)',    # pattern to recognize as response
    'grp' : 1,                 # match group to extract value and compare
}

CALIBRATION = {
    'name': 'Anemometer Calibration Constant',
    'logger' : 'anemomete',
    'mult' : 1.0,              # multiplier to internal value
    'unit' : 'dependant',      # 
    'get' : '(a)',             # string format for GET request
    'set' : '(A%03d)',         # string format for SET request
    'pat' : '\(A(\d{3})\)',    # pattern to recognize as response
    'grp' : 1,                 # match group to extract value and compare
}

MODEL = {
    'name': 'Anemometer Model',
    'logger' : 'anemomete',
    'mult': 1.0,               # multiplier to internal value
    'unit': '',                # 
    'get' : '(z)',             # string format for GET request
    'set' : '(Z%03d)',         # string format for SET request
    'pat' : '\(Z(\d{3})\)',    # pattern to recognize as response
    'grp' : 1,                 # match group to extract value and compare
}



class Anemometer(Device):

    # current value keys in dictionary
    SPEED     = 'speed'
    SPEED10   = 'speed10'
    DIRECTION = 'direction'

    def __init__(self, ema, thres, aver_thres, calibration, model, N, publish):
	Device.__init__(self, publish)
        self.windth    = Parameter(ema, None, thres, **THRESHOLD_I)
        self.wind10th  = Parameter(ema, None, aver_thres, **THRESHOLD_M)
        self.calib     = Parameter(ema, None, calibration, **CALIBRATION)
        self.model     = Parameter(ema, None, model, **MODEL)
        self.windSpeed   = Vector(N)
        self.windSpeed10 = Vector(N)
        self.windDir     = Vector(N)
        ema.addSync(self.windth)
        ema.addSync(self.wind10th)
        ema.addSync(self.calib)
        ema.addSync(self.model)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addThreshold(self)
        ema.addParameter(self)
       

    def onStatus(self, message):
        self.windSpeed.append(int(message[SACB:SACE]))
        self.windSpeed10.append(int(message[SAAB:SAAE]))
        self.windDir.append(int(message[SWDB:SWDE]))


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return {
            Anemometer.SPEED:  (self.windSpeed.last() / 10.0 , "Km/h"),
            Anemometer.SPEED10:   (float(self.windSpeed10.last()) , "Km/h"),
            Anemometer.DIRECTION: (float(self.windDir.last()) , "degrees")
        }


    @property
    def average(self):
        '''Return dictionary averaged values over a period of N samples'''
        accum, n = self.windSpeed.sum()
        av1 = (accum/(10.0*n), "Km/h")
        accum, n = self.windSpeed10.sum()
        av2 = (float(accum) / n, "Km/h")
        accum, n = self.windDir.sum()
        av3 = (float(accum) / n, "degrees")
        return { 
            Anemometer.SPEED: av1, 
            Anemometer.SPEED10: av2, 
            Anemometer.DIRECTION: av3 
            }
    

    @property
    def threshold(self):
         '''Return a dictionary with thresholds'''
         return {
            Anemometer.SPEED: (self.windth.value / self.windth.mult, self.windth.unit) ,
            Anemometer.SPEED10: (self.wind10th.value / self.wind10th.mult, self.wind10th.unit)
        }
         
    
    @property
    def parameter(self):
        '''Return a dictionary with calibration constants'''
        return {
            self.calib.name: (self.calib.value / self.calib.mult, self.calib.unit)
        }
