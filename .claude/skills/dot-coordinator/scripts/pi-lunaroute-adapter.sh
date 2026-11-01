#!/bin/sh
export LUNAROUTE_API_KEY="${LUNAROUTE_API_KEY:-$(lunaroute key)}"
exec "${PI_EXECUTABLE:-pi}" --provider lunaroute --model "${PIL_MODEL:-deepseek-4.1-flash}" "$@"
