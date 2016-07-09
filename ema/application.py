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
   options  = loadCfgFile(config_file)
else:
   options = None

# Start the logging subsystem
log_file = options['ema']['log_file']
startLogging(console=cmdline_opts.console, filepath=log_file)

# ------------------------------------------------
# Assemble application from its service components
# ------------------------------------------------

application = Application("EMA")

emaService  = EMAService(options['ema'],config_file)
emaService.setName(EMAService.NAME)
emaService.setServiceParent(application)

schedulerService = SchedulerService(options['scheduler'])
schedulerService.setName(SchedulerService.NAME)
schedulerService.setServiceParent(emaService)

internetService = InternetService(options['internet'])
internetService.setName(InternetService.NAME)
internetService.setServiceParent(emaService)

scriptsService = ScriptsService(options['scripts'])
scriptsService.setName(ScriptsService.NAME )
scriptsService.setServiceParent(emaService)

serialService = SerialService(options['serial'])
serialService.setName(SerialService.NAME)
serialService.setServiceParent(emaService)

# --------------------------------------------------------
# Store direct links to subservices in our manager service
# --------------------------------------------------------


__all__ = [ "application" ]