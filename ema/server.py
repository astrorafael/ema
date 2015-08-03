# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ----------------------------------------------------------------------

# ========================== DESIGN NOTES ==============================
# This is a tiny aynchronous framework based on the well known select() 
# system call. Not onl it implements input/output activity callbacks but
# also one-shot alarm callbacks and periodic callbacks 
# (aka 'work procedures')
#
# select() timeout vaule is 1 second by default,a value not to coarse
# nor too fine.
#
# For EMA, this only works for *NIX like O.S. Windows doesn't handle I/O on
# devices other than sockets when using select(), so we can't read
# RS232 ports from here.
#
# I could have made this framework more generic by registering callback 
# functions instead of object instances. Bound methods would work as 
# well, but I have not have the need to use isolated functions.
#
# The Lazy class is meant to be subclassed and contains all the logic
# to handle a cyclic counter. When this counter reaches 0 it triggers
# a callback.
#
# The Alarmable class is meant to be subclassed and contains all the 
# logic to handle a counter and triigering a callback when the counter 
# reaches 0. The Server object automatically unregisters the alarmable 
# object before the callback to ensure that it is never called again.
#
# Time in Lazy and Alarmable objects shoudl be expressed in terms of
# counter cycles, using the Server.TIMEOUT constant as the reference
# like so:   N = int(round(T/Server.TIMEOUT))
#
# We use ABCMeta metaclass and @abstractmethod decorator, to enforce
# enforcing some methods to be implemented in subclasses.
#
# In v2.0, we add a SIGALARM event handler to handle tiemout duration
# of several hours with seconds precision. There is onle one SIGALARM
# handler. ALarmable and Laazy classers are just fine for short timeouts.
#
# ======================================================================

import errno
import signal
import select
import logging
import datetime
from   abc import ABCMeta, abstractmethod

log = logging.getLogger('server')

def setLogLevel(level):
    log.setLevel(level)

def sighandler(signum, frame):
    '''
    Signal handler (SIGALARM only)
    '''
    Server.instance.sigflag = True


class Server(object):

    TIMEOUT = 1   # seconds timeout in select()

    instance = None

    def __init__(self):
        self.__readables  = []
        self.__writables  = []
        self.__alarmables = []
        self.__lazy       = []
        self.__sighandler = None
        self.sigflag      = True
        Server.instance   = self
        signal.signal(signal.SIGALRM, sighandler)

    def SetTimeout(self, newT):
        '''Set the select() timeout'''
        Server.TIMEOUT = newT

    def addReadable(self, obj):
        '''
        Adds a readable object implementing the following methods:
        fileno()
        onInput()
        '''
        # Returns AttributeError exception if not
        callable(getattr(obj,'fileno'))
        callable(getattr(obj,'onInput'))
        self.__readables.append(obj)


    def delReadable(self, obj):
        '''Removes readable object from the list, 
        thus avoiding onInput() callback'''
        self.__readables.pop(self.__readables.index(obj))


    def addWritable(self, obj):
        '''
        Adds a readable object implementing the following methods:
        fileno()
        onOutput()
        '''
        # Returns AttributeError exception if not
        callable(getattr(obj,'fileno'))
        callable(getattr(obj,'onOutput'))
        self.__readables.append(obj)


    def delWritable(self, obj):
        '''Removes writable object from the list, 
        thus avoiding onOutput() callback'''
        self.__writables.pop(self.__writables.index(obj))


    def addAlarmable(self, obj):
        '''
        Adds an object implementing the timeout()and onTimeoutDo() method
        onTimeoutDo() is invoked only once, then it is automatically removed.
        '''

        # Returns AttributeError exception if not
        callable(getattr(obj,'timeout'))
        callable(getattr(obj,'onTimeoutDo'))
        self.__alarmables.append(obj)


    def delAlarmable(self, obj):
        '''Removes alarmable object from the list, 
        thus avoiding onTimeoutDo() callback'''
        self.__alarmables.pop(self.__alarmables.index(obj))


    def addLazy(self, obj):
        '''
        Adds an object implementing the work() and mustWork() methods 
        ( i.e. instances of Lazy).
        '''
        # Returns AttributeError exception if not
        callable(getattr(obj,'work'))
        callable(getattr(obj,'mustWork'))
        self.__lazy.append(obj)

    def setSigAlarmHandler(self, obj, T):
        '''
        Set a new object as SIGALARM signal handler and arm 
        the SIGALARM signal with new tiemout T in integer seconds.
	'''
        callable(getattr(obj,'onSigAlarmDo'))
        self.__sighandler = obj
        signal.alarm(T)


    def step(self,timeout):
        '''
        Single step run, invoking I/O handlers or timeout handlers
        '''

	# Catch SIGALARM signal suring select()
	# and execute its handler first
        try:
            nreadables, nwritables, nexceptionals = select.select(
              self.__readables, self.__writables, [], timeout)
        except select.error as e:
            if e[0] == errno.EINTR and self.sigflag:
               self.__sighandler.onSigAlarmDo()
               self.sigflag = False
               return
            raise
        except Exception:
          raise

        io_activity = False
        if nreadables:
            io_activity = True
            for readable in nreadables:
                readable.onInput()
        
        if nwritables:
            io_activity = True
            for writable in nwritables:
                readable.onOutput()

        if not io_activity:                   
            # Execute alarms first
            for alarm in self.__alarmables:
                if alarm.timeout():
                    self.delAlarmable(alarm)
                    alarm.onTimeoutDo()

            # Executes recurring work procedures last
            for lazy in self.__lazy:
                if lazy.mustWork():
                    lazy.work()
    

    def run(self):
        '''
        Endless loop invoking step() until an Exception is caught.
        '''
        while True:
            try:
                self.step(Server.TIMEOUT)
            except KeyboardInterrupt:
                log.warning("Server.run() aborted by user request")
                break
            except Exception as e:
                log.exception(e)
                break
           

    def stop(self):
        '''
        Performs server clean up activity before exiting.
        To be subclassed if needed
        '''
        pass


# ==========================================================

class Lazy(object):
    '''
    Abstract class for all objects implementing a work() method
    to be used within the select() system call 
    when this system call times out.
    '''

    __metaclass__ = ABCMeta     # Only Python 2.7

    def __init__(self, N=1):
        self.__count = 0
        self.__limit = N


    def reset(self):
        self.__count = 0


    def setPeriod(self, N):
        self.__limit = N


    def mustWork(self):
        '''
        Increments counter modulo N.
        Returns True if counter wraps around.
        '''
        self.__count = (self.__count + 1) % self.__limit
        return  (self.__count == 0)

    @abstractmethod
    def work(self):
        '''
        Work procedure for lazy objects.
        To be subclassed and overriden
        '''
        pass

# ==========================================================

class Alarmable(object):
    '''
    Abstract class for all objects implementing a OnTimeoutDo() method
    to be used within the select() system call when this system call times out.
    '''

    __metaclass__ = ABCMeta     # Only Python 2.7

    def __init__(self, N=1):
	self.__delta   = datetime.timedelta(seconds=N)
	self.__tsFinal = datetime.datetime.utcnow() + self.__delta

    def resetAlarm(self):
	self.__tsFinal    = datetime.datetime.utcnow() + self.__delta

    def setTimeout(self, N):
	self.__delta = datetime.timedelta(seconds=N)


    def timeout(self):
        '''
        Returns True if timeout elapsed.
        '''
        return datetime.datetime.utcnow() >= self.__tsFinal   


    @abstractmethod
    def onTimeoutDo(self):
        '''
        To be subclassed and overriden
        '''
        pass


if __name__ == "__main__":
    utils.setDebug()
    server = Server()
    server.run()
    server.stop()
