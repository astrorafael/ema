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

from twisted.logger               import Logger
from twisted.internet.protocol    import ProcessProtocol

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
        self.parent  = parent

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
  





__all__ = [ScriptProtocol]