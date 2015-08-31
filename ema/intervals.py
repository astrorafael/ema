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

import datetime
import logging

log = logging.getLogger('todtimer')

# =================
# Utility functions
# =================

def toTime(hhmm):
   '''Converts HH:MM strings into datetime.time objects'''
        return datetime.time(hour=int(hhmm[0:2]), minute=int(hhmm[3:5]))


# ================================
# Exception classes for validation
# ================================

class ReversedInterval(Exception):
        '''Signals a script has executed'''
   def __init__(self, interval):
      self.interval = interval
   def __str__(self):
      '''Prints useful information'''
                return "Exception: Reversed Interval %s" % self.interval

class OverlappedIntervals(Exception):
        '''Signals overlapped intervals'''
   def __init__(self, w1, w2):
      self.w1 = w1
      self.w2 = w2
   def __str__(self):
      '''Prints useful information'''
                return "Exception: Interval %s overlaps with %s" % (self.w1, self.w2)

class TooShortInterval(Exception):
        '''Signals overlapped intervals'''
   def __init__(self, w1, min):
      self.w1  = w1
      self.min = min
   def __str__(self):
      '''Prints useful information'''
                return "Exception: Interval %s duration %d < %d (minimun allowed)" % (self.w1, self.w1.duration(), self.min)

# ==============
# Interval Class
# ==============

class Interval(object):

   def __init__(self, aList):
      '''aList has two items of type datetime.time objects'''
      self.T   = aList

   # Object represntation protocol
   def  __str__(self):
      '''Pretty-prints interval'''
      return "(%s-%s)" % (self.T[0].strftime("%H:%M:%S"), 
                self.T[1].strftime("%H:%M:%S"))

   # Inmutable sequences protocol
   def __len__(self):
      return len(self.T)

   def __getitem__(self, i):
      return self.T[i]

   def __iter__(self):
      return iter(self.T)
   
   # interval properties
   @property
   def t0(self):
      '''Return interval start time'''
      return self.T[0]

   @property
   def t1(self):
      '''Return interval end time'''
      return self.T[1]


   # Implements interval other operators

   def __invert__(self, other):
      '''Interval inversion'''
      return Interval(self.T[1], self.T[0])

   def reversed(self):
      '''detect interval inverted'''
      return self.T[0] > self.T[1]

   def inside(self, time):
      '''Returns whether a given datetime.time 
      is in a given interval'''
      return time >= self.T[0] and time <= self.T[1]

   def duration(self):
      '''Returns time interval in seconds'''
      today  = datetime.date.today()
      ts0 = datetime.datetime.combine(today, self.T[0])
      ts1 = datetime.datetime.combine(today, self.T[1])
      if ts1 < ts0:
         ts1 += datetime.timedelta(hours=24)
      return int((ts1 - ts0).total_seconds())

   def midpoint(self):
      '''Find the interval midpoint. 
      Returns a datetime.time object'''
      today = datetime.date.today()
      ts0 = datetime.datetime.combine(today, self.T[0])
      ts1 = datetime.datetime.combine(today, self.T[1])
      if ts1 < ts0:
         ts1 += datetime.timedelta(hours=24)
      return ((ts1 - ts0)/2 + ts0).time()

# ===================
# Interval List Class
# ===================

class Intervals(object):

   def __init__(self, alist):
      self.windows = alist

   @staticmethod
   def parse(winstr, minutes):
      '''Build a window list from a windows list spec string 
      taiking the following format HH:MM-HH:MM,HH:MM-HH:MM,etc
      Window interval (Start % end time) separated by dashes
      Window ist separated by commands'''  
      il = Intervals([ Interval(map(toTime, t.split('-'))) for t in winstr.split(',')  ]).sorted()
      il.validate(minutes*60)
      return il

   # Inmutable sequences protocol
   def __len__(self):
      return len(self.windows)

   def __getitem__(self, i):
      return self.windows[i]

   def __iter__(self):
      return iter(self.windows)

   # Object represntation protocol
   def  __str__(self):
      '''Prints useful information'''
                s = [ str(i) for i in self.windows ]
      return ' '.join(s)

   # Operators
   def  __invert__(self):
      '''Interval List inversion. Obtain the complementary interval list'''
      aList = []
      if self.windows[-1].reversed():
         aList.append(Interval([self.windows[-1].t1, self.windows[0].t0]))
         for i in range(0,len(self.windows)-1):
            aList.append(Interval([self.windows[i].t1, self.windows[i+1].t0]))
      else:
         for i in range(0,len(self.windows)-1):
            aList.append(Interval([self.windows[i].t1, self.windows[i+1].t0 ]))
         aList.append(Interval([self.windows[-1].t1, self.windows[0].t0 ]))
      return Intervals(aList)

   # Own methods
   def sorted(self):
      '''Sorts the intervals by start time.
      Returns a new Intervals object'''
      return Intervals(sorted(self.windows, key=lambda interval: interval.t0))
      
   def validate(self, min):
      '''Check for non overlapping, non reversed, 
      minimun width interval (in seconds) 
      in a sorted interval list'''
      for w in self.windows:
         if w.duration() < min:
            raise TooShortInterval(w,min)

      for i in range(0,len(self.windows)-1):
         w1 = self.windows[i]
         if w1.reversed():
            raise ReversedInterval(w1)
         w2 = self.windows[i+1]
         if w2.t0 < w1.t1:
            raise OverlappedIntervals(w1, w2)
   
   def find(self, tNow):
      '''Find out whether time tNow is in any of the intervals.
      Return True, index if found or False, None if not found'''
      if not self.windows[-1].reversed():
         log.debug("last interval is not reversed")
         for i in range(0,len(self.windows)):
            if self.windows[i].inside(tNow):
               log.debug("found interval %d = %s", i, self.windows[i])
               return True, i
         log.debug("No interval found")
         return False, None
      else:
         log.debug("last interval is reversed")
         for i in range(0, len(self.windows)-1):
            if self.windows[i].inside(tNow):
               log.debug("found interval %d = %s", i, self.windows[i])
               return True, i
         log.debug("Checking border intervals")
         i1 = Interval([self.windows[-1].t0, datetime.time.max])
         i2 = Interval([datetime.time.min, self.windows[0].t0])
         if i1.inside(tNow) or i2.inside(tNow):
            log.debug("found interval in borders i1=%s, i2=%s", i1, i2)
            return True, len(self.windows)-1
         log.debug("No interval found")
         return False, None


##########################################################################



if __name__ == "__main__":

    aux_window = "23:00-23:05,23:10-23:15,23:20-23:25,23:30-23:35,23:40-23:45,23:50-23:55,11:00-11:05,11:10-11:15,11:20-11:25,11:30-11:35,11:40-11:45,11:50-11:55,12:00-12:05,12:10-12:15,12:20-12:25,12:30-12:35,12:40-12:45,12:50-12:55,13:00-13:05,13:10-13:15,13:20-13:25,13:30-13:35,13:40-13:45,13:50-13:55,14:00-14:05,14:10-14:15,14:20-14:25,14:30-14:35,14:40-14:45,14:50-14:55,15:00-15:05,15:10-15:15,15:20-15:25,15:30-15:35,15:40-15:45,15:50-15:55,16:00-16:05,16:10-16:15,16:20-16:25,16:30-16:35,16:40-16:45,16:50-16:55,17:00-17:05,17:10-17:15,17:20-17:25,17:30-17:35,17:40-17:45,17:50-17:55,18:00-18:05,18:10-18:15,18:20-18:25,18:30-18:35,18:40-18:45,18:50-18:55,19:00-19:05,19:10-19:15,19:20-19:25,19:30-19:35,19:40-19:45,19:50-19:55,20:00-20:05,20:10-20:15,20:20-20:25,20:30-20:35,20:40-20:45,20:50-20:55,21:00-21:05,21:10-21:15,21:20-21:25,21:30-21:35,21:40-21:45,21:50-21:55,22:00-22:05,22:10-22:15,22:20-22:25,22:30-22:35,22:40-22:45,22:50-22:55"

    w = Intervals.parse(aux_window)
    print(w)
    print
    print "SORTING"
    print
    print(str(w.sorted()))
    print
    #print "INVERTING"
    #print
    #print( str( ~w.sorted() ) )
    flag, i = w.find(now())
    if flag:
       print flag
       print(str(w[i]))
    else:
       print flag
