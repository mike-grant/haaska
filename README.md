# haaska: Home Assistant Alexa Skill Adapter

haaska implements a skill adapter to bridge a [Home Assistant](https://home-assistant.io) instance and the Alexa Lighting API. In short, this allows you to control lights, switches, and scenes exposed by your Home Assistant instance using an Amazon Echo.

Examples:

- "Alexa, set kitchen to twenty percent"
- "Alexa, turn on evening scene"
- "Alexa, turn off bedroom light"

## Setup

1. Run `make` to build a deployable package of haaska. This will generate a `haaska.zip` file that you'll upload to AWS Lambda
2. Register with an OAuth provider, such as Login with Amazon.
    * Note the "Client ID" and "Client Secret", as you'll need those later
3. Create an Alexa skill and Lambda Function by following [these instructions](https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/steps-to-create-a-smart-home-skill) (with the modifications noted below).
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
4. Go back to Login with Amazon and enter the "Redirect URL" as an "Allowed Return URL" for the application you registered.
5. In the `config/` directory, create a `config.json` file. This file must contain a single object with an `ha_url` key for the API endpoint of your Home Assistant instance, and `ha_passwd` key for the its API password. If you're using HTTPS with a self-signed certificate, put the CA certificate in the `config/` directory and add a `ha_cert` key with the certificate's filename.
6. Send a test event by running `make test`, which will validate that haaska can communicate with your Home Assistant instance. Note that you must have the AWS CLI and [jq](https://stedolan.github.io/jq/) installed.

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
