#!/usr/bin/env python2.7
# coding: utf-8

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
import logging
import operator
import requests
import colorsys
from hashlib import sha1
from uuid import uuid4

logger = logging.getLogger()
handlers = {}


LIGHT_SUPPORT_COLOR_TEMP = 2
LIGHT_SUPPORT_RGB_COLOR = 16
LIGHT_SUPPORT_XY_COLOR = 64


class HomeAssistant(object):
    def __init__(self, config):
        self.config = config
        self.url = config.url.rstrip('/')
        self.session = requests.Session()
        self.session.headers = {'x-ha-access': config.password,
                                'content-type': 'application/json'}
        self.session.verify = config.ssl_verify

    def build_url(self, relurl):
        return '%s/%s' % (self.config.url, relurl)

    def get(self, relurl):
        r = self.session.get(self.build_url(relurl))
        r.raise_for_status()
        return r.json()

    def post(self, relurl, d, wait=False):
        read_timeout = None if wait else 0.01
        r = None
        try:
            r = self.session.post(self.build_url(relurl),
                                  data=json.dumps(d),
                                  timeout=(None, read_timeout))
            r.raise_for_status()
        except requests.exceptions.ReadTimeout:
            # Allow response timeouts after request was sent
            logger.debug('request for %s sent without waiting for response',
                         relurl)
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


def handle(event):
    def inner(func):
        handlers[event] = func
        return func
    return inner


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
        logger.exception('HealthCheckRequest failed')
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
    except Exception:
        logger.exception('DiscoverAppliancesRequest failed')
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
        return entity_domain(x) in ha.config.allowed_domains

    def is_skipped_entity(x):
        attr = x['attributes']
        return (('haaska_hidden' in attr and attr['haaska_hidden']) or
                ('hidden' in attr and attr['hidden']))

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
            suffix = ha.config.entity_suffixes[entity_domain(x)]
            if suffix != '':
                o['friendlyName'] += ' ' + suffix
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
                logger.exception('%s handler failed' % name)
                return SmartHomeException().r
        return response_wrapper
    return inner


def payload_to_entity(payload):
    return payload['appliance']['additionalApplianceDetails']['entity_id']


def supported_features(payload):
    try:
        details = 'additionalApplianceDetails'
        return payload['appliance'][details]['supported_features']
    except:
        return 0


@handle('TurnOnRequest')
@control_response('TurnOnConfirmation')
def handle_turn_on(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
    e.turn_on()


@handle('TurnOffRequest')
@control_response('TurnOffConfirmation')
def handle_turn_off(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
    e.turn_off()


@handle('SetPercentageRequest')
@control_response('SetPercentageConfirmation')
def handle_set_percentage(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
    e.set_percentage(payload['percentageState']['value'])


def handle_percentage_adj(ha, payload, op):
    e = mk_entity(ha, payload_to_entity(payload))
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


def handle_color_temperature_adj(ha, payload, op):
    e = mk_entity(ha, payload_to_entity(payload))
    current = e.get_color_temperature()
    new = op(current, 500)
    e.set_color_temperature(new)
    return {'achievedState': {'colorTemperature': {'value': new}}}


@handle('IncrementColorTemperatureRequest')
@control_response('IncrementColorTemperatureConfirmation')
def handle_increment_colortemp(ha, payload):
    return handle_color_temperature_adj(ha, payload, operator.add)


@handle('DecrementColorTemperatureRequest')
@control_response('DecrementColorTemperatureConfirmation')
def handle_decrement_colortemp(ha, payload):
    return handle_color_temperature_adj(ha, payload, operator.sub)


def convert_temp(temp, from_unit=u'°C', to_unit=u'°C'):
    if temp is None or from_unit == to_unit:
        return temp
    if from_unit == u'°C':
        return temp * 1.8 + 32
    else:
        return (temp - 32) / 1.8


@handle('GetTemperatureReadingRequest')
def handle_get_temperature_reading(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
    temperature = e.get_current_temperature()

    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.Query',
                   'messageId': str(uuid4()),
                   'name': 'GetTemperatureReadingResponse',
                   'payloadVersion': '2'}
    r['payload'] = {'temperatureReading': {'value': temperature}}
    return r


@handle('GetTargetTemperatureRequest')
def handle_get_target_temperature(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
    temperature, mode = e.get_temperature()

    r = {}
    r['header'] = {'namespace': 'Alexa.ConnectedHome.Query',
                   'messageId': str(uuid4()),
                   'name': 'GetTargetTemperatureResponse',
                   'payloadVersion': '2'}
    r['payload'] = {'targetTemperature': {'value': temperature},
                    'temperatureMode': {'value': mode}}
    if mode not in ['AUTO', 'COOL', 'HEAT', 'OFF']:
        r['payload']['temperatureMode'] = {
            'value': 'CUSTOM',
            'friendlyName': mode.replace('_', ' ').title()}
    return r


def handle_temperature_adj(ha, payload, op=None):
    e = mk_entity(ha, payload_to_entity(payload))
    state = ha.get('states/' + e.entity_id)
    unit = state['attributes']['unit_of_measurement']
    min_temp = convert_temp(state['attributes']['min_temp'], unit)
    max_temp = convert_temp(state['attributes']['max_temp'], unit)

    temperature, mode = e.get_temperature(state)

    if op is not None and 'deltaTemperature' in payload:
        new = op(temperature, float(payload['deltaTemperature']['value']))
        # Clamp the allowed temperature for relative adjustments
        if temperature != max_temp and temperature != min_temp:
            if new < min_temp:
                new = min_temp
            elif new > max_temp:
                new = max_temp
    else:
        new = float(payload['targetTemperature']['value'])

    if new > max_temp or new < min_temp:
        raise ValueOutOfRangeError(min_temp, max_temp)

    # Only 3 allowed values for mode in this response
    if mode not in ['AUTO', 'COOL', 'HEAT']:
        current = e.get_current_temperature(state)
        mode = 'COOL' if current >= new else 'HEAT'

    e.set_temperature(new, mode.lower(), state)

    return {'targetTemperature': {'value': new},
            'temperatureMode': {'value': mode},
            'previousState': {
                'targetTemperature': {'value': temperature},
                'mode': {'value': mode}}}


@handle('SetTargetTemperatureRequest')
@control_response('SetTargetTemperatureConfirmation')
def handle_set_target_temperature(ha, payload):
    return handle_temperature_adj(ha, payload)


@handle('IncrementTargetTemperatureRequest')
@control_response('IncrementTargetTemperatureConfirmation')
def handle_increment_target_temperature(ha, payload):
    return handle_temperature_adj(ha, payload, operator.add)


@handle('DecrementTargetTemperatureRequest')
@control_response('DecrementTargetTemperatureConfirmation')
def handle_decrement_target_temperature(ha, payload):
    return handle_temperature_adj(ha, payload, operator.sub)


@handle('GetLockStateRequest')
def handle_get_lock_state(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload))
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
    e = mk_entity(ha, payload_to_entity(payload))
    e.set_lock_state(payload["lockState"])
    return {'lockState': payload["lockState"]}


@handle('SetColorRequest')
@control_response('SetColorConfirmation')
def handle_set_color(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.set_color(payload['color']['hue'], payload['color']['saturation'],
                payload['color']['brightness'])
    return {'achievedState': {'color': payload['color']}}


@handle('SetColorTemperatureRequest')
@control_response('SetColorTemperatureConfirmation')
def handle_set_color_temperature(ha, payload):
    e = mk_entity(ha, payload_to_entity(payload), supported_features(payload))
    e.set_color_temperature(payload['colorTemperature']['value'])
    return {'achievedState': {'colorTemperature': payload['colorTemperature']}}


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

        if hasattr(self, 'get_current_temperature'):
            actions.append('getTemperatureReading')
        if hasattr(self, 'set_temperature'):
            actions.append('setTargetTemperature')
        if hasattr(self, 'get_temperature'):
            actions.append('getTargetTemperature')
            actions.append('incrementTargetTemperature')
            actions.append('decrementTargetTemperature')

        if hasattr(self, 'get_lock_state'):
            actions.append('getLockState')
        if hasattr(self, 'set_lock_state'):
            actions.append('setLockState')

        if self.entity_domain == "light":
            if self.supported_features & LIGHT_SUPPORT_RGB_COLOR:
                actions.append('setColor')
            if self.supported_features & LIGHT_SUPPORT_COLOR_TEMP:
                actions.append('setColorTemperature')
                actions.append('incrementColorTemperature')
                actions.append('decrementColorTemperature')

        return actions


class ToggleEntity(Entity):
    def turn_on(self):
        self._call_service('homeassistant/turn_on')

    def turn_off(self):
        self._call_service('homeassistant/turn_off')


class InputSliderEntity(Entity):
    def get_percentage(self):
        state = self.ha.get('states/' + self.entity_id)
        value = state['state']
        minimum = state['attributes']['minimum']
        maximum = state['attributes']['maximum']
        adjusted = value - minimum

        return (adjusted * 100.0 / (maximum - minimum))

    def set_percentage(self, val):
        state = self.ha.get('states/' + self.entity_id)
        minimum = state['attributes']['minimum']
        maximum = state['attributes']['maximum']
        step = state['attributes']['step']
        scaled = val * (maximum - minimum) / 100.0
        rounded = step * round(scaled / step)
        adjusted = rounded + minimum

        self._call_service('input_slider/select_value', {'value': adjusted})


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

    def get_color_temperature(self):
        state = self.ha.get('states/' + self.entity_id)
        current_temperature = state['attributes']['color_temp']
        return (1000000 / current_temperature)

    def set_color(self, hue, saturation, brightness):
        rgb = [int(round(i * 255)) for i in colorsys.hsv_to_rgb(hue / 360.0,
                                                                saturation,
                                                                brightness)]
        self._call_service('light/turn_on', {'rgb_color': rgb})

    def set_color_temperature(self, val):
        self._call_service('light/turn_on',
                           {'color_temp': (1000000 / val)})


class MediaPlayerEntity(ToggleEntity):
    def get_percentage(self):
        state = self.ha.get('states/' + self.entity_id)
        vol = state['attributes']['volume_level']
        return vol * 100.0

    def set_percentage(self, val):
        vol = val / 100.0
        self._call_service('media_player/volume_set', {'volume_level': vol})


class ClimateEntity(Entity):
    def turn_on(self):
        state = self.ha.get('states/' + self.entity_id)
        current = self.get_current_temperature(state)
        temperature, mode = self.get_temperature(state)
        if temperature is None:
            mode = 'auto'
        else:
            mode = 'cool' if current >= temperature else 'heat'
        self._call_service('climate/set_operation_mode',
                           {'operation_mode': mode})

    def turn_off(self):
        self._call_service('climate/set_operation_mode',
                           {'operation_mode': 'off'})

    def get_current_temperature(self, state=None):
        if not state:
            state = self.ha.get('states/' + self.entity_id)
        return convert_temp(
            state['attributes']['current_temperature'],
            state['attributes']['unit_of_measurement'])

    def get_temperature(self, state=None):
        if not state:
            state = self.ha.get('states/' + self.entity_id)
        temperature = convert_temp(
            state['attributes']['temperature'],
            state['attributes']['unit_of_measurement'])
        mode = state['state'].replace('idle', 'off').upper()
        return (temperature, mode)

    def set_temperature(self, val, mode=None, state=None):
        if not state:
            state = self.ha.get('states/' + self.entity_id)
        temperature = convert_temp(
            val,
            to_unit=state['attributes']['unit_of_measurement'])
        data = {'temperature': temperature}
        if mode:
            data['operation_mode'] = mode
        self._call_service('climate/set_temperature', data)


class FanEntity(ToggleEntity):
    def get_percentage(self):
        state = self.ha.get('states/' + self.entity_id)
        speed = state['attributes']['speed']
        if speed == "off":
            return 0
        elif speed == "low":
            return 33
        elif speed == "medium":
            return 66
        elif speed == "high":
            return 100

    def set_percentage(self, val):
        speed = "off"
        if val <= 33:
            speed = "low"
        elif val <= 66:
            speed = "medium"
        elif val <= 100:
            speed = "high"
        self._call_service('fan/set_speed', {'speed': speed})


DOMAINS = {
    'garage_door': GarageDoorEntity,
    'group': ToggleEntity,
    'input_boolean': ToggleEntity,
    'input_slider': InputSliderEntity,
    'switch': ToggleEntity,
    'fan': FanEntity,
    'cover': CoverEntity,
    'lock': LockEntity,
    'script': ScriptEntity,
    'scene': SceneEntity,
    'light': LightEntity,
    'media_player': MediaPlayerEntity,
    'climate': ClimateEntity
}


def mk_entity(ha, entity_id, supported_features=0):
    entity_domain = entity_id.split('.', 1)[0]
    return DOMAINS[entity_domain](ha, entity_id, supported_features)


class Configuration(object):
    def __init__(self, filename=None):
        self._json = {}
        if filename is not None:
            with open(filename) as f:
                self._json = json.load(f)

        opts = {}
        opts['url'] = self.get(['url', 'ha_url'],
                               default='http://localhost:8123/api')
        opts['ssl_verify'] = self.get(['ssl_verify', 'ha_cert'], default=True)
        opts['password'] = self.get(['password', 'ha_passwd'], default='')
        opts['allowed_domains'] = \
            sorted(self.get(['allowed_domains', 'ha_allowed_entities'],
                            default=DOMAINS.keys()))

        default_entity_suffixes = {'group': 'Group', 'scene': 'Scene'}
        opts['entity_suffixes'] = {domain: '' for domain in DOMAINS.keys()}
        opts['entity_suffixes'].update(self.get(['entity_suffixes'],
                                       default=default_entity_suffixes))

        opts['debug'] = self.get(['debug'], default=False)
        self.opts = opts

    def __getattr__(self, name):
        return self.opts[name]

    def get(self, keys, default):
        for key in keys:
            if key in self._json:
                return self._json[key]
        return default

    def dump(self):
        return json.dumps(self.opts, indent=2, separators=(',', ': '))


def event_handler(event, context):
    config = Configuration('config.json')
    if config.debug:
        logger.setLevel(logging.DEBUG)
    ha = HomeAssistant(config)

    name = event['header']['name']
    payload = event['payload']

    logger.debug('calling event handler for %s, payload: %s', name,
                 str({k: v for k, v in payload.items()
                     if k != u'accessToken'}))

    return handlers[name](ha, payload)
