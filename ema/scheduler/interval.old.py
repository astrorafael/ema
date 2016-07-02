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

#--------------
# local imports
# -------------

# ----------------
# Module constants
# ----------------


# -----------------------
# Module global variables
# -----------------------


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
        return time >= self.T[0] and time < self.T[1]

    def duration(self):
        '''Returns time interval in seconds'''
        today  = datetime.date.today().replace(microsecond=0)
        ts0 = datetime.datetime.combine(today, self.T[0])
        ts1 = datetime.datetime.combine(today, self.T[1])
        if ts1 < ts0:
            ts1 += datetime.timedelta(hours=24)
        return int((ts1 - ts0).total_seconds())

    def slice(self, perc):
        '''
        Slices an interval into two new intervals
        Returns two intervals
        '''
        today  = datetime.date.today().replace(microsecond=0)
        ts0 = datetime.datetime.combine(today, self.T[0])
        ts1 = datetime.datetime.combine(today, self.T[1])
        if ts1 < ts0:
            ts1 += datetime.timedelta(hours=24)
        totalLen = int((ts1 - ts0).total_seconds())
        l1 = int(round(totalLen * perc, 0))
        l2 = totalLen - l1
        tf1 = ts0 + datetime.timedelta(seconds=l1).time()
        return Interval(self.t0, tf1),  Interval(tf1, self.t1),


    def midpoint(self):
        '''Find the interval midpoint. 
        Returns a datetime.time object'''
        r, _ = self.slice(0.5)
        return r.t1


if __name__ == "__main__":
  i1 = Interval(datetime.time(0,0), datetime.time(24,0,0))
