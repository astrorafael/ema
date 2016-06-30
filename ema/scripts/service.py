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

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks

#--------------
# local imports
# -------------

from ..utils   import chop
from ..logger  import setLogLevel
from .error    import AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound
from .script   import Script
from ..service import ReloadableService

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




class ScriptsService(ReloadableService):

 
    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='script', levelStr=options['log_level'])
        self.scripts   = {}
    
    def startService(self):
        log.info("starting Scripts Service")
        self.addScript('low_voltage')
        self.addScript('aux_relay')
        self.addScript('roof_relay')
        self.addScript('no_internet')
        ReloadableService.startService(self)


    @inlineCallbacks
    def stopService(self):
        try:
            yield ReloadableService.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='script', levelStr=new_options['log_level'])
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        self.options = new_options
        

    # -------------
    # EMA API
    # -------------

    def onEventExecute(self, event, *args):
        '''
        Event Handlr coming from the Voltmeter
        '''
        log.info("ON EVENT EXECUTE {event} {rest!r}", event=event, rest=args)
        for script in self.scripts[event]:
            try:
                script.run(*args)
            except (AlreadyExecutedScript, AlreadyBeingExecutedScript) as e:
                log.warn("On event {event} executed script => {excp} ", event=event, excp=e)
                continue

    
    # --------------
    # Helper methods
    # ---------------

    def addScript(self, event):
        '''
        *_script are tuples of (path, mode)
        '''
        mode    = self.options[event + '_mode']
        fmt     = self.options[event + '_args']
        scripts = chop(self.options[event], ',')
        aList = self.scripts.get(event, [] )
        for path in scripts:
            if is_exe(path):
                aList.append(Script(path, mode, fmt))
            else:
                raise ScriptNotFound(path)
        self.scripts[event] = aList



__all__ = [ScriptsService]