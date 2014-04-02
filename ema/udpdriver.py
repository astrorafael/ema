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
# This is the counterpart of the serial driver.
#
# EMA desginer was interesetd in broadcasting EMA messages to other
# hosts in the same LAN, so the idea of using UDP instead of TCP
# was born. The local LAN was deemed reliable enough so as not to worry
# about UDP packet losses.
#
# Also, this driver sends responses from EMA to queries from other 
# hosts in the same LAN. 
# Together with the SerialDriver, this is a kind of 
# "serial to Ethernet" adapter, tailored to EMA messages 
#
# Messages not processed internally by this EMA software can be 
# forwarded to other hosts in the same LAN (i.e. an INDI Driver in 
# another host)
#
# UDPDriver listens on an rx_port in any interface. This allows to receive
# messages from themulticast group or directly from a UDP sender.
# Also, iot can transmit messages to the mulicast group, tx_port or to
# given unicast IP, tx_port
#
# Responsibilities:
# 1) Join to a multicast group.
# 2) Get bytes from UDP Rx Port and reassemble them into whole messages
# 3) Register uper layer callbacks and invoke them.
# 4) trasmit EMA messages either to a muticast group or to unicast 
#  sender IP 
#
# UDPDriver does not need to execute code periodically, so there is no 
# need to derive it from Lazy.
#
# UDP driver passes the origin IP + port to upper layers to aid
# matching requests from other hosts.
#
# Chunks of input are internally classified in a dictionary  according 
# to the sender IP+port to allow simultaneous commands from 
# several programs.
#
# ======================================================================


import re
import struct
import socket
import logging

log = logging.getLogger('udpdriver')

def setLogLevel(level):
    log.setLevel(level)

def udpsocket(rx_port, mcast_ip=None):
   '''Creates a UDP socket boind on port rx_port'''
   '''Optionally joins a multicast group on mcast_ip'''
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
   sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
   sock.bind(('', rx_port))   # In any network interface
   if mcast_ip:
      mreq = struct.pack("4sl", socket.inet_aton(mcast_ip), socket.INADDR_ANY)
      sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq) 
      sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
   return sock       

class UDPDriver(object):

   NSTATS = 100  # Print number of reads ecah NSTATs times
	
   def __init__(self, ip, rx_port, tx_port, **kargs):
      self.__nreads   = 0
      self.__nwrites  = 0
      self.__buffer   = {}
      self.__handlers = []
      self.__ip       = ip
      self.__rx_port  = rx_port
      self.__tx_port  = tx_port
      # An EMA message, surronded by brackets
      self.__patt     = re.compile('\([^)]+\)') 
      try:
         self.__sock = udpsocket(rx_port, ip)
      except Exception as e:
         log.error(e)
         raise
      log.info("Receive UDP packets on port %d (all interfaces)", rx_port)    
      
   # ----------------------------------------
   # Public interface exposed to upper layers
   # ----------------------------------------
      
   def write(self, data, unicast_ip=None):
      '''
      Write EMA message to multicast IP (by default) or given unicast_ip
      '''
      ip = unicast_ip if unicast_ip else self.__ip
      log.debug("Tx %s to '%s'", data, (ip, self.__tx_port))
      try:
         self.__sock.sendto(data,(ip, self.__tx_port))
         self.__nwrites += 1
      except socket.error, msg:
         log.error(msg)
         raise

   def addHandler(self, object):
      '''Registers an object implementing a handle(message) method'''
      self.__handlers.append(object)

   # --------------
   # Helper methods
   # --------------

   def read(self):
      '''
      Reads from UDP socket. 
      Return (data, origin) tuple, where origin is itsel a tuple.
      '''
      try:
         data, origin = self.__sock.recvfrom(1024)
         log.debug("Rx %s from '%s'", data, origin)
         return data, origin
      except socket.error, msg:
         log.error(msg)
         raise

      
   def extract(self, origin):
      '''
      Extracts a complete EMA message
      Returns whole message if available or null string if not.
      '''
      message = ''
      matched = None
      if origin in self.__buffer:
         matched = self.__patt.search(self.__buffer[origin])

      if matched:
         message = matched.group()
         self.__buffer[origin] = self.__buffer[origin][matched.end():]
         log.debug("extracted %s, remains %s", message, self.__buffer[origin] if self.__buffer[origin] else None)
         if not self.__buffer[origin]:
            del self.__buffer[origin]
         self.__nreads += 1
      return message


   def show(self):
      '''print read/written message statistcs every NSTATs times'''
      n = max(self.__nreads, self.__nwrites) % MulticastDriver.NSTATS
      if not n:
         log.info("nreads = %d, nwrites = %d, buffer =%s", 
                  self.__nreads, self.__nwrites, self.__buffer)


   def onInput(self):
      '''
      Update message buffer and notify 
      if necessary by invoking onUDPMessage()
      '''
      chunk, origin  = self.read()
      if origin in self.__buffer:
         self.__buffer[origin] += chunk               # accumulate reading
      else:
         self.__buffer[origin] = chunk

      # Loop: May be 1+ messages in buffer, process all until none.
      message = self.extract(origin) # extract whole message
      while message:
         for handler in self.__handlers:
            handler.onUDPMessage(message, origin)
         message = self.extract(origin) # extract whole message


   def fileno(self):
      '''Implement this interface to be added in select() system call'''
      return self.__sock.fileno()




if __name__ == "__main__":

   from utils import setDebug
   from server import Server

   class Sample(object):
      def  __init__(self, driver):
          self.driver = driver

      def onUDPMessage(self, message, origin):
         log.info("Observer receives %s from %s", message.split(),origin)
         self.driver.write('(pepe)')

   setDebug()
   options = {'mcast_ip': '225.100.20.15', 'mcast_rx_port': '850', 'mcast_tx_port' : '849' }
   driver = UDPDriver('225.100.20.15',850,849,**options)
   driver.addHandler( Sample(driver) )
   server = Server()
   server.addReadable(driver)
   server.run()



