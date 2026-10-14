#!/bin/sh
# Consistent application/database/files/queue/config backup, then off-host OCI upload.
set -eu
umask 077
cd /home/ubuntu/chatwoot
dir=/var/backups/chatwoot
mkdir -p "$dir"
exec 9>"$dir/.lock"
flock -n 9 || exit 1
stamp=$(date -u +%Y%m%dT%H%M%SZ)
work=$(mktemp -d "$dir/.snapshot-XXXXXX")
paused=0
cleanup() {
  code=$?
  trap - EXIT INT TERM
  if [ "$paused" = 1 ]; then docker unpause chatwoot-rails-1 chatwoot-sidekiq-1 >/dev/null 2>&1 || true; fi
  rm -rf "$work"
  exit "$code"
}
trap cleanup EXIT INT TERM
paused=1
docker pause chatwoot-rails-1 chatwoot-sidekiq-1 >/dev/null
docker exec chatwoot-postgres-1 sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$work/database.dump"
docker exec chatwoot-redis-1 sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli SAVE' >/dev/null
docker cp chatwoot-redis-1:/data/dump.rdb "$work/redis.rdb"
storage=$(docker volume inspect chatwoot_storage -f '{{.Mountpoint}}')
tar -C "$storage" -czf "$work/storage.tgz" .
cp /etc/chatwoot/chatwoot.env compose.yaml "$work/"
cp REVISION "$work/"
if [ -f /etc/chatwoot/mail-relay.env ]; then
  cp /etc/chatwoot/mail-relay.env "$work/"
  cp -R mail-relay "$work/"
fi
docker unpause chatwoot-rails-1 chatwoot-sidekiq-1 >/dev/null
paused=0
archive="$dir/chatwoot-$stamp.tgz"
tar -C "$work" -czf "$archive" .
python3 /usr/local/lib/chatwoot/upload_backup.py "$archive"
date -u +%FT%TZ > "$dir/last-success"
# Remove only this application's old archives after a successful remote upload.
find "$dir" -maxdepth 1 -type f -name 'chatwoot-*.tgz' -mtime +7 -delete
echo "$(date -u +%FT%TZ) Chatwoot off-host backup succeeded"
