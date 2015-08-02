# -*- coding: iso-8859-15 -*-

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

# ========================== DESIGN NOTES ==============================
#
# This module  periodically generates a simple HTML page containing a 
# table with the latest samples received from EMA.
#
# One of the goals of EMA server is to publish its measurements to
# Internet. What to publish and how to publish depends on the server 
# being used. Meanwhile this question is solved, there should be a way
# to display live values and this is the purpose of this module.
# 
# The webserver I use (webiopi) doesn't allow CGIs or similar, 
# so I just simply decided to generate this page periodically, 
# not on demand (at user request). I think this also matches the 
# ovrall idea of the EMA server and is plain easy to implement.
#
# On the Raspberry Pi, this file is generated on a RAM disk to avoid
# frequent Flash writes.
#
# I tried to use a lightweight template engine (Quik) to embed HTML 
# and logic in the same page, but its 'if' clause didn't work, don't
# know why. So I took the quick and dirty route and generated the page 
# from within the python code. It is not the best solution in terms of
# evolution, but it is fast and solves the problem for the time being.
#
# There is an issue when generating the page at startup. Not all 
# sample values are available at startup (depends on the page generation
#  rate) and this causes exceptions. These are caught, logged and
# silently ignored.
# ======================================================================

import logging
import os
import os.path
import datetime

from server import Lazy, Server

log = logging.getLogger('genpage')


HEADER = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
		<meta http-equiv="refresh" content="60">
	<title>Estacion Meteo-Astronomica EMA</title>

<style>
table,th,td { border:1px solid black; }
th,td { padding:10px; text-align:center; }
caption { padding:10px }
tr.device td { padding:1px }
</style>

</head>
<body>

<div align="center">
<table>
'''

FOOTER='''
<address>Generado el %s</address>
</body>
</html>
'''

TABLE_HEADER='''
<div align="center">
<table>
  <caption>%s</caption>
  <th>Medida</th>
  <th>Valor</th>
  <th>Umbral</th>
'''

TABLE_FOOTER='''
</table>
</div>
<p></p>
'''

TABLE_ROW='''
  <tr>
    <td>%s</td>
    <td>%s %s</td>
    <td>%s %s</td>
  </tr>
'''

TABLE_COLSPAN='''
  <tr class='device' >
    <td colspan='%d' padding='0'><emphasis>%s</emphasis></td>
  </tr>
'''

DEVICE = {
	'RoofRelay' : 'Relé de techo',
	'Voltmeter' : 'Voltímetro',
	'Photometer' : 'Fotómetro' ,
	'Barometer' : 'Barómetro' ,
	'RainSensor' : 'Sensor de lluvia' ,
	'CloudSensor' : 'Sensor de nubes' ,
	'Pyranometer' : 'Medidor de radiación solar' ,
	'Thermometer' : 'Termómetro' ,
	'Anemometer' : 'Anemómetro' ,
	'Pluviometer' : 'Pluviómetro' ,
	'Thermopile' : 'Termopila' ,
	'WatchDog' : 'Perro Guardian',
	'AuxRelay' : 'Relé Auxiliar',
	'Timer' : 'Temporizador Diario',
}

MEASUREMENT = {
	'open' : '¿ Rele Abierto ?' ,
	'voltage' : 'Voltaje de Batería' ,
	'magnitude' : 'Magnitud de fondo de cielo' ,
	'pressure' : 'Presion Atmosférica' ,
	'rain' : 'Lluvia detectada' ,
	'cloud':  'Nivel de nubes' ,
	'irradiation': 'Nivel de radiacion solar',
	'humidity' : 'Humedad',
	'dewpoint' : 'Punto de rocío' ,
	'ambient' : 'Temperatura Ambiente' ,
	'speed' : 'Velocidad del viento' ,
	'speed10' : 'Velocidad promedio en 10 min.' ,
	'direction' :'Dirección del viento' ,
	'current' : 'Lluvia medida actual' ,
	'accumulated' : 'Lluvia acumulada' ,
	'sky' : 'Temperatura del cielo' ,
	'ambient' : 'Temperatura ambiente' ,
	'interval'  : 'Ventana de tiempo',
}

PARAMETER = {
	'Aux Relay mode' : 'Modo de operacion el rele auxiliar',
	'Aux Relay Switch on Time' : 'Hora de enciendido del rele auxiliar',
	'Aux Relay Switch off Time': 'Hora de apagado del rele auxiliar',
	'Watchdog Period': 'Periodo de sondeo a la EMA',
	'Voltmeter Offset': 'Offset del voltimetro de la EMA',
	'Photometer Offset' : 'Offset del Fotometro',
	'Barometer Offset': 'Offset del Barómetro',
	'Barometer Height': 'Barometro: Altura sobe el Nivel del mar',
	'Cloud Sensor Gain' : 'Ganancia del Sensor de Nubes',
	'Pyranometer Offset' : 'Offset del Piranómetro',
	'Pyranometer Gain' : 'Ganancia del Piranómetro' ,
	'Anemometer Calibration Constant': 'Constante de calibración del anemómetro',
	'Pluviometer Calibration constant': 'Constante de calibracion del Pluviometro',
	'Timer Active Intervals' : 'Intervalos activos del temporizador',
} 



class HTML(Lazy):
	TEMPNAME = '.ema.html'

	def __init__(self, ema, parser):
                lvl      = parser.get("HTML", "html_log")
		log.setLevel(lvl)
		path     = parser.get("HTML", "html_file")
                period   = parser.getfloat("HTML", "html_period")
                N        =  int(round(period / Server.TIMEOUT) )
		Lazy.__init__(self, N)
		self.path     = path
		self.dirname  = os.path.dirname(path)
		self.ema  = ema
		ema.addLazy(self)
		

	def generate(self):
		'''Generates an HTML page on to prediefined path'''
		tempfile = os.path.join(self.dirname, HTML.TEMPNAME) 
		with open(tempfile, 'w') as page:
			self.globalHeader(page)
			self.instantTable(page)
			self.parameterTable(page)
			self.averagesTable(page)
			t = datetime.datetime.now().replace(microsecond=0).isoformat(' ')
			self.globalFooter(page, t)
		# os.rename is atomic in Linux, not in Windows
		os.rename(tempfile, self.path)
		#log.debug("Generated HTML page")

	# --------------------------
	# HTML page generation parts
	# --------------------------

	

	def instantTable(self, page):
		self.tableHeader(page, 'Valores actuales')
		self.tableRowsCurrent(page)
		self.tableFooter(page)


	def averagesTable(self, page):
		self.tableHeader(page, 'Valores promedio')
		self.tableRowsAverage(page)
		self.tableFooter(page)


	def globalHeader(self, page):
		page.write(HEADER)


	def globalFooter(self, page, timestamp):
		page.write(FOOTER % timestamp)


	def tableHeader(self, page, caption):
		page.write(TABLE_HEADER % caption)


	def tableFooter(self,page):
		page.write(TABLE_FOOTER)


	def tableRow(self, page, name, value, units, thres=None, unitthres=None):
		page.write(TABLE_ROW % (MEASUREMENT[name], value, units, thres, unitthres) )


	def tableDevice(self, page, device):
		page.write(TABLE_COLSPAN % (3, DEVICE[device.name]))


	def tableRowsCurrent(self, page):
		for device in self.ema.currentList:
			if not ('html','current') in device.publishable:
				log.debug("(current) skipping publihing Device = %s", device.name)
				continue
			self.tableDevice(page, device)
			try:
				for key,value in device.current.iteritems():
					val = value[0] ; unit=value[1]  
					th, uth = device.threshold.get(key,('',''))
					self.tableRow(page, key, val, unit, th, uth)
			except IndexError as e:
					log.warning("(current) Too early for HTML page generation, got %s", e)
			

	def tableRowsAverage(self, page):
		for device in self.ema.averageList:
			if not ('html','average') in device.publishable:
                                log.debug("(average) skipping publihing Device = %s", device.name)
                                continue
			self.tableDevice(page, device)
			try:
				for key,value in device.average.iteritems():
					val = value[0] ; unit=value[1]
					th, uth = device.threshold.get(key,('',''))
					self.tableRow(page, key, val, unit, th, uth)
			except (IndexError, ZeroDivisionError) as e:
				log.warning("(average) Too early for HTML page generation, got %s", e)
					
	def parameterTable(self, page):
		self.tableHeader(page, 'Parametros de ajuste')
		self.tableRowsParameter(page)
		self.tableFooter(page)


	def tableRowsParameter(self, page):
		for device in self.ema.parameterList:
			self.tableDevice(page, device)
			try:
				for par in device.parameter:
					value, unit = device.parameter[par]
					self.tableRowParameter(page, par, value, unit)
			except IndexError as e:
					log.warning("(parameters) Too early for HTML page generation, got %s", e)
			except KeyError as e:
					log.debug("(parameters) Ignoring missing parameter for %s",e)

	def tableRowParameter(self, page, name, value, units):
		page.write(TABLE_ROW % (PARAMETER[name], value, units, '', '') )



	# -------------------------------
	# Implemanting the Lazy interface
	# -------------------------------

	def work(self):
		'''Periodically triggers an HTML page generation'''
		if not self.ema.isSyncDone():
			log.debug("Not ready yet to generate HTML")
			return
		self.generate()

if __name__ == '__main__':
	HTML().generate()
