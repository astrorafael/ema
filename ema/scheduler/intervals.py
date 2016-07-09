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
import re

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel

#--------------
# local imports
# -------------

# ----------------
# Module constants
# ----------------

HH     = r'\s*(\d{1,2})'
HHMM   = r'\s*(\d{1,2}):(\d{1,2})'
HHMMSS = r'\s*(\d{1,2}):(\d{1,2}):(\d{1,2})'

# -----------------------
# Module global variables
# -----------------------

log2 = Logger(namespace='interv')

pat1 = re.compile(HH)
pat2 = re.compile(HHMM)
pat3 = re.compile(HHMMSS)

def clipHour(hh,mm,ss):
  '''
  Test for proper hh, mm, ss
  '''
  carry = 0
  if hh > 24:
      raise OverflowError(hh,"Hours must be from [0..24] (yes, 24!)")
  elif hh == 24:
      carry = 1
      hh = 0; mm = 0; ss = 0
  return hh, mm, ss, carry


def toRefDate(ts):
    '''
    Sets the datetome.datetime object ts to the given reference date'''
    return ts.replace(year=2000, month=1, day=1, microsecond=0)


def toDateTime(strtime):
  '''
  Parses a string time for HH, HH:MM or HH:MM:SS format
  and returns a datetime object
  '''
  matchobj = pat3.search(strtime)
  if matchobj:
      hh = int(matchobj.group(1))
      mm = int(matchobj.group(2))
      ss = int(matchobj.group(3)) 
      hh, mm, ss, carry = clipHour(hh, mm, ss)
      return datetime.datetime(2000,1,1,hh,mm,ss) + datetime.timedelta(days=carry)
  matchobj = pat2.search(strtime)
  if matchobj:
      hh = int(matchobj.group(1))
      mm = int(matchobj.group(2))
      ss = 0
      hh, mm, ss, carry = clipHour(hh, mm, ss)
      return datetime.datetime(2000,1,1,hh,mm,ss) + datetime.timedelta(days=carry)
  matchobj = pat1.search(strtime)
  if not matchobj:
      raise ValueError(strtime, "No proper time format")
  hh = int(matchobj.group(1)); mm = 0; ss = 0
  hh, mm, ss, carry = clipHour(hh, mm, ss)
  return datetime.datetime(2000,1,1,hh,mm,ss) + datetime.timedelta(days=carry)


def toString(dt):
  '''Alternative format to datetime objects for Intervals'''
  if dt.day == 2:
    return "24:00" if dt.second == 0 else "24:00:00"
  else:
    return "%02d:%02d" % (dt.hour, dt.minute) if dt.second == 0 else  "%02d:%02d:%02d" % (dt.hour, dt.minute, dt.second) 

# ==============
# Interval Class
# ==============

class Interval(object):
    '''
    Interval is a slice of time bounded by two values
    The lower value belongs to the interval
    while the upper value strictly does not belong to the interval
    [00:00:00-24:00:00] is the time interval from 0H 0m 0s to 23:59:59
    '''

    @staticmethod
    def create(lowTime, highTime):
      '''
      Builds an interval given two strings, datetime objects or anything in between
      Datetimes are first normalized to 2001 jan, 1
      '''
      if type(lowTime) == str and type(highTime) == str:
        return Interval(toDateTime(lowTime), toDateTime(highTime))
      if type(lowTime) == str and type(highTime) == datetime.datetime:
        highTime = toRefDate(highTime)
        return Interval(toDateTime(lowTime), highTime) 
      if type(lowTime) == datetime.datetime and type(highTime) == str:
        lowTime = toRefDate(lowTime)
        return Interval(lowTime, toDateTime(highTime)) 
      if type(lowTime) == datetime.datetime and type(highTime) == datetime.datetime:
        highTime = toRefDate(highTime)
        lowTime = toRefDate(lowTime)
        return Interval(lowTime, highTime) 
        

    def __init__(self, lowTime, hightTime=None):
        '''
        Initialize an interval either with two datetime objects 
        or a list containing two datetime objects
        '''
        if type(lowTime) == list:
            self.T   = lowTime
        elif type(lowTime) == datetime.datetime:
            self.T   = [lowTime, hightTime]
        self.T[0] = self.T[0].replace(day = 1, microsecond=0) # Never allow 24:00 as T[0]

    # Object represntation protocol
    def  __str__(self):
        '''Pretty-prints interval'''
        return "[%s-%s)" % (toString(self.T[0]), toString(self.T[1]))

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

    def __invert__(self):
        '''Interval inversion'''
        return Interval(self.T[1], self.T[0])

    def isReversed(self):
        '''detect interval inverted'''
        return self.T[0] > self.T[1]

    def contains(self, dt):
        '''
        Find if interval contains timestamp.
        Returns True if so'
        '''
        return self.T[0] <= dt < self.T[1]

    def duration(self):
        '''Returns interval duration in seconds'''
        if self.T[1] < self.T[0]:
            delta = datetime.timedelta(hours=24)
        else:
            delta = datetime.timedelta(hours=0)
        return int((self.T[1] + delta - self.T[0]).total_seconds())




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
      '''Find out which interval contains tNow (a datitime stamp).
      Return True, index if found or False, None if not found'''
      tNow = toRefDate(tNow)
      log2.debug("finding if tNow={t} is in any interval", t=tNow)
      if not self.windows[-1].isReversed():
         log2.debug("last interval is not reversed")
         N = len(self.windows)
      else:
         log2.debug("last interval is reversed")
         N = len(self.windows) - 1

      for i in range(0,N):
         if self.windows[i].contains(tNow):
            log2.debug("found interval index {i} = {window}", i=i, window=self.windows[i])
            return True, i
      return False, None
      


##########################################################################



if __name__ == "__main__":

  print toDateTime("24")
  print toDateTime("3")
  print toDateTime("22")
  print toDateTime("24:00")
  print toDateTime("3:5")
  print toDateTime("22:23")
  print toDateTime("24:00:00")
  print toDateTime("23:45:56")
  print toDateTime("24:23:45")

  print Interval.create("23:45:56", "24:00:00")
  print Interval.create("23:45:56", "24:00:00").isReversed()
  print Interval.create("23:45:56", "00:00:00").isReversed()
  print ~Interval.create("23:45:56", "00:00:00")
  print ~Interval.create("23:45:56", "24:00:00")

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
 
 