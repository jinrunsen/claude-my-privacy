#!/bin/sh
set -eu
umask 077
verification_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$verification_root/run-targeted.py"
