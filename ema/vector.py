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
#
# When I started writting this EMA software, I though that it could be 
# a good idea to accumulate the measurements contained in the EMA status
# message. If I ever POST these samples to an external web graphical server
# it couldbe the case hat it didn't accept updates so often.
# SO eitehr I coud do a bulk dump lest frequently or just compute an 
# average over a longer perido of time.
#
# Currently, the sliding window is ony used to monitor the battery
# voltage (and I do not use the whole vector, only a slice).
#
# Responsibilities:
# 1) Maintain an array of measurements over time.
# 2) Implement a sliding window protocol. Each time a new masurement is
# added, the oldest one is dropped.
# 3) Compute the sum of the entire array or a given slice.
# 4) inform about the actual sum and vector length 
#
# Keep a timestamp of current sample to inform interested parties
#
# ======================================================================

import logging

log = logging.getLogger('vector')

class Vector(object):
   """
   Vector implementing a sliding window protocol of size N.
   to calculate moving average
   """


   def __init__(self, N):
      '''Initializes a vector with max size N'''
      self.N       = N
      self.accum   = 0
      self.samples = []


   def append(self, sample, timestamp):
      '''append a sample tuple (value, Time) to the vector 
      and move the window if necessary'''
      self.samples.append( (sample, timestamp) )
      self.accum += sample
      if len(self.samples) > self.N:
         pop = self.samples[0]
         self.accum -= self.samples.pop(0)[0]


   def last(self):
      '''Returns the newest sample tuple added'''
      return self.samples[-1]

   def first(self):
      '''Returns the oldest sample tuple added'''
      return self.samples[0]


   def len(self):
      '''Returns the vector length'''
      return len(self.samples)


   def sum(self, N=None):
      '''
      Returns a tuple with the accumulated value of last N samples
      and vector length. 
      If N is supplied, returns min(N, vector size)
      '''
      if not N: 
         return (self.accum, len(self.samples))
      else:
         return (sum(self.samples[-N:][0]), min(N,len(self.samples)))


if __name__ == '__main__':
   from datetime import datetime
   v =Vector(5)
   print(v.sum())
   v.append(7,datetime.utcnow())
   print(v.last())
   print(v.sum())
   v.append(1, datetime.utcnow())
   print(v.last()[0])
   print(v.sum())
   v.append(3, datetime.utcnow())
   print(v.last()[0])
   print(v.sum())
   v.append(5, datetime.utcnow())
   print(v.last())
   print(v.sum())
   v.append(9, datetime.utcnow())
   print(v.last())
   print(v.sum())
   v.append(2, datetime.utcnow())
   print(v.last())
   print(v.sum())
   v.append(4, datetime.utcnow())
   print(v.last())
   print(v.sum())
   v.append(6, datetime.utcnow())
   print(v.last())
   print(v.sum())
   print(v.sum(N=3))

      
