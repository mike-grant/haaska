#!/usr/bin/env python3.6
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

import os
import json
import logging
import operator
import requests
import colorsys
import datetime
from uuid import uuid4

logger = logging.getLogger()


LIGHT_SUPPORT_COLOR_TEMP = 2
LIGHT_SUPPORT_RGB_COLOR = 16
LIGHT_SUPPORT_XY_COLOR = 64


class HomeAssistant(object):
    def __init__(self, config):
        self.config = config
        self.url = config.url.rstrip('/')
        agent_str = 'Home Assistant Alexa Smart Home Skill - %s - %s'
        agent_fmt = agent_str % (os.environ['AWS_DEFAULT_REGION'],
                                 requests.utils.default_user_agent())
        self.session = requests.Session()
        self.session.headers = {'x-ha-access': config.password,
                                'content-type': 'application/json',
                                'User-Agent': agent_fmt}
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
            logger.debug('calling %s with %s', relurl, str(d))
            r = self.session.post(self.build_url(relurl),
                                  data=json.dumps(d),
                                  timeout=(None, read_timeout))
            r.raise_for_status()
        except requests.exceptions.ReadTimeout:
            # Allow response timeouts after request was sent
            logger.debug('request for %s sent without waiting for response',
                         relurl)
        return r


class ConnectedHomeCall(object):
    def __init__(self, namespace, name, ha, payload, endpoint):
        logger.debug('Building connected home call %s, %s, %s', namespace,
                     name, payload)
        self.namespace = namespace
        self.name = name
        self.response_name = self.name + '.Response'
        self.ha = ha
        self.payload = payload
        self.endpoint = endpoint
        self.entity = None
        self.context_properties = []
        # if 'appliance' in self.payload:
        #    details = payload['appliance']['additionalApplianceDetails']
        #    self.entity = mk_entity(ha, details['entity_id'])
        if self.endpoint and ('endpointId' in self.endpoint):
            self.entity = mk_entity(ha, self.endpoint['endpointId']
                                    .replace(':', '.'))

    class ConnectedHomeException(Exception):
        def __init__(self, name="DriverInternalError", payload={}):
            self.error_name = name
            self.payload = payload

    class ValueOutOfRangeError(ConnectedHomeException):
        def __init__(self, minValue, maxValue):
            self.error_name = 'ValueOutOfRangeError'
            self.payload = {'minimumValue': minValue, 'maximumValue': maxValue}

    def invoke(self, name):
        logger.debug('invoking %s %s', self.namespace, name)
        r = {'event': {}}
        try:
            payload = operator.attrgetter(name)(self)()
            if payload:
                r['event']['payload'] = payload
            else:
                r['event']['payload'] = {'success': True}
            logger.debug('response payload: %s', str(r['event']))
        except ConnectedHomeCall.ConnectedHomeException as e:
            logger.exception('handler failed: %s, %s', e.error_name, e.payload)
            self.response_name = e.error_name
            r['event']['payload'] = e.payload
        except Exception:
            logger.exception('handler failed unexpectedly')
            self.response_name = 'DriverInternalError'
            r['event']['payload'] = {}

        r['event']['header'] = {'namespace': self.namespace,
                                'messageId': str(uuid4()),
                                'name': self.response_name,
                                'payloadVersion': '3',
                                'correlationToken': '123456'
                                }
        return r


class Alexa(object):
    class Discovery(ConnectedHomeCall):
        def Discover(self):
            try:
                return {'endpoints': discover_appliances(self.ha)}
            except Exception:
                logger.exception('v3 DiscoverAppliancesRequest failed')

    class PowerController(ConnectedHomeCall):
        def TurnOn(self):
            self.entity.turn_on()
            self.context_properties.append({
                "namespace": "Alexa.PowerController",
                "name": "powerState",
                "value": "ON",
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

        def TurnOff(self):
            self.entity.turn_off()
            self.context_properties.append({
                "namespace": "Alexa.PowerController",
                "name": "powerState",
                "value": "OFF",
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

    class BrightnessController(ConnectedHomeCall):
        def AdjustBrightness(self):
            percentage = self.payload['brightness']
            self.entity.set_percentage(percentage)
            self.context_properties.append({
                "namespace": "Alexa.BrightnessController",
                "name": "brightness",
                "value": percentage,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

        def SetBrightness(self):
            delta = self.payload['brightnessDelta']
            val = self.entity.get_percentage()
            val += delta
            if val < 0.0:
                val = 0
            elif val >= 100.0:
                val = 100.0
            self.entity.set_percentage(val)
            self.context_properties.append({
                "namespace": "Alexa.BrightnessController",
                "name": "brightness",
                "value": val,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

    class PercentageController(ConnectedHomeCall):
        def SetPercentage(self):
            percentage = self.payload['percentage']
            self.entity.set_percentage(percentage)
            self.context_properties.append({
                "namespace": "Alexa.PercentageController",
                "name": "percentage",
                "value": percentage,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

        def AdjustPercentage(self):
            delta = self.payload['percentageDelta']
            val = self.entity.get_percentage()
            val += delta
            if val < 0.0:
                val = 0
            elif val >= 100.0:
                val = 100.0
            self.entity.set_percentage(val)
            self.context_properties.append({
                "namespace": "Alexa.PercentageController",
                "name": "percentage",
                "value": val,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

    class ColorTemperatureController(ConnectedHomeCall):
        def DecreaseColorTemperature(self):
            current = self.entity.get_color_temperature()
            new = current - 500
            self.entity.set_color_temperature(new)
            self.context_properties.append({
                "namespace": "Alexa.ColorTemperatureController",
                "name": "colorTemperatureInKelvin",
                "value": new,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

        def IncreaseColorTemperature(self):
            current = self.entity.get_color_temperature()
            new = current + 500
            self.entity.set_color_temperature(new)
            self.context_properties.append({
                "namespace": "Alexa.ColorTemperatureController",
                "name": "colorTemperatureInKelvin",
                "value": new,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

        def SetColorTemperature(self):
            temp = self.payload['colorTemperatureInKelvin']
            self.entity.set_color_temperature(temp)
            self.context_properties.append({
                "namespace": "Alexa.ColorTemperatureController",
                "name": "colorTemperatureInKelvin",
                "value": temp,
                "timeOfSample": datetime.datetime.utcnow().isoformat(),
                "uncertaintyInMilliseconds": 200
            })

    class ConnectedHome(object):
        class System(ConnectedHomeCall):
            def HealthCheckRequest(self):
                try:
                    self.ha.get('states')
                    return {'isHealthy': True}
                except Exception as e:
                    logger.exception('HealthCheckRequest failed')
                    return {'isHealthy': False, 'description': str(e)}

        class Discovery(ConnectedHomeCall):
            def DiscoverAppliancesRequest(self):
                try:
                    return {'discoveredAppliances':
                            discover_appliances(self.ha)}
                except Exception:
                    logger.exception('DiscoverAppliancesRequest failed')
                    # v2 documentation is unclear as to what should be returned
                    # here if discovery fails, so in the mean-time, just return
                    # 0 devices and log the error
                    return {'discoveredAppliances': {}}

        class Control(ConnectedHomeCall):
            def __init__(self, namespace, name, ha, payload):
                super(Alexa.ConnectedHome.Control, self).__init__(
                    namespace, name, ha, payload)
                self.response_name = name.replace('Request', 'Confirmation')

            def TurnOnRequest(self):
                self.entity.turn_on()

            def TurnOffRequest(self):
                self.entity.turn_off()

            def SetPercentageRequest(self):
                percentage = self.payload['percentageState']['value']
                self.entity.set_percentage(percentage)

            def handle_percentage_adj(self, deltaValue):
                current = self.entity.get_percentage()
                new = current + deltaValue

                # So this looks weird, but the relative adjustments seem to
                # always be +/- 25%, which means depending on the current
                # brightness we could over-/undershoot the acceptable range.
                # Instead, if we're not currently saturated, clamp the desired
                # brightness to the allowed brightness.
                if current != 100 and current != 0:
                    if new < 0:
                        new = 0
                    elif new > 100:
                        new = 100

                if new > 100 or new < 0:
                    raise ConnectedHomeCall.ValueOutOfRangeError(0, 100)

                self.entity.set_percentage(new)

            def IncrementPercentageRequest(self):
                deltaValue = self.payload['deltaPercentage']['value']
                return self.handle_percentage_adj(deltaValue)

            def DecrementPercentageRequest(self):
                deltaValue = -self.payload['deltaPercentage']['value']
                return self.handle_percentage_adj(deltaValue)

            def handle_color_temperature_adj(self, op):
                current = self.entity.get_color_temperature()
                new = op(current, 500)
                self.entity.set_color_temperature(new)
                return {'achievedState': {'colorTemperature': {'value': new}}}

            def IncrementColorTemperatureRequest(self):
                return self.handle_color_temperature_adj(operator.add)

            def DecrementColorTemperatureRequest(self):
                return self.handle_color_temperature_adj(operator.sub)

            def SetColorTemperatureRequest(self):
                temp = self.payload['colorTemperature']['value']
                self.entity.set_color_temperature(temp)
                return {'achievedState': {'colorTemperature': {'value': temp}}}

            def handle_temperature_adj(self, op=None):
                state = self.ha.get('states/' + self.entity.entity_id)
                unit = state['attributes']['unit_of_measurement']
                min_temp = convert_temp(state['attributes']['min_temp'], unit)
                max_temp = convert_temp(state['attributes']['max_temp'], unit)

                temperature, mode = self.entity.get_temperature(state)

                if op is not None and 'deltaTemperature' in self.payload:
                    new = op(temperature,
                             float(self.payload['deltaTemperature']['value']))
                    # Clamp the allowed temperature for relative adjustments
                    if temperature != max_temp and temperature != min_temp:
                        if new < min_temp:
                            new = min_temp
                        elif new > max_temp:
                            new = max_temp
                else:
                    new = float(self.payload['targetTemperature']['value'])

                if new > max_temp or new < min_temp:
                    raise ConnectedHomeCall.ValueOutOfRangeError(min_temp,
                                                                 max_temp)

                # Only 3 allowed values for mode in this response
                if mode not in ['AUTO', 'COOL', 'HEAT']:
                    current = self.entity.get_current_temperature(state)
                    mode = 'COOL' if current >= new else 'HEAT'

                self.entity.set_temperature(new, mode.lower(), state)

                return {'targetTemperature': {'value': new},
                        'temperatureMode': {'value': mode},
                        'previousState': {
                            'targetTemperature': {'value': temperature},
                            'mode': {'value': mode}}}

            def SetTargetTemperatureRequest(self):
                return self.handle_temperature_adj()

            def IncrementTargetTemperatureRequest(self):
                return self.handle_temperature_adj(operator.add)

            def DecrementTargetTemperatureRequest(self):
                return self.handle_temperature_adj(operator.sub)

            def SetLockStateRequest(self):
                self.entity.set_lock_state(self.payload["lockState"])
                return {'lockState': self.payload["lockState"]}

            def SetColorRequest(self):
                self.entity.set_color(self.payload['color']['hue'],
                                      self.payload['color']['saturation'],
                                      self.payload['color']['brightness'])
                return {'achievedState': {'color': self.payload['color']}}

        class Query(ConnectedHomeCall):
            def __init__(self, namespace, name, ha, payload):
                super(Alexa.ConnectedHome.Query, self).__init__(
                        namespace, name, ha, payload)

            def GetTemperatureReadingRequest(self):
                temperature = self.entity.get_current_temperature()
                return {'temperatureReading': {'value': temperature}}

            def GetTargetTemperatureRequest(self):
                temperature, mode = self.entity.get_temperature()
                payload = {'targetTemperature': {'value': temperature},
                           'temperatureMode': {'value': mode}}
                if mode not in ['AUTO', 'COOL', 'HEAT', 'OFF']:
                    payload['temperatureMode'] = {
                        'value': 'CUSTOM',
                        'friendlyName': mode.replace('_', ' ').title()}
                return payload

            def GetLockStateRequest(self):
                lock_state = self.entity.get_lock_state().upper()
                return {'lockState': lock_state}


def invoke(namespace, name, ha, payload, endpoint):
    class allowed(object):
        Alexa = Alexa
    make_class = operator.attrgetter(namespace)
    logger.debug('Calling invoke %s, %s, %s, %s, %s', namespace, name, ha,
                 payload, endpoint)
    obj = make_class(allowed)(namespace, name, ha, payload, endpoint)
    return obj.invoke(name)


def discover_appliances(ha):
    def entity_domain(x):
        return x['entity_id'].split('.', 1)[0]

    def is_supported_entity(x):
        return entity_domain(x) in ha.config.exposed_domains

    def is_exposed_entity(x):
        attr = x['attributes']
        if 'haaska_hidden' in attr:
            return not attr['haaska_hidden']
        elif 'hidden' in attr:
            return not attr['hidden']
        else:
            return ha.config.expose_by_default

    def mk_appliance(x):
        features = 0
        if 'supported_features' in x['attributes']:
            features = x['attributes']['supported_features']
        entity = mk_entity(ha, x['entity_id'], features)
        o = {}
        # this needs to be unique and has limitations on allowed characters:
        o['endpointId'] = x['entity_id'].replace('.', ':')
        o['manufacturerName'] = 'Unknown'
        o['modelName'] = 'Unknown'
        o['displayCategories'] = ['SWITCH']
        if 'haaska_name' in x['attributes']:
            o['friendlyName'] = x['attributes']['haaska_name']
        else:
            o['friendlyName'] = x['attributes']['friendly_name']
            suffix = ha.config.entity_suffixes[entity_domain(x)]
            if suffix != '':
                o['friendlyName'] += ' ' + suffix
        if 'haaska_desc' in x['attributes']:
            o['description'] = x['attributes']['haaska_desc']
        else:
            o['description'] = 'Home Assistant ' + \
                entity_domain(x).replace('_', ' ').title()
        o['capabilities'] = entity.get_capabilities()
        return o

    states = ha.get('states')
    return [mk_appliance(x) for x in states if is_supported_entity(x) and
            is_exposed_entity(x)]


def supported_features(payload):
    try:
        details = 'additionalApplianceDetails'
        return payload['appliance'][details]['supported_features']
    except Exception:

        return 0


def convert_temp(temp, from_unit=u'°C', to_unit=u'°C'):
    if temp is None or from_unit == to_unit:
        return temp
    if from_unit == u'°C':
        return temp * 1.8 + 32
    else:
        return (temp - 32) / 1.8


class Entity(object):
    def __init__(self, ha, entity_id, supported_features):
        self.ha = ha
        self.entity_id = entity_id
        self.supported_features = supported_features
        self.entity_domain = self.entity_id.split('.', 1)[0]

    def _call_service(self, service, data={}):
        data['entity_id'] = self.entity_id
        self.ha.post('services/' + service, data)

    def get_capabilities(self):
        capabilities = []
        capabilities.append(
            {
                "type": "AlexaInterface",
                "interface": "Alexa",
                "version": "3"
            })

        if hasattr(self, 'turn_on') or hasattr(self, 'turn_off'):
            capabilities.append(
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.PowerController",
                    "version": "3",
                    "properties": {
                        "supported": [
                            {
                                "name": "powerState"
                            }
                        ],
                        "proactivelyReported": True,
                        "retrievable": True
                    }
                })

        if hasattr(self, 'set_percentage') or hasattr(self, 'get_percentage'):
            capabilities.append(
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.PercentageController",
                    "version": "3",
                    "properties": {
                        "supported": [
                            {
                                "name": "percentage"
                            }
                        ],
                        "proactivelyReported": True,
                        "retrievable": True
                    }
                })

        if hasattr(self, 'get_current_temperature') or hasattr(
                                           self, 'get_temperature'):
            capabilities.append(
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.TemperatureSensor",
                    "version": "3",
                    "properties": {
                        "supported": [
                            {
                                "name": "temperature"
                            }
                        ],
                        "proactivelyReported": True,
                        "retrievable": True
                    }
                })

        if hasattr(self, 'set_temperature'):
            capabilities.append(
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.ThermostatController",
                    "version": "3",
                    "properties": {
                        "supported": [
                            {
                                "name": "upperSetpoint"
                            },
                            {
                                "name": "lowerSetpoint"
                            },
                            {
                                "name": "thermostatMode"
                            }
                        ],
                        "proactivelyReported": True,
                        "retrievable": True
                    }
                })

        if hasattr(self, 'get_lock_state') or hasattr(self, 'set_lock_state'):
            capabilities.append(
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.LockController",
                    "version": "3",
                    "properties": {
                        "supported": [
                            {
                                "name": "lockState"
                            }
                        ],
                        "proactivelyReported": True,
                        "retrievable": True
                    }
                })

        if self.entity_domain == "light":
            if self.supported_features & LIGHT_SUPPORT_RGB_COLOR:
                capabilities.append(
                    {
                        "type": "AlexaInterface",
                        "interface": "Alexa.ColorController",
                        "version": "3",
                        "properties": {
                            "supported": [
                                {
                                    "name": "color"
                                }
                            ],
                            "proactivelyReported": True,
                            "retrievable": True
                        }
                    })
            if self.supported_features & LIGHT_SUPPORT_COLOR_TEMP:
                capabilities.append(
                    {
                        "type": "AlexaInterface",
                        "interface": "Alexa.ColorTemperatureController",
                        "version": "3",
                        "properties": {
                            "supported": [
                                {
                                    "name": "colorTemperatureInKelvin"
                                }
                            ],
                            "proactivelyReported": True,
                            "retrievable": True
                        }
                    })

        return capabilities

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
        value = float(state['state'])
        minimum = state['attributes']['min']
        maximum = state['attributes']['max']
        adjusted = value - minimum

        return (adjusted * 100.0 / (maximum - minimum))

    def set_percentage(self, val):
        state = self.ha.get('states/' + self.entity_id)
        minimum = state['attributes']['min']
        maximum = state['attributes']['max']
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
    'climate': ClimateEntity,
    'alert': ToggleEntity,
    'automation': ToggleEntity
}


def mk_entity(ha, entity_id, supported_features=0):
    entity_domain = entity_id.split('.', 1)[0]
    logger.debug('Making entity w/ domain: %s', entity_domain)
    return DOMAINS[entity_domain](ha, entity_id, supported_features)


class Configuration(object):
    def __init__(self, filename=None, optsDict=None):
        self._json = {}
        if filename is not None:
            with open(filename) as f:
                self._json = json.load(f)

        if optsDict is not None:
            self._json = optsDict

        opts = {}
        opts['url'] = self.get(['url', 'ha_url'],
                               default='http://localhost:8123/api')
        opts['ssl_verify'] = self.get(['ssl_verify', 'ha_cert'], default=True)
        opts['password'] = self.get(['password', 'ha_passwd'], default='')
        opts['exposed_domains'] = \
            sorted(self.get(['exposed_domains', 'ha_allowed_entities'],
                            default=DOMAINS.keys()))

        default_entity_suffixes = {'group': 'Group', 'scene': 'Scene'}
        opts['entity_suffixes'] = {domain: '' for domain in DOMAINS.keys()}
        opts['entity_suffixes'].update(self.get(['entity_suffixes'],
                                       default=default_entity_suffixes))

        opts['expose_by_default'] = self.get(['expose_by_default'],
                                             default=True)
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


def get_directive_version(request):
    try:
        return request["directive"]["header"]["payloadVersion"]
    except Exception:
        try:
            return request["header"]["payloadVersion"]
        except Exception:
            return "-1"


# Lambda entry point
def event_handler(event, context):
    config = Configuration('config.json')
    if config.debug:
        logger.setLevel(logging.DEBUG)
    ha = HomeAssistant(config)
    version = get_directive_version(event)

    if version == "3":
        logger.setLevel(logging.DEBUG)
        directive = event['directive']
        namespace = directive['header']['namespace']
        name = directive['header']['name']

        payload = directive.get('payload')
        endpoint = directive.get('endpoint')

        logger.debug('calling v3 event handler for %s, payload: %s', name, str(
            {k: v for k, v in payload.items()
                if k != u'accessToken'}))

        return invoke(namespace, name, ha, payload, endpoint)
    else:
        logger.debug('calling v2 event handler')
        return ''
