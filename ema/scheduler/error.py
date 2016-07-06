# -*- coding: iso-8859-15 -*-
# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

# ---------------
# Twisted imports
# ---------------


#--------------
# local imports
# -------------

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------

# -----------------------
# Module global variables
# -----------------------

from __future__ import division

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

__all__ = [
    "ReversedInterval",
    "OverlappedIntervals",
    "TooShortInterval",
]