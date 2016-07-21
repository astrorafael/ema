# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import datetime
import re

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks, returnValue

#--------------
# local imports
# -------------

from .service.relopausable import Service
from .logger   import setLogLevel


# ----------------
# Module constants
# ----------------

HH     = r'\s*(\d{1,2})'
HHMM   = r'\s*(\d{1,2}):(\d{1,2})'
HHMMSS = r'\s*(\d{1,2}):(\d{1,2}):(\d{1,2})'

# ----------------
# Global functions
# -----------------

def toRefDate(ts):
    '''
    Set the datetome.datetime object ts to the given reference date
    '''
    return ts.replace(year=2000, month=1, day=1, microsecond=0)


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
  and returns a datetime.datetime object
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


# -----------------------
# Module global variables
# -----------------------

log  = Logger(namespace='sched')
log2 = Logger(namespace='interv')

pat1 = re.compile(HH)
pat2 = re.compile(HHMM)
pat3 = re.compile(HHMMSS)

# ----------
# Exceptions
# ----------

class ReversedInterval(Exception):
    '''Interval is reversed'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

class OverlappedIntervals(Exception):
    '''Signals overlapped intervals'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: {1} with {2}".format(s, self.args[0], self.args[1])
        s = '{0}.'.format(s)
        return s

class TooShortInterval(Exception):
    '''Interval is too short'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: {1} => {2} min".format(s, self.args[0], self.args[1])
        s = '{0}.'.format(s)
        return s
 
class BadSlice(ValueError):
    '''Interval Slice is not [10%, 30%, 50%, 70%, 90%]'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s  

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

    MIN = datetime.datetime(2000,1,1,0,0,0)
    MAX = datetime.datetime(2000,1,2,0,0,0)

    @staticmethod
    def create(lowTime, highTime):
      '''
      Builds an interval given two strings, datetime objects or anything in between
      Datetimes are first normalized to 2000 jan, 1
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
        result = self.T[0] <= dt < self.T[1]
        #log2.debug("{t0} <= {dt} < {t1} => {result}", t0=self.T[0], dt=dt, t1=self.T[1], result=result)
        return result

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

   def asList(self):
      return self.windows

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
      N = len(self.windows)  
      tNow = toRefDate(tNow)
      if self.windows[-1].isReversed():
         N -= 1
         log2.debug("last interval is reversed")
         interval1 = Interval(self.windows[-1].t0, Interval.MAX)
         interval2 = Interval( Interval.MIN, self.windows[-1].t0)
         log2.debug("checking {tNow} against interval {interval}", tNow=tNow.time(), interval=interval1)
         if interval1.contains(tNow):
            return True, N
         log2.debug("checking {tNow} against interval {interval}", tNow=tNow.time(), interval=interval2)
         if interval2.contains(tNow):
            return True, N
         
      for i in range(0,N):
         log2.debug("checking {tNow} against interval {interval}", tNow=tNow.time(), interval=self.windows[i])
         if self.windows[i].contains(tNow):
            log2.debug("found interval index {i} = {window}", i=i, window=self.windows[i])
            return True, i
      return False, None
      
# =======================
# Scheduler Service Class
# =======================

class SchedulerService(Service):

    # Service name
    NAME = 'Scheduler Service'

    # Interval constants
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    
    T = 9

    def __init__(self, options):
        Service.__init__(self)
        self.options = options
        self.activities = dict()
        self.periodicTask = None
        setLogLevel(namespace='sched',  levelStr=self.options['log_level'])
        setLogLevel(namespace='interv', levelStr='info')

    
    def startService(self):
        log.info("starting {name}", name=self.name)
        Service.startService(self)
        self.windows  = IntervalList.parse(self.options['intervals'], 15)
        self.gaps     = ~ self.windows
        self.periodicTask = task.LoopingCall(self._schedule)
        self.periodicTask.start(self.T, now=False) # call every T seconds
        log.debug("Active   intervals = {windows!s}", windows=self.windows)
        log.debug("Inactive intervals = {gaps!s}", gaps=self.gaps)
      

    def stopService(self):
        self.periodicTask.stop()
        Service.stopService(self)


    def addActivity(self, func, sliceperc, active, inactive):
        '''
        Add and activity (a callable) to be called active window.
        '''
        if sliceperc not in [10, 30, 50, 70, 90]:
            raise BadSlice(sliceperc)
        event = 'active{0}'.format(sliceperc) 
        tPerc = (active.t0 + datetime.timedelta(seconds=int(active.duration()*sliceperc/100)))
        log.debug("Adding activity to interval = {interval}, tPerc = {tPerc}", interval=active, tPerc=tPerc)
        values = self.activities.get(tPerc, list())
        self.activities[tPerc] = values
        # register non duplicate activities in order
        if (func, active, inactive, event) not in values:
            self.activities[tPerc].append((func, active, inactive, event))
       

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['scheduler']
        log.info("new log level is {lvl}", lvl=options['log_level'])
        setLogLevel(namespace='inet', levelStr=options['log_level'])
        if self.periodicTask:
            self.periodicTask.reset()   # ESTO HAY QUE VERLO, A LO MEJOR HAY QUE CREAR OTRA TAREA
        self.options = options

    # --------------
    # Helper methods
    # ---------------

    @inlineCallbacks
    def _schedule(self):
        '''
        Runs a schedule cycle.
        '''
        now = toRefDate(datetime.datetime.utcnow())
        tstamps = sorted(self.activities.keys(), reverse=False)
        if len(tstamps) == 0:
            log.debug("Registering all activities again")
            self.parent.addActivities()
            returnValue(None)

        for target in tstamps:
            delta = (target - now).total_seconds()
            log.debug("target = {target}, delta={delta}", target=target, delta=delta)
            if 0<= delta < self.T:
                yield task.deferLater(reactor, delta, lambda: None)
                info = self.activities[target]
                del self.activities[target]
                for item in info: 
                    item[0](item[1], item[2])
                self.parent.onEventExecute(item[3], now.time(),
                    str(item[1].t0.time()), str(item[1].t1.time()),
                    str(item[2].t0.time()), str(item[2].t1.time())
                    )
                break
            elif delta < 0 and self.findActiveInactive(now) == self.ACTIVE:
                log.debug("deleting OBSOLETE activity at {target}", target=target)
                info = self.activities[target]
                del self.activities[target]
               

    def findCurrentInterval(self):
        '''Find the current interval'''     
        tNow = datetime.datetime.utcnow()
        found, i = self.windows.find(tNow)
        if found:
            active   = self.windows[i]
            inactive = self.gaps[i]
            log.debug("now {now} we are in the active window {window}", now=tNow.strftime("%H:%M:%S"), window=active)
            log.debug("Next inactive gap will be {gap}",  gap=inactive)
        else:
            found, i = self.gaps.find(tNow)
            inactive = self.gaps[i]
            active   = self.windows[i+1 % len(self.windows)]
            log.debug("now {now} we are in the inactive window {gap}", now=tNow.strftime("%H:%M:%S"), gap=inactive)
            log.debug("Next active gap will be {window}", window=active)
        return active, inactive


    def findActiveInactive(self, tNow):
        '''A shorter version which only returns ACTIVE or INACTIVE state'''
        found, i = self.windows.find(tNow)
        if found:
            where = self.ACTIVE
        else:
            where = self.INACTIVE
        return where
           


__all__ = [
    "Interval"
    "ScheduleService",
    "ReversedInterval",
    "OverlappedIntervals",
    "TooShortInterval",
]