# ----------------------------------------------------------------------
# Copyright (c) 2015 Rafael Gonzalez.
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

# ========================== DESIGN NOTES ==============================
#
# This object is the global server implementing the EMA daemon service
# It contains an amount of embedded to delegate responsibilities
# It acts as a mediator between these embedded objects too.
#
# Its main responsibilitioers are
#
# 1) Gobal initialization, mainly from a config file
# 2) Maintaining list of subscribed objects to certain events
# 3) Dispatchnig message events from Serial Port and UDP ports
#  to the proper embedded objects
#
# ======================================================================

import logging
import re
import os
import sys
import datetime
import errno

import requests

from utils import chop
from dev.todtimer import Timer
from dev.rtc      import RTC


log = logging.getLogger('httpprobe')


def voting3(v):
   '''
   Voting Function of 3 boolean variables in sequence/tuple v. 
   Any 2 True inputs makes it return True, otherwise returns False
   '''
   return (v[0] and v[1]) or (v[0] and v[2]) or (v[1] and v[2])


class HTTPProbe(object):
        

   def __init__(self, ema, parser):
      self.ema = ema
      ema.todtimer.addSubscriber(self)
      self.probes = chop(parser.get("GENERIC", "probe_sites"), ',')

   # -----------------------------------------------
   # Implement the TOD Timer onNewInterval interface
   # -----------------------------------------------

   def onNewInterval(self, where, i):
      # skips inactive intervals
      if where == Timer.INACTIVE:
         return
      votes = []
      for site in self.probes:
         try:
            r = requests.head(site)
            r.raise_for_status()
         except Exception as e:
            votes.append(False)
         else:
            votes.append(True)

      success = voting3(votes)
      if success:
         self.ema.rtc.sync()


