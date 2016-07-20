# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

from __future__ import division

import json
import hashlib
import datetime
import time

# ---------------
# Twisted imports
# ---------------

from twisted.logger               import Logger, LogLevel
from twisted.internet             import reactor, task
from twisted.internet.defer       import inlineCallbacks, returnValue
from twisted.internet.task        import deferLater
from twisted.internet.defer       import DeferredList
from twisted.application.service  import Service
from twisted.internet.endpoints   import serverFromString
from twisted.web.server           import Site
from twisted.web.resource         import Resource
from klein import Klein



from zope.interface import implementer
from twisted.cred.portal import IRealm, Portal
from twisted.cred.checkers import FilePasswordDB
from twisted.web.resource  import IResource
from twisted.web.guard     import HTTPAuthSessionWrapper, BasicCredentialFactory



#--------------
# local imports
# -------------

from .logger import setLogLevel
from .service.relopausable import Service

import device

from command import EMARangeError, EMAReturnError
from serial  import EMATimeoutError

# ----------------
# Module constants
# ----------------



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
    code = 501
    msg = 'Internal Server Error'
    

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

    @app.route('/ema/v1/anemometer/current/windspeed/threshold', methods=['GET'])
    def get_current_windspeed_threshold(self, request):
        metadata = device.Anemometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.anemometer.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/anemometer/current/windspeed/threshold', methods=['PUT', 'POST'])
    def set_current_windspeed_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.anemometer.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.anemometer.threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['GET'])
    def get_average_windspeed_threshold(self, request):
        metadata = device.Anemometer.AverageThreshold.getter.metadata
        # Initiate read
        d = self.parent.anemometer.ave_threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['PUT', 'POST'])
    def set_average_windspeed_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.anemometer.ave_threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.anemometer.ave_threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/cloudsensor/threshold', methods=['GET'])
    def get_cloudsensor_threshold(self, request):
        metadata = device.CloudSensor.Threshold.getter.metadata
        # Initiate read
        d = self.parent.cloudsensor.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/cloudsensor/threshold', methods=['PUT', 'POST'])
    def set_cloudsensor_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.cloudsensor.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.cloudsensor.threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/photometer/threshold', methods=['GET'])
    def get_photometer_threshold(self, request):
        metadata = device.Photometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.photometer.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/photometer/threshold', methods=['PUT', 'POST'])
    def set_photometer_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.photometer.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.photometer.threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/rainsensor/threshold', methods=['GET'])
    def get_rainsensor_threshold(self, request):
        metadata = device.RainSensor.Threshold.getter.metadata
        # Initiate read
        d = self.parent.rainsensor.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/rainsensor/threshold', methods=['PUT', 'POST'])
    def set_rainsensor_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.rainsensor.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.rainsensor.threshold
            d.addCallback(self.writeOkCallback, request)
            return d



    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['GET'])
    def get_deltatemp_threshold(self, request):
        metadata = device.Thermometer.Threshold.getter.metadata
        # Initiate read
        d = self.parent.themomenter.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['PUT', 'POST'])
    def set_deltatemp_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.thermometer.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.thermometer.threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/voltmeter/threshold', methods=['GET'])
    def get_voltmeter_threshold(self, request):
        metadata = device.Voltmeter.Threshold.getter.metadata
        # Initiate read
        d = self.parent.voltmeter.threshold
        d.addCallback(self.readOkCallback, request, metadata)
        return d



    @app.route('/ema/v1/voltmeter/threshold', methods=['PUT', 'POST'])
    def set_voltmeter_threshold(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.voltmeter.threshold = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.voltmeter.threshold
            d.addCallback(self.writeOkCallback, request)
            return d


    # ESTA ES ESPECIAL
    @app.route('/ema/v1/roof/relay/mode', methods=['GET'])
    def get_roof_relay_mode(self, request):
        raise NotFound('Not implemented')


    @app.route('/ema/v1/roof/relay/mode', methods=['PUT', 'POST'])
    def set_roof_relay_mode(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.roof_relay.mode = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.roof_relay.mode
            d.addCallback(self.writeOkCallback, request)
            return d


    @app.route('/ema/v1/aux/relay/mode', methods=['GET'])
    def get_aux_relay_mode(self, request):
        metadata = device.AuxiliarRelay.Mode.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.mode
        d.addCallback(self.readOkCallback, request, metadata)
        return d

    #  Esta es peligrosa
    @app.route('/ema/v1/aux/relay/mode', methods=['PUT', 'POST'])
    def set_aux_relay_mode(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.aux_relay.mode = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.mode
            d.addCallback(self.writeOkCallback, request)
            return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['GET'])
    def get_aux_relay_switch_on_time(self, request):
        metadata = device.AuxiliarRelay.SwitchOnTime.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.switchOnTime
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_on_time(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.aux_relay.switchOnTime = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.switchOnTime
            d.addCallback(self.writeOkCallback, request)
            return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['GET'])
    def get_aux_relay_switch_off_time(self, request):
        metadata = device.AuxiliarRelay.SwitchOffTime.getter.metadata
        # Initiate read
        d = self.parent.aux_relay.switchOffTime
        d.addCallback(self.readOkCallback, request, metadata)
        return d


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_off_time(self, request):
        value    = self.validate(request)
        try:
            # Initiate write
            self.parent.aux_relay.switchOffTime = value
        except EMARangeError as e:
            raise UnprocessableEntry(str(e))
        except (RuntimeError, AttributeError) as e:
            raise InternalServerError(str(e))
        else:
            # get same deferred object from write
            d = self.parent.aux_relay.switchOffTime
            d.addCallback(self.writeOkCallback, request)
            return d

    @app.handle_errors
    def handle_errors(self, request, failure):
        '''
        Default handler for all REST API errors
        '''
        if failure.type in [NotFound, BadRequest, UnsupportedMediaType, UnprocessableEntry]:
            request.setResponseCode(failure.value.code, message=failure.value.msg)
            request.setHeader('Content-Type', 'application/json')
            return str(failure.value)
        else:
            request.setHeader('Content-Type', 'text/plain')
            request.setResponseCode(InternalServerError.code, message=InternalServerError.msg)
            # This is temporary, to aid debugging
            # we shoudl return the empty string
            import StringIO
            output = StringIO.StringIO() 
            failure.printTraceback(file=output)
            return output.getvalue()

    # --------------
    # Helper methods
    # --------------

    
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
            obj   = json.loads(body,object_hook=object_hook)
            value = obj['value']
        except Exception as e:
            log.failure("exception {e}", e=e)
            raise UnprocessableEntry(str(e))
        else:
            return value
           
    

__all__ = [
    "WebService"
]