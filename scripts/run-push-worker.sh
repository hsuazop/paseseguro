#!/bin/bash
set -euo pipefail
umask 077
APP=/home/hector/apps/paseseguro
exec 9> "$APP/tmp/push-worker.lock"
flock -n 9 || exit 0
set -a
. "$APP/production.env"
set +a
cd "$APP/myproject"
exec "$APP/env/bin/python" manage.py procesar_push --loop
