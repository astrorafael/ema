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

log = logging.getLogger('historic')

class Averages5Min(object):

   PATH = '/var/cache/ema/his5min.txt'
   NPAGES = 288

   # ----------
   # Public API
   # ----------

   def __init__(self, overlap=0):
      self.oneDay  = datetime.timedelta(days=1)
      self.overlap = overlap

   def begin(self):
      '''Invoke just before isssuing the (@t0000) command to EMA'''
      self.data      = []
      self.today     = datetime.datetime.utcnow()
      self.yesterday = self.today - self.oneDay
      self.todayPage = self.toPage(self.today.time())
      self.lastDay   = None

      if of.path.isfile(self.PATH):
         with open(self.PATH,'r') as f:
            self.lastDay  = datetime.strptime(f.readline(),STRFTIME)

      if not self.lastDay or (self.now - self.lastDay) >= self.oneDay:
         self.lastPage = 0 
      else:
         self.lastPage = self.toPage(self.lastDay.time())

   def append(self, message):
      '''Accumulate and timestamp oner of the 288 samples'''
      page = int(message[SMFB:SMFE])

      if  self.todayPage < page:
         ts = datetime.datetime.combine(self.today.date(), self.toTime(page))
      else:
         ts = datetime.datetime.combine(self.yesterday.date(), 
                                        self.toTime(page))
      ts = st.strftime(STRFITME)
      self.data.append('\n'.join( (transform(message), ts) ))      

   def getResult(self):
      '''Get the result array, taking into account an overlap factor'''
      self.updateCache()
      lastPage = (self.lastPage - self.overlap ) % self.NPAGES
      if self.todayPage > lastPage:
         return self.data[lastPage:self.todayPage]
      else:
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
      return datetime.time(hour=minutes//60, minute=minutes%60)
   
   def updateCache(self):
      with open(self.PATH,'w') as f:
         f.write(self.today.strftime(STRFTIME) + '\n')

# =============================================================================
#
# =============================================================================

class MinMax1h(object):

   PATH   = '/var/cache/ema/his1h.txt'
   NPAGES = 24
   START  = 300

   # ----------
   # Public API
   # ----------

   def __init__(self, overlap=0):
      self.oneDay  = datetime.timedelta(days=1)
      self.overlap = overlap


   def begin(self):
      '''Invoke just before isssuing the (@H0300) command to EMA'''
      self.data      = []
      self.today     = datetime.datetime.utcnow()
      self.yesterday = self.today - self.oneDay
      self.todayPage = self.toPage(self.today.time())
      self.lastDay   = None

      if of.path.isfile(self.PATH):
         with open(self.PATH,'r') as f:
            self.lastDay  = datetime.strptime(f.readline(),STRFTIME)

      if not self.lastDay or (self.now - self.lastDay) >= self.oneDay:
         self.lastPage = 0 
      else:
         self.lastPage = self.toPage(self.lastDay.time())

   def append(self, message):
      '''Accumulate and timestamp oner of the 24x3 samples'''
      if len(message) == STATLEN:
         self.minmaxBulkDump.append(transform(message))
      else:
         self.minmaxBulkDump.append(message)

   def getResult(self):
      '''Get the result array, taking into account an overlap factor'''
      self.updateCache()
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
   
   def updateCache(self):
      with open(self.PATH,'w') as f:
         f.write(self.today.strftime(STRFTIME) + '\n')
