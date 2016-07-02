
# EMA

Windows/Linux service and command line tool for [Cristobal Garcia's EMA Weather Station](http://www.observatorioremoto.com/emav2/meteoen.htm)

This is a new version using [Python Twisted Asynchronous I/O framweork](https://twistedmatrix.com/)

| Table of Contents                                                          |
|:---------------------------------------------------------------------------|
| 1. [Description](README.md#Description)
| 1. [Installation](README.md#Installation)
|   1. [Linux](README.md#Linux)
|   1. [Windows](README.md#Windows)
|   1. [Startup and verification](README.md#Startup and verification)
| 1. [Configuration](README.md#Configuration)
| 1. [Publishing Data](README.md#Publishing Data)
|   1. [MQTT](README.md#MQTT)
| 1. [Scheduler](README.md#Scheduler)
| 1. [Scripts](README.md#Scripts)

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

**Warning** You need Debian package libffi-dev to install Pip 'service-identity' requirement

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

# DESIGN

## MQTT Topics

| Topic                | Description                                          |
|:--------------------:|:-----------------------------------------------------|
| EMA/register         | Where EMA weather stations declare themselves online |
| EMA/<channel>/events           | Log for important events, with levels      |
| EMA/<channel>/current/state    | EMA current measurements,every minute      |
| EMA/<channel>/historic/minmax  | Daily minima and maxima, every hour        |
| EMA/<channel>/historic/average | Daily average, every 5 minutes             |

<channel> is an intermedaite topic level that aggregates several EMAs into one.
In the extreme cases, <channel> could be the unique device name or a single constant string for all EMAs.

## MQTT Payloads

All payloads are in JSON format

### Published on EMA/register

| Field name              |  Type  | Description                             |
|:-----------------------:|:------:|:----------------------------------------|
| rev                     | int    | Payload format revision number          |
| who                     | string | EMA station emitting this record        |
| tstamp                  | string | timestamp "YYYY-MM-DDThh:mm:ss", UTC    |
| mac                     | string | MAC address "AA:BB:CC:DD:EE:FF"         |
| anemometer_model        | string | Either 'Simple' or 'TX20'               |
| anemometer_calibration  | int    | [Km/h] or [mm] depending on model       |
| barometer_height        | int    | Barometer height [m]                    |
| barometer_offset        | int    | Barometer offset [mBar]                 |
| cloudsensor_gain        | float  | Cloud sensor gain                       |
| photometer_offset       | float  | Photometer offset [mag/arcsec²]         |
| pyranometer_gain        | float  | Pyranometer gain                        |
| pyranometer_offset      | int    | Pyranometer offset                      |
| pluviometer_calibration | int    | Pluviometer calibration                 |
| voltmeter_offset        | float  | ADC Voltage offset [V]                  |
 

### Published on EMA/<channel>/events

All fields are mandatory

| Field name |  Type  | Description                                          |
|:----------:|:------:|:-----------------------------------------------------|
| rev        | int    | Payload format revision number                       |
| who        | string | EMA station emitting this record                     |
| tstamp     | string | timestamp "YYYY-MM-DDThh:mm:ss", UTC                 |
| type       | string | one of "critical", error", warning" or "info"        |
| msg        | string | Free style string. Recommended max size: 80 chars    |

***Example:**
```
{ "who": "ema1", "tstamp": "2016-06-05T23:45:03" "type": "info", "msg": "<a message>"} 
```

### Published on EMA/<channel>/current/state

All fields are mandatory

| Field name |  Type  | Description                                          |
|:----------:|:------:|:-----------------------------------------------------|
| rev        | int    | Payload format revision number                       |
| who        | string | EMA station emitting this record                     |
| tstamp     | string | timestamp "YYYY-MM-DDThh:mm:ss", UTC                 |
| current    | seq    | Current readings vector                              |

### Published on EMA/<channel>/historic/minmax

All fields are mandatory

| Field name |  Type  | Description                                          |
|:----------:|:------:|:-----------------------------------------------------|
| rev        | int    | Payload format revision number                       |
| who        | string | EMA station emitting this record                     |
| tstamp     | string | timestamp "YYYY-MM-DDThh:mm:ss", UTC                 |
| minmax     | seq    | Sequence of 24 tuples [timestamp, max vec, min vec ] |

### Published on EMA/<channel>/historic/average

All fields are mandatory

| Field name |  Type  | Description                                          |
|:----------:|:------:|:-----------------------------------------------------|
| rev        | int    | Payload format revision number                       |
| who        | string | EMA station emitting this record                     |
| tstamp     | string | timestamp "YYYY-MM-DDThh:mm:ss", UTC                 |
| averages   | seq    | Sequence of 288 tuples [timestamp, average vector]   |

### Readings vector

JSON sequence embedded in messages above, with all instrument readings.
This vector may contain current, maxima minima or averaged values depending
on the actual MQTT message being published.

| Index |  Type  | Units | Description                                  |
|:-----:|:------:|:-----:|:---------------------------------------------|
|  0    | string |  --   | Roof relay state 1 char code. See Note 1     |
|  1    | string |  --   | Auxiliar relay state 1 char code. See Note 2 |
|  2    | float  | Volts | Power supply voltage                         |
|  3    | float  |   %   | Rain detector prob (0% dry 100% totally wet) |
|  4    | float  |   %   | Cloud level. 100.0% = totally cloudy         |
|  5    | float  |  HPa  | Absolute Pressure                            |
|  6    | float  |  HPa  | Calibrated Pressure                          |
|  7    | float  |  mm   | Pluviometer level                            |
|  8    | int    |  mm   | Accumulated pluviomenter since ????          |
|  9    | float  |   %   | Pyranometer radiation level                  |
| 10    | float  |   Hz  | Photometer frequency                         |
| 11    | float  |   ºC  | Ambient temperature                          |
| 12    | float  |   %   | Humidity level                               |
| 13    | float  |   ºC  | Dew point                                    |
| 14    | float  | Km/h  | Wind speed                                   |
| 15    | int    | Km/h  | Average windn speed in 10 mins               |
| 16    | int    | deg   | Wind orientation (0...359)                   |

***Note 1: Roof relay codes:***
- 'C' : Switched Off
- 'A' : Switched On
- 'a' : Switched On with thresholds override

***Note 2: Auxiliar relay codes:***
- 'A' : Switched Off automatically (heaters off)
- 'E' : Switched On  automatically (heaters on)
- 'a' : Switched Off (Manual or by timer)
- 'e' : Switched On (Manual or by timer)
- '!' : Switched Off by humidity sensor read error.

