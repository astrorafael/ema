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
# ======================================================================


import logging
import datetime
import os.path

from emaproto import SMFB, SMFE, STRFTIME, STATLEN, transform

log = logging.getLogger('mqtt')

# =============================================================================
# Base class
# =============================================================================

class HistoricBase(object):

   # ----------
   # Public API
   # ----------

   def __init__(self, path):
      self.oneDay  = datetime.timedelta(days=1)
      self.path    = path

   def begin(self):
      '''Invoke just before isssuing the (@t0000) command to EMA'''
      self.data      = []
      self.today     = datetime.datetime.utcnow()
      self.yesterday = self.today - self.oneDay
      self.todayPage = self.toPage(self.today.time())
      self.lastDay   = None

      if os.path.isfile(self.path):
         with open(self.path,'r') as f:
            self.lastDay  = datetime.datetime.strptime(f.readline()[:-1],
                                                       STRFTIME)

      # If unknown of a long time ago, set the last page to the oldest
      # possible page so that we do a full dump
      if not self.lastDay or (self.today - self.lastDay) >= self.oneDay:
         self.lastPage = self.todayPage
      else:
         self.lastPage = self.toPage(self.lastDay.time())

   def append(self, message):
      '''Accumulate and timestamp a sample'''
      pass

   def getResult(self):
      '''Get the result array, taking into account an overlap factor'''
      pass


   # --------------
   # Helper Methods
   # --------------

   def toPage(self, time):
      '''Computes the flash page corresponding to a given time'''
      pass

   def toTime(self, page):
      '''Computes the end time coresponding to a given page'''
      pass
   
   def updateCache(self):
      with open(self.path,'w') as f:
         f.write(self.today.strftime(STRFTIME) + '\n')


# =============================================================================
# Daily 5m average class
# =============================================================================

class Averages5Min(HistoricBase):

   PATH = '/var/cache/ema/his5min.txt'
   NPAGES = 288

   # ----------
   # Public API
   # ----------

   def __init__(self, overlap=0):
      HistoricBase.__init(self, self.PATH)
      self.overlap = int(round(NPAGES * overlap*0.01)) # in pages
      log.debug("Average5Min: Overlapping by %s pages", self.overlap)

   def append(self, message):
      '''Accumulate and timestamp oner of the 288 samples'''
      page = int(message[SMFB:SMFE])

      if  self.todayPage < page:
         log.verbose("Timestamping with today's day")
         ts = datetime.datetime.combine(self.today.date(), self.toTime(page))
      else:
         log.verbose("Timestamping with yesterday's day")
         ts = datetime.datetime.combine(self.yesterday.date(), 
                                        self.toTime(page))
      ts = ts.strftime(STRFTIME)
      self.data.append('\n'.join( (transform(message), ts) ))      

   def getResult(self):
      '''Get the result array, taking into account an overlap factor'''
      self.updateCache()
      lastPage = (self.lastPage - self.overlap ) % self.NPAGES
      if self.todayPage > lastPage:
         log.debug("Adding results of today only")
         return self.data[lastPage:self.todayPage]
      else:
         log.debug("Adding yesterday's and today's results")
         subset1 = self.data[0:self.todayPage]
         subset2 = self.data[self.lastPage:]
         return subset1 + subset2

   # --------------
   # Helper Methods
   # --------------

   def toPage(self, time):
      '''Computes the flash page corresponding to a given time'''
      return (time.hour*60 + time.minute)//5

   def toTime(self, page):
      '''Compues the end time coresponding to a given page'''
      minutes = page*5 + 5
      hour = (minutes//60) % 24
      return datetime.time(hour=hour, minute=minutes%60)
   

# =============================================================================
# MinMax hourly dump class
# =============================================================================

class MinMax1h(HistoricBase):

   PATH   = '/var/cache/ema/his1h.txt'
   NPAGES = 24
   START  = 300


   # ----------
   # Public API
   # ----------

   def __init__(self, overlap=0):
      HistoricBase.__init(self, self.PATH, overlap)
      self.overlap = int(round(NPAGES * overlap*0.01)) # in pages
      log.debug("MinMax1h: Overlapping by %s pages", self.overlap)

   def append(self, message):
      '''Accumulate one of the of the 24x3 samples'''
      if len(message) == STATLEN:
         self.data.append(transform(message))
      else:                     # this is the timestamp comming
         self.data.append(message)

   def getResult(self):
      '''Get the result array, taking into account an overlap factor'''
      self.updateCache()
      lastPage = (self.lastPage - self.overlap ) % self.NPAGES
      if self.todayPage > lastPage:
         log.debug("Adding results of today only")
         return self.data[3*lastPage:3*self.todayPage]
      else:
         log.debug("Adding yesterday's and today's results")
         subset1 = self.data[0:3*self.todayPage]
         subset2 = self.data[3*self.lastPage:]
         return subset1 + subset2
      return self.data

   # --------------
   # Helper Methods
   # --------------

   def toPage(self, time):
      '''Computes the flash page corresponding to a given time'''
      return time.hour + self.START

   def toTime(self, page):
      '''Compues the end time coresponding to a given page'''
      hour = page - self.START
      return datetime.time(hour=hour)
   
