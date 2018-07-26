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
import requests
import boto3
from sshtunnel import SSHTunnelForwarder
from base64 import b64decode

logger = logging.getLogger()


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
        self.session.cert = config.ssl_client

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
        opts['ssl_client'] = self.get(['ssl_client'], default='')
        opts['debug'] = self.get(['debug'], default=False)
        opts['ssh_enabled'] = self.get(['ssh_enabled'], default=False)
        if opts['ssh_enabled']:
            opts['ssh_username'] = self.get(['ssh_username'], default='')
            opts['ssh_remote_host_public_url'] = self.get(
                ['ssh_remote_host_public_url'], default='')
            opts['ssh_remote_host_public_port'] = self.get(
                ['ssh_remote_host_public_port'], default=22)
            opts['ssh_remote_host_private_url'] = self.get(
                ['ssh_remote_host_private_url'], default='0.0.0.0')
            opts['ssh_remote_host_private_port'] = self.get(
                ['ssh_remote_host_private_port'], default=8123)
            opts['ssh_local_host_port'] = self.get(
                ['ssh_local_host_port'], default=8123)
            opts['ssh_key_is_encrypted'] = self.get(
                ['ssh_key_is_encrypted'], default=False)
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


DECRYPTED_SSH_KEY_PASS = ""


def get_decrypted_ssh_key_pass():
    global DECRYPTED_SSH_KEY_PASS
    if not DECRYPTED_SSH_KEY_PASS:
        password = os.environ['ssh_key_pass']
        DECRYPTED_SSH_KEY_PASS = boto3.client('kms').decrypt(
            CiphertextBlob=b64decode(password))['Plaintext']
    return DECRYPTED_SSH_KEY_PASS


def event_handler(event, context):
    config = Configuration('config.json')
    if config.debug:
        logger.setLevel(logging.DEBUG)
    if config.ssh_enabled:
        ssh_tunnel = SSHTunnelForwarder(
            (config.ssh_remote_host_public,
             config.ssh_remote_host_public_port),
            ssh_username=config.ssh_username,
            ssh_pkey="./ssh.key",
            ssh_private_key_password=(get_decrypted_ssh_key_pass()
                                      if config.ssh_key_is_encrypted
                                      else os.environ['ssh_key_pass']),
            remote_bind_address=(config.ssh_remote_host_private,
                                 config.ssh_remote_host_private_port),
            local_bind_address=('0.0.0.0', config.ssh_local_host_port)
        )
        ssh_tunnel.start()

    ha = HomeAssistant(config)
    result = ha.post('alexa/smart_home', event, wait=True).json()

    if config.ssh_enabled:
        ssh_tunnel.stop()

    return result
