
# EMA

Windows/Linux service and command line tool for [Cristobal Garcia's EMA Weather Station](http://www.observatorioremoto.com/emav2/meteoen.htm)

This is a new version using [Python Twisted Asynchronous I/O framweork](https://twistedmatrix.com/)

## Description


**ema** is a software package that talks to the EMA Weather Station through a serial port or TCP port. Since EMA hardware is rather smart, the server has really very little processing to do, so it can run happily on a Raspberry Pi. 

Main features:

1. Publishes current and historic data to an MQTT broker.

2. If voltage threshold is reached it triggers a custom alarm script. Supplied script sends an SMS using the gammu-python package

3. If the roof relay changes state (from open to close and viceversa), it triggers a custom script.

4. Maintains EMA RTC in sync with the host computer RTC.

5. Manages active/inactive auxiliar relay time windows. Shuts down
host computer if needed. A Respberry Pi with **internal RTC is strongly recommended**.


## Instalation

### Linux

  `sudo pip install ema`

  or from GitHub:

    git clone https://github.com/astrorafael/ema.git
    cd ema
    sudo python setup.py install


All executables and custom scripts are copied to `/usr/local/bin`

Type `ema -k` to start the service on foreground with console output

An available startup service script for debian-based systems is provided. 
Type `sudo service ema start` to start it
Type `sudo update-rc.d emad defaults` to install it at boot time

### Windows

The Windows python 2.7 distro comes with the pip utility included. 

1. Open a `CMD.exe` console, **with Administrator privileges for Windows 7 and higher**
2. Inside this console type:

`pip install twisted`

Twisted will install (15.5.0 at this moment)

You can test that this installation went fine by opening a python command line (IDLE or Python CMD)
and type:

    ```
    >>> import twisted
    >>> print twisted.__version__
    15.5.0
    >>> _
    ```

3. Inside this new created folder type:

 `pip install ema`

* The executables (.bat files) are located in the same folder `C:\ema`
* The log file is located at `C:\ema\log\ema.log`
* The following required PIP packages will be automatically installed:
    - twisted,
    - twisted-mqtt

    
### Start up and Verification

In the same CMD console, type`.\ema.bat`to start it in forground and verify that it starts without errors or exceptions.

Go to the Services Utility and start the TESSDB database service.

### EMA Server Configuation ###

By default, file `/etc/ema.d/config` provides the configuration options needed.
This file is self explanatory. 

On Windows, configuration is located at `C:\ema\config`. 

In both cases, you need to create a new `config` or `config.ini` file from the examples.

Some parameters are defined as *reloadable*. Type `sudo service ema reload` for the new configuration to apply without stopping the service.

### Logging ###

Log file is placed under `/var/log/ema.log` (Linux) or `C:\ema\log\ema.log` (Windows). 
Default log level is `info`. It generates very litte logging at this level.
On Linux, the log is rotated through the /etc/logrotate.d/ema policy. On Windows, there is no such policy.



