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

from ema.emaproto  import SPSB, PERIOD
from ema.parameter import Parameter
from ema.vector    import Vector
from ema.device    import Device
from ema.utils     import chop

log = logging.getLogger('voltmeter')

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

class Voltmeter(Device):

    VOLTAGE = 'voltage'

    def __init__(self, ema, parser, N):
        lvl = parser.get("VOLTMETER", "volt_log")
        log.setLevel(lvl)
        thres   = parser.getfloat("VOLTMETER", "volt_thres")
        offset  = parser.getfloat("VOLTMETER", "volt_offset")
        delta   = parser.getfloat("VOLTMETER", "volt_delta")
        time    = parser.getint("VOLTMETER",    "volt_time")
        publish_where = chop(parser.get("VOLTMETER","volt_publish_where"), ',')
        publish_what  = chop(parser.get("VOLTMETER","volt_publish_what"), ',')
        scripts = chop(parser.get("VOLTMETER","low_volt_script"), ',')
        mode    = parser.get("VOLTMETER","low_volt_mode")
	Device.__init__(self, publish_where, publish_what)
        self.ema         = ema
        self.offset      = Parameter(ema, offset, **OFFSET)
        self.thres       = Parameter(ema, thres, self.offset, **THRESHOLD)
        self.voltage     = Vector(N)
        self.averlen     = int(round(time / PERIOD))
        self.lowvolt     = delta + thres
        ema.addSync(self.thres)
        ema.subscribeStatus(self)
        ema.addCurrent(self)
        ema.addAverage(self)
        ema.addThreshold(self)
        ema.addParameter(self)
	for script in scripts:
		ema.notifier.addScript('VoltageLow',mode,script)
       

    def onStatus(self, message, timestamp):
        self.voltage.append(ord(message[SPSB]), timestamp)
        accum, n = self.voltage.sum(self.averlen)
        average = accum / (n * 10.0)
        if average < self.lowvolt:
            self.ema.notifier.onEventExecute('VoltageLow', '--voltage', "%.1f" % average, '--threshold', "%.1f" % self.lowvolt, '--size' , str(n))


    def timespan(self):
        '''Return the bounding timespan objects and sample length'''
        return self.voltage.newest()[1],  self.voltage.oldest()[1],  self.voltage.len()

    @property
    def current(self):
        '''Return dictionary with current measured values'''
        return { Voltmeter.VOLTAGE: (self.voltage.newest()[0] / 10.0 , "V") }

    @property
    def raw_current(self):
        '''Return dictionary with current measured values'''
        return { Voltmeter.VOLTAGE: self.voltage.newest()[0] }


    @property
    def average(self):
        '''Return dictionary of averaged values over a period of N samples'''
        accum, n = self.voltage.sum()
        return { Voltmeter.VOLTAGE: (accum/(10.0*n), "V") }

    @property
    def raw_average(self):
        '''Return dictionary of averaged values over a period of N samples'''
        accum, n = self.voltage.sum()
        return { Voltmeter.VOLTAGE: float(accum)/n }


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
