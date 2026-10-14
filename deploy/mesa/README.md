# Mesa Chatwoot pilot

Mesa's fork is `https://github.com/mesainc/chatwoot`. The `mesa` branch starts at upstream stable
`v4.18.0` (`9f920b549c14491a4e587687a3eed5d21c6ccc7d`), with deployment files added here.
Mesa staff pages use the shared Mesa geometric mark, self-hosted Fraunces display font, Inter controls,
warm surface tokens and burgundy navigation. The backend remains the matching official Community
Edition runtime, pinned by digest; compiled staff UI assets are layered over it. Customer widget
branding remains controlled by its inbox. No enterprise features are unlocked.

## Hosting and limits

- URL: `https://chatwoot.mesa.tech`; Cloudflare DNS-only A record to `147.224.162.1`.
- Existing Oracle Cloud `plane-pilot`, Chicago, ARM64, 4 cores / 24 GB RAM.
- Stack: `/home/ubuntu/chatwoot/compose.yaml`; secrets: `/etc/chatwoot/chatwoot.env` (root, `0600`).
- Separate PostgreSQL with pgvector, Redis, and upload volumes. No published container ports.
- The web container and signature-verifying email relay join `plane_default`, as `chatwoot-web` and `chatwoot-mail-relay`, for Plane's existing Caddy proxy.
- Caddy route: `/data/mesa-sites/chatwoot.caddy` in the persistent `plane_proxy_data` volume.
  Plane's canonical Caddyfile imports `/data/mesa-sites/*.caddy`, so later Plane deployments retain it.
- Hard aggregate CPU ceiling: 2.2 cores; aggregate memory ceiling: 6.75 GB. Low CPU scheduling priority.
  One Puma process, three web threads, two Sidekiq threads. Logs rotate at 30 MB per service.
- Public account signup disabled. Bootstrap the first confirmed administrator before publishing the route.
- General mail uses Plane's existing Resend SMTP connection. The dedicated pilot inbox is
  `vendeuganhou@suporte.mesa.tech`, with Resend for both receiving and outgoing replies.
  `antonio@mesainc.com.br` is only the administrator; no personal Gmail access is required.
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

## Mesa UI releases

Build on an ARM64 development machine, then inspect login, conversations, settings, controls and
menus in both themes before packaging. The shared host assembles a small runtime layer only:

```sh
revision=$(git rev-parse HEAD)
image="mesa/chatwoot:v4.18.0-mesa-$revision"
docker build --build-arg MESA_REVISION="$revision" -f deploy/mesa/Dockerfile -t "$image" .
sh deploy/mesa/package-ui.sh "$image" /absolute/private/release/mesa-ui.tgz
```

Transfer the archive and operational files using the verified Bastion connection. On the host,
keep the archive at `/home/ubuntu/chatwoot/mesa-ui.tgz` for backup/recovery, extract it into a release
directory and build its Dockerfile with the same `MESA_REVISION` and image tag. Before changing
`CHATWOOT_IMAGE` in the private environment, take a backup. Set that variable to the assembled tag,
validate compose and recreate only `rails sidekiq` with `up -d --no-deps --wait --wait-timeout 300`.
Run `configure-branding.rb` via `bundle exec rails runner` in the Rails container. This sets the
installation name to Mesa Support, without changing inbox names or account permissions. Record
the merged source commit in `REVISION`, verify the app and Plane, and take a new backup.

For a UI rollback, restore the prior `CHATWOOT_IMAGE`, recreate only Rails/Sidekiq, and restore the
previous compiled archive/REVISION metadata. No database migration is part of a UI-only release.
Keep the prior image and archive until the new release is verified.

## Backups and recovery

The nightly backup briefly pauses Chatwoot web/background processes to make database, uploads,
Redis queue, application secrets and deployment metadata consistent. Plane continues serving.
It resumes Chatwoot even if the backup fails. Archives are root-readable only, with seven-day
local retention after successful upload. The existing bucket-scoped Plane backup identity uploads
to the private OCI backup bucket under `snapshots/chatwoot/`; existing lifecycle rules retain
current archives 90 days and previous versions 30 days. No Plane object is changed.

To restore, retrieve and verify an archive from OCI, extract it in a root-only directory,
restore `chatwoot.env`, `mail-relay.env`, relay source and the archived image/compose revision, start PostgreSQL/Redis, then
restore `database.dump` with `pg_restore` into a fresh `chatwoot_production` database. Extract
`storage.tgz` into `chatwoot_storage`. Before starting Redis, install `redis.rdb` into its volume
and remove only the replacement instance's empty AOF directory so it loads that snapshot.
For Mesa UI releases, the backup includes `mesa-ui.tgz`. Extract it and build its Dockerfile
with the archived `.git_sha` as `MESA_REVISION`, using the `CHATWOOT_IMAGE` tag from the private
environment, before starting Rails/Sidekiq. Never restore over a running instance. Validate privately before switching the edge route.

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

## Pilot email configuration

Resend receives `suporte.mesa.tech`. Its signed `email.received` webhook goes to
`https://chatwoot.mesa.tech/email-ingress/resend`; the small relay retrieves the original MIME
(including attachments) and posts it to stock Rails ActionMailbox over the private Docker network.
The public proxy blocks direct ActionMailbox ingress. Only the pilot address and this domain's
`reply+UUID` recipients are accepted. Resend events for other workspace domains are discarded
before fetching message contents. MIME message IDs and references are preserved; stock Rails
handles duplicate deliveries and Chatwoot threads replies. Transfer failures return non-2xx for
Resend's documented retry/replay mechanism. Check failed deliveries in Resend's webhook dashboard.

Resend currently offers only full-access and sending-only API keys. Receiving content retrieval
requires a dedicated full-access key in the mesainc workspace, with account-wide permissions;
there is no receiving-only/domain-restricted key. Keep this key only in root-readable
`/etc/chatwoot/mail-relay.env`, together with the webhook signing secret and an independent
ActionMailbox password. Keep the outgoing key separate: sending-only, restricted to
`suporte.mesa.tech`, in `SUPPORT_SMTP_PASSWORD` in `chatwoot.env`. Do not reuse another application's
full-access key. The shared ingress password must also be set as `RAILS_INBOUND_EMAIL_PASSWORD`
in `chatwoot.env`. Set `RAILS_INBOUND_EMAIL_SERVICE=relay`,
`MAILER_INBOUND_EMAIL_DOMAIN=suporte.mesa.tech`, and `SUPPORT_EMAIL` to the pilot address.
Remove the unused Google OAuth environment settings from the personal-mailbox setup.

In Resend create/verify the support subdomain in São Paulo, with sending and receiving enabled:

| Type | Name within mesa.tech | Content | Priority |
| --- | --- | --- | --- |
| TXT | resend._domainkey.suporte | The support domain's public DKIM value from Resend | — |
| CNAME | rsend.suporte | rsend-sae1.forge.rmta.net | — |
| CNAME | send.suporte | send.forge.rmta.net | — |
| MX | suporte | inbound-smtp.sa-east-1.amazonaws.com | 10 |

Keep CNAME records DNS-only. These records affect only the support subdomain. Leave existing
root-domain mail records intact. After verification, install the scoped sending key and run
`configure-support-email.rb` in Rails. It replaces the unused personal pilot inbox with the
dedicated address and refuses to change an inbox containing conversations. The outgoing channel
uses SMTP implicit TLS on port 465 with certificate verification.

Build the relay from `mail-relay/`, restart Chatwoot Rails/Sidekiq for environment changes, and start
`mail-relay`. Install the updated Caddy route with a validated reload. The relay has a 0.2-core,
256-MB limit, runs without root privileges, uses a read-only filesystem, and logs no email contents.
Dependency versions and the official Python base image are pinned. Mail handling uses stock Chatwoot endpoints.
Backups include both private environment files and the relay source for recovery.

Validate signed/invalid/expired webhooks, incoming MIME with attachments, duplicate delivery,
threaded replies and an actual received email/delivered reply before routing customer traffic.
SMTP authentication alone does not establish delivery or domain permission. Domain verification,
credentials and a real transport check are required before calling the email pilot ready.
