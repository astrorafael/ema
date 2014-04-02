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

from ema.emaproto  import SPYB, SPYE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('pyranomet')

def setLogLevel(level):
    log.setLevel(level)

GAIN = {
    'name': 'Pyranometer Gain',
    'logger' : 'pyranomet',
    'mult' : 10.0,              # multiplier to internal value
    'unit' : '',                # dimensonless
    'get' : '(j)',              # string format for GET request
    'set' : '(J%03d)',          # string format for SET request
    'pat' : '\(J(\d{3})\)',     # pattern to recognize as response
    'grp'  : 1,                 # match group to extract value and compare
}

OFFSET = {
    'name': 'Pyranometer Offset',
    'logger' : 'pyranomet',
    'mult' : 1.0,               # multiplier to internal value
    'unit' : '?',               # unknown to me :-)
    'get' : '(u)',              # string format for GET request
    'set' : '(U%03d)',          # string format for SET request
    'pat' : '\(U(\d{3})\)',     # pattern to recognize as response
    'grp'  : 1,                 # match group to extract value and compare
}



class Pyranometer(Device):

    IRRADIATION = 'irradiation'

    def __init__(self, ema, gain, offset, N):
        self.gain   = Parameter(ema, None, gain, **GAIN)
        self.offset = Parameter(ema, None, offset, **OFFSET)
        self.led    = Vector(N)
        ema.addSync(self.gain)
        ema.addSync(self.offset)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addParameter(self)


    def onStatus(self, message):
        self.led.append(int(message[SPYB:SPYE]))


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return { Pyranometer.IRRADIATION: (self.led.last() / 10.0 , '%') }


    @property
    def average(self):
        '''Return dictionary averaged values over a period of N samples'''
        accum, n = self.led.sum()
        return { Pyranometer.IRRADIATION: (accum/(10.0*n), '%') }


    @property
    def parameter(self):
        '''Return dictionary with calibration constants'''
        ret = {}
        for param in [self.gain, self.offset]:
            ret[param.name] = (param.value / param.mult, param.unit)
        return ret


