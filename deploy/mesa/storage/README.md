# Chatwoot OCI upload storage

Live files use `mesa-chatwoot-pilot-uploads`, a private, versioned Standard bucket in the existing
`mesa-plane` compartment, Chicago. OCI encrypts objects at rest. There is no upload expiration rule.
This bucket is separate from Plane uploads and from the existing backup bucket. The Chatwoot
technical identity can list/read/create/overwrite/delete current objects in this bucket only;
it cannot purge object versions or access Plane files/backups. S3-compatible credentials are
root-only on the host and never committed. No public bucket or pre-authenticated request is used.

The application uses upstream's `s3_compatible` Active Storage adapter. Attachment URLs continue
to go through Chatwoot, which redirects to expiring signed OCI downloads. Browser direct uploads
use signed PUT requests. `files.rb probe` exercises the actual Rails adapter, signed PUT, CORS,
signed download/disposition and rejection of unsigned reads. No DNS change or custom app endpoint
is required. Configuration follows [Chatwoot's supported storage providers](https://developers.chatwoot.com/self-hosted/deployment/storage/supported-providers)
and [OCI's compatibility API](https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/s3compatibleapi.htm).

## Provision and cut over

With the existing authenticated OCI operator session:

```sh
python3 deploy/mesa/storage/provision_oci.py \
  --profile mesa-plane-operator --compartment <mesa-plane-compartment-ocid> \
  --environment pilot --email <technical-identity-email> \
  --output-dir ~/.config/chatwoot/oci-pilot-storage
```

This reuses matching resources, refuses differing policies or public/unversioned buckets, and
writes new credentials to private files outside the checkout. It never rotates missing credentials
automatically. Install `uploads.env` at `/etc/chatwoot/oci-uploads.env` as root `0600`.
Install `files.rb` and `update_env.py` at `/usr/local/lib/chatwoot/storage/`, plus the updated backup
script. Use the existing verified Bastion access; no public SSH or host-key bypass.

Stage credentials without activating them:

```sh
python3 storage/update_env.py --source /etc/chatwoot/chatwoot.env --target /etc/chatwoot/oci-uploads.env
```

From `/home/ubuntu/chatwoot`, use a one-off container with the **current deployed image**, matching
environment, database/network and original storage volume:

```sh
docker compose --env-file /etc/chatwoot/chatwoot.env -f compose.yaml run --rm --no-deps -T \
  --entrypoint bundle -v /usr/local/lib/chatwoot/storage/files.rb:/tmp/storage-files.rb:ro \
  rails exec rails runner /tmp/storage-files.rb probe
```

Take and verify a pre-cutover off-host backup. Preserve the exact previous environment as a private
rollback file. Stop only Rails and Sidekiq, leaving PostgreSQL, Redis, Plane and the email relay
running. Incoming relay failures remain retryable. Run the same one-off command with `migrate-local`
instead of `probe`. It copies all disk objects (including variants), verifies database sizes/MD5
and remote SHA-256 bytes, refuses unrelated destination keys, and changes blob service names in
one database transaction only after all copies verify. It preserves keys and attachment associations.
The source volume is retained. Writers must remain stopped throughout this operation.

Activate the credentials with `update_env.py ... --activate`, validate compose, then recreate only
Rails/Sidekiq with `up -d --no-deps --wait --wait-timeout 300 rails sidekiq`. Verify downloads through
Chatwoot, a fresh upload, web/worker health, and Plane. Take a new off-host backup. No app-image build
or schema migration is required. Record the merged deployment source revision in `REVISION`.

## Backups and recovery

The nightly backup still pauses writers while capturing the database, queue and files. For OCI it
runs `files.rb snapshot /snapshot/object-storage` in the matching Rails image, downloading every
current object with its content type, disposition and custom metadata. It conditionally reads
objects, compares the bucket inventory before/after, and validates every database blob's size and
MD5 against the captured bytes. The manifest also records SHA-256 for every object. A changed
bucket, missing file or checksum mismatch fails the backup. Object versions are additional recovery
protection; the snapshot archives the current state, not all previous versions.

The archive includes the object snapshot, database dump, environment/encryption keys, queue, relay,
compiled UI and storage tools. The existing separate create/read/list-only backup identity uploads
and verifies it under `snapshots/chatwoot/` in the private Plane backup bucket. Its existing 90-day
current / 30-day previous-version retention remains in effect. No backup credential is passed to
the Chatwoot application. Retain pre-cutover backups containing `storage.tgz` for old local restores.

For full recovery, restore the database/queue/config privately as documented in the parent runbook.
Provision an **empty** private/versioned replacement uploads bucket and a new restricted credential;
use those in the restored environment. Mount the extracted archive at `/snapshot`, and run the
matching Rails image with `files.rb restore /snapshot/object-storage` before starting writers.
This refuses a nonempty destination and verifies every uploaded object's SHA-256. Database keys
and the `s3_compatible` service name remain unchanged. Validate the restored application before
changing its public route. Do not restore the old config's bucket credentials over the replacement.

`verify DIRECTORY` checks snapshot bytes and database references without uploading. For an isolated
file recovery check, `restore-drill DIRECTORY` writes only unique `mesa-restore-checks/<random>/`
objects, checks their bytes/metadata, then removes those current objects with recoverable delete
markers. It leaves live app objects untouched. This tests file recovery; a complete disaster recovery
exercise also needs an isolated database/queue/application restore.

## Rollback

Before resuming writers, rollback can restore the exact previous environment and set the migrated
blob service names back to `local` in a transaction; all original bytes remain in the disk volume.
If writers have resumed on OCI, **do not simply switch the environment back**. Stop writers, copy
and verify every new/current OCI object back to the corresponding Disk service key, reconcile
database blob references, and only then switch service names/configuration. Keep OCI authoritative
if that copy cannot be verified. Never delete the live bucket or purge versions as part of rollback.
