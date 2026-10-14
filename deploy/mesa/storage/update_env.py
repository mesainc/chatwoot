"""Stage OCI upload credentials or activate the native S3-compatible service."""

import argparse
import os
import shlex
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        if value.startswith(('"', "'")):
            value = shlex.split(value, comments=True)[0]
        values[key] = value
    return values


def update(source, target, activate):
    existing, storage = read_env(source), read_env(target)
    endpoint = urlsplit(storage['STORAGE_ENDPOINT'])
    if endpoint.scheme != 'https' or not endpoint.hostname.endswith('.oci.customer-oci.com'):
        raise ValueError('An OCI HTTPS compatibility endpoint is required')
    if storage['ACTIVE_STORAGE_SERVICE'] != 's3_compatible' or storage['STORAGE_FORCE_PATH_STYLE'] != 'true':
        raise ValueError('Expected the native path-style S3-compatible service')
    if existing['ACTIVE_STORAGE_SERVICE'] not in {'local', 's3_compatible'}:
        raise ValueError('Unexpected current storage service')
    updates = {key: value for key, value in storage.items() if key.startswith('STORAGE_')}
    if activate:
        updates['ACTIVE_STORAGE_SERVICE'] = 's3_compatible'
    source = Path(source)
    lines = [line for line in source.read_text().splitlines() if line.split('=', 1)[0] not in updates]
    lines.extend(f'{key}={value}' for key, value in updates.items())
    info = source.stat()
    with tempfile.NamedTemporaryFile('w', dir=source.parent, delete=False) as output:
        temporary = Path(output.name)
        os.fchmod(output.fileno(), 0o600)
        os.fchown(output.fileno(), info.st_uid, info.st_gid)
        output.write('\n'.join(lines) + '\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    update(args.source, args.target, args.activate)
