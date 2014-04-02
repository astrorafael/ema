EMA
===

Linux service and command ine tool for [Cristobal Garcia's EMA Weather Station](http://www.observatorioremoto.com/emav2/meteoen.htm)

Description
-----------

**ema** is a software package that talks to the [EMA Weather Station] through a serial port. 
Since EMA hardware is rather smart, the server has really very little processing to do, so
it can run happily on a Raspberry Pi. 

Its main activities are:
1. Maintaining a vector of measurements for the different sensors

2. If voltage threshold is reached it triggers a custom alarm script. Supplied script sends an SMS using the gammu-python package

3. If the roof relay changes state (from open to close and viceversa), it triggers a custom script.

4. Periodically generates a simpe HTML page with the current values, threshold values and callibration constants. This page can be set under 
the document root of a given webserver.

5. Maintains periodic sync with the host computer RTC.

6. Receives commands from the *ema* command line tool to manually open or close relays or extending aux relay the Timed mode.

See `/etc/ema/config` for configuration details

Most of the files containg desing notes t explain underlying intent.
Enjoy !

EMA command line utility
------------------------
**ema** is a command line utility that ends commands to the emad service. 

Commands implemented so far are:
* roof relay force open
* roof relay force close
* aux relay status
* aux relay force open
* aux relay force close
* aux relay, set switch off time to a given HH:MM
* auxrelay, extends switch time by N minutes

Type `ema -h` or `ema --help` to see actual command line options.

Instalation
-----------
Simply type:

  `sudo ./setup.sh`

All executables and custom scripts are copied to /usr/local/bin

Type `emad -k` to start the service on foreground with console output

An available startup service script for debian-based systems is provided. 
Type `sudo service emad start` to start it
Type `sudo update-rc.d emad defaults` to install it at boot time

Configuation
------------
By default, file `/etc/ema/config` provdes the configuration options needed

Logging
-------
Log file is placed under `/var/log/emad.log`. 
Default log level is INFO. It generates very litte logging at this level
File is rotated by a logrotate policy installed under `/etc/logrotate.d`
