# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


#--------------------
# System wide imports
# -------------------

from __future__ import division

import sys
import signal

# ---------------
# Twisted imports
# ---------------

from twisted.logger import Logger
from twisted.internet import reactor

#--------------
# local imports
# -------------

from .logger import sysLogInfo,  startLogging
from .config import VERSION_STRING, cmdline, loadCfgFile
from .application import EMAApplication

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------


# ------------------------
# Module Utility Functions
# ------------------------

# SIGNAL HANDLERS

def sigreload(signum, frame):
   '''
   Signal handler (SIGHUP)
   '''
   EMAApplication.instance.sigreload = True
   
def sigpause(signum, frame):
   '''
   Signal handler (SIGUSR1)
   '''
   EMAApplication.instance.sigpause = True

def sigresume(signum, frame):
   '''
   Signal handler (SIGUSR2)
   '''
   EMAApplication.instance.sigresume = True



# Read the command line arguments and config file options
cmdline_opts = cmdline()
config_file = cmdline_opts.config
if config_file:
   config_opts  = loadCfgFile(config_file)
else:
   config_opts = None

log_file = config_opts['ema']['log_file']

# Install signal handlers
signal.signal(signal.SIGHUP,  sigreload)
signal.signal(signal.SIGUSR1, sigpause)
signal.signal(signal.SIGUSR2, sigresume)

config_file=cmdline_opts.config
# Start the logging subsystem
startLogging(console=cmdline_opts.console, filepath=log_file)

sysLogInfo("Starting {0}".format(VERSION_STRING))
application = EMAApplication(config_file, config_opts)
application.startService()
reactor.run()
sysLogInfo("Stopped {0}".format(VERSION_STRING))
