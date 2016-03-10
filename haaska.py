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
import requests
from hashlib import sha1

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


@handle('HealthCheckRequest')
def handle_health_check(ha, payload):
    r = {}
    r['header'] = {'namespace': 'System',
                   'name': 'HealthCheckResponse',
                   'payloadVersion': '1'}
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
    r['header'] = {'namespace': 'Discovery',
                   'name': 'DiscoverAppliancesResponse',
                   'payloadVersion': '1'}
    try:
        r['payload'] = {'discoveredAppliances': discover_appliances(ha)}
    except Exception as e:
        r['payload'] = {'exception': {'code': 'INTERNAL_ERROR',
                                      'description': str(e)}}
    finally:
        return r


def discover_appliances(ha):
    def entity_domain(x):
        return x['entity_id'].split('.', 1)[0]

    def mk_appliance(x):
        dimmable = 'brightness' in x['attributes']
        o = {}
        # this needs to be unique and has limitations on allowed characters:
        o['applianceId'] = sha1(x['entity_id']).hexdigest()
        o['manufacturerName'] = 'Unknown'
        o['modelName'] = 'Unknown'
        o['version'] = 'Unknown'
        o['friendlyName'] = x['attributes']['friendly_name']
        if entity_domain(x) == 'scene':
            o['friendlyName'] += ' Scene'
        o['friendlyDescription'] = o['friendlyName']
        o['isReachable'] = True
        o['additionalApplianceDetails'] = {'entity_id': x['entity_id'],
                                           'dimmable': dimmable}
        return o

    states = ha.get('states')
    return [mk_appliance(x) for x in states
            if entity_domain(x) in ['light', 'switch', 'scene']]


class AwsLightingError(Exception):
    def __init__(self, code, description):
        self.code = code
        self.description = description


def control_response(name):
    def inner(func):
        def response_wrapper(ha, payload):
            r = {}
            r['header'] = {'namespace': 'Control',
                           'name': name,
                           'payloadVersion': '1'}
            try:
                func(ha, payload)
                r['payload'] = {'success': True}
            except AwsLightingError as e:
                r['payload'] = {'success': False,
                                'exception': {'code': e.code,
                                              'description': e.description}}
            except Exception as e:
                r['payload'] = {'success': False,
                                'exception': {'code': 'INTERNAL_ERROR',
                                              'description': str(e)}}
            finally:
                return r
        return response_wrapper
    return inner


def context(payload):
    return payload['appliance']['additionalApplianceDetails']


@handle('SwitchOnOffRequest')
@control_response('SwitchOnOffResponse')
def handle_switch_on_off(ha, payload):
    data = {'entity_id': context(payload)['entity_id']}

    if payload['switchControlAction'] == 'TURN_ON':
        ha.post('services/homeassistant/turn_on', data=data)
    else:
        ha.post('services/homeassistant/turn_off', data=data)


@handle('AdjustNumericalSettingRequest')
@control_response('AdjustNumericalSettingResponse')
def handle_adjust_numerical(ha, payload):
    if context(payload)['dimmable'] == 'false':
        raise AwsLightingError('UNSUPPORTED_TARGET_SETTING', 'Not dimmable')

    assert payload['adjustmentUnit'] == 'PERCENTAGE'
    adjustment = round(payload['adjustmentValue'] / 100.0 * 255.0)
    entity_id = context(payload)['entity_id']

    brightness = adjustment
    if payload['adjustmentType'] == 'RELATIVE':
        state = ha.get('states/' + entity_id)
        current_brightness = state['attributes']['brightness']
        brightness = current_brightness + adjustment

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
