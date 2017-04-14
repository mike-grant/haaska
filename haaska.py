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


LIGHT_SUPPORT_COLOR_TEMP = 2
LIGHT_SUPPORT_RGB_COLOR = 16
LIGHT_SUPPORT_XY_COLOR = 64


def get_config():
    with open('config.json') as f:
        cfg = json.load(f)
        if 'ha_cert' not in cfg:
            cfg['ha_cert'] = False
        return cfg


cfg = get_config()


def event_handler(event, context):
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


class SmartHomeException(Exception):
    def __init__(self, name="DriverInternalError", payload={}):
        self.r = {}
        self.r['header'] = {'namespace': 'Alexa.ConnectedHome.Control',
                            'name': name,
                            'payloadVersion': '2',
                            'messageId': str(uuid4())}
        self.r['payload'] = payload


class ValueOutOfRangeError(SmartHomeException):
    def __init__(self, minValue, maxValue):
        super(ValueOutOfRangeError, self).__init__('ValueOutOfRangeError',
                                                   {'minimumValue': minValue,
                                                    'maximumValue': maxValue})


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
        print('Discovery failed: ' + str(e))
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
        allowed_entities = ['group', 'input_boolean', 'light', 'media_player',
                            'scene', 'script', 'switch', 'garage_door', 'lock',
                            'cover']
        if 'ha_allowed_entities' in cfg:
            allowed_entities = cfg['ha_allowed_entities']
        return entity_domain(x) in allowed_entities

    def is_skipped_entity(x):
        attr = x['attributes']
        return 'haaska_hidden' in attr and attr['haaska_hidden']

    def mk_appliance(x):
        features = 0
        if 'supported_features' in x['attributes']:
            features = x['attributes']['supported_features']
        entity = mk_entity(ha, x['entity_id'], features)
        o = {}
        # this needs to be unique and has limitations on allowed characters:
        o['applianceId'] = sha1(x['entity_id'].encode('utf-8')).hexdigest()
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
            o['friendlyDescription'] = 'Home Assistant ' + \
                entity_domain(x).replace('_', ' ').title()
        o['isReachable'] = True
        o['actions'] = entity.get_actions()
        o['additionalApplianceDetails'] = {'entity_id': x['entity_id'],
                                           'supported_features': features}
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
                response_payload = func(ha, payload) or {'success': True}
                r['payload'] = response_payload
                return r
            except SmartHomeException as e:
                return e.r
            except Exception as e:
                print('operation failed: ' + str(e))
                return SmartHomeException().r
        return response_wrapper
    return inner


def payload_to_entity(payload):
    return payload['appliance']['additionalApplianceDetails']['entity_id']


def supported_features(payload):
    return payload['appliance']['additionalApplianceDetails']['supported_features']


@handle('TurnOnRequest')
@control_response('TurnOnConfirmation')
def handle_turn_on(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.turn_on()


@handle('TurnOffRequest')
@control_response('TurnOffConfirmation')
def handle_turn_off(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.turn_off()


@handle('SetPercentageRequest')
@control_response('SetPercentageConfirmation')
def handle_set_percentage(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.set_percentage(payload['percentageState']['value'])


def handle_percentage_adj(ha, payload, op):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    current = e.get_percentage()
    new = op(current, payload['deltaPercentage']['value'])

    # So this looks weird, but the relative adjustments seem to always be
    # +/- 25%, which means depending on the current brightness we could
    # over-/undershoot the acceptable range. Instead, if we're not
    # currently saturated, clamp the desired brightness to the allowed
    # brightness.
    if current != 100 and current != 0:
        if new < 0:
            new = 0
        elif new > 100:
            new = 100

    if new > 100 or new < 0:
        raise ValueOutOfRangeError(0, 100)

    e.set_percentage(new)


@handle('IncrementPercentageRequest')
@control_response('IncrementPercentageConfirmation')
def handle_increment_percentage(ha, payload):
    return handle_percentage_adj(ha, payload, operator.add)


@handle('DecrementPercentageRequest')
@control_response('DecrementPercentageConfirmation')
def handle_decrement_percentage(ha, payload):
    return handle_percentage_adj(ha, payload, operator.sub)


@handle('GetLockStateRequest')
def handle_get_lock_state(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    lock_state = e.get_lock_state().upper()

    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.Query',
                   'messageId': str(uuid4()),
                   'name': 'GetLockStateResponse',
                   'payloadVersion': '2'}
    r['payload'] = {'lockState': lock_state}
    return r


@handle('SetLockStateRequest')
@control_response('SetLockStateConfirmation')
def handle_set_lock_state(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.set_lock_state(payload["lockState"])
    return {'lockState': payload["lockState"]}


@handle('SetColorTemperatureRequest')
@control_response('SetColorTemperatureConfirmation')
def handle_set_color_temperature(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.set_color_temperature(payload['colorTemperature']['value'])


class Entity(object):
    def __init__(self, ha, entity_id, supported_features):
        self.ha = ha
        self.entity_id = entity_id
        self.supported_features = supported_features
        self.entity_domain = self.entity_id.split('.', 1)[0]

    def _call_service(self, service, data={}):
        data['entity_id'] = self.entity_id
        self.ha.post('services/' + service, data)

    def get_actions(self):
        actions = []

        if hasattr(self, 'turn_on'):
            actions.append('turnOn')
        if hasattr(self, 'turn_off'):
            actions.append('turnOff')

        if hasattr(self, 'set_percentage'):
            actions.append('setPercentage')
        if hasattr(self, 'get_percentage'):
            actions.append('incrementPercentage')
            actions.append('decrementPercentage')

        if hasattr(self, 'get_lock_state'):
            actions.append('getLockState')
        if hasattr(self, 'set_lock_state'):
            actions.append('setLockState')

        if self.entity_domain == "light":
            if self.supported_features & (LIGHT_SUPPORT_COLOR_TEMP or LIGHT_SUPPORT_RGB_COLOR or LIGHT_SUPPORT_XY_COLOR):
                actions.append('setColorTemperature')

        return actions


class ToggleEntity(Entity):
    def turn_on(self):
        self._call_service('homeassistant/turn_on')

    def turn_off(self):
        self._call_service('homeassistant/turn_off')


class GarageDoorEntity(ToggleEntity):
    def turn_on(self):
        self._call_service('garage_door/open')

    def turn_off(self):
        self._call_service('garage_door/close')


class CoverEntity(ToggleEntity):
    def turn_on(self):
        self._call_service('cover/open_cover')

    def turn_off(self):
        self._call_service('cover/close_cover')


class LockEntity(Entity):
    def set_lock_state(self, state):
        if state == "LOCKED":
            self._call_service('lock/lock')
        elif state == "UNLOCKED":
            self._call_service('lock/unlock')

    def get_lock_state(self):
        state = self.ha.get('states/' + self.entity_id)
        return state['state']


class ScriptEntity(ToggleEntity):
    def turn_off(self):
        self.turn_on()


class SceneEntity(ToggleEntity):
    def turn_off(self):
        self.turn_on()


class LightEntity(ToggleEntity):
    def get_percentage(self):
        state = self.ha.get('states/' + self.entity_id)
        current_brightness = state['attributes']['brightness']
        return (current_brightness / 255.0) * 100.0

    def set_percentage(self, val):
        brightness = (val / 100.0) * 255.0
        self._call_service('light/turn_on', {'brightness': brightness})

    def set_color_temperature(self, val):
        color_temp = (val / 1000000)
        self._call_service('light/turn_on', {'color_temp': color_temp})


class MediaPlayerEntity(ToggleEntity):
    def get_percentage(self):
        state = self.ha.get('states/' + self.entity_id)
        vol = state['attributes']['volume_level']
        return vol * 100.0

    def set_percentage(self, val):
        vol = val / 100.0
        self._call_service('media_player/volume_set', {'volume_level': vol})


def mk_entity(ha, entity_id, supported_features):
    entity_domain = entity_id.split('.', 1)[0]

    domains = {'garage_door': GarageDoorEntity,
               'cover': CoverEntity,
               'lock': LockEntity,
               'script': ScriptEntity,
               'scene': SceneEntity,
               'light': LightEntity,
               'media_player': MediaPlayerEntity}

    return domains.setdefault(entity_domain, ToggleEntity)(ha, entity_id,
                                                           supported_features)
