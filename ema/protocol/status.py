# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#
# Constants belinging the EMA Protocol v2, for portability issues
# EMA protocol is sometimes revised
#
VERSION = 2

# EMA send status messages every 5 seconds
PERIOD = 5

STATLEN = 83            # Status message length including ( and ) 

# OFFSETS IN GEHERAL STATUS MESSAGE
# 'end' constants are 1 character past the given field , 
# to directly use in string slicing with [:]

SRRB = 1          # Status Roof Relay Begin
SRRE = SRRB + 1      # Status Roof Relay End

SARB = 2             # Status Aux Relay Begin
SARE = SARB + 1      # Status Aux Relay End

SPSB = 3             # Status Power Supply Begin
SPSE = SPSB + 1      # Status Power Supply End

SRAB = 5       # Status Rain Detector Begin
SRAE = SRAB + 3      # Status Rain Detector End

SCLB = 9       # Status Cloud sensor Begin
SCLE = SCLB + 3      # Status Cloud Sensor Emd

SCBB = 13         # Status Calibrated Barometric pressure Begin
SCBE = SCBB + 5      # Status Calibrated Barometric oressure End

SABB = 19         # Status Absolute Barometric pressure Begin
SABE = SABB + 5      # Status Absolute Barometric pressuer End

SPCB = 25         # Status Pluviometer Current value Begin
SPCE = SPCB +  4  # Status Pluviometer Current value End

SPAB = 30         # Status Pluviometer Accumulated value Begin
SPAE = SPAB + 4      # Status Pluviometer Accumulated value End

SPYB = 35         # Status Pyrometer Begin
SPYE = SPYB + 3   # Status Pyrometer End

SPHB = 39         # Status Photometer Begin
SPHE = SPHB + 5      # Status Photometer End

SATB = 45         # Status Ambient Temperature Begin
SATE = SATB + 4   # Status Ambient Temperature End

SRHB = 50         # Status Relative Humidity Begin
SRHE = SRHB + 3   # Status Relative Humidity End

SDPB = 54         # Status Dew Point Begin
SDPE = SDPB + 4   # Status Dew Point End

SAAB = 64         # Status Anemometer Accumlated value Begin
SAAE = SAAB + 3   # Status Anemometer Accumulated value End

SACB = 68         # Status Anemometer Current wind Begin
SACE = SACB + 4   # Status Anemometer Curent wind End

SWDB = 73         # Status Wind Direction Begin
SWDE = SWDB + 3   # Status Wind direction End

SMTB = 77         # Status Message Type Begin
SMTE = SMTB + 1   # Status Message Type End

SMFB = 78         # Status Message Flash Page Begin
SMFE = SMFB + 4   # Status Message Flash Page End 

# Status Message Types
MTCUR = 'a'       # Current values status message type
MTHIS = 't'       # 24h historic values message type
MTISO = '0'       # 24h isolated historic values message type
MTMIN = 'm'       # daily minima message type
MTMAX = 'M'       # daily maxima message type

STATUS_TYPE = {
  'a' : 'current',
  't' : 'historic',
  'm' : 'minima',
  'M' : 'maxima',
  '0' : 'isolated' 
}

# Independen Thermpile message
THERMOINF = 4     # Thermopile digit string offset ('0' = infrared ; '1' = ambient)

# Offset to magnitude visual digits (18:35:43 mv:24.00)
MVI = 13 # Integer part
MVD = 16 # decimal part

# Timestamp format, the EMA way
EMA_STRFTIME = "(%H:%M:%S %d/%m/%Y)"

import math

def encodeFreq(hertz):
    '''Encode frequency in Hertz into EMA format field'''
    hertz *= 1000               # to milihertz
    exp = 0
    while hertz > 9999:
        hertz /= 10
        exp += 1
    return "%d%04d" % (exp, hertz)
        
def decodeFreq(enc):
    '''
    Decode a EMMMM frequency EMA format fragment. 
    Returns frequency in Hertz
    '''
    exp  = int(enc[0])-3
    mant = int(enc[1:5])
    return round(mant*math.pow(10, exp), 3)
        
# --------------------------------------------------------------------
# Visual magnitude computed by the following C function
# --------------------------------------------------------------------
# float HzToMag(float HzTSL ) 
# {
#  float mv;
#     mv = HzTSL/230.0;             // Iradiancia en (uW/cm2)/10
#     if (mv>0){
#        mv = mv * 0.000001;       //irradiancia en W/cm2
#        mv = -1*(log10(mv)/log10(2.5));    //log en base 2.5
#        if (mv < 0) mv = 24;
#     }
#     else mv = 24;
#
#     return mv;
#}
# --------------------------------------------------------------------


K_INV_LOG10_2_5 = 1.0/math.log10(2.5)
K_INV_230      = (1.0/230)

# When everithing goes wrong
MAG_CLIP_VALUE = 24

def magnitude(frequency):
   '''Extract and Transform into Visual maginitued per arcsec 2'''
   mv = frequency * K_INV_230 * 1.0e-6
   if mv > 0.0:
      mv = -1.0 * math.log10(mv) * K_INV_LOG10_2_5
      mv = MAG_CLIP_VALUE if mv < 0.0 else mv
   else:
      mv = MAG_CLIP_VALUE
   return round(mv,1)


# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------


#TSTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

def decodeAsDict(line):
  '''Decode an EMA status line'''
  #status = { 'rev': VERSION, 'tstamp': timestamp.strftime(TSTAMP_FORMAT) }
  status            = {}
  status['roof']    = 'Closed' if line[SRRB] == 'C' else 'Open'
  status['aux']     = 'Open'   if line[SARB] == 'E' or line[SARB] == 'e' else 'Closed'
  status['volt']    = round(ord(line[SPSB])       * 0.10, 1) # Volts
  status['rain']    = round(int(line[SRAB:SRAE])  * 0.10, 1) # %
  status['cloud']   = round(int(line[SCLB:SCLE])  * 0.10, 1) # %
  status['abspres'] = round(int(line[SABB:SABE])  * 0.10, 1) # HPa
  status['calpres'] = round(int(line[SCBB:SCBE])  * 0.10, 1) # HPa
  status['pluv']    = round(int(line[SPCB:SPCE])  * 0.10, 1) # mm
  status['accpluv'] = int(line[SPAB:SPAE])        # mm
  status['pyro']    = round(int(line[SPYB:SPYE])  * 0.10, 1) # %
  status['phot']    = decodeFreq(line[SPHB:SPHE]) # Hz
  status['temp']    = round(int(line[SATB:SATE]) * 0.10, 1) # deg C
  status['hum']     = round(int(line[SRHB:SRHE]) * 0.10, 1) # %
  status['dew']     = round(int(line[SDPB:SDPE]) * 0.10, 1) # deg C
  status['anem']    = round(int(line[SACB:SACE]) * 0.10, 1) # Km/h
  status['aveanem'] = int(line[SAAB:SAAE])        # Km/h
  status['wind']    = int(line[SWDB:SWDE])        # degrees
  #status['type']    = STATUS_TYPE[line[SMTB:SMTE]] # status type
  status['page']    = int(line[SMFB:SMFE])  # page number
  return status

def decodeAsList(line):
  '''Decode an EMA status line'''
  #status = { 'rev': VERSION, 'tstamp': timestamp.strftime(TSTAMP_FORMAT) }
  status            = []
  status.append('Closed' if line[SRRB] == 'C' else 'Open')  # Roof
  status.append('Open' if line[SARB] == 'E' or line[SARB] == 'e' else 'Closed') # Aux Relay
  status.append(round(ord(line[SPSB])       * 0.10, 1))      # Volts
  status.append(round(int(line[SRAB:SRAE])  * 0.10, 1))      # Rain %
  status.append(round(int(line[SCLB:SCLE])  * 0.10, 1))      # Cloud %
  status.append(round(int(line[SABB:SABE])  * 0.10, 1))      # Abs Press HPa
  status.append(round(int(line[SCBB:SCBE])  * 0.10, 1))      # Calib HPa
  status.append(round(int(line[SPCB:SPCE])  * 0.10, 1))      # Current pluviom mm
  status.append(int(line[SPAB:SPAE]))             # Accumulated pluviom mm
  status.append(round(int(line[SPYB:SPYE])  * 0.10, 1))      # Pyranomenter %
  status.append(decodeFreq(line[SPHB:SPHE]))      # Photometer Hz
  status.append(round(int(line[SATB:SATE]) * 0.10, 1))      # Ambient Temp deg C
  status.append(round(int(line[SRHB:SRHE]) * 0.10, 1))      # Humidity %
  status.append(round(int(line[SDPB:SDPE]) * 0.10, 1))      # Dew Point deg C
  status.append(round(int(line[SACB:SACE]) * 0.10, 1))      # Wind Speed Km/h
  status.append(int(line[SAAB:SAAE]))             # Wind Speedn 10 min Km/h
  status.append(int(line[SWDB:SWDE]))             # Wind direction, degrees
  #status['type']    = STATUS_TYPE[line[SMTB:SMTE]] # status type
  status.append(int(line[SMFB:SMFE]))             # Flash page number
  return status

__all__ = [PERIOD, VERSION, decodeAsDict, decodeAsList]