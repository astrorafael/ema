# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

# ---------------
# Twisted imports
# ---------------

from twisted.internet import task, reactor

#--------------
# local imports
# -------------

from .service.relopausable import Service, MultiService, Application
from .logger import sysLogInfo,  startLogging
from .config import VERSION_STRING, cmdline, loadCfgFile

#from .mqttservice import MQTTService

from .ema            import EMAService

from .serial.service import SerialService
from .internet       import InternetService
from .scripts        import ScriptsService 
from .scheduler      import SchedulerService



# Read the command line arguments and config file options
cmdline_opts = cmdline()
config_file = cmdline_opts.config
if config_file:
   config_opts  = loadCfgFile(config_file)
else:
   config_opts = None

# Start the logging subsystem
log_file = config_opts['ema']['log_file']
startLogging(console=cmdline_opts.console, filepath=log_file)


# Assemble application from its service components
application = Application("ema")
emaService  = EMAService(config_opts['ema'])
emaService.setServiceParent(application)
schedulerService = SchedulerService(config_opts['scheduler'])
schedulerService.setServiceParent(emaService)
internetService = InternetService(config_opts['internet'])
internetService.setServiceParent(emaService)
scriptsService = ScriptsService(config_opts['scripts'])
scriptsService.setServiceParent(emaService)
serialService = SerialService(config_opts['serial'])
serialService.setServiceParent(emaService)



# Store direct links to subservices in our manager service
emaService.schedulerService = schedulerService
emaService.internetService  = internetService
emaService.scriptsService   = scriptsService
emaService.serialService    = serialService


__all__ = [ "application" ]