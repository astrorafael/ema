EMA
===

Linux service and command line tool for [Cristobal Garcia's EMA Weather Station](http://www.observatorioremoto.com/emav2/meteoen.htm)

Description
-----------

**ema** is a software package that talks to the EMA Weather Station through a serial port. 
Since EMA hardware is rather smart, the server has really very little processing to do, so
it can run happily on a Raspberry Pi. 

Server main activities are:

1. Maintaining a vector of measurements for the different sensors

2. If voltage threshold is reached it triggers a custom alarm script. Supplied script sends an SMS using the gammu-python package

3. If the roof relay changes state (from open to close and viceversa), it triggers a custom script.

4. Periodically generates a simpe HTML page with the current values, threshold values and callibration constants. This page can be set under 
the document root of a given webserver.

5. Maintains periodic sync with the host computer RTC.

6. Generates an HTML page with current, averages measurements to be used
with a local web server

7. Publishes current, averages and historic data to an MQTT broker

8. Manages active/inactive auxiliar relay time windows. Shuts down
host computer if needed.

9. Receives commands from the *ema* command line tool to manually open or close relays or extending aux relay the Timed mode.

Most of the files contain desing notes explaining its intent.
Enjoy !

Instalation
-----------

  `sudo pip install ema`

All executables and custom scripts are copied to /usr/local/bin

Type `ema` to start the service on foreground with console output

An available startup service script for debian-based systems is provided. 
Type `sudo service ema start` to start it
Type `sudo update-rc.d emad defaults` to install it at boot time

### EMA Server Configuation ###

By default, file `/etc/ema/config` provdes the configuration options needed.
This file is self explanatory.

### Logging ###

Log file is placed under `/var/log/ema.log`. 
Default log level is INFO. It generates very litte logging at this level

### EMA command line utility ###

**emacli** is a command line utility that ends commands to the emad service. 
It only works in the same LAN, not through Internet.

Commands implemented so far are:
* roof relay force open
* roof relay force close
* aux relay status
* aux relay force open
* aux relay force close
* aux relay, set switch off time to a given HH:MM
* auxrelay, extends switch time by N minutes

Type `emacli -h` or `emacli --help` to see actual command line options.

