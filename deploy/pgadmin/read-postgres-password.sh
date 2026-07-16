#!/bin/sh
set -eu

if [ -z "${MESYNC_POSTGRES_PASSWORD:-}" ]; then
    exit 1
fi

printf '%s\n' "$MESYNC_POSTGRES_PASSWORD"
