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
from twisted.application.service  import Service

#--------------
# local imports
# -------------

from ..utils   import chop
from ..logger  import setLogLevel
from .error    import AlreadyExecutedScript, AlreadyBeingExecutedScript, ScriptNotFound, BadScriptMode
from .script   import Script
from ..service.relopausable import Service

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




class ScriptsService(Service):

 
    def __init__(self, options):
        Service.__init__(self)
        self.options = options
        self.scripts = {}
        setLogLevel(namespace='script', levelStr=self.options['log_level'])
    
    def startService(self):
        Service.startService(self)
        log.info("starting Scripts Service")
        try:
            self.addScript('low_voltage')
            self.addScript('aux_relay')
            self.addScript('roof_relay')
            self.addScript('no_internet')
        except Exception as e:
            log.error("{excp}", excp=e)


    def stopService(self):
        Service.stopService(self)
      

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self):
        setLogLevel(namespace='script', levelStr=self.new_options['log_level'])
        log.info("new log level is {lvl}", lvl=self.new_options['log_level'])
        self.options = self.new_options
        

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
        if not mode in ['Once', 'Many', 'Never']:
            raise BadScriptMode(mode)
        fmt     = self.options[event + '_args']
        scripts = chop(self.options[event], ',')
        aList = self.scripts.get(event, [] )
        for path in scripts:
            if is_exe(path):
                aList.append(Script(path, mode, fmt))
            else:
                raise ScriptNotFound(path)
        self.scripts[event] = aList



__all__ = ["ScriptsService"]