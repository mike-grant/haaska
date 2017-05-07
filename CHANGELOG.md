# haaska Changelog

## [0.2] - 2017-05-07
### Added
- Support for controlling the color ("Alexa, turn kitchen green") and color
temperature ("Alexa, set lamp to cool white") of lights. 
- Support for controlling fans 

### Changed
- The format of `config.json` has changed, though old formats are still
supported. To migrate to the new format, run `make modernize_config`.
- Instead of the hardcoded "Group" and "Scene" suffixes on entities in those
domains, the suffix is now configurable on a per-domain basis using the
`entity_suffixes` key in the configuration file. 

## [0.1] - 2017-03-19

First tagged release.


