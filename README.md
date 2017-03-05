# haaska: Home Assistant Alexa Skill Adapter

[![Join the chat at https://gitter.im/auchter/haaska](https://badges.gitter.im/auchter/haaska.svg)](https://gitter.im/auchter/haaska?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

haaska implements a skill adapter to bridge a [Home Assistant](https://home-assistant.io) instance and the Alexa Lighting API. Currently, haaska supports the following entity types:

| Type           | On/Off Supported? | Dim Supported? |
|----------------|-------------------|----------------|
| Groups         | Yes               | No             |
| Input Booleans | Yes               | No             |
| Lights         | Yes               | Yes            |
| Locks          | Lock/Unlock       | No             |
| Media Players  | Yes               | Yes (volume)   |
| Scenes         | Yes               | No             |
| Scripts        | Yes               | No             |
| Switches       | Yes               | No             |

[@brusc](https://github.com/brusc) put together a good [video](https://www.youtube.com/watch?v=zZuwQ9spPkQ) which demonstrates haaska in action, and provides a walkthrough of the setup process.

## Setup

1. In the `config/` directory, copy `config.json.sample` to `config.json` and update it. [Below](#config-values) is a listing of properties that `config.json` will accept.

1. Run `make` to build a deployable package of haaska. This will generate a `haaska.zip` file that you'll upload to AWS Lambda (if you're used to docker you can try running make with `docker build -t haaska . && docker run -v "$PWD":/usr/src/app haaska`
1. Register with an OAuth provider, such as Login with Amazon.
    * Note the "Client ID" and "Client Secret", as you'll need those later
1. Create an Alexa skill and Lambda Function by following [these instructions](https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/steps-to-create-a-smart-home-skill) (with the modifications noted below).
    * The name of the Alexa skill doesn't matter, but I'd suggest "haaska"
    * The name of the Lambda function does matter; use "haaska", otherwise you'll need to modify the `FUNCTION_NAME` variable in the `Makefile`.
    * Select `lambda_basic_execution` for the Lambda role
    * Select "Upload a .ZIP file" for "Code entry type", and upload `haaska.zip` that you created in step 1.
    * For "Handler", enter "haaska.event\_handler"
    * Leave the rest of the defaults alone, and click "Next"
    * Check "Enable event source"
    * Under the "Account Linking" section:
        * Set Authorization URL to: https://www.amazon.com/ap/oa
        * Set the Client ID to the previously noted value from Login with Amazon
        * Set Scope to profile
        * Set Access Token URI to https://api.amazon.com/auth/o2/token
        * Set Client Secret to the previously noted value from Login with Amazon
        * Note the "Redirect URL"
    * There are two properly sized Home Assistant logos in the images/ folder which you can upload to Amazon for use with your skill. Upload both on the "Publishing Information" step of the process.
1. Go back to Login with Amazon and enter the "Redirect URL" as an "Allowed Return URL" for the application you registered.
1. Send a test event by running `make test`, which will validate that haaska can communicate with your Home Assistant instance. Note that you must have the AWS CLI and [jq](https://stedolan.github.io/jq/) installed.

### Config Values

| Key                   | Example Value                                                                      | Required? | Notes                                                                                            |
|-----------------------|------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------|
| `ha_url`              | `https://demo.home-assistant.io/api`                                               | **Yes**   | The API endpoint of your Home Assistant instance. This must end in /api (**no trailing slash**). |
| `ha_passwd`           | `securepassword`                                                                   | **Yes**   | The API password of your Home Assistant instance.                                                |
| `ha_cert`             | `mycert.crt`                                                                       | No        | The name of your self-signed certificate located in the `config/` directory. |
| `ha_allowed_entities` | `["light", "switch", "group", "scene", "media_player", "input_boolean", "script"]` | No        | A JSON array of entity types to expose to Alexa. If not provided, the example value is used.     |

## Usage
After completing setup of haaska, tell Alexa: "Alexa, discover my devices". If there is an issue you can go to `Menu / Smart Home` in the [web](http://echo.amazon.com/#smart-home) or mobile app and have Alexa forget all devices and then do the discovery again.

Then you can say "Alexa, Turn on the office light" or whatever name you have given your configured devices.

Here is the table of possible commands to use to tell Alexa what you want to do:

To do this... | Say this...
--------------|------------
ON Commands |
 | Alexa, turn on `<Device Name>`
 | Alexa, start `<Device Name>`
 | Alexa, unlock `<Device Name>`
 | Alexa, open `<Device Name>`
 | Alexa, boot up `<Device Name>`
 | Alexa, run `<Device Name>`
 | Alexa, arm `<Device Name>`
OFF Commands |
 | Alexa, turn off `<Device Name>`
 | Alexa, stop `<Device Name>` (this one is tricky to get right)
 | Alexa, stop running `<Device Name>` (also very tricky)
 | Alexa, lock `<Device Name>`
 | Alexa, close `<Device Name>`
 | Alexa, shutdown `<Device Name>`
 | Alexa, shut `<Device Name>`
 | Alexa, disarm `<Device Name>`
DIM Commands | `<Position>` is a percentage or a number 1-10
 | Alexa, brighten `<Device Name>` to `<Position>`
 | Alexa, dim `<Device Name> to <Position>`
 | Alexa, raise `<Device Name>` to `<Position>`
 | Alexa, lower `<Device Name>` to `<Position>`
 | Alexa, set `<Device Name>` to `<Position>`
 | Alexa, turn up `<Device Name>` to `<Position>`
 | Alexa, turn down `<Device Name>` to `<Position>`

To see what Alexa thinks you said, you can see the command history under `Menu / Settings / History` in the [web](http://echo.amazon.com/#settings/dialogs) or mobile app.

To view or remove devices that Alexa knows about, you can go to `Menu / Smart Home` in the [web](http://echo.amazon.com/#smart-home) or mobile app.

(Thanks to [ha-bridge](https://github.com/bwssytems/ha-bridge) for originally writing this section!)

## Upgrading

To upgrade to a new version, run `make deploy`

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
  switch.a_switch:
    haaska_hidden: true
```
