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

from ema.emaproto  import SPCB, SPCE, SPAB, SPAE
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('pluviomet')

def setLogLevel(level):
    log.setLevel(level)

CALIBRATION = {
    'name': 'Pluviometer Calibration constant',
    'logger': 'pluviomet',
    'mult': 1.0,                # multiplier to internal value
    'unit': 'l',
    'get' : '(p)',              # string format for GET request
    'set' : '(P%03d)',          # string format for SET request
    'pat' :  '\(P(\d{3})\)',    # pattern to recognize as response
    'grp' : 1,                  # group to extract value and compare
}


class Pluviometer(Device):

    CURRENT     = 'current'
    ACCUMULATED = 'accumulated'

    def __init__(self, ema, calibration, N):
        self.calibration   = Parameter(ema, None, calibration, **CALIBRATION)
        self.instant       = Vector(N)
        self.accumulated   = Vector(N)
        ema.addSync(self.calibration)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addParameter(self)


    def onStatus(self, message):
        self.instant.append(int(message[SPCB:SPCE]))
        self.accumulated.append(int(message[SPAB:SPAE]))


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return {
            Pluviometer.CURRENT:     (self.instant.last() / 10.0  , "mm"),
            Pluviometer.ACCUMULATED: (float(self.accumulated.last())  , "mm"),
        }


    @property
    def average(self):
        '''Return dictionary averaged values over a period of N samples'''
        accum, n = self.instant.sum()
        av1 = (accum/(10.0*n), "mm")
        accum, n = self.accumulated.sum()
        av2 = (float(accum)/n, "mm")
        return { Pluviometer.CURRENT: av1, 'accumulated': av2 }


    @property
    def parameter(self):
        '''Return tdictionary with calibration constants'''
        return {
            self.calibration.name: (self.calibration.value / self.calibration.mult, self.calibration.unit )
        }
        

