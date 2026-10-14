#!/bin/sh
# Run on plane-pilot after installing this directory in /home/ubuntu/chatwoot.
set -eu
cd /home/ubuntu/chatwoot
compose() { docker compose --env-file /etc/chatwoot/chatwoot.env -f compose.yaml "$@"; }
test "$(uname -m)" = aarch64
test -s /etc/chatwoot/chatwoot.env
free_mb=$(awk '/MemAvailable:/ {print int($2/1024)}' /proc/meminfo)
disk_kb=$(df -Pk . | awk 'NR==2 {print $4}')
test "$free_mb" -ge 8192 || { echo 'At least 8 GB available RAM required'; exit 1; }
test "$disk_kb" -ge 10485760 || { echo 'At least 10 GB free disk required'; exit 1; }
docker network inspect plane_default >/dev/null
compose config --quiet
if docker inspect chatwoot-rails-1 >/dev/null 2>&1; then
  /usr/local/sbin/chatwoot-backup.sh
fi
compose pull --ignore-buildable
compose build mail-relay
compose up -d postgres redis
# A run container inherits the web service's resource limits.
compose run --rm --no-deps rails bundle exec rails db:chatwoot_prepare
compose up -d --wait --wait-timeout 300
echo 'Chatwoot is healthy. Complete administrator bootstrap before publishing the edge route.'
