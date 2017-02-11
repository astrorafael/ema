# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

# ---------------
# Twisted imports
# ---------------

from twisted.internet import task, reactor

#--------------
# local imports
# -------------

from ema.service.reloadable import Service, MultiService, Application
from ema.logger import sysLogInfo,  startLogging
from ema.config import VERSION_STRING, cmdline, loadCfgFile


from ema.ema       import EMAService
from ema.serial    import SerialService    
from ema.probe     import ProbeService  
from ema.scripts   import ScriptsService   
from ema.scheduler import SchedulerService
from ema.mqttpub   import MQTTService
from ema.web       import WebService


# Read the command line arguments and config file options
cmdline_opts = cmdline()
config_file = cmdline_opts.config
if config_file:
   options  = loadCfgFile(config_file)
else:
   options = None

# Start the logging subsystem
LOG_FILE = "/var/log/ema.log"
startLogging(console=cmdline_opts.console, filepath=LOG_FILE)

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

probeService = ProbeService(options['probe'])
probeService.setName(ProbeService.NAME)
probeService.setServiceParent(emaService)

scriptsService = ScriptsService(options['scripts'])
scriptsService.setName(ScriptsService.NAME )
scriptsService.setServiceParent(emaService)

serialService = SerialService(options['serial'])
serialService.setName(SerialService.NAME)
serialService.setServiceParent(emaService)

mqttService = MQTTService(options['mqtt'])
mqttService.setName(MQTTService.NAME)
mqttService.setServiceParent(emaService)

webService = WebService(options['web'])
webService.setName(WebService.NAME)
webService.setServiceParent(emaService)

# --------------------------------------------------------
# Store direct links to subservices in our manager service
# --------------------------------------------------------


__all__ = [ "application" ]