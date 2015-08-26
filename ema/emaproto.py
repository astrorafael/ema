# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ----------------------------------------------------------------------


#
# Constants belinging the EMA Protocol v2, for portability issues
# EMA protocol is sometimes revised
#

# EMA send status messages every 5 seconds
PERIOD = 5

STATLEN = 83				# Status message length including ( and ) 
STATLENEXT = STATLEN + 11	# Extended status message with final tumestamp

# OFFSETS IN GEHERAL STATUS MESSAGE
# 'end' constants are 1 character past the given field , 
# to directly use in string slicing with [:]

SRRB = 1         	# Status Roof Relay Begin
SRRE = SRRB + 1   	# Status Roof Relay End

SARB = 2          	# Status Aux Relay Begin
SARE = SARB + 1   	# Status Aux Relay End

SPSB = 3          	# Status Power Supply Begin
SPSE = SPSB + 1   	# Status Power Supply End

SRAB = 5			# Status Rain Detector Begin
SRAE = SRAB + 3		# Status Rain Detector End

SCLB = 9			# Status Cloud sensor Begin
SCLE = SCLB + 3		# Status Cloud Sensor Emd

SCBB = 13			# Status Calibrated Barometric pressure Begin
SCBE = SCBB + 5		# Status Calibrated Barometric oressure End

SABB = 19			# Status Absolute Barometric pressure Begin
SABE = SABB + 5		# Status Absolute Barometric pressuer End

SPCB = 25 			# Status Pluviometer Current value Begin
SPCE = SPCB +  4	# Status Pluviometer Current value End

SPAB = 30			# Status Pluviometer Accumulated value Begin
SPAE = SPAB + 4		# Status Pluviometer Accumulated value End

SPYB = 35			# Status Pyrometer Begin
SPYE = SPYB + 3 	# Status Pyrometer End

SPHB = 39			# Status Photometer Begin
SPHE = SPHB + 5		# Status Photometer End

SATB = 45			# Status Ambient Temperature Begin
SATE = SATB + 4 	# Status Ambient Temperature End

SRHB = 50			# Status Relative Humidity Begin
SRHE = SRHB + 3 	# Status Relative Humidity End

SDPB = 54			# Status Dew Point Begin
SDPE = SDPB + 4 	# Status Dew Point End

SAAB = 64			# Status Anemometer Accumlated value Begin
SAAE = SAAB + 3 	# Status Anemometer Accumulated value End

SACB = 68			# Status Anemometer Current wind Begin
SACE = SACB + 4 	# Status Anemometer Curent wind End

SWDB = 73			# Status Wind Direction Begin
SWDE = SWDB + 3 	# Status Wind direction End

SMTB = 77 			# Status Message Type Begin
SMTE = SMTB + 1     # Status Message Type End

# Status Message Types
MTCUR = 'a'			# Current values status message type
MTHIS = 't'			# 24h historic values message type
MTISO = '0'			# 24h isolated historic values message type
MTMIN = 'm'			# daily minima message type
MTMAX = 'M'			# daily maxima message type


# Independen Thermpile message
THERMOINF = 4 		# Thermopile digit string offset ('0' = infrared ; '1' = ambient)

# Offset to magnitude visual digits (18:35:43 mv:24.00)
MVI = 13	# Integer part
MVD = 16	# decimal part

