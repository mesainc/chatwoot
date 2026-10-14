# Mesa Chatwoot pilot

Mesa's fork is `https://github.com/mesainc/chatwoot`. The `mesa` branch starts at upstream stable
`v4.18.0` (`9f920b549c14491a4e587687a3eed5d21c6ccc7d`), with deployment files added here.
Application code is unchanged. The pilot uses the matching official Community Edition image,
pinned by digest. Future application changes require a Mesa-built image and a deliberate image update.

## Hosting and limits

- URL: `https://chatwoot.mesa.tech`; Cloudflare DNS-only A record to `147.224.162.1`.
- Existing Oracle Cloud `plane-pilot`, Chicago, ARM64, 4 cores / 24 GB RAM.
- Stack: `/home/ubuntu/chatwoot/compose.yaml`; secrets: `/etc/chatwoot/chatwoot.env` (root, `0600`).
- Separate PostgreSQL with pgvector, Redis, and upload volumes. No published container ports.
- Only the web container joins `plane_default`, as `chatwoot-web`, for Plane's existing Caddy proxy.
- Caddy route: `/data/mesa-sites/chatwoot.caddy` in the persistent `plane_proxy_data` volume.
  Plane's canonical Caddyfile imports `/data/mesa-sites/*.caddy`, so later Plane deployments retain it.
- Hard aggregate CPU ceiling: 2 cores; aggregate memory ceiling: 6.5 GB. Low CPU scheduling priority.
  One Puma process, three web threads, two Sidekiq threads. Logs rotate at 30 MB per service.
- Public account signup disabled. Bootstrap the first confirmed administrator before publishing the route.
- SMTP uses Plane's existing configured relay. No incoming support mailbox is connected automatically.
- Require at least 8 GB available RAM and 10 GB free disk for a deployment. Monitor actual workload
  before expanding adoption; resource limits cannot guarantee performance under future load.

## Install and operate

Use Plane's existing verified OCI Bastion helper from the Plane checkout:
`python3 deploy/mesa/access/plane_admin.py`. The operator login may need a browser refresh.
Do not enable public SSH or bypass host-key checks.

Copy this directory's operational files into `/home/ubuntu/chatwoot`, create the private environment
from `chatwoot.env.example` with unique secrets, and set the SMTP values from the existing relay.
The three encryption values should each be a random 32-character value; the cookie secret should be
at least 64 random bytes encoded as hex. Keep all keys for restores and MFA compatibility.

Run as root:

```sh
install -m 700 backup.sh /usr/local/sbin/chatwoot-backup.sh
install -m 700 health.sh /usr/local/sbin/chatwoot-health.sh
install -d -m 755 /usr/local/lib/chatwoot
install -m 644 upload_backup.py /usr/local/lib/chatwoot/upload_backup.py
sh deploy.sh
```

Create a private JSON file with `name`, `email`, and a unique `password`; copy it and
`bootstrap-admin.rb` into the running Rails container. Run `bundle exec rails runner` on that script
with the private file path, then delete the copies and retain the password in a password manager.
The script refuses to run when users already exist. It uses upstream's account builder and clears
the installation onboarding flag. No application patches or bypassed paid features are involved.

Install `chatwoot.caddy` in the persistent proxy data volume under `mesa-sites/`, copy the
canonical Plane Caddyfile into the proxy at `/tmp/Caddyfile.deploy`, validate that file,
then reload Caddy from it. Explicit copying handles a retained proxy whose bind mount points
to an old inode from an earlier deployment. A reload preserves active Plane connections.
Run the first backup and health check, then install `chatwoot.cron` as `/etc/cron.d/chatwoot`.

Check services with `docker compose --env-file /etc/chatwoot/chatwoot.env -f compose.yaml ps`.
Run `/usr/local/sbin/chatwoot-health.sh` for service, free-disk, and backup freshness checks.
Hourly results go to the system journal (`journalctl -t chatwoot-health`); this is logging,
not an external notification service. Backup logs are in `/var/log/chatwoot-backup.log`.

## Backups and recovery

The nightly backup briefly pauses Chatwoot web/background processes to make database, uploads,
Redis queue, application secrets and deployment metadata consistent. Plane continues serving.
It resumes Chatwoot even if the backup fails. Archives are root-readable only, with seven-day
local retention after successful upload. The existing bucket-scoped Plane backup identity uploads
to the private OCI backup bucket under `snapshots/chatwoot/`; existing lifecycle rules retain
current archives 90 days and previous versions 30 days. No Plane object is changed.

To restore, retrieve and verify an archive from OCI, extract it in a root-only directory,
restore `chatwoot.env` and the archived image/compose revision, start PostgreSQL/Redis, then
restore `database.dump` with `pg_restore` into a fresh `chatwoot_production` database. Extract
`storage.tgz` into `chatwoot_storage`. Before starting Redis, install `redis.rdb` into its volume
and remove only the replacement instance's empty AOF directory so it loads that snapshot.
Never restore over a running instance. Validate privately before switching the edge route.

Before an upgrade: take a backup, select a stable upstream release, update all image digests,
run `db:chatwoot_prepare`, verify web/worker health and the public pilot, then record `REVISION`.
On a failed migration, restore the pre-upgrade database/files/queue/config into an isolated stack
with the old images. Merely reverting an image does not undo a database migration.

## Tomorrow's adoption

Sign in as the initial administrator, invite the pilot team, create inboxes, and connect the chosen
support mailbox through Chatwoot's supported email settings. Verify one received request and one
delivered reply with the actual mailbox before routing customer traffic. Website/API inboxes are
also available. Existing Jira Service Management data is not migrated, and no Plane integration
is configured. Treat this as a support-conversation pilot; validate request types, portals, SLAs,
approvals, incident/change management and asset management separately before replacing JSM.
