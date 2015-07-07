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

from ema.server    import Alarmable
from ema.emaproto  import SPSB
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('voltmeter')

def setLogLevel(level):
    log.setLevel(level)

THRESHOLD = {
    'name': 'Voltmeter Threshold',
    'logger': 'voltmeter' ,
    'mult': 10.0,               # multiplier to internal value
    'unit': 'V',
    'get' : '(f)',              # string format for GET request
    'set' : '(F%03d)',          # string format for SET request
    'pat' : '\(F(\d{3})\)',     # pattern to recognize as response
    'grp' : 1,                  # match group to extract value and compare
}

OFFSET = {
    'name': 'Voltmeter Offset',
    'logger' : 'voltmeter' ,
    'mult': 10.0,                   # multiplier to internal value
    'unit': 'V',
    'get' : '(f)',                  # string format for GET request
    'set' : '(F%+03d)',             # string format for SET request
    'pat' :  '\(F([+-]\d{2})\)',    # pattern to recognize as response
    'grp' : 1,                      # group to extract value and compare
}


# inheriting from alarmable is a kludge to solve the two message respones issue
# in voltmeter adjustments

class Voltmeter(Alarmable, Device):

    VOLTAGE = 'voltage'

    def __init__(self, ema, thres, offset, volt_delta, N, AVLEN):
        Alarmable.__init__(self,3)
	Device.__init__(self)
        self.ema         = ema
        self.thres       = Parameter(ema, self, thres, **THRESHOLD)
        self.offset      = Parameter(ema, None, offset, **OFFSET)
        self.voltage     = Vector(N)
        self.averlen     = AVLEN
        self.lowvolt     = volt_delta + thres
        ema.addSync(self.thres)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addThreshold(self)
        ema.addParameter(self)
       

    def onStatus(self, message):
        self.voltage.append(ord(message[SPSB]))
        accum, n = self.voltage.sum(self.averlen)
        average = accum / (n * 10.0)
        if average < self.lowvolt:
            self.ema.onVoltageLow("%.1f" % average, "%.1f" % self.lowvolt, str(n))


    def onTimeoutDo(self):
        self.offset.sync()      # trigger offset sync from here


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return { Voltmeter.VOLTAGE: (self.voltage.last() / 10.0 , "V") }


    @property
    def average(self):
        '''Return dictionary of averaged values over a period of N samples'''
        accum, n = self.voltage.sum()
        return { Voltmeter.VOLTAGE: (accum/(10.0*n), "V") }


    @property
    def threshold(self):
        '''Return dictionary with thresholds'''
        return {
             Voltmeter.VOLTAGE: (self.thres.value / self.thres.mult, self.thres.unit)
        }


    @property
    def parameter(self):
        '''Return dictionary with calibration constants'''
        return {
            self.offset.name: (self.offset.value / self.offset.mult , self.offset.unit )
        }
