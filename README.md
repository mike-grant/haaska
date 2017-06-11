# haaska: Home Assistant Alexa Skill Adapter

[![Join the chat at https://gitter.im/auchter/haaska](https://badges.gitter.im/auchter/haaska.svg)](https://gitter.im/auchter/haaska?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Build Status](https://travis-ci.org/auchter/haaska.svg?branch=master)](https://travis-ci.org/auchter/haaska)

haaska implements a bridge between a [Home Assistant](https://home-assistant.io) instance and the [Smart Home Skill API](https://developer.amazon.com/alexa/smart-home) for Amazon's Alexa. It provides voice control for a connected home managed by Home Assistant, through any Alexa-enabled device. Currently, haaska supports the following entity types:

| Type           | On/Off Supported? | Dim Supported? |
|----------------|-------------------|----------------|
| Climate        | Yes               | Temperature    |
| Cover          | Yes               | No             |
| Fans           | Yes               | Yes (speed)    |
| Groups         | Yes               | No             |
| Input Booleans | Yes               | No             |
| Input Sliders  | No                | Yes (value)    |
| Lights         | Yes               | Yes            |
| Locks          | Lock/Unlock       | No             |
| Media Players  | Yes               | Yes (volume)   |
| Scenes         | Yes               | No             |
| Scripts        | Yes               | No             |
| Switches       | Yes               | No             |

[@brusc](https://github.com/brusc) put together a good [video](https://www.youtube.com/watch?v=zZuwQ9spPkQ) which demonstrates haaska in action, and provides a walkthrough of the setup process.

Note that Home Assistant includes a component (`emulated_hue`) to communicate with Amazon Echo and Google Home devices. `emulated_hue` exposes the entities in Home Assistant as Philips Hue lights. This allows basic voice control without the effort of setting up haaska, but its capabilities are limited compared to an Alexa skill and it does not work with every Alexa-enabled device.

## Setup

1. In the `config/` directory, copy `config.json.sample` to `config.json` and update it. [Below](#config-values) is a listing of properties that `config.json` will accept.

1. Run `make` to build a deployable package of haaska. This will generate a `haaska.zip` file that you'll upload to AWS Lambda (if you're used to docker you can try running make with `docker build -t haaska . && docker run -v "$PWD":/usr/src/app haaska`
1. Register with an OAuth provider, such as Login with Amazon.
    * To use the current version of Login with Amazon, you must go to the [Developer Console](https://developer.amazon.com/)
        * Under "Apps & Services", select "Login with Amazon" (not "Security Profiles")
        * Click "Create a New Security Profile"
        * You can enter anything for the name (which is shown on the login page) and the privacy URL
    * Note the "Client ID" and "Client Secret", as you'll need those later
1. Create an Alexa skill and Lambda Function by following [these instructions](https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/steps-to-create-a-smart-home-skill) (with the modifications noted below).
    * The name of the Alexa skill doesn't matter, but I'd suggest "haaska"
    * The name of the Lambda function does matter; use "haaska", otherwise you'll need to modify the `FUNCTION_NAME` variable in the `Makefile`.
    * For "Runtime", select "Python 2.7" as in the example
    * Select "Upload a .ZIP file" for "Code entry type", and upload `haaska.zip` that you created in step 1.
    * For "Handler", enter `haaska.event_handler`
    * For "Role":
        * Select "Choose an existing role", and underneath, select `lambda_basic_execution` if it exists
        * If `lambda_basic_execution` doesn't exist, select "Create a custom role" instead, and enter `lambda_basic_execution` as the "Role Name"
    * Leave the rest of the defaults alone, and click "Next"
    * Check "Enable event source"
    * Under the "Account Linking" section:
        * Set Authorization URL to: https://www.amazon.com/ap/oa
        * Set the Client ID to the previously noted value from Login with Amazon
        * Set Scope to: `profile`
        * Set Access Token URI to: https://api.amazon.com/auth/o2/token
        * Set Client Secret to the previously noted value from Login with Amazon
        * Note the one or more "Redirect URL(s)"
    * There are two properly sized Home Assistant logos in the images/ folder which you can upload to Amazon for use with your skill. Upload both on the "Publishing Information" step of the process.
1. Go back to Login with Amazon, select "Web Settings" under "Manage" for your security profile, and add each "Redirect URL" from the Lambda function as an "Allowed Return URL".
1. Send a test event by running `make test`, which will validate that haaska can communicate with your Home Assistant instance. Note that you must have the AWS CLI and [jq](https://stedolan.github.io/jq/) installed.

### Config Values

| Key                   | Example Value                                                                                                      | Required? | Notes                                                                                        |
|-----------------------|--------------------------------------------------------------------------------------------------------------------|-----------|----------------------------------------------------------------------------------------------|
| `url`.                | `https://demo.home-assistant.io.`.                                                                                 | **Yes**   | The API endpoint of your Home Assistant instance.                                            |
| `password `           | `securepassword`                                                                                                   | **Yes**   | The API password of your Home Assistant instance.                                            |
| `ssl_verify`          | `mycert.crt`                                                                                                       | No        | This will be passed as the `verify` parameter for all requests; see [here](http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification) for options |
| `allowed_domains`     | `["cover", "garage_door", "group", "input_boolean", "light", "lock", "media_player", "scene", "script", "switch"]` | No        | A JSON array of entity types to expose to Alexa. If not provided, the example value is used. |

## Usage
After completing setup of haaska, tell Alexa: "Alexa, discover my devices". If there is an issue you can go to `Menu / Smart Home` in the [web](http://echo.amazon.com/#smart-home) or mobile app and have Alexa forget all devices, and then do the discovery again. To prevent duplicate devices from appearing, ensure that the `emulated_hue` component of Home Assistant is not enabled.

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
