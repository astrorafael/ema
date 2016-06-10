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

import logging
import gammu
import sys
import argparse

CONFIG_FILE = '/home/pi/.smsdrc'
PHONE       = '+34xxxxxxxxx'
VERSION_STRING = "1.0"

def parser():
	'''Create the command line interface options'''
	_parser = argparse.ArgumentParser()
	_parser.add_argument('--version', action='version', version='%s' % VERSION_STRING)
	_parser.add_argument('-s' , '--status', type=str, action='store', metavar='ON|OFF', help='current roof status')
	_parser.add_argument('-r' , '--reason', type=str, action='store', metavar='code', help='EMA Reason Code')
	return _parser

opt = parser().parse_args()


text  = 'AVISO: EMA ha cerrado el techo automaticamente'


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
  
if opt.status == "OFF":   
	sendSMS(PHONE, text)
