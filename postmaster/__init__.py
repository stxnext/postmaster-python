# Postmaster Python bindings
# API docs at http://postmaster.io/docs
# Author: Jesse Lovelace <jesse@postmaster.io>

from .version import *
from .http import *
from .conf import config

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        raise


class PostmasterObject(object):
    """
    Base object for Postmaster.  Allows slightly easlier access to data and
    some REST-like opertations.
    """
    
    ARGS = []
    PATH = None
    
    def __init__(self, **kwargs):
        if self.ARGS:
            for k in kwargs.iterkeys():
                if not k in self.ARGS:
                    raise TypeError('%s is an invalid argument for %s.' % (k, self.__class__.__name__))
                
        self._data = kwargs

    def __getattr__(self, name):
        if not name in self._data:
            raise AttributeError("Cannot find attribute.")
        
        return self._data[name]
        
    def __repr__(self):
        return '<postmaster.%s at %s> JSON: %s' % (self.__class__.__name__, id(self), self._data)

    def put(self, id_=None, action=None):
        """
        Put object to server.
        """
        if id_:
            response = HTTPTransport.put(
                action and '%s/%s/%s' % (self.PATH, id_, action) or \
                    '%s/%s' % (self.PATH, id_),
                self._data, headers=config.headers)
        else:
            response = HTTPTransport.post(self.PATH, self._data, headers=config.headers)
        return response
        
    def get(self, id_=None, action=None, params=None):
        """
        Get object(s) from server.
        """

        if id_:
            response = HTTPTransport.get(
                action and '%s/%s/%s' % (self.PATH, id_, action) or \
                    '%s/%s' % (self.PATH, id_), params, headers=config.headers)
        else:
            response = HTTPTransport.get(
                self.PATH, params, headers=config.headers)
        return response


class Tracking(PostmasterObject):
    pass


class Rate(PostmasterObject):
    PATH = '/v1/rates'


class TimeInTransit(PostmasterObject):
    PATH = '/v1/times'


class Address(PostmasterObject):

    PATH = '/v1/validate'

    def __init__(self, company=None, contact=None, line1=None, line2=None, line3=None, city=None, state=None, zip_code=None, country=None):
        kwargs = dict(
            company=company,
            contact=contact,
            line1=line1,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country
        )
        if line2:
            kwargs['line2'] = line2
        if line3:
            kwargs['line3'] = line3
        super(Address, self).__init__(**kwargs)

    def validate(self):
        return self.put()


class Shipment(PostmasterObject):

    PATH = '/v1/shipments'

    @classmethod

    def create(cls, to, packages, service, from_=None, carrier=None, reference=None, options=None):
        """
        Create a new shipment.

        Arguments:

         * to (required) - a dict representing the ship-to address:
           * company
           * contact
           * street - a list of strings defining the street address
           * city
           * state
           * zip
         * packages (required) - a dict (or list of dicts) representing the package:
           * weight
           * length
           * width
           * height
         * from (optional) - a dict representing the ship-from address.
                             Will use default for account if not provided.
         * customs (optional)
        """

        shipment = Shipment()
        shipment._data = {
            'to': to,
            'packages': packages,
            'service': service,
        }

        if from_:
            shipment._data['from'] = from_
        if carrier:
            shipment._data['carrier'] = carrier
        if reference:
            shipment._data['reference'] = reference
        if options:
            shipment._data['options'] = options

        resp = shipment.put()

        shipment._data.update(resp)
        shipment.id = resp['id']

        return shipment

    @classmethod
    def retrieve(cls, package_id):
        """
        Retrieve a package by ID.
        """
        shipment = Shipment()
        shipment._data = shipment.get(package_id)
        return shipment

    def track(self):
        """
        Track a shipment (from an object)
        """
        return Tracking(**self.get(self.id, 'track'))

    def void(self):
        """
        Void a shipment (from an object)
        """
        self.put(self.id, 'void')


def track_by_reference(tracking_number):
    """
    Track any package by it's carrier-specific tracking number.
    Note: if this package was not shipped my Postmaster
    the resulting data will not contain detailed information
    about the shipment.
    """
    return HTTPTransport.get('/v1/track', dict(tracking=tracking_number))


def validate_address(address_object):
    """
    Validate that an address is correct.
    """
    pass


def get_transit_time(from_zip, to_zip, weight, carrier=None):
    """
    Find the time needed for a package to get from point A to point B
    """
    tit = TimeInTransit(
        from_zip=from_zip,
        to_zip=to_zip,
        weight=weight,
        carrier=carrier,
    )
    return tit.put()


def get_rate(carrier, to_zip, weight, from_zip=None, service='ground'):
    """
    Find the cost to ship a package from point A to point B.
    """
    rate = Rate(
        from_zip=from_zip,
        to_zip=to_zip,
        weight=weight,
        carrier=carrier,
        service=service,
    )

    return rate.put()


def get_token():
    return HTTPTransport.get('/v1/token')


def void_shipment(id):
    """
    Cancel shipment by ID.
    :param id: Shipment ID.
    :return: True if when shipment was canceled. None if shipment doesn't exist.
    """
    status = HTTPTransport.delete('/v1/shipments/%s/void' % id)
    if isinstance(status, dict) and status.get('message') == 'OK':
        return True


def list_shipments(cursor=None, limit=None):
    """
    List of user defined shipments.
    :param cursor: cursor or previousCursor for shipments list querying.
    :param limit: Quantity of shipments per query.
    :return: Dict with keys 'cursor', 'previousCursor' and 'results'.
        'results' is a list of shipments as a dict.
    """
    data = {}
    if cursor is not None:
        data['cursor'] = cursor
    if limit is not None:
        data['limit'] = limit

    return HTTPTransport.get('/v1/shipments', data)


def create_box(width, height, length, weight=None, weight_units=None,
               size_units=None, name=None):
    """
    Create a user-defined box type.
    :param width: The width of the box (required).
    :param height: The height of the box (required).
    :param length: The length of the box (required).
    :param weight: The weight of the box (optional).
    :param weight_units:
        The units of weight: LB, OZ, KG, G (optional, default: LB).
    :param size_units: The units of size: IN, FT, CM, M (optional, default: IN)
    :param name: Give this box a memorable name (optional).
    :return: Box ID.
    Raises a postmaster.InvalidDataError when input is invalid.
    """
    data = {
        'width': width,
        'height': height,
        'length': length,
    }
    if weight is not None:
        data['weight'] = weight
    if weight_units is not None:
        data['weight_units'] = weight_units
    if size_units is not None:
        data['size_units'] = size_units
    if name is not None:
        data['name'] = name

    return HTTPTransport.post('/v1/packages', data)


def list_boxes(cursor=None, limit=None):

    """
    List all user-defined box types.
    :param cursor: The cursor offset (optional).
    :param limit: The number of boxes to get (optional, default: 10).
    :return: Dict with keys 'cursor', 'previousCursor' and 'results'.
        'results' is a list of boxes as a dict.
    """
    data = {}
    if cursor is not None:
        data['cursor'] = cursor
    if limit is not None:
        data['limit'] = limit

    return HTTPTransport.get('/v1/packages', data)
