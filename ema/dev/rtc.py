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
import datetime

from ema.server    import Server, Lazy
from ema.parameter import AbstractParameter
from ema.emaproto  import PERIOD

log = logging.getLogger('rtc')


class RTCParameter(AbstractParameter):
    '''RTC sync parameter does not fit into the generic Parameter class
    as the time value to syncronize is volatile in nature'''

    RETRIES   = 1
    TIMEOUT   = 30
    # Common pattern forn GET/SET message responses
    PAT = '\(\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}\)' 

    def __init__(self, ema, deltaT=60):
        AbstractParameter.__init__(self, ema, RTCParameter.TIMEOUT, 
                                       RTCParameter.PAT, 
                                       RTCParameter.PAT, 
                                       RTCParameter.RETRIES)
        self.deltaT = datetime.timedelta(seconds=deltaT)
        self.name = "EMA RTC Time Syncronization"


    def sendDateTime(self):
        n    = self.ema.serdriver.queueDelay()
        tadj = int(round(n*Server.TIMEOUT))
        self.now = (datetime.datetime.utcnow() + datetime.timedelta(seconds=tadj)).replace(microsecond=0)
        msg = self.now.strftime('(Y%d%m%y%H%M%S)')
        self.ema.serdriver.write(msg)
        self.setTimeout(n+RTCParameter.TIMEOUT)      # adjust for queue length
        self.resetAlarm()        
        log.debug("Tadj = %d seconds", tadj)


    def actionStart(self):
        n = self.ema.serdriver.queueDelay()
        n += RTCParameter.TIMEOUT
        self.setTimeout(n)      # adjust for queue length
        self.resetAlarm()        
        self.ema.serdriver.write('(y)')


    def actionGet(self, message, matchobj):
        log.debug("matched GET message")
        self.now = datetime.datetime.utcnow().replace(microsecond=0)
        ema = datetime.datetime.strptime(message,'(%H:%M:%S %d/%m/%Y)')
        deltaT = abs(ema - self.now)
        if deltaT > self.deltaT:
            self.sendDateTime()
            log.warning("DeltaT (ema - now) = %s, max DeltaT = %s", deltaT, self.deltaT)
            needsSync = True
        else:
            log.info("No need to sync RTC. DeltaT = %s", deltaT)
            needsSync = False
        return needsSync


    def actionSet(self, message, matchobj):
        log.debug("matched SET message")
        ema = datetime.datetime.strptime(message,'(%H:%M:%S %d/%m/%Y)')
        if ema - self.now > self.deltaT or self.now - ema > self.deltaT :
            log.warning("EMA RTC is still not synchronized")
        else:
            log.info("EMA RTC succesfully sincronized")

    def actionEnd(self):
        log.debug("EMA RTC sync process complete")


    def retryGet(self):
        log.debug("Retry a GET message (%d/%d)" % self.getRetries() )
        self.actionStart()


    def retrySet(self):
        log.debug("Retry a SET message (%d/%d)" % self.getRetries() )
        self.sendDateTime()


    def actionTimeout(self):
        log.error("Timeout: EMA not responding to RTC sync request")



class RTC(Lazy):

    def __init__(self, ema, parser):
        lvl = parser.get("RTC", "rtc_log")
        log.setLevel(lvl)
        deltaT = parser.getint("RTC", "rtc_delta")
        period = parser.getfloat("RTC", "rtc_period")
        Lazy.__init__(self, 3600*period)
        self.ema = ema
        self.param = RTCParameter(ema, deltaT)
        ema.addSync(self.param)
        ema.addLazy(self)


    def work(self):
        '''
        Periodic synchornization routine.
        Should be once a day.
        '''
        self.ema.addSync(self.param)
        self.param.sync()
        

