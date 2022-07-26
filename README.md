# haaska: Home Assistant Alexa Skill Adapter

[![Main](https://github.com/mike-grant/haaska/actions/workflows/main.yml/badge.svg)](https://github.com/mike-grant/haaska/actions/workflows/main.yml)

---

haaska implements a bridge between the [Home Assistant Smart Home API](https://www.home-assistant.io/components/alexa/#smart-home) and the [Alexa Smart Home Skill API](https://developer.amazon.com/alexa/smart-home) from Amazon.

This provides voice control for a connected home managed by Home Assistant, through any Alexa-enabled device.

### Getting Started
To get started, head over to the [haaska Wiki](https://github.com/mike-grant/haaska/wiki).

### Development

Run tests

```
python -m pytest test.py
```

### Thanks and Acknowledgement

Thanks to [@auchter](https://github.com/auchter) for creating the original haaska.

Thanks to [@bitglue](https://github.com/bitglue) for his work in getting the Smart Home API exposed via HTTP, making this slimmed down version possible.

This fork of haaska was created by [@mike-grant](https://github.com/mike-grant).

Documentation and additional maintenance is done by [@anthonylavado](https://github.com/anthonylavado), and contributors like you.

### License
haaska is provided under the [MIT License](LICENSE).
