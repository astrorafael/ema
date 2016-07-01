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

import os
import os.path
import shlex

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger
from twisted.internet             import reactor

#--------------
# local imports
# -------------

from .error    import AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from .protocol import ScriptProtocol

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------

def is_exe(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='script')



class Script(object):
    '''
    Notifier creates Script wrapper objects, representing scripts to be launched.
    Instances of these running scripts are controlled by the ScriptProtcol class
    '''

    # modes as constants
    NEVER = 0
    ONCE  = 1
    MANY  = 2

    # mappping from strings to numbers
    MODES = { 'Never' : NEVER, 'Once' : ONCE, 'Many' : MANY }

    def __init__(self,  path, mode, fmt):
        self.mode        = self.MODES[mode]
        self.path        = path
        self.fmt         = fmt
        self.name        = os.path.basename(self.path)
        self.terminated  = True
        self.protocol    = None

    def runOnce(self, *args):
        '''
        Run only once in the whole server lifetime.
        Raises AlreadyExecutedScript exception if already run
        Otherwise, spawns the script
        '''
        args = shlex.split(self.path + ' ' + self.fmt % args)
        if self.protocol is not None:
            raise AlreadyExecutedScript(self.name, args)
        # If not running, spawn it
        self.protocol = ScriptProtocol(self)
        reactor.spawnProcess(self.protocol, self.path, args, {})
        self.terminated = False
       


    def runMany(self, *args):
        '''
        Run one more time, if previous run completed
        If scrip is already running raise AlreadyBeingExecutedScript.
        Otherwise, spawns the script
        '''
        args = shlex.split(self.path + ' ' + self.fmt % args)
        if not self.terminated:
            raise AlreadyBeingExecutedScript(self.name, *args)
        self.protocol = ScriptProtocol(self)
        reactor.spawnProcess(self.protocol, self.path, args, {})
        self.terminated = False
       

   
    def run(self, *args):
        '''
        Launch a script, depending on the launch mode.
        Skip if no script is configured
        '''
        if not self.path:
            return
        if self.mode == Script.ONCE:
            self.runOnce(*args)
        elif self.mode == Script.MANY:
            self.runMany(*args)

      
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------

__all__ = ["Script"]