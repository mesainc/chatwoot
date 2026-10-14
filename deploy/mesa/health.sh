#!/bin/sh
set -eu
for container in chatwoot-rails-1 chatwoot-sidekiq-1 chatwoot-postgres-1 chatwoot-redis-1 chatwoot-mail-relay-1; do
  test "$(docker inspect -f '{{.State.Running}}' "$container")" = true || { echo "$container is down"; exit 1; }
done
test "$(docker inspect -f '{{.State.Health.Status}}' chatwoot-rails-1)" = healthy
test "$(docker inspect -f '{{.State.Health.Status}}' chatwoot-mail-relay-1)" = healthy
disk_kb=$(df -Pk /home/ubuntu/chatwoot | awk 'NR==2 {print $4}')
test "$disk_kb" -ge 10485760 || { echo 'Chatwoot pilot host has less than 10 GB free disk'; exit 1; }
success=/var/backups/chatwoot/last-success
test -f "$success" || { echo 'Chatwoot has no successful off-host backup'; exit 1; }
age=$(($(date +%s) - $(date -d "$(cat "$success")" +%s)))
test "$age" -le 93600 || { echo 'Chatwoot off-host backup is older than 26 hours'; exit 1; }
echo 'Chatwoot services, disk headroom and off-host backup are healthy'
