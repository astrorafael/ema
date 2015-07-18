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

from ema.server    import Lazy, Server
from ema.parameter import Parameter
from ema.device    import Device

log = logging.getLogger('watchdog')

PERIOD = {
    'name': 'Watchdog Period',
    'logger' : 'watchdog' ,
    'mult' : 1.0,              # multiplier to internal value
    'unit' : 's',              # seconds
    'get' : '(t)',              # string format for GET request
    'set' : '(T%03d)',          # string format for SET request
    'pat' : '\(T(\d{3})\)',    # pattern to recognize as response
    'grp' : 1,                 # match group to extract value and compare
}

class WatchDog(Lazy, Device):

    def __init__(self, ema, parser):
        lvl = parser.get("WATCHDOG", "wdog_log")
        log.setLevel(lvl)
        period = parser.getint("WATCHDOG", "keepalive")
        Lazy.__init__(self)
        self.ema = ema
        self.period = Parameter(ema, period, None, **PERIOD)
        self.setPeriod(int(self.period.value / (2*Server.TIMEOUT)))
        ema.addLazy(self)
        ema.addSync(self.period)
        ema.addParameter(self)


    def work(self):
        '''Implemantation of the Lazy interface'''
        self.ema.serdriver.write('( )')


    @property
    def parameter(self):
        '''Return dictionary with calibration constants'''
        return {
            self.period.name: (self.period.value / self.period.mult, self.period.unit)
        }
        
