# haaska Changelog

## [0.5] - 2018-09-18
###
- Breaking Change: Remove support for the legacy_auth provider in homeassistant
- Implemented authentication using Long-Lived Access Tokens

## [0.4] - 2018-01-24
###
- Changed code to work with Hass 0.62, please note this skill will break on any version older than this.

## [0.3.1] - 2017-06-24
### Changed
- Hotfix for a logic error in exposed/hidden entities.
- Fixed a few formatting and link errors in the changelog.

## [0.3] - 2017-06-24
### Added
- There's now a `discover` target in the `Makefile`, which will send a discovery
  request to your running haaska instance using the AWS CLI and print the
  results using `jq`. This is helpful for debugging configuration changes.
- Color temperature can now be incremented and decremented (*"Alexa, make lamp
  cooler"*, *"Alexa, make lamp warmer"*).
- `input_slider`, `automation`, and `alert` entities are now supported.
- There's now a configuration option to hide Home Assistant entities by default.

### Changed
- haaska will no longer wait for a response from a POST to Home Assistant. This
  reduces the delay between issuing a command and getting a confirmation from
  Alexa on some devices.
- haaska will now accept numbers encoded as strings for thermostat commands.
  This makes haaska a bit more robust, since these commands seem to have
  inconsistent types at times.

## [0.2] - 2017-05-07
### Added
- Support for controlling the color (*"Alexa, turn kitchen green"*) and color
  temperature (*"Alexa, set lamp to cool white"*) of lights.
- Support for controlling fans.

### Changed
- The format of `config.json` has changed, though old formats are still
  supported. To migrate to the new format, run `make modernize_config`.
- Instead of the hardcoded "Group" and "Scene" suffixes on entities in those
  domains, the suffix is now configurable on a per-domain basis using the
  `entity_suffixes` key in the configuration file.
- Entities hidden in Home Assistant (via the `hidden` attribute) are now hidden
  from haaska.
- Improved logging, and added a way to increase verbosity for
  debugging. Set the `debug` key in the configuration to `true`
  to enable more verbose logging to CloudWatch.

## [0.1] - 2017-03-19

First tagged release.

[unreleased]: https://github.com/auchter/haaska/tree/dev
[0.3.1]: https://github.com/auchter/haaska/tree/0.3.1
[0.3]: https://github.com/auchter/haaska/tree/0.3
[0.2]: https://github.com/auchter/haaska/tree/0.2
[0.1]: https://github.com/auchter/haaska/tree/0.1
