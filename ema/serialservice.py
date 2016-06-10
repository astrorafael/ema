# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import os
import errno
import sys
import datetime
import json
import math

# ---------------
# Twisted imports
# ---------------

from twisted.logger              import Logger, LogLevel
from twisted.internet            import reactor, task
from twisted.internet.defer      import inlineCallbacks
from twisted.internet.serialport import SerialPort
from twisted.application.service import Service
from twisted.protocols.basic     import LineReceiver, LineOnlyReceiver


#--------------
# local imports
# -------------

from .logger import setLogLevel
from .utils  import chop

# ----------------
# Module constants
# ----------------


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='serial')

class EMAProtocol(LineOnlyReceiver):

    # -------------------------
    # Twisted Line Receiver API
    # -------------------------

    def __init__(self):
        '''Sets the delimiter to the closihg parenthesis'''
        LineOnlyReceiver.delimiter = b')'

    def connectionMade(self):
        log.debug("connectionMade()")


    def lineReceived(self, line):
        now = datetime.datetime.utcnow()
        line = line.lstrip() + b')'
        log.debug("<== EMA {line}", line=line)


    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, including the delimiter.
        @type line: C{bytes}
        """
        log.debug("==> EMA {line}", line=line)
        return self.transport.write(line)
        



class SerialService(Service):


    def __init__(self, parent, options, **kargs):
        self.parent     = parent
        self.options    = options
        setLogLevel(namespace='serial', levelStr=options['log_level'])
       
        self.protocol  = EMAProtocol()
        self.port      = None

        self.resetCounters()
        Service.__init__(self)

    
    def startService(self):
        log.info("starting Serial Service")
        if self.port is None:
            self.port      = SerialPort(self.protocol, self.options['port'], reactor, baudrate=self.options['baud'])
        Service.startService(self)


    @inlineCallbacks
    def stopService(self):
        try:
            yield Service.stopService(self)
        except Exception as e:
            log.error("Exception {excp!s}", excp=e)
            reactor.stop()

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, new_options):
        setLogLevel(namespace='serial', levelStr=new_options['log_level'])
        log.info("new log level is {lvl}", lvl=new_options['log_level'])
        self.options = new_options
        

    def pauseService(self):
        pass

    def resumeService(self):
        pass

    # -------------
    # log stats API
    # -------------

    def resetCounters(self):
        '''Resets stat counters'''
        pass
        

    def getCounters(self):
        return [ ]

    def logCounters(self):
        '''log stat counters'''
        pass
        

    # --------------
    # Helper methods
    # ---------------
   
  


    def onPublish(self):
        '''
        Serial message Handler
        '''
        pass


__all__ = [SerialService]