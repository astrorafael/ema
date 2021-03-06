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

class Device(object):

	def __init__(self, publish_where=tuple(), publish_what=tuple()):
		self.__publishable = [(where,what) for where in publish_where for what in publish_what]
	
	@property
	def name(self):
		'''Return object name'''
		return self.__class__.__name__

	@property
	def current(self):
		'''Return dictionary with current measured values'''
		return {}


	@property
	def average(self):
		'''Return dictionary of averaged values over a period of N samples'''
		return {}


	@property
	def threshold(self):
		'''Return dictionary with thresholds'''
		return {}


	@property
	def parameter(self):
		'''Return dictionary with calibration constants'''
		return {}


	@property
	def publishable(self):
		'''Return list of tuples with publishable destinantions (i.e. "mqtt", "html", etc.)
		and what things to bublish '''
		return self.__publishable

