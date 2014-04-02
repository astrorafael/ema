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
from ema.emaproto  import MVI, MVD
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device

log = logging.getLogger('photomete')

def setLogLevel(level):
    log.setLevel(level)

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

class Photometer(Alarmable, Device):

    MAGNITUDE = 'magnitude'

    def __init__(self, ema, thres, offset, N):
        Alarmable.__init__(self,3)
        self.thres   = Parameter(ema, self, thres, **THRESHOLD)
        self.offset      = Parameter(ema, None, offset, **OFFSET)
        self.photom      = Vector(N)
        ema.addSync(self.thres)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addThreshold(self)
        ema.addParameter(self)


    def add(self, message, matchobj):
        self.photom.append(int(message[MVI:MVI+2])*100 + int(message[MVD:MVD+2]))
        

    def onTimeoutDo(self):
        self.offset.sync()      # trigger offset sync from here


    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return {  Photometer.MAGNITUDE: (self.photom.last() / 100.0 , 'Mv/arcsec^2') }


    @property
    def average(self):
        '''Return dictionary of averaged values over a period of N samples'''
        accum, n = self.photom.sum()
        return { Photometer.MAGNITUDE: (accum/(100.0*n), 'Mv/arcsec^2' ) }


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
