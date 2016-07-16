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
import crypt

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

# ----------------
# Module constants
# ----------------



# ----------------
# Global functions
# -----------------


def cmp_pass(uname, password, storedpass):
    log.err("uname=%s password=%s storedpass=%s" % (uname, password, storedpass) )
    return crypt.crypt(password, storedpass[:2])


# -----------------------
# Module global variables
# -----------------------

log = Logger(namespace='web')

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

class NotFound(Exception):
    '''Resource not found'''
    code = 404
    

class BadRequest(Exception):
    '''Could not parse request'''
    code = 400
    

class UnsupportedMediaType(Exception):
    '''POST/PUT request occurred without a application/json content type'''
    code = 416
    

class UnprocessableEntry(Exception):
    '''A request to modify a resource failed due to a validation error'''
    code = 422
    

class InternalServerError(Exception):
    '''An internal server error occured'''
    code = 501
    

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
        portal = Portal(PublicHTMLRealm(self.app.resource()), 
            [ FilePasswordDB(self.options['passwd']) ] )
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
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.anemometer.PARAMS['threshold']['value'],
            'units': self.parent.serialService.anemometer.PARAMS['threshold']['units'],
            'range': self.parent.serialService.anemometer.PARAMS['threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/anemometer/current/windspeed/threshold', methods=['PUT', 'POST'])
    def set_current_windspeed_threshold(self, request):
        valrange = self.parent.serialService.anemometer.PARAMS['threshold']['range']
        valtype  = self.parent.serialService.anemometer.PARAMS['threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['GET'])
    def get_average_windspeed_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.anemometer.PARAMS['ave_threshold']['value'],
            'units': self.parent.serialService.anemometer.PARAMS['ave_threshold']['units'],
            'range': self.parent.serialService.anemometer.PARAMS['ave_threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/anemometer/average/windspeed/threshold', methods=['PUT', 'POST'])
    def set_average_windspeed_threshold(self, request):
        valrange = self.parent.serialService.anemometer.PARAMS['ave_threshold']['range']
        valtype  = self.parent.serialService.anemometer.PARAMS['ave_threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/cloudsensor/threshold', methods=['GET'])
    def get_cloudsensor_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.cloudsensor.PARAMS['threshold']['value'],
            'units': self.parent.serialService.cloudsensor.PARAMS['threshold']['units'],
            'range': self.parent.serialService.cloudsensor.PARAMS['threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/cloudsensor/threshold', methods=['PUT', 'POST'])
    def set_cloudsensor_threshold(self, request):
        valrange = self.parent.serialService.cloudsensor.PARAMS['threshold']['range']
        valtype  = self.parent.serialService.cloudsensor.PARAMS['threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/photometer/threshold', methods=['GET'])
    def get_photometer_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.photometer.PARAMS['threshold']['value'],
            'units': self.parent.serialService.photometer.PARAMS['threshold']['units'],
            'range': self.parent.serialService.photometer.PARAMS['threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/photometer/threshold', methods=['PUT', 'POST'])
    def set_photometer_threshold(self, request):
        valrange = self.parent.serialService.photometer.PARAMS['threshold']['range']
        valtype  = self.parent.serialService.photometer.PARAMS['threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/rainsensor/threshold', methods=['GET'])
    def get_rainsensor_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.rainsensor.PARAMS['threshold']['value'],
            'units': self.parent.serialService.rainsensor.PARAMS['threshold']['units'],
            'range': self.parent.serialService.rainsensor.PARAMS['threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/rainsensor/threshold', methods=['PUT', 'POST'])
    def set_rainsensor_threshold(self, request):
        valrange = self.parent.serialService.rainsensor.PARAMS['threshold']['range']
        valtype  = self.parent.serialService.rainsensor.PARAMS['threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['GET'])
    def get_deltatemp_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.themomenter.PARAMS['delta_threshold']['value'],
            'units': self.parent.serialService.themomenter.PARAMS['delta_threshold']['units'],
            'range': self.parent.serialService.themomenter.PARAMS['delta_threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/thermometer/deltatemp/threshold', methods=['PUT', 'POST'])
    def set_deltatemp_threshold(self, request):
        valrange = self.parent.serialService.themomenter.PARAMS['delta_threshold']['range']
        valtype  = self.parent.serialService.themomenter.PARAMS['delta_threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/voltmeter/threshold', methods=['GET'])
    def get_voltmeter_threshold(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.voltmeter.PARAMS['threshold']['value'],
            'units': self.parent.serialService.voltmeter.PARAMS['threshold']['units'],
            'range': self.parent.serialService.voltmeter.PARAMS['threshold']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/voltmeter/threshold', methods=['PUT', 'POST'])
    def set_voltmeter_threshold(self, request):
        valrange = self.parent.serialService.voltmeter.PARAMS['threshold']['range']
        valtype  = self.parent.serialService.voltmeter.PARAMS['threshold']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    # ESTA ES ESPECIAL
    @app.route('/ema/v1/roof/relay/mode', methods=['GET'])
    def get_roof_relay_mode(self, request):
        raise NotFound()


    # Y ESTA TAMBIEN
    @app.route('/ema/v1/roof/relay/mode', methods=['PUT', 'POST'])
    def set_roof_relay_mode(self, request):
        valrange = self.parent.serialService.roof_relay.PARAMS['mode']['range']
        valtype  = self.parent.serialService.roof_relay.PARAMS['mode']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    @app.route('/ema/v1/aux/relay/mode', methods=['GET'])
    def get_aux_relay_mode(self, request):
        request.setHeader('Content-Type', 'application/json')
        result = {
            'value': self.parent.serialService.aux_relay.PARAMS['mode']['value'],
            'units': self.parent.serialService.aux_relay.PARAMS['mode']['units'],
            'range': self.parent.serialService.aux_relay.PARAMS['mode']['range'],
        }
        return json.dumps(result, cls=DateTimeEncoder)


    @app.route('/ema/v1/aux/relay/mode', methods=['PUT', 'POST'])
    def set_aux_relay_mode(self, request):
        valrange = self.parent.serialService.aux_relay.PARAMS['mode']['range']
        valtype  = self.parent.serialService.aux_relay.PARAMS['mode']['type']
        value    = self.getValidated(request, valtype, valrange)
        raise NotFound()


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['GET'])
    def get_aux_relay_switch_on_time(self, request):
        raise NotFound()


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/on/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_on_time(self, request):
        raise NotFound()


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['GET'])
    def get_aux_relay_switch_off_time(self, request):
        raise NotFound()


    # Estas son muy especiales y peligrosas
    @app.route('/ema/v1/aux/relay/switch/off/time', methods=['PUT', 'POST'])
    def set_aux_relay_switch_off_time(self, request):
        raise NotFound()

    # --------------
    # Helper methods
    # --------------

# Test with
# curl -v -u foo:bar -H "Content-Type: application/json" \
#    -H "X-HTTP-Method-Override: PUT" -X POST \
#    -d '{ "value": "Hello world" }'  \
#     http://localhost:8080/ema/v1/anemometer/current/windspeed/threshold 

    def getValidated(self, request, valtype, valrange):
        '''
        Generic Validation for all POST/PUT requests.
        Individual JSON contents must be validated by each route
        '''
        headers = request.getAllHeaders()
        log.debug("{headers}", headers=request.getAllHeaders())
        if request.method == 'POST' and 'x-http-method-override' not in headers:
            raise BadRequest()
        if 'content-type' not in headers:
            raise BadRequest()
        if headers['content-type'] != 'application/json':
            raise UnsupportedMediaType()
        body = request.content.read()
        try:
            obj   = json.loads(body)
            value = obj['value']
        except Exception as e:
            log.failure("exception {e}", e=e)
            raise UnprocessableEntry()
        else:
            if type(value) != valtype:
                log.debug("Value's type is {t}, expected {e}", t=type(value), e=valtype)
                raise UnprocessableEntry()
            if type(value) == str and value not in valrange:
                log.debug("Value {v} not in range {r}", v=value, r=valrange)
                raise UnprocessableEntry()
            if  not (valrange[0] <= value <= valrange[1]):
                log.debug("Value {v} not in range {r}", v=value, r=valrange)
                raise UnprocessableEntry()
            log.debug("Value {v} is ok", v=value)
            return value
            

    def json_4xx_error(self, request, code, msg):
        '''
        Returns a JSON body for all 4xx error
        '''
        request.setResponseCode(code)
        request.setHeader('Content-Type', 'application/json')
        return json.dumps( { 'message': msg } )


    @app.handle_errors
    def handle_errors(self, request, failure):
        '''
        Default handler for all REST API errors
        '''
        if failure.type in [NotFound, BadRequest, UnsupportedMediaType, UnprocessableEntry]:
            return self.json_4xx_error(request, failure.type.code, failure.type.__doc__)
        else:
            request.setResponseCode(500)
            return ''


__all__ = [
    "WebService"
]