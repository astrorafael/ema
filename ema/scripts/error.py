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

class AlreadyExecutedScript(Exception):
    '''Script has already been executed'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

class AlreadyBeingExecutedScript(Exception):
    '''Script is stil being executed'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

class ScriptNotFound(IOError):
    '''Script not found or not executable'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s


__all__ = [
    AlreadyExecutedScript,
    AlreadyBeingExecutedScript,
    ScriptNotFound,
]