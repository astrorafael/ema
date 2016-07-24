# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division, absolute_import

import json
import hashlib
import datetime
import time

# ---------------
# Twisted imports
# ---------------

from zope.interface import implementer

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.task        import deferLater
from twisted.internet.defer       import DeferredList
from twisted.application.service  import Service
from twisted.internet.endpoints   import serverFromString
from twisted.web.server           import Site
from twisted.web.resource         import Resource, IResource
from twisted.cred.portal          import IRealm, Portal
from twisted.cred.checkers        import FilePasswordDB
from twisted.web.guard            import HTTPAuthSessionWrapper, BasicCredentialFactory

from klein import Klein

#--------------
# local imports
# -------------

import ema.device    as device
import ema.scheduler as scheduler
# only for debugging
import ema.command   as command

from .service.reloadable import Service
from .logger    import setLogLevel
from .serial    import EMATimeoutError

# ----------------
# Module constants
# ----------------

DEBUG_HTTP = 1

# ----------------
# Global functions
# -----------------

def encrypt(password):
    return hashlib.sha256(password).hexdigest()

def emahash(uname, password, storedpass):
    return encrypt(password)

def as_time(dct):
    '''
    Convert HH:MM JSON strings into datetime.time objects'''
    try:
        t = time.strptime(dct['value'], '%H:%M:%S')
    except ValueError:
        # This may raise an exception as well
        t = time.strptime(dct['value'], '%H:%M')   
        dct['value'] = datetime.time(t.tm_hour, t.tm_min)
        return dct
    else:
        dct['value'] = datetime.time(t.tm_hour, t.tm_min, t.tm_sec)
        return dct


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='web')

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

class HTTPException(Exception):
    def __str__(self):
        m = { 'message' : self.__doc__ }
        if self.args:
            m['error'] = self.args[0]
        return json.dumps(m)


class NotFound(HTTPException):
    '''Resource not found'''
    code = 404
    

class BadRequest(HTTPException):
    '''Could not parse request'''
    code = 400
    msg = 'Bad Request'
    

class UnsupportedMediaType(HTTPException):
    '''POST/PUT request occurred without a application/json content type'''
    code = 416
    msg = 'Unsupported Media Type'
    

class UnprocessableEntry(HTTPException):
    '''A request to modify a resource failed due to a validation error'''
    code = 422
    msg = 'Unprocessable Entry'
    
class InternalServerError(HTTPException):
    '''An internal server error occured'''
    code = 500
    msg = 'Internal Server Error'

class HTTPNotImplementedError(HTTPException):
    '''Not Implemented'''
    code = 501
    msg = 'The server currently dos not recognize this method'

class GatewayTimeoutError(HTTPException):
    '''The server did not receive a timely response from EMA'''
    code = 504
    msg = 'Gateway Timeout'
    

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

@implementer(IRealm)
class PublicHTMLRealm(object):
    '''
    Defines an ACL where all users get the same resource 
    (the Klein root resource)
    '''
    def __init__(self, resource):
        self.resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return IResource, self.resource, lambda: None
        raise NotImplementedError()

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

class DateTimeEncoder(json.JSONEncoder):
    '''Helper class to encode datetime objets in JSON'''
    def default(self, o):
        if  isinstance(o, datetime.datetime):
            return o.strftime("%Y-%m-%dT%H:%M:%S")
        elif  isinstance(o, datetime.time):
            return o.strftime("%H:%M:%S")
        elif  isinstance(o, scheduler.Interval):
            return str(o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

class WebService(Service):

    # Service name
    NAME = 'Web Service'

    # Klein Application
    app = Klein()

    def __init__(self, options):
        self.options  = options
        self._port = None
        setLogLevel(namespace='web', levelStr=self.options['log_level'])


    @inlineCallbacks
    def startService(self):
        log.info("starting {name}", name=self.name)
        Service.startService(self)
        endpoint = serverFromString(reactor, self.options['server'])
        func = None if self.options['plain'] else emahash
        portal = Portal(PublicHTMLRealm(self.app.resource()), 
            [ FilePasswordDB(self.options['passwd'], hash=func) ] )
        credentialFactory = BasicCredentialFactory("EMA")
        root = HTTPAuthSessionWrapper(portal, [credentialFactory])
        factory = Site(root, logPath=self.options['access'])
        self._port = yield endpoint.listen(factory)

    @inlineCallbacks
    def stopService(self):
        log.info("stopping {name}", name=self.name)
        yield self._port.stopListening()
        Service.stopService(self)

    #---------------------
    # Extended Service API
    # --------------------

    def reloadService(self, options):
        options = options['internet']
        setLogLevel(namespace='web', levelStr=options['log_level'])
        log.info("new log level is {lvl}", lvl=options['log_level'])
        self.options = options
    

    
    #---------------------
    # Exposed EMA REST API
    # --------------------

    @app.route('/ema/v1/scheduler/intervals', methods=['GET'])
    def get_scheduler_intervals(self, request):
        value = self.parent.schedulerService.windows.asList()
        log.info("{req.method} {req.uri} ok.", req=request)
        request.setResponseCode(200)
        request.setHeader('Content-Type', 'application/json')
        return json.dumps({'value': value}, cls=DateTimeEncoder)


    @app.route('/ema/v1/anemometer/current/windspeed/threshold', methods=['GET'])
    def get_current_windspeed_threshold(self, request):
        metadata = device.Anemometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.anemometer.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/anemometer/current/windspeed/threshold', methods=['PUT', 'POST'])
    def set_current_windspeed_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.anemometer.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.anemometer.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['GET'])
    def get_average_windspeed_threshold(self, request):
        metadata = device.Anemometer.AverageThreshold.getter.metadata
        # Initiate read
        d = self.parent.anemometer.ave_threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['PUT', 'POST'])
    def set_average_windspeed_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.anemometer.ave_threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.anemometer.ave_threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/cloudsensor/threshold', methods=['GET'])
    def get_cloudsensor_threshold(self, request):
        metadata = device.CloudSensor.Threshold.getter.metadata
        # Initiate read
        d = self.parent.cloudsensor.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/cloudsensor/threshold', methods=['PUT', 'POST'])
    def set_cloudsensor_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.cloudsensor.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.cloudsensor.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/photometer/threshold', methods=['GET'])
    def get_photometer_threshold(self, request):
        metadata = device.Photometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.photometer.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/photometer/threshold', methods=['PUT', 'POST'])
    def set_photometer_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.photometer.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.photometer.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/rainsensor/threshold', methods=['GET'])
    def get_rainsensor_threshold(self, request):
        metadata = device.RainSensor.Threshold.getter.metadata
        # Initiate read
        d = self.parent.rainsensor.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/rainsensor/threshold', methods=['PUT', 'POST'])
    def set_rainsensor_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.rainsensor.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.rainsensor.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d



    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['GET'])
    def get_deltatemp_threshold(self, request):
        metadata = device.Thermometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.themomenter.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['PUT', 'POST'])
    def set_deltatemp_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.thermometer.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.thermometer.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/voltmeter/threshold', methods=['GET'])
    def get_voltmeter_threshold(self, request):
        metadata = device.Voltmeter.Threshold.getter.metadata
        # Initiate read
        d = self.parent.voltmeter.threshold
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d



    @app.route('/ema/v1/voltmeter/threshold', methods=['PUT', 'POST'])
    def set_voltmeter_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.voltmeter.threshold = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.voltmeter.threshold
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    # ESTA ES ESPECIAL
    @app.route('/ema/v1/roof/relay/mode', methods=['GET'])
    def get_roof_relay_mode(self, request):
        raise HTTPNotImplemented('No Roof Relay Get command available from EMA protocol')


    @app.route('/ema/v1/roof/relay/mode', methods=['PUT', 'POST'])
    def set_roof_relay_mode(self, request):
        # json returns value as unicode in python 2.7, not str
        value    = str(self.validate(request)) 
        try:
            # Initiate write
            self.parent.roof_relay.mode = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.roof_relay.mode
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    @app.route('/ema/v1/aux/relay/mode', methods=['GET'])
    def get_aux_relay_mode(self, request):
        metadata = device.AuxiliarRelay.Mode.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.mode
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d

    #  Esta es peligrosa
    @app.route('/ema/v1/aux/relay/mode', methods=['PUT', 'POST'])
    def set_aux_relay_mode(self, request):
        # json returns value as unicode in python 2.7, not str
        value    = str(self.validate(request)) 
        try:
            # Initiate write
            self.parent.aux_relay.mode = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.mode
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['GET'])
    def get_aux_relay_switch_on_time(self, request):
        metadata = device.AuxiliarRelay.SwitchOnTime.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.switchOnTime
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_on_time(self, request):
        # json returns value as unicode in python 2.7, not str
        value    = str(self.validate(request))   
        try:
            # Initiate write
            self.parent.aux_relay.switchOnTime = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.switchOnTime
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['GET'])
    def get_aux_relay_switch_off_time(self, request):
        metadata = device.AuxiliarRelay.SwitchOffTime.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.switchOffTime
        d.addCallbacks(self.readOkCallback, self.errorCallback, 
                callbackArgs=(request,metadata), errbackArgs=(request,))
        return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_off_time(self, request):
        # json returns value as unicode in python 2.7, not str
        value    = str(self.validate(request))   
        try:
            # Initiate write
            self.parent.aux_relay.switchOffTime = value
        except (ValueError, TypeError) as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.switchOffTime
            d.addCallbacks(self.writeOkCallback, self.errorCallback, 
                callbackArgs=(request,), errbackArgs=(request,))
            return d

    # Esta es solo para depuracion, quitar despues
    @app.route('/ema/v1/historic/minmax', methods=['GET'])
    def get_minmax(self, request):
        def enqueue(value, request):
            self.parent.queue['minmax'].append(value)
            log.info("{req.method} {req.uri} ok.", req=request)
            request.setResponseCode(200)
            request.setHeader('Content-Type', 'application/json')
            result = {
                'value': "daily bulk dump being loaded through MQTT broker",
                'units': 'n/a',
                'range': 'n/a',
            }
            return json.dumps(result, cls=DateTimeEncoder)
        cmd = command.GetDailyMinMaxDump()
        d = self.parent.serialService.protocol.execute(cmd)
        d.addCallbacks(enqueue, self.errorCallback,
            callbackArgs=(request,), errbackArgs=(request,))
        return d


    # Esta es solo para depuracion, quitar despues
    @app.route('/ema/v1/historic/average', methods=['GET'])
    def get_averages(self, request):
        def enqueue(value, request):
            self.parent.queue['ave5min'].append(value)
            log.info("{req.method} {req.uri} ok.", req=request)
            request.setResponseCode(200)
            request.setHeader('Content-Type', 'application/json')
            result = {
                'value': "average 5min bulk dump being loaded through MQTT broker",
                'units': 'n/a',
                'range': 'n/a',
            }
            return json.dumps(result, cls=DateTimeEncoder)
        cmd = command.Get5MinAveragesDump()
        d = self.parent.serialService.protocol.execute(cmd)
        d.addCallbacks(enqueue, self.errorCallback,
            callbackArgs=(request,), errbackArgs=(request,))
        return d

    @app.handle_errors
    def handle_errors(self, request, failure):
        '''
        Default handler for all REST API errors
        '''
        if failure.type in [NotFound, BadRequest, UnsupportedMediaType, UnprocessableEntry, 
                            HTTPNotImplementedError, GatewayTimeoutError]:
            request.setResponseCode(failure.value.code, message=failure.value.msg)
            request.setHeader('Content-Type', 'application/json')
            return str(failure.value)
        else:
            request.setHeader('Content-Type', 'text/plain')
            request.setResponseCode(InternalServerError.code, message=InternalServerError.msg)
            # This is temporary, to aid debugging
            # we shoudl return the empty string
            if DEBUG_HTTP:
                import StringIO
                output = StringIO.StringIO() 
                failure.printTraceback(file=output)
                return output.getvalue()
            else:
                return ''

    # --------------
    # Helper methods
    # --------------

    def errorCallback(self, failure, request, *args):
        log.info("{req.method} {req.uri} error.", req=request)
        raise GatewayTimeoutError(str(failure.value))
       

    def writeOkCallback(self, value, request):
        log.info("{req.method} {req.uri} = {val} ok.", req=request, val=value)
        request.setResponseCode(200)
        request.setHeader('Content-Type', 'application/json')
        return json.dumps({'value': value}, cls=DateTimeEncoder)


    def readOkCallback(self, value, request, metadata):
        log.info("{req.method} {req.uri} = {val} ok.", req=request, val=value)
        request.setResponseCode(200)
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': value,
            'units': metadata.units,
            'range': metadata.domain,
        }
        return json.dumps(result, cls=DateTimeEncoder)


# Test with
# curl -v -u foo:bar -H "Content-Type: application/json" \
#    -H "X-HTTP-Method-Override: PUT" -X POST \
#    -d '{ "value": "Hello world" }'  \
#     http://localhost:8080/ema/v1/anemometer/current/windspeed/threshold 

    def validate(self, request, object_hook=None):
        '''
        Generic Validation for all POST/PUT requests.
        Individual JSON contents must be validated by each route
        '''
        headers = request.getAllHeaders()
        if request.method == 'POST' and 'x-http-method-override' not in headers:
            raise BadRequest('HTTP POST method without X-HTTP-Method-Override header')
        if headers['x-http-method-override'] != 'PUT':
            raise BadRequest("X-HTTP-Method-Override header value isn't 'PUT'")
        if 'content-type' not in headers:
            raise BadRequest('missing Content-Type header')
        if headers['content-type'] != 'application/json':
            raise UnsupportedMediaType('Content-Type is not application/json')
        body = request.content.read()
        try:
            obj   = json.loads(body, object_hook=object_hook)
            value = obj['value']
        except Exception as e:
            log.failure("exception {e}", e=e)
            raise UnprocessableEntry(str(e))
        else:
            return value
           
    

__all__ = [
    "WebService"
]