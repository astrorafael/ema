# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import re
import datetime

from collections import deque

# ---------------
# Twisted imports
# ---------------

from zope.interface               import implementer

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task, defer
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.serialport  import SerialPort
from twisted.internet.protocol    import ClientFactory
from twisted.protocols.basic      import LineOnlyReceiver
from twisted.application.service  import Service
from twisted.application.internet import ClientService
from twisted.internet.endpoints   import clientFromString

#--------------
# local imports
# -------------

from .service.interfaces import IReloadable, IPausable
from .logger   import setLogLevel
from .utils    import chop

import ema.command as command

# ----------------
# Module constants
# ----------------

# Unsolicited Responses Patterns
UNSOLICITED_RESPONSES = (
    {
        'name'    : 'Current status message',
        'pattern' : '^\(.{76}a\d{4}\)',       
    },
    {
        'name'    : 'Photometer begin',
        'pattern' : '^\(\d{2}:\d{2}:\d{2} wait\)',            
    },
    {
        'name'    : 'Photometer end',
        'pattern' : '^\(\d{2}:\d{2}:\d{2} mv:(\d{2}\.\d{2})\)',            
    },
    {
        'name'    : 'Thermopile I2C',
        'pattern' : '^\(>10[01] ([+-]\d+\.\d+)\)',            
    },
    {
        'name'    : 'Timer',
        'pattern' : '^\(\d{2}:\d{2}:\d{2} Timer (ON|OFF)\)',
    },
    {
        'name'    : 'Datalogger',
        'pattern' : '^\(\d{2}:\d{2}:\d{2}_\d{4}_\d{2}_\d{4}_\d{4}\)',
    }
)

UNSOLICITED_PATTERNS = [ re.compile(ur['pattern']) for ur in UNSOLICITED_RESPONSES ]

# ----------------
# Module functions
# ----------------


def match_unsolicited(line):
    '''Returns matched command descriptor or None'''
    for regexp in UNSOLICITED_PATTERNS:
        matchobj = regexp.search(line)
        if matchobj:
            log.debug("matched {pattern}", pattern=UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)]['name'])
            return UNSOLICITED_RESPONSES[UNSOLICITED_PATTERNS.index(regexp)], matchobj
    return None, None

# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')
log2 = Logger(namespace='protoc')



# ----------
# Exceptions
# ----------


class EMAError(Exception):
    '''Base class for all exceptions below'''
    pass


class EMATimeoutError(EMAError):
    '''EMA no responding to command'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s


# -------
# Classes
# -------


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class Interval(object):
    '''
    This class build automatically incrementing interval objects, 
    to be used in requests timeouts.
    
    Use like:
    C{interval = Interval()}
    C{Interval.maxDelay = 16}
    C{t = interval()}
    C{t = interval()}

    @var initial:  Initial interval value, in seconds.
    @var maxDelay: maximun interval value produced, in seconds.
    @var factor:   multiplier for the next interval.
    '''
  
    def __init__(self, initial=1, maxDelay=256, factor=2):
        '''Initialize interval object'''
        self.initial = initial
        self.factor = factor
        self.maxDelay = max(initial, maxDelay)
        self._value   = self.initial


    def __call__(self):
        '''Call the interval with an id and produce a new value for that id'''
        v = self._value
        self._value *= self.factor
        self._value = min(self._value, self.maxDelay)
        return v

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class EMAProtocolFactory(ClientFactory):

    def startedConnecting(self, connector):
        log.debug('Factory: Started to connect.')

    def buildProtocol(self, addr):
        log.debug('Factory: Connected.')
        return EMAProtocol()

    def clientConnectionLost(self, connector, reason):
        log.debug('Factory: Lost connection. Reason: {reason}', reason=reason)

    def clientConnectionFailed(self, connector, reason):
        log.febug('Factory: Connection failed. Reason: {reason}', reason=reason)

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class EMAProtocol(LineOnlyReceiver):


    # So that we can patch it in tests with Clock.callLater ...
    callLater = reactor.callLater

    # -------------------------
    # Twisted Line Receiver API
    # -------------------------

    def __init__(self):
        '''Sets the delimiter to the closihg parenthesis'''
        LineOnlyReceiver.delimiter = b')'
        self._onStatus     = set()                # callback sets
        self._onPhotometer = set()
        self._queue        = deque()              # Command queue
        self.busy   = False
        self.paused = False
        # stat counters
        self.nreceived = 0
        self.nresponse = 0
        self.nunsolici = 0
        self.nunknown  = 0
      
    def connectionMade(self):
        log.debug("connectionMade()")


    def lineReceived(self, line):
        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.5)
        line = (line.lstrip(' \t\n\r') + b')').decode('latin-1')
        log2.info("<== EMA [{l:02d}] {line}", l=len(line), line=line)
        self.nreceived += 1
        handled = self._handleCommandResponse(line, now)
        if handled:
            self.nresponse += 1
            return
        handled = self._handleUnsolicitedResponse(line, now)
        if handled:
            self.nunsolici += 1
            return
        self.nunknown += 1
        log.warn("Unknown/Unexpected message {line}", line=line)



    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, including the delimiter.
        @type line: C{bytes}
        """
        log2.info("==> EMA [{l:02d}] {line}", l=len(line), line=line)
        return self.transport.write(line)
        
    # ================
    # EMA Protocol API
    # ================


    def addStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus.add(callback)

    def delStatusCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onStatus.remove(callback)

    def addPhotometerCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onPhotometer.add(callback)

    def delPhotometerCallback(self, callback):
        '''
        API Entry Point
        '''
        self._onPhotometer.remove(callback)


    def execute(self, cmd, nretries=None):
        '''
        API Entry Point.
        Send a command to EMA for execution.
        Retuns a Deferred whose success callback returns the command value.
        An errback may be invoked with EMATimeoutError after nretries have been made.
        '''
        nretries = nretries or cmd.retries
        return self._enqueue(cmd, nretries=nretries)

    def resetStats(self):
        '''
        Reset statistics counters.
        '''
        self.nreceived = 0
        self.nresponse = 0
        self.nunsolici = 0
        self.nunknown  = 0

    # --------------
    # Helper methods
    # --------------

    def _pause(self):
        '''
        Pauses the sending of commands
        '''
        log.debug("EMA protocol pause()")
        self.paused = True

    def _resume(self):
        '''
        Resume the sending of commands
        '''
        log.debug("EMA protocol resume()")
        self.paused = False
        if len(self._queue) and not self.busy:
            self._retry()


    def _enqueue(self, request, nretries):
        '''
        Starts the ball rolling for the given request
        '''
        request.interval = Interval(initial=request.timeout['min'], 
                                    maxDelay=request.timeout['max'],
                                    factor=request.timeout['factor']) 
        request.nretries = nretries
        request.retries  = 0  
        request.deferred = defer.Deferred()
        request.encode()
        request.reset()
        self._queue.append(request)
        if not self.busy and not self.paused:    # start the ball rolling
            self._retry()
        return request.deferred


    def _retry(self):
        '''
        Transmit/Retransmit the oldest request
        '''
        request = self._queue[0]
        t = request.interval()
        request.alarm = self.callLater(t, self._responseTimeout)
        log.info("Executing -> {request.name} (retries={request.retries}/{request.nretries}) [Timeout={t}]", 
            request=request, t=t)
        self.sendLine(request.getEncoded())
        self.busy = True


    def _responseTimeout(self):
        '''
        Handle lack of response from EMA by retries or raising a Failure
        '''
        request = self._queue[0]
        log.error("{timeout} {request.name}", request=request, timeout="Timeout")
        if request.retries == request.nretries:
            request.deferred.errback(EMATimeoutError(request.name))
            request.deferred = None
            self._queue.popleft()
            del request
            self.busy = False
            if len(self._queue) and not self.paused:    # Continue with the next command
                self._retry()
        else:
            request.retries += 1
            request.reset()
            self._retry()


    def _handleCommandResponse(self, line, tstamp):
        '''
        Handle incoming command responses.
        Returns True if handled or finished, False otherwise
        '''
        if len(self._queue) == 0:
            return False

        request = self._queue[0]
        handled, finished = request.decode(line)
        if finished:
            log.info("Completed <- {request.name} (retries={request.retries}/{request.nretries})", 
            request=request)
            self._queue.popleft()
            self.busy = False
            request.alarm.cancel()
            if len(self._queue) and not self.paused:    # Fires next command if any
                self._retry()
            request.deferred.callback(request.getResult()) # Fire callback after _retry() !!!
            del request
        return handled or finished

    def _handleUnsolicitedResponse(self, line, tstamp):
        '''
        Handle unsolicited responses from EMA.
        Returns True if handled, False otherwise
        '''
        ur, matchobj = match_unsolicited(line)
        if not ur:
            return False
        if ur['name'] == 'Photometer begin':
            self._pause()
            return True
        if ur['name'] == 'Photometer end':
            mag = float(matchobj.group(1))
            for callback in self._onPhotometer:
                callback(mag, tstamp)
            self._resume()
            return True
        if ur['name'] == 'Current status message':
            curState, _ = command.decodeStatus(line)
            for callback in self._onStatus:
                callback(curState, tstamp)
            return True
        if ur['name'] == 'Thermopile I2C':
            return True
        if ur['name'] == 'Timer':
            return True
        if ur['name'] == 'Datalogger':
            return True
        log.error("We should never have reached this unsolicited response")
        return False
        
#---------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

@implementer(IPausable, IReloadable)
class SerialService(ClientService):

    # Service name
    NAME = 'Serial Service'


    def __init__(self, options):
        self.options    = options    
        protocol_level  = 'info' if self.options['log_messages'] else 'warn'
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        setLogLevel(namespace='serial', levelStr=self.options['log_level'])
        setLogLevel(namespace='ema.serial.protocol.base.EMAProtocolFactory', levelStr='error')
        self.factory   = EMAProtocolFactory()
        self.serport   = None
        self.protocol  = None
        self.vmag      = None
        self.devices   = []
        self.goSerial  = self._decide()


    def _decide(self):
        '''Decide which endpoint must be built, either TCP or Serial'''

        def backoffPolicy(initialDelay=4.0, maxDelay=60.0, factor=2):
            '''Custom made backoff policy to exit after a number of reconnection attempts'''
            def policy(attempt):
                delay = min(initialDelay * (factor ** attempt), maxDelay)
                if attempt > 3:
                    self.stopService()
                return delay
            return policy


        parts = chop(self.options['endpoint'], sep=':')
        if parts[0] == 'serial':
            self.endpoint = parts[1:]
            Service.__init__(self)
            return True
        else:
            self.endpoint = clientFromString(reactor, self.options['endpoint'])
            ClientService.__init__(self, self.endpoint, self.factory, retryPolicy=backoffPolicy())
            return False

    
    def startService(self):
        '''
        Starts the Serial Service that takls to EMA
        By exception, this returns a deferred that is handled by emaservice
        '''
        log.info("starting Serial Service")
        self.statTask = task.LoopingCall(self.printStats)
        self.statTask.start(3600, now=False)  # call every hour
        if self.goSerial:
            Service.startService(self)
            if self.serport is None:
                self.protocol = self.factory.buildProtocol(0)
                self.serport  = SerialPort(self.protocol, self.endpoint[0], reactor, baudrate=self.endpoint[1])
            self.gotProtocol(self.protocol)
            log.info("Using serial port {tty}", tty=self.endpoint[0])
        else:
            ClientService.startService(self)
            d = self.whenConnected()
            d.addCallback(self.gotProtocol)
            log.info("Using TCP endpopint {endpoint} as serial port", endpoint=self.endpoint)
            return d
            
    @inlineCallbacks
    def stopService(self):
        self.statTask.cancel()
        if not self.goSerial:
            try:
                yield ClientService.stopService(self)
            except Exception as e:
                log.error("Exception {excp!s}", excp=e)
                raise 
        else:
            Service.stopService(self)

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['serial']
        protocol_level  = 'debug' if options['log_messages'] else 'info'
        setLogLevel(namespace='serial', levelStr=options['log_level'])
        setLogLevel(namespace='protoc', levelStr=protocol_level)
        log.info("new log level is {lvl}", lvl=options['log_level'])
        self.options = options

    # --------------
    # Periodic task
    # ---------------

    def printStats(self):
        tot  = self.protocol.nreceived
        nack = self.protocol.nresponse
        nuns = self.protocol.nunsolici
        nunk = self.protocol.nunknown 
        quality = (nack + nuns)*100 / tot if tot != 0 else None 
        log.info("EMA SERIAL STATS: TOTAL = {tot:03d}, UNKNOWN = {nunk:03d}", 
            tot=tot, nunk=nunk)
        log.info("EMA SERIAL LINE QUALITY = {q:0.4f}%", q=quality)
        self.parent.logMQTTEvent("Serial Line Quality (total-unknown)/total) = {q:0.4f}%".format(q=quality))
        self.protocol.resetStats()


    # --------------
    # Helper methods
    # ---------------

    def gotProtocol(self, protocol):
        log.debug("got Protocol")
        self.protocol  = protocol
        self.protocol.addStatusCallback(self.onStatus)
        self.protocol.addPhotometerCallback(self.onVisualMagnitude)
        self.parent.gotProtocol(protocol)
       

    # ----------------------------
    # Event Handlers from Protocol
    # -----------------------------

    def onVisualMagnitude(self, vmag, tstamp):
        '''Records last visual magnitude update'''
        self.vmag = vmag


    def onStatus(self, status, tstamp):
        '''
        Adds last visual magnitude estimate
        and pass it upwards
        '''
        if self.vmag:
            status.append(self.vmag)
        else:
            status.append(24.0)
        self.parent.onStatus(status, tstamp)


__all__ = [
    "EMATimeoutError",
    "EMAProtocol",
    "EMAProtocolFactory",
    "SerialService",
]