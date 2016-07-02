# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

import os
import sys
import argparse
import errno

import win32serviceutil
import win32event
import servicemanager  
import win32api

import win32service
import win32con
import win32evtlogutil

# ---------------
# Twisted imports
# ---------------

#from twisted.internet import win32eventreactor
#win32eventreactor.install()

from twisted.internet import reactor
from twisted.logger import Logger, LogLevel

#--------------
# local imports
# -------------

from .  import __version__

from .logger               import sysLogInfo
from .config               import VERSION_STRING
from .application          import application
from .service.relopausable import sigreload, sigpause, sigresume

# ----------------
# Module constants
# ----------------

# Custom Windows service control in the range of [128-255]
SERVICE_CONTROL_RELOAD = 128

# -----------------------
# Module global variables
# -----------------------


# ------------------------
# Module Utility Functions
# ------------------------


# ----------
# Main Class
# ----------

class TESSWindowsService(win32serviceutil.ServiceFramework):
	"""
	Windows service for the TESS database.
	"""
	_svc_name_         = "ema"
	_svc_display_name_ = "EMA service {0}".format( __version__)
	_svc_description_  = "A MQTT publisher Client for EMA astronomical weather station"


	def __init__(self, args):
		win32serviceutil.ServiceFramework.__init__(self, args)
		

	def SvcStop(self):
		'''Service Stop entry point'''
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		reactor.callFromThread(reactor.stop)
		sysLogInfo("Stopping  ema {0} Windows service".format( __version__ ))


	def SvcPause(self):
		'''Service Pause entry point'''
		self.ReportServiceStatus(win32service.SERVICE_PAUSE_PENDING)
		reactor.callFromThread(sigpause)
		sysLogInfo("Pausing ema {0} Windows service".format( __version__ ))
		self.ReportServiceStatus(win32service.SERVICE_PAUSED)
		

	def SvcContinue(self):
		'''Service Continue entry point'''
		self.ReportServiceStatus(win32service.SERVICE_CONTINUE_PENDING)
		reactor.callFromThread(sigresume)
		sysLogInfo("Resuming ema {0} Windows service".format( __version__ ))
		self.ReportServiceStatus(win32service.SERVICE_RUNNING)
		

	def SvcOtherEx(self, control, event_type, data):
		'''Implements a Reload functionality as a service custom control'''
		if control == SERVICE_CONTROL_RELOAD:
			self.SvcDoReload()
		else:
			self.SvcOther(control)


	def SvcDoReload(self):
		sysLogInfo("Reloading ema {0} Windows service".format( __version__ ))
		reactor.callFromThread(sigreload)


	def SvcDoRun(self):
		'''Service Run entry point'''
		# initialize your services here
		sysLogInfo("Starting {0}".format(VERSION_STRING))
		IService(application).startService()
		reactor.run(installSignalHandlers=0)
		sysLogInfo("ema Windows service stopped {0}".format( __version__ ))

     
def ctrlHandler(ctrlType):
    return True

if not servicemanager.RunningAsService():   
    win32api.SetConsoleCtrlHandler(ctrlHandler, True)   
    win32serviceutil.HandleCommandLine(TESSWindowsService)