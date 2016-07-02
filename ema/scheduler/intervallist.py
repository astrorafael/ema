# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division
import datetime

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel

#--------------
# local imports
# -------------

from ..utils   import chop
from .error    import ReversedInterval, OverlappedIntervals, TooShortInterval
from .interval import Interval, toDateTime

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='sched')


# ===================
# Interval List Class
# ===================

class IntervalList(object):

   def __init__(self, alist):
      self.windows = alist

   @staticmethod
   def parse(winstr, minutes):
      '''Build a window list from a windows list spec string 
      taiking the following format HH:MM-HH:MM,HH:MM-HH:MM,etc
      Window interval (Start % end time) separated by dashes
      Window ist separated by commands'''  
      il = IntervalList([ Interval(map(toDateTime, t.split('-'))) for t in winstr.split(',')  ]).sorted()
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
      if self.windows[-1].isReversed():
         aList.append(Interval([self.windows[-1].t1, self.windows[0].t0]))
         for i in range(0,len(self.windows)-1):
            aList.append(Interval([self.windows[i].t1, self.windows[i+1].t0]))
      else:
         for i in range(0,len(self.windows)-1):
            aList.append(Interval([self.windows[i].t1, self.windows[i+1].t0 ]))
         aList.append(Interval([self.windows[-1].t1, self.windows[0].t0 ]))
      return IntervalList(aList)

   # Own methods
   def sorted(self):
      '''Sorts the intervals by start time.
      Returns a new IntervalList object'''
      return IntervalList(sorted(self.windows, key=lambda interval: interval.t0))
      
   def validate(self, min):
      '''Check for non overlapping, non reversed, 
      minimun width interval (in seconds) 
      in a sorted interval list'''
      for w in self.windows:
         if w.duration() < min:
            raise TooShortInterval(w,min)

      for i in range(0,len(self.windows)-1):
         w1 = self.windows[i]
         if w1.isReversed():
            raise ReversedInterval(w1)
         w2 = self.windows[i+1]
         if w2.t0 < w1.t1:
            raise OverlappedIntervalList(w1, w2)
   
   def find(self, tNow):
      '''Find out which interval contains tNow.
      Return True, index if found or False, None if not found'''
      if not self.windows[-1].isReversed():
         log.debug("last interval is not reversed")
         for i in range(0,len(self.windows)):
            if self.windows[i].contains(tNow):
               log.debug("found interval %d = %s", i, self.windows[i])
               return True, i
         log.debug("No interval found")
         return False, None
      else:
         log.debug("last interval is reversed")
         for i in range(0, len(self.windows)-1):
            if self.windows[i].contains(tNow):
               log.debug("found interval %d = %s", i, self.windows[i])
               return True, i
         log.debug("Checking border intervals")
         i1 = Interval([self.windows[-1].t0, datetime.time.max])
         i2 = Interval([datetime.time.min, self.windows[0].t0])
         if i1.contains(tNow) or i2.contains(tNow):
            log.debug("found interval in borders i1=%s, i2=%s", i1, i2)
            return True, len(self.windows)-1
         log.debug("No interval found")
         return False, None


##########################################################################



if __name__ == "__main__":

    aux_window = "23:00-23:05,23:10-23:15,23:20-23:25,23:30-23:35,23:40-23:45,23:50-23:55,11:00-11:05,11:10-11:15,11:20-11:25,11:30-11:35,11:40-11:45,11:50-11:55,12:00-12:05,12:10-12:15,12:20-12:25,12:30-12:35,12:40-12:45,12:50-12:55,13:00-13:05,13:10-13:15,13:20-13:25,13:30-13:35,13:40-13:45,13:50-13:55,14:00-14:05,14:10-14:15,14:20-14:25,14:30-14:35,14:40-14:45,14:50-14:55,15:00-15:05,15:10-15:15,15:20-15:25,15:30-15:35,15:40-15:45,15:50-15:55,16:00-16:05,16:10-16:15,16:20-16:25,16:30-16:35,16:40-16:45,16:50-16:55,17:00-17:05,17:10-17:15,17:20-17:25,17:30-17:35,17:40-17:45,17:50-17:55,18:00-18:05,18:10-18:15,18:20-18:25,18:30-18:35,18:40-18:45,18:50-18:55,19:00-19:05,19:10-19:15,19:20-19:25,19:30-19:35,19:40-19:45,19:50-19:55,20:00-20:05,20:10-20:15,20:20-20:25,20:30-20:35,20:40-20:45,20:50-20:55,21:00-21:05,21:10-21:15,21:20-21:25,21:30-21:35,21:40-21:45,21:50-21:55,22:00-22:05,22:10-22:15,22:20-22:25,22:30-22:35,22:40-22:45,22:50-22:55"

    w = IntervalList.parse(aux_window)
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
