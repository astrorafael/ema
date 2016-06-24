# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#--------------------
# System wide imports
# -------------------

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

    options['serial'] = {}
    options['serial']['endpoint']   = parser.get("serial","endpoint")
    options['serial']['log_level']  = parser.get("serial","log_level")
    options['serial']['log_messages']  = parser.getboolean("serial","log_messages")

    options['serial']['voltmeter'] = {}
    options['serial']['voltmeter']['sync']            = parser.getboolean("voltmeter","sync")
    options['serial']['voltmeter']['offset']          = parser.getfloat("voltmeter","offset")
    options['serial']['voltmeter']['threshold']       = parser.getfloat("voltmeter","threshold")
    options['serial']['voltmeter']['delta']           = parser.getfloat("voltmeter","delta")
    options['serial']['voltmeter']['low_volt_script'] = parser.get("voltmeter","low_volt_script")
    options['serial']['voltmeter']['low_volt_mode']   = parser.get("voltmeter","low_volt_mode")

    options['serial']['anemometer'] = {}
    options['serial']['anemometer']['sync']            = parser.getboolean("anemometer","sync")
    options['serial']['anemometer']['calibration']     = parser.getint("anemometer","calibration")
    options['serial']['anemometer']['model']           = parser.get("anemometer","model")
    options['serial']['anemometer']['threshold']       = parser.getint("anemometer","threshold")
    options['serial']['anemometer']['ave_threshold']   = parser.getint("anemometer","ave_threshold")
   
    options['serial']['barometer'] = {}
    options['serial']['barometer']['sync']            = parser.getboolean("barometer","sync")
    options['serial']['barometer']['height']          = parser.getint("barometer","height")
    options['serial']['barometer']['offset']          = parser.getint("barometer","offset")
    
   
   

    options['mqtt'] = {}
    options['mqtt']['channel']        = parser.get("mqtt","channel")
    options['mqtt']['log_level']      = parser.get("mqtt","log_level")
    options['mqtt']['broker']         = parser.get("mqtt","broker")
    options['mqtt']['username']       = parser.get("mqtt","username")
    options['mqtt']['password']       = parser.get("mqtt","password")
    options['mqtt']['keepalive']      = parser.getint("mqtt","keepalive")

   


    return options


__all__ = [VERSION_STRING, loadCfgFile, cmdline]
