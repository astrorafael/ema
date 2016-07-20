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
import os
import os.path
import argparse
import errno

# Only Python 2
import ConfigParser

# ---------------
# Twisted imports
# ---------------

from twisted.logger import LogLevel

#--------------
# local imports
# -------------

from .utils import chop
from . import __version__

# ----------------
# Module constants
# ----------------


VERSION_STRING = "ema/{0}/Python {1}.{2}".format(__version__, sys.version_info.major, sys.version_info.minor)

# Default config file path
if os.name == "nt":
    CONFIG_FILE=os.path.join("C:\\", "ema", "config", "config.ini")
else:
    CONFIG_FILE="/etc/ema/config"


# -----------------------
# Module global variables
# -----------------------


# ------------------------
# Module Utility Functions
# ------------------------

def cmdline():
    '''
    Create and parse the command line for the ema package.
    Minimal options are passed in the command line.
    The rest goes into the config file.
    '''
    parser = argparse.ArgumentParser(prog='ema')
    parser.add_argument('--version',            action='version', version='{0}'.format(VERSION_STRING))
    parser.add_argument('-k' , '--console',     action='store_true', help='log to console')
    parser.add_argument('-i' , '--interactive', action='store_true', help='run in foreground (Windows only)')
    parser.add_argument('-c' , '--config', type=str,  action='store', metavar='<config file>', help='detailed configuration file')
    parser.add_argument('-s' , '--startup', type=str, action='store', metavar='<auto|manual>', help='Windows service starup mode')
    group = parser.add_mutually_exclusive_group()
    group.add_argument(' install', type=str, nargs='?', help='install Windows service')
    group.add_argument(' start',   type=str, nargs='?', help='start Windows service')
    group.add_argument(' stop',    type=str, nargs='?', help='start Windows service')
    group.add_argument(' remove',  type=str, nargs='?', help='remove Windows service')
    return parser.parse_args()


def loadCfgFile(path):
    '''
    Load options from configuration file whose path is given
    Returns a dictionary
    '''

    if path is None or not (os.path.exists(path)):
        raise IOError(errno.ENOENT,"No such file or directory", path)

    options = {}
    parser  = ConfigParser.RawConfigParser()
    # str is for case sensitive options
    #parser.optionxform = str
    parser.read(path)

    options['ema'] = {}
    options['ema']['log_file']   = parser.get("ema","log_file")
    options['ema']['log_level']  = parser.get("ema","log_level")
    options['ema']['host_rtc']   = parser.getboolean("ema","host_rtc")
    options['ema']['nretries']   = parser.getint("ema","nretries")
    options['ema']['period']     = parser.getint("ema","period")
    options['ema']['shutdown']   = parser.getboolean("ema","shutdown")
    options['ema']['relay_shutdown'] = parser.getboolean("ema","relay_shutdown")

    options['ema']['sync']          = parser.getboolean("serial","sync")
    options['ema']['upload_period'] = parser.getint("serial","upload_period")
    options['ema']['voltmeter'] = {}
    options['ema']['voltmeter']['sync']            = parser.getboolean("voltmeter","sync")
    options['ema']['voltmeter']['offset']          = parser.getfloat("voltmeter","offset")
    options['ema']['voltmeter']['threshold']       = parser.getfloat("voltmeter","threshold")
    options['ema']['voltmeter']['delta']           = parser.getfloat("voltmeter","delta")
    options['ema']['anemometer'] = {}
    options['ema']['anemometer']['sync']            = parser.getboolean("anemometer","sync")
    options['ema']['anemometer']['calibration']     = parser.getint("anemometer","calibration")
    options['ema']['anemometer']['model']           = parser.get("anemometer","model")
    options['ema']['anemometer']['threshold']       = parser.getint("anemometer","threshold")
    options['ema']['anemometer']['ave_threshold']   = parser.getint("anemometer","ave_threshold")
    options['ema']['barometer'] = {}
    options['ema']['barometer']['sync']            = parser.getboolean("barometer","sync")
    options['ema']['barometer']['height']          = parser.getint("barometer","height")
    options['ema']['barometer']['offset']          = parser.getint("barometer","offset")
    options['ema']['cloudsensor'] = {}
    options['ema']['cloudsensor']['sync']            = parser.getboolean("cloudsensor","sync")
    options['ema']['cloudsensor']['threshold']       = parser.getint("cloudsensor","threshold")
    options['ema']['cloudsensor']['gain']            = parser.getfloat("cloudsensor","gain")
    options['ema']['photometer'] = {}
    options['ema']['photometer']['sync']            = parser.getboolean("photometer","sync")
    options['ema']['photometer']['threshold']       = parser.getfloat("photometer","threshold")
    options['ema']['photometer']['offset']          = parser.getfloat("photometer","offset")
    options['ema']['pluviometer'] = {}
    options['ema']['pluviometer']['sync']            = parser.getboolean("pluviometer","sync")
    options['ema']['pluviometer']['calibration']     = parser.getint("pluviometer","calibration")
    options['ema']['pyranometer'] = {}
    options['ema']['pyranometer']['sync']            = parser.getboolean("pyranometer","sync")
    options['ema']['pyranometer']['gain']            = parser.getfloat("pyranometer","gain")
    options['ema']['pyranometer']['offset']          = parser.getint("pyranometer","offset")
    options['ema']['rainsensor'] = {}
    options['ema']['rainsensor']['sync']            = parser.getboolean("rainsensor","sync")
    options['ema']['rainsensor']['threshold']       = parser.getint("rainsensor","threshold")
    options['ema']['thermometer'] = {}
    options['ema']['thermometer']['sync']            = parser.getboolean("thermometer","sync")
    options['ema']['thermometer']['threshold']      = parser.getfloat("thermometer","threshold")
    options['ema']['watchdog'] = {}
    options['ema']['watchdog']['sync']            = parser.getboolean("watchdog","sync")
    options['ema']['watchdog']['period']          = parser.getint("watchdog","period")
    options['ema']['rtc'] = {}
    options['ema']['rtc']['max_drift']          = parser.getint("rtc","max_drift")
    options['ema']['aux_relay'] = {}
    options['ema']['aux_relay']['sync']          = parser.getboolean("aux_relay","sync")
    options['ema']['aux_relay']['mode']          = parser.get("aux_relay","mode")
    options['ema']['roof_relay'] = {}
    options['ema']['roof_relay']['sync']          = parser.getboolean("roof_relay","sync")

    options['serial'] = {}
    options['serial']['endpoint']      = parser.get("serial","endpoint")
    options['serial']['log_level']     = parser.get("serial","log_level")
    options['serial']['log_messages']  = parser.getboolean("serial","log_messages")
   

    
  
    options['scripts'] = {}
    options['scripts']['roof_relay']       = parser.get("scripts","roof_relay")
    options['scripts']['roof_relay_args']  = parser.get("scripts","roof_relay_args")
    options['scripts']['roof_relay_mode']  = parser.get("scripts","roof_relay_mode")
    options['scripts']['aux_relay']        = parser.get("scripts","aux_relay")
    options['scripts']['aux_relay_args']   = parser.get("scripts","aux_relay_args")
    options['scripts']['aux_relay_mode']   = parser.get("scripts","aux_relay_mode")
    options['scripts']['low_voltage']      = parser.get("scripts","low_voltage")
    options['scripts']['low_voltage_args'] = parser.get("scripts","low_voltage_args")
    options['scripts']['low_voltage_mode'] = parser.get("scripts","low_voltage_mode")
    options['scripts']['no_internet']      = parser.get("scripts","no_internet")
    options['scripts']['no_internet_args'] = parser.get("scripts","no_internet_args")
    options['scripts']['no_internet_mode'] = parser.get("scripts","no_internet_mode")
    options['scripts']['active10']         = parser.get("scripts","active10")
    options['scripts']['active10_args']    = parser.get("scripts","active10_args")
    options['scripts']['active10_mode']    = parser.get("scripts","active10_mode")
    options['scripts']['active30']         = parser.get("scripts","active30")
    options['scripts']['active30_args']    = parser.get("scripts","active30_args")
    options['scripts']['active30_mode']    = parser.get("scripts","active30_mode")
    options['scripts']['active50']         = parser.get("scripts","active50")
    options['scripts']['active50_args']    = parser.get("scripts","active50_args")
    options['scripts']['active50_mode']    = parser.get("scripts","active50_mode")
    options['scripts']['active70']         = parser.get("scripts","active70")
    options['scripts']['active70_args']    = parser.get("scripts","active70_args")
    options['scripts']['active70_mode']    = parser.get("scripts","active70_mode")
    options['scripts']['active90']         = parser.get("scripts","active90")
    options['scripts']['active90_args']    = parser.get("scripts","active90_args")
    options['scripts']['active90_mode']    = parser.get("scripts","active90_mode")
    options['scripts']['log_level']        = parser.get("scripts","log_level")
   
    options['probe'] = {}
    options['probe']['site1']         = parser.get("probe","site1")
    options['probe']['site2']         = parser.get("probe","site2")
    options['probe']['site3']         = parser.get("probe","site3")
    options['probe']['interval']      = parser.getint("probe","interval")
    options['probe']['attempts']      = parser.getint("probe","attempts")
    options['probe']['log_level']     = parser.get("probe","log_level")

    options['scheduler'] = {}
    options['scheduler']['intervals']     = parser.get("scheduler","intervals")
    options['scheduler']['log_level']     = parser.get("scheduler","log_level")
   
    options['mqtt'] = {}
    options['mqtt']['id']             = parser.get("mqtt","id")
    options['mqtt']['channel']        = parser.get("mqtt","channel")
    options['mqtt']['log_level']      = parser.get("mqtt","log_level")
    options['mqtt']['broker']         = parser.get("mqtt","broker")
    options['mqtt']['username']       = parser.get("mqtt","username")
    options['mqtt']['password']       = parser.get("mqtt","password")
    options['mqtt']['keepalive']      = parser.getint("mqtt","keepalive")
    options['mqtt']['timeout']        = parser.getint("mqtt","timeout")
    options['mqtt']['bandwidth']      = parser.getint("mqtt","bandwidth")
  
    options['web'] = {}
    options['web']['server']        = parser.get("web","server")
    options['web']['access']        = parser.get("web","access")
    options['web']['passwd']        = parser.get("web","passwd")
    options['web']['plain']         = parser.getboolean("web","plain")
    options['web']['log_level']     = parser.get("web","log_level")
   
    return options


__all__ = ["VERSION_STRING", "loadCfgFile", "cmdline"]
