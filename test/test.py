#!/usr/bin/env python2.7
# coding: utf-8

# Basic tests meant to be run against a demo instance of Home-Assistant
# $ hass --demo

import haaska  # noqa: E402
import sys
import unittest
sys.path.insert(0, '..')


def discover_appliance_request():
    return {
            "directive": {
                "header": {
                    "namespace": "Alexa.Discovery",
                    "name": "Discover",
                    "payloadVersion": "3",
                    "messageId": "1bd5d003-31b9-476f-ad03-71d471922820"
                },
                "payload": {
                    "scope": {
                        "type": "BearerToken",
                        "token": "access-token-from-skill"
                    }
                }
            }
        }


discovery = haaska.event_handler(discover_appliance_request(), None)
appliances = discovery['event']['payload']['endpoints']


class DiscoveryTests(unittest.TestCase):
    def test_discovery_header(self):
        self.assertEqual(discovery['event']['header']['namespace'],
                         'Alexa.Discovery')
        self.assertEqual(discovery['event']['header']['name'],
                         'Discover.Response')
