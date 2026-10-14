"""Reuse Plane's bucket-scoped OCI backup identity under a distinct Chatwoot prefix."""

import subprocess
import sys
from pathlib import Path


archive = Path(sys.argv[1]).resolve()
if archive.parent != Path('/var/backups/chatwoot') or not archive.name.startswith('chatwoot-'):
    raise ValueError('Unexpected backup path')

# boto3 is already present in the running Plane image. Credentials stay on the host.
script = '''
import boto3, hashlib, sys
from pathlib import Path
env = dict(line.split('=', 1) for line in Path('/run/backup.env').read_text().splitlines() if line and not line.startswith('#'))
path = Path(sys.argv[1])
digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
client = boto3.client('s3', endpoint_url=env['AWS_S3_ENDPOINT_URL'], region_name=env['AWS_REGION'], aws_access_key_id=env['AWS_ACCESS_KEY_ID'], aws_secret_access_key=env['AWS_SECRET_ACCESS_KEY'])
# Reuse the existing 90-day snapshot / 30-day previous-version lifecycle.
key = 'snapshots/chatwoot/' + path.name
client.upload_file(str(path), env['AWS_S3_BUCKET_NAME'], key, ExtraArgs={'Metadata': {'sha256': digest}})
head = client.head_object(Bucket=env['AWS_S3_BUCKET_NAME'], Key=key)
if head['ContentLength'] != path.stat().st_size or head['Metadata'].get('sha256') != digest:
    raise RuntimeError('Backup verification failed')
body = client.get_object(Bucket=env['AWS_S3_BUCKET_NAME'], Key=key)['Body']
with body:
    readback = hashlib.sha256()
    for chunk in iter(lambda: body.read(1048576), b''):
        readback.update(chunk)
if readback.hexdigest() != digest:
    raise RuntimeError('Remote backup readback failed')
print('Verified private OCI backup: ' + key)
'''
image = subprocess.check_output(['docker', 'inspect', '-f', '{{.Image}}', 'plane-api-1'], text=True).strip()
subprocess.run([
    'docker', 'run', '--rm', '--cpus', '0.2', '--memory', '512m', '--entrypoint', 'python',
    '-v', '/etc/plane/backup.env:/run/backup.env:ro',
    '-v', f'{archive}:{archive}:ro', image, '-c', script, str(archive),
], check=True)
