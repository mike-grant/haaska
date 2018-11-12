
SHELL := /bin/bash

# Function name in AWS Lambda:
FUNCTION_NAME=haaska

BUILD_DIR=build

PIPVERSIONEQ9 := $(shell expr `pip3 -V | cut -d ' ' -f 2` \= 9.0.1)

ifneq (,$(wildcard /etc/debian_version))
	ifeq "$(PIPVERSIONEQ9)" "1"
		PIP_VER=3
        	PIP_EXTRA = --system
	endif
else
        PIP_VER =
	PIP_EXTRA =
endif

haaska.zip: haaska.py config/*
	mkdir -p $(BUILD_DIR)
	cp $^ $(BUILD_DIR)
	pip$(PIP_VER) install $(PIP_EXTRA) -t $(BUILD_DIR) requests
	chmod 755 $(BUILD_DIR)/haaska.py
	cd $(BUILD_DIR); zip ../$@ -r *

.PHONY: deploy
deploy: haaska.zip
	aws lambda update-function-configuration \
		--function-name $(FUNCTION_NAME) \
		--handler haaska.event_handler
	aws lambda update-function-code \
		--function-name $(FUNCTION_NAME) \
		--zip-file fileb://$<

DISCOVERY_PAYLOAD:='                                \
{                                                         \
  "directive": {                                          \
    "header": {                                           \
      "namespace": "Alexa.Discovery",                     \
      "name": "Discover",                                 \
      "payloadVersion": "3",                              \
      "messageId": "1bd5d003-31b9-476f-ad03-71d471922820" \
    },                                                    \
    "payload": {                                          \
      "scope": {                                          \
        "type": "BearerToken",                            \
        "token": "access-token-from-skill"                \
      }                                                   \
    }                                                     \
  }                                                       \
}'

.PHONY: discover
discover:
	@aws lambda invoke \
		--function-name $(FUNCTION_NAME) \
		--payload ${DISCOVERY_PAYLOAD} \
		/dev/fd/3 3>&1 >/dev/null | jq '.'


.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) haaska.zip

.PHONY: sample_config
sample_config:
	python -c 'from haaska import Configuration; print(Configuration().dump())' > config/config.json.sample

.PHONY: modernize_config
modernize_config: config/config.json
	@python -c 'from haaska import Configuration; print(Configuration("config/config.json").dump())' > config/config.json.modernized
	@echo Generated config/config.json.modernized from your existing config/config.json
	@echo Inspect that file and replace config/config.json with it to update your configuration
