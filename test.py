import os
import pytest

from haaska import HomeAssistant, Configuration


@pytest.fixture
def configuration() -> Configuration:
    return Configuration(opts_dict={
        "url": "http://localhost:8123",
        "bearer_token": "",
        "debug": False,
        "ssl_verify": True,
        "ssl_client": []
    })


@pytest.fixture
def home_assistant(configuration: Configuration):
    return HomeAssistant(configuration)


def test_ha_build_url(home_assistant: HomeAssistant):
    url = home_assistant.build_url("test")
    assert url == "http://localhost:8123/api/test"


def test_get_user_agent():
    os.environ["AWS_DEFAULT_REGION"] = "test"
    user_agent = HomeAssistant.get_user_agent()
    assert user_agent.startswith("Home Assistant Alexa Smart Home Skill - test - python-requests/")


def test_config_get(configuration: Configuration):
    assert configuration.get(["debug"]) is False
    assert configuration.get(["test"]) is None
    assert configuration.get(["test"], default="default") == "default"


def test_config_get_url(configuration: Configuration):
    test_urls = [
        "http://hass.example.com:8123",
        "http://hass.example.app"
    ]
    for expected_url in test_urls:
        assert configuration.get_url(expected_url + "/") == expected_url
        assert configuration.get_url(expected_url + "/api") == expected_url
        assert configuration.get_url(expected_url + "/api/") == expected_url
