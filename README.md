# haaska: Home Assistant Alexa Skill Adapter

haaska implements a skill adapter to bridge a [Home Assistant](https://home-assistant.io) instance and the Alexa Lighting API. In short, this allows you to control lights, switches, and scenes exposed by your Home Assistant instance using an Amazon Echo.

Examples:

- "Alexa, set kitchen to twenty percent"
- "Alexa, turn on evening scene"
- "Alexa, turn off bedroom light"

## Setup

Lighting skill adapters must run on AWS Lambda, and the initial setup is unfortunately a manual process. 

1. Create an AWS Lambda function using [these instructions](https://developer.amazon.com/public/binaries/content/assets/html/alexa-lighting-api.html#creating-a-lambda-function). Name the function `ha-bridge` and specify the handler as `haaska.event_handler`.
2. Follow the rest of the [Lighting API provisioning steps](https://developer.amazon.com/public/binaries/content/assets/html/alexa-lighting-api.html#what-you-need-to-do-return). Note that the Lighting Skill API requires the use of OAuth; you can use [Login with Amazon](http://login.amazon.com) for this purpose; haaska does not currently perform any authentication.
3. In the `config/` directory, create a `config.json` file. This file must contain a single object with an `ha_url` key for the API endpoint of your Home Assistant instance, and `ha_passwd` key for the its API password. If you're using HTTPS with a self-signed certificate, put the CA certificate in the `config/` directory and add a `ha_cert` key with the certificate's filename.
4. Run `make` to generate `build.zip`, which you can then manually upload to AWS Lambda. Alternatively, if you have the AWS CLI configured correctly, run `make deploy` to deploy to AWS Lambda.
5. Send a test event in AWS with:

  ```json
  {
    "header": {
      "payloadVersion": "1",
      "namespace": "Control",
      "name": "DiscoverAppliancesRequest"
    },
    "payload": {
        "accessToken": "whatever"
    }
  }
  ```
Or, if you have the AWS CLI and [jq](https://stedolan.github.io/jq/) installed, you can run `make test`, which will validate that haaska can communicate with your Home Assistant instance.

## Customization

Sometimes the "friendly name" of an entity in Home Assistant differs from what you'd actually like to call that entity when talking to Alexa. haaska provides a mechanism to define a custom name for an entity that will be used via Alexa. This is achieved by adding your entity to a [customize](https://home-assistant.io/getting-started/devices/) block in your `configuration.yaml`, and setting the `haaska_name` key to the desired name.

```yaml
customize:
  light.some_long_light_name:
    haaska_name: Overhead
```
If there's an entity you'd like to hide from haaska, you can do that by adding a `haaska_hidden` tag and setting it to `true`; e.g.:

```yaml
customize:
  switch.a_switch
    haaska_hidden: true
```
