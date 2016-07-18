# EMA DOMAIN OBJECTS

## Virtual instruments

A Virtual instruments collects one or more measurement magnitudes (or values) and additional calibration or threshold parameters. Values updated automatically via a status message notification from EMA. In this case, the get operation is done by caching, not by issuing a 'get command' to EMA.

* Virtual Instruments list:
    - Anemometer:
        + Value: wind speed
            * Type: float
            * Range: [0, 999]
            * Units: Km/h
            * Accesors: get/notify
        + Value: wind orientation
            * Type: int
            * Range: [0, 359]
            * Units: arc degrees
            * Accesors: get/notify
        + Value: average wind speed over 10 minutes
            * Type: int
            * Range: [0, 999]
            * Units: Km/h
             Accesors: get/notify
        + Parameter: wind speed threshold
            * Type: int
            * Range: [0, 999]
            * Units: Km/h
            * Accesors: get/set 
        + Parameter: average wind speed threshold
            * Type: int
            * Range: [0, 999]
            * Units: Km/h
            * Accesors: get/set
        + Parameter: anemometer calibration constant
            * Type: int
            * Range: [0, 999]
            * Units: ?
            * Accesors: get/set
        + Parameter: anemometer model
            * Type: str
            * Range: [0, 999]
            * Units: ['TX20', 'Simple']
            * Accesors: get/set
    - Barometer:
        + Value: absolute pressure
            * Type: float
            * Range: [0, ?]
            * Units: HPa
            * Accesors: get/notify
        + Value: calibrated pressure
            * Type: float
            * Range: [0, ?]
            * Units: HPa
            * Accesors: get/notify
        + Parameter: height
            * Type: int
            * Range: [0, 99999]
            * Units: meters
            * Accesors: get/set
        + Parameter: offset
            * Type: int
            * Range: [-99, 99]
            * Units: mBar
            * Accesors: get/set
    - Cloud Sensor:
        + Parameter: threshold
            * Type: int
            * Range: [0, 999]
            * Units: % (review this and the range)
            * Accesors: get/set
        + Parameter: gain
            * Type: float
            * Range: [0.0, 99.9]
            * Units: ?
            * Accesors: get/set
        + Value: cloud level
            * Type: float
            * Range: [0, 100.0]
            * Units: %
            * Accesors: get/notify
    - Photometer:
        + Parameter: threshold
            * Type: float
            * Range: [0, 99.9]
            * Units: % (review this and the range)
            * Accesors: get/set
        + Parameter: offset
            * Type: float
            * Range: [-99.9, +99.9]
            * Units: mag/arcsec^2
            * Accesors: get/set
        + Value: raw magnitude
            * Type: float
            * Range: [0, 99999] ? (check range)
            * Units: Hz            
            * Accesors: get/notify
        + Value: magnitude
            * Type: float
            * Range: [0, 24.0]
            * Units: mag/arcsec^2            
            * Accesors: get/notify
    - Pluviometer:
        + Parameter: calibration
            * Type: int
            * Range: [0, 999]
            * Units: mm
            * Accesors: get/set
        + Value: level
            * Type: float
            * Range: ?
            * Units: mm            
            * Accesors: get/notify
        + Value: accumulated level since ????
            * Type: int
            * Range: ?
            * Units: mm            
            * Accesors: get/notify
    - Pyranometer:
        + Parameter: gain
            * Type: float
            * Range: [0, 99.9]
            * Units: ?
            * Accesors: get/set
        + Parameter: offset
            * Type: int
            * Range: [0, 999]
            * Units: ?
            * Accesors: get/set
        + Value: irradiation
            * Type: float
            * Range: ???
            * Units:  %            
            * Accesors: get/notify
    - Rain Sensor:
        + Parameter: threshold
            * Type: int
            * Range: [0, 999]
            * Units: mm (?)
            * Accesors: get/set
        + Value: probability
            * Type: float
            * Range: [0, 100.0] 100 = totally wet
            * Units:  %            
            * Accesors: get/notify
    - Thermometer:
        + Parameter: delta temperature threshold
            * Type: int
            * Range: [0, 999]
            * Units: ºC
            * Accesors: get/set
        + Value: ambient temperature
            * Type: float
            * Range: [-99.9, +99.9]
            * Units: ºC            
            * Accesors: get/notify
        + Value: humidity
            * Type: float
            * Range: [0, 100.0]
            * Units: %            
            * Accesors: get/notify
        + Value: dew point
            * Type: float
            * Range: [-99.9, +99.9]
            * Units: ºC            
            * Accesors: get/notify
    - Voltmeter:
        + Parameter: threshold
            * Type: float
            * Range: [0.0, 25.5]
            * Units: V
            * Accesors: get/set
        + Parameter: offset
            * Type: float
            * Range: [-99.9, +99.9]
            * Units: V
            * Accesors: get/set
        + Value: voltage
            * Type: float
            * Range: [0, 25.5]
            * Units: V            
            * Accesors: get/notify

## Actuators
EMA has two actuators:
- The roof relay that closes the observatory room depending on one of or more thresholds being reached:
    + voltage below the threshold ???
    + dew point above the threshold
    + wind gust above the threshold
- the auxiliar relay

* Actuators:
    - Roof Relay:
        + Parameter: mode (ESTO PUEDE SER EL VALOR DEL RELE!)
            * Type: str
            * Range: ['Closed', 'Open']
            * Units: n/a
            * Accesors: set (only!)
    - Auxiliar Relay:
        + Parameter: mode (ESTO PUEDE SER EL VALOR DEL RELE!)
            * Type: str
            * Range: ['Closed', 'Open']
            * Units: n/a
            * Accesors: set (only!)
* Other Devices:
    - RTC:
        + Value: time
            * Type: datetime.datetime
            * Range: [2016-01-01T00:00:00, 2100-12-31:23:59:59]
            * Units: YYYY-MM-HHTHH:MM:SS
            * Accesors: get/set
    - WatchDog:
        + Parameter: period
            * Type: int
            * Range: [0, 999]
            * Units: sec
            * Accesors: get/set
        + Value: echo
            * Type: str
            * Range [' ']
            * Units: n/a
            * Accesors: get