
SHELL := /bin/bash

# Function name in AWS Lambda:
FUNCTION_NAME=ha-bridge

BUILD_DIR=build

build.zip: haaska.py config/*
	mkdir -p $(BUILD_DIR)
	cp $^ $(BUILD_DIR)
	pip install -t $(BUILD_DIR) requests
	cd $(BUILD_DIR); zip ../$@ -r *

.PHONY: deploy
deploy: build.zip
	aws lambda update-function-configuration \
		--function-name $(FUNCTION_NAME) \
		--handler haaska.event_handler
	aws lambda update-function-code \
		--function-name $(FUNCTION_NAME) \
		--zip-file fileb://$<

TEST_PAYLOAD:='                  \
{                                \
  "header": {                    \
    "payloadVersion": "1",       \
    "namespace": "System",       \
    "name": "HealthCheckRequest" \
  },                             \
  "payload": {                   \
    "accessToken": "..."         \
  }                              \
}'

.PHONY: test
test:
	@aws lambda invoke \
		--function-name $(FUNCTION_NAME) \
		--payload ${TEST_PAYLOAD} \
		/dev/fd/3 3>&1 >/dev/null | jq -e '., .payload.isHealthy'

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) build.zip

