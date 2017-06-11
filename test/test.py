#!/usr/bin/env python2.7
# coding: utf-8

# Basic tests meant to be run against a demo instance of Home-Assistant
# $ hass --demo

import sys
import unittest
from nose.tools import assert_raises
sys.path.insert(0, '..')
import haaska  # noqa: E402


def discover_appliance_request():
    return {
        "header": {
            "messageId": "6d6d6e14-8aee-473e-8c24-0d31ff9c17a2",
            "name": "DiscoverAppliancesRequest",
            "namespace": "Alexa.ConnectedHome.Discovery",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": ""
        }
    }


discovery = haaska.event_handler(discover_appliance_request(), None)
appliances = discovery['payload']['discoveredAppliances']


class DiscoveryTests(unittest.TestCase):
    def test_discovery_header(self):
        self.assertEqual(discovery['header']['namespace'],
                         'Alexa.ConnectedHome.Discovery')
        self.assertEqual(discovery['header']['name'],
                         'DiscoverAppliancesResponse')

    def test_reachable(self):
        for ap in appliances:
            self.assertTrue(ap['isReachable'])


def find_appliance(entity_id):
    for ap in appliances:
        if ap['additionalApplianceDetails']['entity_id'] == entity_id:
            return ap
    return None


def get_state(ap):
    entity_id = ap['additionalApplianceDetails']['entity_id']
    ha = haaska.HomeAssistant(haaska.Configuration('config.json'))
    return ha.get('states/' + entity_id)


def entity_domain(ap):
    entity_id = ap['additionalApplianceDetails']['entity_id']
    return entity_id.split('.')[0]


def to_appliance(ap):
    return {"additionalApplianceDetails": ap['additionalApplianceDetails'],
            "applianceId": ap['applianceId']}


class UnexpectedResponseException(Exception):
    pass


def turn_off(ap):
    req = {
        "header": {
            "messageId": "01ebf625-0b89-4c4d-b3aa-32340e894688",
            "name": "TurnOffRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "",
            "appliance": to_appliance(ap)
        }
    }
    resp = haaska.event_handler(req, None)
    if resp['header']['name'] != 'TurnOffConfirmation':
        raise UnexpectedResponseException
    return resp


def turn_on(ap):
    req = {
        "header": {
            "messageId": "01ebf625-0b89-4c4d-b3aa-32340e894688",
            "name": "TurnOnRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "",
            "appliance": to_appliance(ap)
        }
    }
    resp = haaska.event_handler(req, None)
    if resp['header']['name'] != 'TurnOnConfirmation':
        raise UnexpectedResponseException
    return resp


def assert_state_is(ap, state):
    assert get_state(ap)['state'] == state


class OnOffTests(unittest.TestCase):
    def assertStateIs(self, ap, state):
        self.assertEqual(get_state(ap)['state'], state)

    def test_switch_on_off_on(self):
        sw = find_appliance(u'switch.decorative_lights')
        turn_on(sw)
        self.assertStateIs(sw, 'on')
        turn_off(sw)
        self.assertStateIs(sw, 'off')
        turn_on(sw)
        self.assertStateIs(sw, 'on')

    def test_switch_turn_on_twice(self):
        sw = find_appliance(u'switch.decorative_lights')
        turn_on(sw)
        self.assertStateIs(sw, 'on')
        turn_on(sw)
        self.assertStateIs(sw, 'on')

    def test_switch_turn_off_twice(self):
        sw = find_appliance(u'switch.decorative_lights')
        turn_off(sw)
        self.assertStateIs(sw, 'off')
        turn_off(sw)
        self.assertStateIs(sw, 'off')

    def test_light_on_off_on(self):
        light = find_appliance(u'light.bed_light')
        turn_on(light)
        self.assertStateIs(light, 'on')
        turn_off(light)
        self.assertStateIs(light, 'off')
        turn_on(light)
        self.assertStateIs(light, 'on')

    def test_input_boolean_on_off_on(self):
        ib = find_appliance('input_boolean.notify')
        turn_on(ib)
        self.assertStateIs(ib, 'on')
        turn_off(ib)
        self.assertStateIs(ib, 'off')
        turn_on(ib)
        self.assertStateIs(ib, 'on')

    def test_media_player_on_off_on(self):
        player = find_appliance('media_player.bedroom')
        self.assertStateIs(player, 'playing')
        turn_off(player)
        self.assertStateIs(player, 'off')
        turn_on(player)
        self.assertStateIs(player, 'playing')

    def test_climate_on_off_on(self):
        climate = find_appliance('climate.ecobee')
        self.assertIn(get_state(climate)['state'], ['auto', 'cool', 'heat'])
        turn_off(climate)
        self.assertStateIs(climate, 'off')
        turn_on(climate)
        self.assertIn(get_state(climate)['state'], ['auto', 'cool', 'heat'])

    def test_lock_off_on_fails(self):
        lock = find_appliance('lock.kitchen_door')
        assert_raises(UnexpectedResponseException, turn_off, lock)
        assert_raises(UnexpectedResponseException, turn_on, lock)

    def test_cover_on_off_on(self):
        cover = find_appliance('cover.garage_door')
        turn_on(cover)
        self.assertStateIs(cover, 'open')
        turn_off(cover)
        self.assertStateIs(cover, 'closed')
        turn_on(cover)
        self.assertStateIs(cover, 'open')

    def test_turn_off(self):
        for ap in appliances:
            if 'turnOff' not in ap['actions']:
                continue
            resp = turn_off(ap)
            self.assertEqual(resp['header']['name'], 'TurnOffConfirmation')
            self.assertTrue(resp['payload']['success'])
            if entity_domain(ap) == 'light' or \
                    entity_domain(ap) == 'input_boolean':
                self.assertStateIs(ap, 'off')
            elif entity_domain(ap) == 'media_player':
                self.assertStateIs(ap, 'off')
            elif entity_domain(ap) == 'climate':
                self.assertStateIs(ap, 'off')
            elif entity_domain(ap) == 'garage_door':
                self.assertStateIs(ap, 'closed')
            elif entity_domain(ap) == 'lock':
                self.assertStateIs(ap, 'unlocked')

    def test_turn_on(self):
        for ap in appliances:
            if 'turnOn' not in ap['actions']:
                continue
            resp = turn_on(ap)
            self.assertEqual(resp['header']['name'], 'TurnOnConfirmation')
            self.assertTrue(resp['payload']['success'])
            if entity_domain(ap) == 'light' or \
                    entity_domain(ap) == 'input_boolean':
                self.assertStateIs(ap, 'on')
            elif entity_domain(ap) == 'media_player':
                self.assertStateIs(ap, 'playing')
            elif entity_domain(ap) == 'climate':
                self.assertIn(get_state(ap)['state'], ['auto', 'cool', 'heat'])
            elif entity_domain(ap) == 'garage_door':
                self.assertStateIs(ap, 'open')
            elif entity_domain(ap) == 'lock':
                self.assertStateIs(ap, 'locked')


def set_lock_state(ap, locked):
    req = {
        "header": {
            "messageId": "01ebf625-0b89-4c4d-b3aa-32340e894688",
            "name": "SetLockStateRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
            "lockState": "LOCKED" if locked else "UNLOCKED"
        }
    }

    resp = haaska.event_handler(req, None)
    if resp['header']['name'] != 'SetLockStateConfirmation':
        raise UnexpectedResponseException
    return resp


def get_lock_state(ap):
    req = {
        "header": {
            "messageId": "01ebf625-0b89-4c4d-b3aa-32340e894688",
            "name": "GetLockStateRequest",
            "namespace": "Alexa.ConnectedHome.Query",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
        }
    }

    resp = haaska.event_handler(req, None)
    if resp['header']['name'] != 'GetLockStateResponse':
        raise UnexpectedResponseException
    return resp


class LockTests(unittest.TestCase):
    # TODO: don't copy this all over
    def assertStateIs(self, ap, state):
        self.assertEqual(get_state(ap)['state'], state)

    def test_lock_unlock(self):
        lock = find_appliance('lock.kitchen_door')
        set_lock_state(lock, True)
        self.assertStateIs(lock, 'locked')
        set_lock_state(lock, False)
        self.assertStateIs(lock, 'unlocked')
        set_lock_state(lock, True)
        self.assertStateIs(lock, 'locked')

    def test_get_lock_state(self):
        lock = find_appliance('lock.kitchen_door')

        set_lock_state(lock, True)
        self.assertStateIs(lock, 'locked')
        r = get_lock_state(lock)
        self.assertEqual(r['payload']['lockState'], 'LOCKED')

        set_lock_state(lock, False)
        self.assertStateIs(lock, 'unlocked')
        r = get_lock_state(lock)
        self.assertEqual(r['payload']['lockState'], 'UNLOCKED')


def set_percentage(ap, percentage):
    req = {
        "header": {
            "messageId": "95872301-4ff6-4146-b3a4-ae84c760c13e",
            "name": "SetPercentageRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "",
            "appliance": to_appliance(ap),
            "percentageState": {
                "value": percentage
            }
        }
    }
    return haaska.event_handler(req, None)


def get_brightness(ap):
    b = (get_state(ap)['attributes']['brightness'] * 100) / 255.0
    b = int(b + 0.5)
    return b


class PercentageTests(unittest.TestCase):
    def test_set_light_percentage(self):
        for ap in appliances:
            if 'setPercentage' not in ap['actions']:
                continue
            if entity_domain(ap) != 'light':
                continue
            turn_on(ap)
            if 'brightness' not in get_state(ap)['attributes']:
                continue
            for v in [10, 50, 75, 100]:
                resp = set_percentage(ap, v)
                self.assertEqual(resp['header']['name'],
                                 'SetPercentageConfirmation')
                self.assertEqual(get_state(ap)['state'], 'on')
                self.assertEqual(get_brightness(ap), v)

    def test_set_volume(self):
        for ap in appliances:
            if 'setPercentage' not in ap['actions']:
                continue
            if entity_domain(ap) != 'media_player':
                continue
            features = get_state(ap)['attributes']['supported_features']
            if int(features) & 4 == 0:
                continue
            for v in [10, 50, 75, 100]:
                resp = set_percentage(ap, v)
                self.assertEqual(resp['header']['name'],
                                 'SetPercentageConfirmation')
                level = get_state(ap)['attributes']['volume_level'] * 100.0
                self.assertEqual(level, v)


def convert_temp(temp, from_unit=u'°C', to_unit=u'°C'):
    if temp is None or from_unit == to_unit:
        return temp
    if from_unit == u'°C':
        return temp * 1.8 + 32
    else:
        return (temp - 32) / 1.8


def get_temperature_reading(ap):
    req = {
        "header": {
            "messageId": "01ebf625-0b89-4c4d-b3aa-32340e894689",
            "name": "GetTemperatureReadingRequest",
            "namespace": "Alexa.ConnectedHome.Query",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
        }
    }

    resp = haaska.event_handler(req, None)
    if resp['header']['name'] != 'GetTemperatureReadingResponse':
        raise UnexpectedResponseException
    return resp


def set_target_temperature(ap, temperature):
    req = {
        "header": {
            "messageId": "95872301-4ff6-4146-b3a4-ae84c760c13f",
            "name": "SetTargetTemperatureRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
            "targetTemperature": {
                "value": temperature
            }
        }
    }
    return haaska.event_handler(req, None)


def lower_target_temperature(ap, temperature):
    req = {
        "header": {
            "messageId": "95872301-4ff6-4146-b3a4-ae84c760c140",
            "name": "DecrementTargetTemperatureRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
            "deltaTemperature": {
                "value": temperature
            }
        }
    }
    return haaska.event_handler(req, None)


class ClimateTests(unittest.TestCase):
    def test_get_current_temperature(self):
        climate = find_appliance('climate.heatpump')
        r = get_temperature_reading(climate)
        self.assertEqual(r['payload']['temperatureReading']['value'], 25)
        climate = find_appliance('climate.hvac')
        r = get_temperature_reading(climate)
        self.assertEqual(r['payload']['temperatureReading']['value'], 22)
        climate = find_appliance('climate.ecobee')
        r = get_temperature_reading(climate)
        self.assertEqual(r['payload']['temperatureReading']['value'], 23)

    def test_set_temperature(self):
        for ap in appliances:
            if 'setTargetTemperature' not in ap['actions']:
                continue
            if entity_domain(ap) != 'climate':
                continue
            turn_on(ap)
            if 'temperature' not in get_state(ap)['attributes']:
                continue
            for t in [10, 15, 20, 25]:
                r = set_target_temperature(ap, t)
                self.assertEqual(r['header']['name'],
                                 'SetTargetTemperatureConfirmation')
                self.assertEqual(t, convert_temp(
                    get_state(ap)['attributes']['temperature'],
                    get_state(ap)['attributes']['unit_of_measurement']))

    def test_lower_temperature(self):
        for ap in appliances:
            if 'decrementTargetTemperature' not in ap['actions']:
                continue
            if entity_domain(ap) != 'climate':
                continue
            turn_on(ap)
            if 'temperature' not in get_state(ap)['attributes']:
                continue
            t = 20
            set_target_temperature(ap, t)
            self.assertEqual(t, convert_temp(
                get_state(ap)['attributes']['temperature'],
                get_state(ap)['attributes']['unit_of_measurement']))

            r = lower_target_temperature(ap, 5)
            self.assertEqual(r['header']['name'],
                             'DecrementTargetTemperatureConfirmation')
            t = 15
            self.assertEqual(t, convert_temp(
                get_state(ap)['attributes']['temperature'],
                get_state(ap)['attributes']['unit_of_measurement']))


def dim_light(ap, val):
    req = {
        "header": {
            "messageId": "7048c18d-4141-4871-bf0e-da3e54dee3f7",
            "name": "DecrementPercentageRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
            "deltaPercentage": {
                "value": val
            }
        }
    }
    return haaska.event_handler(req, None)


def brighten_light(ap, val):
    req = {
        "header": {
            "messageId": "7048c18d-4141-4871-bf0e-da3e54dee3f7",
            "name": "IncrementPercentageRequest",
            "namespace": "Alexa.ConnectedHome.Control",
            "payloadVersion": "2"
        },
        "payload": {
            "accessToken": "[OAuth Token here]",
            "appliance": to_appliance(ap),
            "deltaPercentage": {
                "value": val
            }
        }
    }
    return haaska.event_handler(req, None)


class LightTests(unittest.TestCase):
    def test_brighten_light(self):
        for ap in appliances:
            if 'incrementPercentage' not in ap['actions']:
                continue
            if entity_domain(ap) != 'light':
                continue
            turn_on(ap)
            if 'brightness' not in get_state(ap)['attributes']:
                continue
            set_percentage(ap, 50)
            self.assertEqual(get_brightness(ap), 50)
            resp = brighten_light(ap, 20)
            self.assertEqual(resp['header']['name'],
                             'IncrementPercentageConfirmation')
            self.assertEqual(get_state(ap)['state'], 'on')
            self.assertEqual(get_brightness(ap), 70)

    def test_dim_light(self):
        for ap in appliances:
            if 'decrementPercentage' not in ap['actions']:
                continue
            if entity_domain(ap) != 'light':
                continue
            turn_on(ap)
            if 'brightness' not in get_state(ap)['attributes']:
                continue
            set_percentage(ap, 50)
            self.assertEqual(get_brightness(ap), 50)
            resp = dim_light(ap, 20)
            self.assertEqual(resp['header']['name'],
                             'DecrementPercentageConfirmation')
            self.assertEqual(get_state(ap)['state'], 'on')
            self.assertEqual(get_brightness(ap), 30)
