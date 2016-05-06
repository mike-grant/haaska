#!/usr/bin/env python2.7

# Copyright (c) 2015 Michael Auchter <a@phire.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import operator
import requests
from hashlib import sha1
from uuid import uuid4

handlers = {}


def get_config():
    with open('config.json') as f:
        cfg = json.load(f)
        if 'ha_cert' not in cfg:
            cfg['ha_cert'] = False
        return cfg


def event_handler(event, context):
    cfg = get_config()
    ha = HomeAssistant(cfg['ha_url'], cfg['ha_passwd'], cfg['ha_cert'])

    name = event['header']['name']
    payload = event['payload']

    return handlers[name](ha, payload)


def handle(event):
    def inner(func):
        handlers[event] = func
        return func
    return inner


class HomeAssistant(object):
    def __init__(self, url, passwd, cert=False):
        self.url = url
        self.headers = {'x-ha-access': passwd,
                        'content-type': 'application/json'}
        self.cert = cert

    def get(self, relurl):
        r = requests.get(self.url + '/' + relurl, headers=self.headers,
                         verify=self.cert)
        r.raise_for_status()
        return r.json()

    def post(self, relurl, data):
        r = requests.post(self.url + '/' + relurl, headers=self.headers,
                          verify=self.cert, data=json.dumps(data))
        r.raise_for_status()
        return r


def driver_internal_error():
    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.Control',
                   'name': 'DriverInternalError',
                   'payloadVersion': '2',
                   'messageId': str(uuid4())}
    r['payload'] = {}
    return r


@handle('HealthCheckRequest')
def handle_health_check(ha, payload):
    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.System',
                   'messageId': str(uuid4()),
                   'name': 'HealthCheckResponse',
                   'payloadVersion': '2'}
    try:
        ha.get('states')
        r['payload'] = {'isHealthy': True}
    except Exception as e:
        r['payload'] = {'isHealthy': False, 'description': str(e)}
    finally:
        return r


@handle('DiscoverAppliancesRequest')
def handle_discover_appliances(ha, payload):
    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.Discovery',
                   'name': 'DiscoverAppliancesResponse',
                   'messageId': str(uuid4()),
                   'payloadVersion': '2'}
    try:
        r['payload'] = {'discoveredAppliances': discover_appliances(ha)}
    except Exception as e:
        print 'Discovery failed: ' + str(e)
        # v2 documentation is unclear as to what should be returned here if
        # discovery fails, so in the mean-time, just return 0 devices and log
        # the error
        r['payload'] = {'discoveredAppliances': {}}
    finally:
        return r


def discover_appliances(ha):
    def entity_domain(x):
        return x['entity_id'].split('.', 1)[0]

    def is_supported_entity(x):
        allowed_entities = ['group', 'input_boolean', 'light', 'media_player', 'scene', 'script', 'switch']
        cfg = get_config()
        if 'ha_allowed_entities' in cfg:
          allowed_entities = cfg['ha_allowed_entities']
        return entity_domain(x) in allowed_entities

    def is_skipped_entity(x):
        attr = x['attributes']
        return 'haaska_hidden' in attr and attr['haaska_hidden']

    def mk_appliance(x):
        dimmable = entity_domain(x) in ('light', 'group')
        o = {}
        # this needs to be unique and has limitations on allowed characters:
        o['applianceId'] = sha1(x['entity_id']).hexdigest()
        o['manufacturerName'] = 'Unknown'
        o['modelName'] = 'Unknown'
        o['version'] = 'Unknown'
        if 'haaska_name' in x['attributes']:
            o['friendlyName'] = x['attributes']['haaska_name']
        else:
            o['friendlyName'] = x['attributes']['friendly_name']
            if entity_domain(x) == 'scene':
                o['friendlyName'] += ' Scene'
            elif entity_domain(x) == 'group':
                o['friendlyName'] += ' Group'
        if 'haaska_desc' in x['attributes']:
            o['friendlyDescription'] = x['attributes']['haaska_desc']
        else:
            o['friendlyDescription'] = 'Home Assistant ' + entity_domain(x).replace('_', ' ').title()
        o['isReachable'] = True
        o['actions'] = ['turnOn', 'turnOff']
        if dimmable:
            o['actions'] += ['incrementPercentage', 'decrementPercentage',
                             'setPercentage']
        o['additionalApplianceDetails'] = {'entity_id': x['entity_id'],
                                           'dimmable': dimmable}
        return o

    states = ha.get('states')
    return [mk_appliance(x) for x in states if is_supported_entity(x) and not
            is_skipped_entity(x)]


def control_response(name):
    def inner(func):
        def response_wrapper(ha, payload):
            r = {}
            r['header'] = {'namespace': 'Alexa.ConnectedHome.Control',
                           'name': name,
                           'messageId': str(uuid4()),
                           'payloadVersion': '2'}
            try:
                func(ha, payload)
                r['payload'] = {'success': True}
                return r
            except Exception as e:
                print 'operation failed: ' + str(e)
                return driver_internal_error()
        return response_wrapper
    return inner


def context(payload):
    return payload['appliance']['additionalApplianceDetails']


@handle('TurnOnRequest')
@control_response('TurnOnConfirmation')
def handle_turn_on(ha, payload):
    entity_id = context(payload)['entity_id']
    ha.post('services/homeassistant/turn_on', data={'entity_id': entity_id})


@handle('TurnOffRequest')
@control_response('TurnOffConfirmation')
def handle_turn_off(ha, payload):
    entity_id = context(payload)['entity_id']
    data = {'entity_id': entity_id}
    entity_domain = entity_id.split('.', 1)[0]

    # Alexa sometimes mishears "turn off" for "turn on"; since it makes no
    # sense to turn off a scene or script, just turn it on
    if entity_domain == 'scene' or entity_domain == 'script':
        ha.post('services/homeassistant/turn_on', data=data)
    else:
        ha.post('services/homeassistant/turn_off', data=data)


@handle('SetPercentageRequest')
@control_response('SetPercentageConfirmation')
def handle_set_percentage(ha, payload):
    entity_id = context(payload)['entity_id']
    brightness = round(payload['percentageState']['value'] / 100.0 * 255.0)

    ha.post('services/light/turn_on', data={'entity_id': entity_id,
                                            'brightness': brightness})

def handle_percentage_adj(ha, payload, op):
    entity_id = context(payload)['entity_id']
    delta = round(payload['deltaPercentage']['value'] / 100.0 * 255.0)

    state = ha.get('states/' + entity_id)
    current_brightness = state['attributes']['brightness']
    brightness = op(current_brightness, delta)

    # So this looks weird, but the relative adjustments seem to always be
    # +/- 25%, which means depending on the current brightness we could
    # over-/undershoot the acceptable range. Instead, if we're not
    # currently saturated, clamp the desired brightness to the allowed
    # brightness.
    if current_brightness != 255 and current_brightness != 0:
        if brightness < 0:
            brightness = 0
        elif brightness > 255:
            brightness = 255

    if brightness > 255 or brightness < 0:
        raise AwsLightingError('TARGET_SETTING_OUT_OF_RANGE', str(brightness))

    ha.post('services/light/turn_on', data={'entity_id': entity_id,
                                            'brightness': brightness})


@handle('IncrementPercentageRequest')
@control_response('IncrementPercentageConfirmation')
def handle_increment_percentage(ha, payload):
    handle_percentage_adj(ha, payload, operator.add)


@handle('DecrementPercentageRequest')
@control_response('DecrementPercentageConfirmation')
def handle_decrement_percentage(ha, payload):
    handle_percentage_adj(ha, payload, operator.sub)
