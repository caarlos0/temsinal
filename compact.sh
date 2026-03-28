#!/bin/sh
jq -c . antennas.json >tmp.json && mv tmp.json antennas.json
jq -c . population.json >tmp.json && mv tmp.json population.json
