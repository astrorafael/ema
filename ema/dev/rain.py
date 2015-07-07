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

from ema.emaproto  import SRAB, SRAE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('rainsenso')

def setLogLevel(level):
    log.setLevel(level)

THRESHOLD = {
    'name': 'Rain Sensor Threshold',
    'logger' : 'rainsenso',
    'mult' : 1.0,               # multiplier to internal value
    'unit' : 'mm',
    'get' : '(l)',              # string format for GET request
    'set' : '(L%03d)',          # string format for SET request
    'pat' :  '\(L(\d{3})\)',    # pattern to recognize as response
    'grp'  : 1,                 # group to extract value and compare
}


class RainSensor(Device):

    RAIN = 'rain'

    def __init__(self, ema, thres, N, publish):
	Device.__init__(self, publish)
        self.thres     = Parameter(ema, None, thres, **THRESHOLD)
        self.rain      = Vector(N)
        ema.addSync(self.thres)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addThreshold(self)



    def onStatus(self, message):
        self.rain.append(int(message[SRAB:SRAE]))


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return { RainSensor.RAIN: (self.rain.last() / 10.0 , 'mm') }


    @property
    def average(self):
        '''Return dictionary averaged values over a period of N samples'''
        accum, n = self.rain.sum()
        return { RainSensor.RAIN: (accum/(10.0*n), 'mm') }

    @property
    def threshold(self):
        '''Return dictionary with thresholds'''
        return {
            RainSensor.RAIN: (self.thres.value / self.thres.mult, self.thres.unit)
        }
