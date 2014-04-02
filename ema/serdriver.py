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
# EMA sends messages between () brackes, so after the tiny asynchronous 
# server framework was setup to get input activity, the next thing to do
# was to reassemble from a continuous stream of bytes, so that the 
# "upper processing layers" dealt with one complete message at a time.
#
# Also, output to EMA should be done a a moderate pace, so as not to
# overload EMA with a buch of messages with the probability of many of
# them being lost.
#
# So this is the purpose of the SerialDriver. 
# Responsibilities:
# 1) Get bytes from SerialPort and reassemble them into whole messages
# 2) Register uper layer callbacks and invoke them.
# 3) Enqueue output messages to EMA and trasmit them at a moderate pace 
# 4) Hold/resume the transmission of output messages from the queue.
#
#
# SerialDriver inherits from Lazy so that we can use an periodic work()
# method to pop messages from the queue and transmit them to EMA.
#
# Enqueing output messages from "upper layers" adds delay to messages 
# and this is relevant to timeout & retry procedures, However, 
# its effect was easy to take into account and the upper layers can add
# the delay to be introduced by the  last element in the queue.
#
# Peculiar to EMA is the need to suspend/resume he transmssion of output
# messages at certain times.
#
# I have never had the need to unregister a handler, 
# so there is no delHandler()
# ======================================================================

import serial
import re
import logging

from server import Lazy


log = logging.getLogger('serdriver')

def setLogLevel(level):
    log.setLevel(level)


class SerialDriver(Lazy):

   NSTATS = 1000  # Print number of reads each NSTATs times
	
   def __init__(self, port, baud, **kargs):
      Lazy.__init__(self)
      self.__nreads   = 0
      self.__nwrites  = 0
      self.__buffer   = ''
      self.__handlers = []
      self.__outqueue = []
      self.__stopped  = False
      
      # An EMA message, surronded by brackets
      self.__patt     = re.compile('\([^)]+\)') 
      self.__serial          = serial.Serial()
      self.__serial.port     = port
      self.__serial.baudrate = baud
      try:
         self.__serial.open()
         self.__serial.flushInput()
         self.__serial.flushOutput()
      except serial.SerialException, e:
         log.error("Could not open serial port %s: %s", self.__serial.name, e)
         raise
      log.info("Opened %s at %s bps", self.__serial.port, self.__serial.baudrate)
      
   # ----------------------------------------
   # Public interface exposed to upper layers
   # -----------------------------------------


   def write(self, message):
      '''
      Enqueues message to output queue
      '''
      self.__outqueue.append(message)


   def queueDelay(self):
       '''returns the max wait time in multiples of Server.TIMEOUT'''
       return 1+len(self.__outqueue) 


   def hold(self, flag):
      '''
      Stop/Resume dequeuing messages from the output queue
      and transmitting to serial port.
      '''
      self.__stopped = flag
      log.debug("on hold = %s", flag)


   def addHandler(self, object):
      '''Registers an object implementing a handle(message) method'''
      self.__handlers.append(object)


   # --------------
   # Helper methods
   # --------------

   def work(self):
      '''
      Writes data to serial port configured at init. 
      Called periodically from a Server object.
      Write blocking behaviour.
      '''
      qlen = len(self.__outqueue)
      if self.__stopped:
         return

      if qlen:
         try:
            log.debug("Tx %s",  self.__outqueue[0])
            self.__nwrites += 1
            self.__serial.write(self.__outqueue.pop(0))                 
         except serial.__serialException, e:
            log.error("%s: %s" , self.__serial.portstr, e)
            raise


   def read(self):
      '''
      Reads from serial port. 
      Return all available data in buffer.
      '''
      try:
         return self.__serial.read(self.__serial.inWaiting())
      except serial.SerialException, e:
         log.error("%s: %s" , self.__serial.portstr, e)
         raise

      
   def extract(self):
      '''
      Extracts a complete EMA message
      Returns whole message if available or null string if not.
      '''
      matched = self.__patt.search(self.__buffer)
      message = ''
      if matched:
         message = matched.group()
         self.__buffer = self.__buffer[matched.end():]
         self.__nreads += 1
         log.debug("Rx %s", message)
      return message


   def show(self):
      '''print read/written message statistcs every NSTATs times'''
      n = max(self.__nreads, self.__nwrites) % SerialDriver.NSTATS
      if not n:
         log.info("nreads = %d, nwrites = %d , queue = %d", self.__nreads, self.__nwrites, len(self.__outqueue))


   def onInput(self):
      '''
      Read from message buffer and notify handlers if message complete.
      Called from Server object
      '''
      self.__buffer += self.read()           # accumulate reading
      message        = self.extract()        # extract whole message
      if message:
         for handler in self.__handlers:
            handler.onSerialMessage(message)


   def fileno(self):
      '''Implement this interface to be added in select() system call'''
      return self.__serial.fileno()




if __name__ == "__main__":

   from utils import setDebug
   class Sample(object):
      def onSerialMessage(self, message):
         log.info(message.split())

   setDebug()
   options = {'serial_baud': '9600', 'serial_port': '/dev/ttyAMA0'}
   driver = SerialDriver('/dev/ttyAMA0', 9600, **options)
   driver.addHandler( Sample() )
   driver.write('( )')
   s = server.Server()
   s.addReadable(driver)
   s.run()


