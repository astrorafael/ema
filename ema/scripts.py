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
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.protocol    import ProcessProtocol
from twisted.internet.defer       import inlineCallbacks
from twisted.application.service  import Service


#--------------
# local imports
# -------------

from .logger   import setLogLevel
from .utils    import chop

# ----------------
# Module constants
# ----------------

# ----------------
# Global functions
# -----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='script')



class ScriptProtocol(ProcessProtocol):
    '''
    The base-class definitions of most of these functions are no-ops. 
    This will result in all stdout and stderr being thrown away.
    Note that it is important for data you don’t care about to be thrown away: 
    if the pipe were not read, the child process would eventually block 
    as it tried to write to a full pipe.

    The following are the basic ways to control the child process:
    
    * self.transport.write(data) : Stuff some data in the stdin pipe. Note that this write 
    method will queue any data that can’t be written immediately. 
    Writing will resume in the future when the pipe becomes writable again.
    
    * self.transport.closeStdin() : Close the stdin pipe. Programs which act as filters 
    (reading from stdin, modifying the data, writing to stdout) usually take this as 
    a sign that they should finish their job and terminate.
    For these programs, it is important to close stdin when you’re done with it, 
    otherwise the child process will never quit.

    * self.transport.closeStdout() : Not usually called, since you’re putting the process 
    into a state where any attempt to write to stdout will cause a SIGPIPE error. 
    This isn’t a nice thing to do to the poor process.

    * self.transport.closeStderr() : Not usually called, same reason as closeStdout().

    * self.transport.loseConnection() : Close all three pipes.

    * self.transport.signalProcess(’KILL’) : Kill the child process. 
    This will eventually result in processEnded() being called.

    '''

    def __init__(self, parent):
        #ProcessProtocol.__init__(self)
        self.parent = parent


    def connectionMade(self):
        '''
        This is called when the program is started, 
        and makes a good place to write data into
        the stdin pipe (using self.transport.write )
        '''
        log.debug("connectionMade!")
        
    def outReceived(self, data):
        '''
        This is called with data that was received from the process’ stdout pipe. 
        Pipes tend to provide data in larger chunks than sockets (one kilobyte is
        a common buffer size), so you may not experience the “random dribs and drabs” 
        behavior typical of network sockets, but regardless you should be prepared to deal
        if you don’t get all your data in a single call. 
        To do it properly, outReceived ought to simply accumulate the
        data and put off doing anything with it until the process has finished.
        '''
        log.info("script sent => {data}", data=data)
       

    def errReceived(self, data):
        '''
        This is called with data from the process’ stderr pipe. 
        It behaves just like outReceived().
        '''
        log.info("error from script => {data}", data=data)

    def inConnectionLost(self):
        '''
        This is called when the reactor notices that the process’ stdin pipe has closed. 
        Programs don’t typically close their own stdin, so this will probably get called 
        when your ProcessProtocol has shutdown the write side with 
        self.transport.loseConnection()
        '''
        log.debug("inConnectionLost! stdin is closed! (we probably did it)")

    def outConnectionLost(self):
        '''
        This is called when the program closes its stdout pipe. 
        This usually happens when the program terminates.
        '''
        pass

    def errConnectionLost(self):
        '''
        Same as outConnectionLost() , but for stderr instead of stdout.
        '''
        pass

    def processExited(self, reason):
        '''
        This is called when the child process has been reaped, and receives information 
        about the process’ exit status. The status is passed in the form of a Failure 
        instance, created with a .value that either holds a ProcessDone object if the 
        process terminated normally (it died of natural causes instead of receiving a signal,
        and if the exit code was 0), or a ProcessTerminated object (with an .exitCode attribute) 
        if something went wrong.
        '''
        pass

    def processEnded(self, reason):
        '''
        This is called when all the file descriptors associated with the child process
        have been closed and the process has been reaped. This means it is the last callback 
        which will be made onto a ProcessProtocol. The status parameter has the same meaning 
        as it does for processExited .
        '''
        if reason.value.exitCode != 0:
            log.info("Chid script with error: {message}", message=reason.getErrorMessage())
        else:
            log.info("Chid script finished successfully")
        self.parent.terminated = True
  



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

    def __init__(self,  cfg):
        self.mode        = self.MODES[cfg[1]]
        self.path        = cfg[0]
        self.name        = os.path.basename(self.path)
        self.terminated  = True
        self.protocol    = None

    def runOnce(self, *args):
        '''
        Run only once in the whole server lifetime.
        Raises AlreadyExecutedScript exception if already run
        Otherwise, spawns the script
        '''
        # 
        # otherwise, spawn it
        if self.protocol is not None:
            raise AlreadyExecutedScript(self.name, *args)
        # If not running, spawn it
        self.protocol = ScriptProtocol(self)
        self.terminated = False
        reactor.spawnProcess(self.protocol, self.path, [self.path] + list(args), {})
       


    def runMany(self, *args):
        '''
        Run one more time, if previous run completed
        If scrip is already running raise AlreadyBeingExecutedScript.
        Otherwise, spawns the script
        '''
        if not self.terminated:
            raise AlreadyBeingExecutedScript(self.name, *args)
        self.protocol = ScriptProtocol(self)
        self.terminated = False
        reactor.spawnProcess(self.protocol, self.path, [self.path] + list(args), {})
       

   
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


class ScriptsService(Service):

 
    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='script', levelStr=options['log_level'])
        self.scripts   = {}
        self.addScript('low_voltage')
        self.addScript('aux_relay')
        self.addScript('roof_relay')
        self.addScript('no_internet')

    
    def startService(self):
        log.info("starting Scripts Service")
        Service.startService(self)


    @inlineCallbacks
    def stopService(self):
        try:
            yield Service.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='script', levelStr=new_options['log_level'])
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        self.options = new_options
        

    def pauseService(self):
        pass

    def resumeService(self):
        pass

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
        modekey = event + '_mode'
        mode    = self.options[modekey]
        scripts = chop(self.options[event], ',')
        aList = self.scripts.get(event, [] )
        for path in scripts:
            aList.append(Script( (path, mode) ))
        self.scripts[event] = aList



__all__ = [ScriptsService]