#!/bin/bash

# Ensure we have /workspace in all scenarios
mkdir -p /workspace

if [[ ! -d /workspace/test ]]
then
	mv /test /workspace
	# Set permissions right for directory
    chmod -R 777 /workspace/test
else
	rm -rf /test
fi

# Linking
rm -rf /test
ln -s /workspace/test /test
