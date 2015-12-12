# haaska: Home Assistant Alexa Skill Adapter

haaska implements a skill adapter to bridge a Home Assistant instance and the
Alexa Lighting API. In short, this allows you to control lights, switches, and
scenes exposed by your Home Assistant instance using an Amazon Echo.

Examples:

- "Alexa, set kitchen to twenty percent"
- "Alexa, turn on evening scene"
- "Alexa, turn off bedroom light"

## Setup

Lighting skill adapters must run on AWS Lambda, and the initial setup is unfortunately a manual process. 

1. Create an AWS Lambda function using [these instructions](https://developer.amazon.com/public/binaries/content/assets/html/alexa-lighting-api.html#creating-a-lambda-function). Name the function "ha-bridge".
2. Follow the rest of the [Lighting API provisioning steps](https://developer.amazon.com/public/binaries/content/assets/html/alexa-lighting-api.html#what-you-need-to-do-return). Note that the Lighting Skill API requires the use of OAuth; you can use [Login with Amazon](http://login.amazon.com) for this purpose; haaska does not currently perform any authentication.
3. In the `config/` directory, create a `config.json` file. This file must contain a single object with an `ha_url` key for the API endpoint of your Home Assistant instance, and `ha_passwd` key for the its API password. If you're using HTTPS with a self-signed certificate, put the CA certificate in the `config/` directory and add a `ha_cert` key with the certificate's filename.
4. Run "make" to generate "build.zip", which you can then manually upload to AWS Lambda. Alternatively, if you have the AWS CLI configured correctly, run "make deploy" to deploy to AWS Lambda.
