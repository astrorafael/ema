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
        highTime = highTime.replace(year=2001,month=1, day=1)
        return Interval(toDateTime(lowTime), highTime) 
      if type(lowTime) == datetime.datetime and type(highTime) == str:
        lowTime = lowTime.replace(year=2001,month=1, day=1)
        return Interval(lowTime, toDateTime(highTime)) 
      if type(lowTime) == datetime.datetime and type(highTime) == datetime.datetime:
        lowTime = lowTime.replace(year=2001,month=1, day=1)
        highTime = highTime.replace(year=2001,month=1, day=1)
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
        dt = dt.replace(year=2001,month=1, day=1)
        return dt >= self.T[0] and dt < self.T[1]

    def duration(self):
        '''Returns interval duration in seconds'''
        if self.T[1] < self.T[0]:
            delta = datetime.timedelta(hours=24)
        else:
            delta = datetime.timedelta(hours=0)
        return int((self.T[1] + delta - self.T[0]).total_seconds())

    def slice(self, percent=0.5):
        '''
        Slices an interval into two new intervals
        Returns two Intervals, left and right
        '''
        total = self.duration()
        l1 = int(round(total * percent, 0))
        tslice = self.T[0] + datetime.timedelta(seconds=l1)
        return Interval(self.T[0], tslice),  Interval(tslice, self.T[1]),


    def midpoint(self):
        '''Find the interval midpoint. 
        Returns a datetime.time object ready to be combined
        with the current datetime.date'''
        left, right = self.slice(0.5)
        return left.T[1].time()


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
 
 