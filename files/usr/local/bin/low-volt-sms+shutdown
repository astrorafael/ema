#!/usr/bin/env python

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

import gammu
import sys
import subprocess


CONFIG_FILE = '/etc/gammu-smsdrc'
PHONE       = '+34xxxxxxxxx'

def parser():
	'''Create the command line interface options'''
	_parser = argparse.ArgumentParser()
	_parser.add_argument('--version', action='version', version='%s' % VERSION_STRING)
	_parser.add_argument('-v' , '--voltage', type=str, action='store', metavar='Volts', help='current votage')
	_parser.add_argument('-s' , '--size',    type=str, action='store', metavar='Size', help='sample size on which voltage was measured')
	_parser.add_argument('-t' , '--threshold', type=str, action='store', metavar='Volts', help='low threshold voltage')
	return _parser

opt = parser().parse_args()


text  = '''AVISO:
Auto Apagado por bajo voltaje (%s V < %s V) tras una media de %s muestras
''' % (opt.voltage, opt.threshold, opt.size)



def sendSMS(phone, text):
	smsd = gammu.SMSD(CONFIG_FILE)
	message = { 
		'SMSC'   : {'Location' : 1},
		'Text'   : text,
		'Number' : phone,
		 }
	msgList = []
	msgList.append(message)
	smsd.InjectSMS(msgList)
  
sendSMS(PHONE, text)
# shuts down in two minutes from now
subprocess.call(['sudo','shutdown','-h','+2'])






