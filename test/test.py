#!/usr/bin/env python2.7

# Basic tests meant to be run against a demo instance of Home-Assistant
# $ hass --demo

import sys
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


def test_discovery_header():
    assert discovery['header']['namespace'] == 'Alexa.ConnectedHome.Discovery'
    assert discovery['header']['name'] == 'DiscoverAppliancesResponse'


def test_reachable():
    for ap in appliances:
        assert ap['isReachable']


def find_appliance(entity_id):
    for ap in appliances:
        if ap['additionalApplianceDetails']['entity_id'] == entity_id:
            return ap
    return None


def get_state(ap):
    entity_id = ap['additionalApplianceDetails']['entity_id']
    ha = haaska.HomeAssistant(haaska.get_config())
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


def test_switch_on_off_on():
    sw = find_appliance(u'switch.decorative_lights')
    turn_on(sw)
    assert_state_is(sw, 'on')
    turn_off(sw)
    assert_state_is(sw, 'off')
    turn_on(sw)
    assert_state_is(sw, 'on')


def test_switch_turn_on_twice():
    sw = find_appliance(u'switch.decorative_lights')
    turn_on(sw)
    assert_state_is(sw, 'on')
    turn_on(sw)
    assert_state_is(sw, 'on')


def test_switch_turn_off_twice():
    sw = find_appliance(u'switch.decorative_lights')
    turn_off(sw)
    assert_state_is(sw, 'off')
    turn_off(sw)
    assert_state_is(sw, 'off')


def test_light_on_off_on():
    light = find_appliance(u'light.bed_light')
    turn_on(light)
    assert_state_is(light, 'on')
    turn_off(light)
    assert_state_is(light, 'off')
    turn_on(light)
    assert_state_is(light, 'on')


def test_input_boolean_on_off_on():
    ib = find_appliance('input_boolean.notify')
    turn_on(ib)
    assert_state_is(ib, 'on')
    turn_off(ib)
    assert_state_is(ib, 'off')
    turn_on(ib)
    assert_state_is(ib, 'on')


def test_media_player_on_off_on():
    player = find_appliance('media_player.bedroom')
    assert_state_is(player, 'playing')
    turn_off(player)
    assert_state_is(player, 'off')
    turn_on(player)
    assert_state_is(player, 'playing')


def test_lock_off_on_fails():
    lock = find_appliance('lock.kitchen_door')
    assert_raises(UnexpectedResponseException, turn_off, lock)
    assert_raises(UnexpectedResponseException, turn_on, lock)


def test_cover_on_off_on():
    cover = find_appliance('cover.garage_door')
    turn_on(cover)
    assert_state_is(cover, 'open')
    turn_off(cover)
    assert_state_is(cover, 'closed')
    turn_on(cover)
    assert_state_is(cover, 'open')


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


def test_lock_unlock():
    lock = find_appliance('lock.kitchen_door')
    set_lock_state(lock, True)
    assert_state_is(lock, 'locked')
    set_lock_state(lock, False)
    assert_state_is(lock, 'unlocked')
    set_lock_state(lock, True)
    assert_state_is(lock, 'locked')


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


def test_get_lock_state():
    lock = find_appliance('lock.kitchen_door')

    set_lock_state(lock, True)
    assert_state_is(lock, 'locked')
    r = get_lock_state(lock)
    assert r['payload']['lockState'] == 'LOCKED'

    set_lock_state(lock, False)
    assert_state_is(lock, 'unlocked')
    r = get_lock_state(lock)
    assert r['payload']['lockState'] == 'UNLOCKED'


def test_turn_off():
    for ap in appliances:
        if 'turnOff' not in ap['actions']:
            continue
        resp = turn_off(ap)
        assert resp['header']['name'] == 'TurnOffConfirmation'
        assert resp['payload']['success']
        if entity_domain(ap) == 'light' or \
                entity_domain(ap) == 'input_boolean':
            assert get_state(ap)['state'] == 'off'
        elif entity_domain(ap) == 'media_player':
            assert get_state(ap)['state'] == 'off'
        elif entity_domain(ap) == 'garage_door':
            assert get_state(ap)['state'] == 'closed'
        elif entity_domain(ap) == 'lock':
            assert get_state(ap)['state'] == 'unlocked'


def test_turn_on():
    for ap in appliances:
        if 'turnOn' not in ap['actions']:
            continue
        resp = turn_on(ap)
        assert resp['header']['name'] == 'TurnOnConfirmation'
        assert resp['payload']['success']
        if entity_domain(ap) == 'light' or \
                entity_domain(ap) == 'input_boolean':
            assert get_state(ap)['state'] == 'on'
        elif entity_domain(ap) == 'media_player':
            assert get_state(ap)['state'] == 'playing'
        elif entity_domain(ap) == 'garage_door':
            assert get_state(ap)['state'] == 'open'
        elif entity_domain(ap) == 'lock':
            assert get_state(ap)['state'] == 'locked'


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


def test_set_light_percentage():
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
            assert resp['header']['name'] == 'SetPercentageConfirmation'
            assert get_state(ap)['state'] == 'on'
            assert get_brightness(ap) == v


def test_set_volume():
    for ap in appliances:
        if 'setPercentage' not in ap['actions']:
            continue
        if entity_domain(ap) != 'media_player':
            continue
        if (int(get_state(ap)['attributes']['supported_features'])) & 4 == 0:
            continue
        for v in [10, 50, 75, 100]:
            resp = set_percentage(ap, v)
            assert resp['header']['name'] == 'SetPercentageConfirmation'
            assert (get_state(ap)['attributes']['volume_level'] * 100.0) == v


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


def test_dim_light():
    for ap in appliances:
        if 'decrementPercentage' not in ap['actions']:
            continue
        if entity_domain(ap) != 'light':
            continue
        turn_on(ap)
        if 'brightness' not in get_state(ap)['attributes']:
            continue
        set_percentage(ap, 50)
        assert get_brightness(ap) == 50
        resp = dim_light(ap, 20)
        assert resp['header']['name'] == 'DecrementPercentageConfirmation'
        assert get_state(ap)['state'] == 'on'
        assert get_brightness(ap) == 30


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


def test_brighten_light():
    for ap in appliances:
        if 'incrementPercentage' not in ap['actions']:
            continue
        if entity_domain(ap) != 'light':
            continue
        turn_on(ap)
        if 'brightness' not in get_state(ap)['attributes']:
            continue
        set_percentage(ap, 50)
        assert get_brightness(ap) == 50
        resp = brighten_light(ap, 20)
        assert resp['header']['name'] == 'IncrementPercentageConfirmation'
        assert get_state(ap)['state'] == 'on'
        assert get_brightness(ap) == 70
