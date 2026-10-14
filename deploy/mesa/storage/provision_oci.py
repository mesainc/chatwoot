#!/usr/bin/env python3
"""Provision a private Chatwoot upload bucket and bucket-scoped technical identity.

Uses an authenticated OCI CLI operator session. Secrets are written only to new
0600 files outside the checkout; command output never includes credentials.
Existing resources are inspected and reused; existing credentials aren't rotated.
"""

import argparse
import configparser
import json
import os
import stat
import subprocess
from pathlib import Path


class OCI:
    def __init__(self, profile):
        self.profile = profile
        self.iam_region = None

    def call(self, *args):
        command = [
            "oci",
            *args,
            "--profile",
            self.profile,
            "--auth",
            "security_token",
            "--output",
            "json",
        ]
        if args[0] == "iam" and self.iam_region:
            command.extend(["--region", self.iam_region])
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            env={**os.environ, "SUPPRESS_LABEL_WARNING": "True"},
        )
        if result.returncode:
            # OCI error output may include request payloads or credential material.
            raise RuntimeError(f"OCI operation failed: {' '.join(args[:3])}")
        if not result.stdout.strip() and any(arg.startswith("list") for arg in args):
            return []
        return json.loads(result.stdout)["data"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--compartment", required=True)
    parser.add_argument(
        "--environment", required=True, choices=["pilot", "staging", "production"]
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--email", required=True, help="Technical identity primary email"
    )
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[3]
    if output.is_relative_to(checkout):
        parser.error("Credentials must be stored outside the checkout")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(output.stat().st_mode) & 0o077:
        parser.error("Output directory must be private (0700)")
    config = configparser.ConfigParser()
    config.read(Path.home() / ".oci/config")
    tenancy = config[args.profile]["tenancy"]
    region = config[args.profile]["region"]
    oci = OCI(args.profile)
    subscriptions = oci.call(
        "iam", "region-subscription", "list", "--tenancy-id", tenancy
    )
    oci.iam_region = next(
        item["region-name"] for item in subscriptions if item["is-home-region"]
    )
    namespace = oci.call("os", "ns", "get")
    endpoint = f"https://{namespace}.compat.objectstorage.{region}.oci.customer-oci.com"
    buckets = {}
    existing = oci.call(
        "os", "bucket", "list", "--compartment-id", args.compartment, "--all"
    )
    for purpose in ["uploads"]:
        name = f"mesa-chatwoot-{args.environment}-{purpose}"
        if not any(bucket["name"] == name for bucket in existing):
            oci.call(
                "os",
                "bucket",
                "create",
                "--compartment-id",
                args.compartment,
                "--name",
                name,
                "--public-access-type",
                "NoPublicAccess",
                "--versioning",
                "Enabled",
                "--storage-tier",
                "Standard",
            )
        data = oci.call("os", "bucket", "get", "--name", name)
        if (
            data["public-access-type"] != "NoPublicAccess"
            or data["versioning"] != "Enabled"
        ):
            raise RuntimeError(
                "Existing bucket is not private and versioned; inspect before proceeding"
            )
        buckets[purpose] = name
    groups = oci.call("iam", "group", "list", "--compartment-id", tenancy, "--all")
    users = oci.call("iam", "user", "list", "--compartment-id", tenancy, "--all")
    identities = {}
    for purpose in ["uploads"]:
        name = f"mesa-chatwoot-{args.environment}-{purpose}"
        group = next((group for group in groups if group["name"] == name), None)
        if not group:
            group = oci.call(
                "iam",
                "group",
                "create",
                "--compartment-id",
                tenancy,
                "--name",
                name,
                "--description",
                f"Chatwoot {args.environment} {purpose} bucket only",
            )
        user = next((user for user in users if user["name"] == name), None)
        if not user:
            user = oci.call(
                "iam",
                "user",
                "create",
                "--compartment-id",
                tenancy,
                "--name",
                name,
                "--description",
                f"Chatwoot {args.environment} {purpose} service identity",
                "--email",
                args.email,
            )
        memberships = oci.call(
            "iam",
            "user",
            "list-groups",
            "--compartment-id",
            tenancy,
            "--user-id",
            user["id"],
            "--all",
        )
        if any(item["id"] != group["id"] for item in memberships):
            raise RuntimeError(
                "Service identity has unrelated group membership; inspect before proceeding"
            )
        if not memberships:
            oci.call(
                "iam",
                "group",
                "add-user",
                "--user-id",
                user["id"],
                "--group-id",
                group["id"],
            )
        identities[purpose] = {"user": user["id"], "group": group["id"]}
    statements = []
    for purpose, identity in identities.items():
        permissions = ["OBJECT_INSPECT", "OBJECT_READ", "OBJECT_CREATE"]
        if purpose == "uploads":
            permissions.extend(["OBJECT_OVERWRITE", "OBJECT_DELETE"])
        allowed = ", ".join(
            f"request.permission='{permission}'" for permission in permissions
        )
        statements.extend(
            [
                f"Allow group id {identity['group']} to read buckets in compartment id {args.compartment} where target.bucket.name='{buckets[purpose]}'",
                f"Allow group id {identity['group']} to manage objects in compartment id {args.compartment} "
                + "where all {target.bucket.name='"
                + buckets[purpose]
                + "', any {"
                + allowed
                + "}}",
            ]
        )
    policy_name = f"mesa-chatwoot-{args.environment}-storage"
    policies = oci.call(
        "iam", "policy", "list", "--compartment-id", args.compartment, "--all"
    )
    policy = next(
        (policy for policy in policies if policy["name"] == policy_name), None
    )
    if policy:
        if set(policy["statements"]) != set(statements):
            raise RuntimeError(
                "Existing storage policy differs; inspect instead of expanding it automatically"
            )
    else:
        oci.call(
            "iam",
            "policy",
            "create",
            "--compartment-id",
            args.compartment,
            "--name",
            policy_name,
            "--description",
            "Bucket-scoped Chatwoot uploads identity; no version purge",
            "--statements",
            json.dumps(statements),
        )
    for purpose, identity in identities.items():
        path = output / f"{purpose}.env"
        if path.exists():
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise RuntimeError("Existing credential file must have mode 0600")
            continue
        keys = oci.call(
            "iam", "customer-secret-key", "list", "--user-id", identity["user"]
        )
        if keys:
            raise RuntimeError(
                "Identity already has credentials without a local file; explicit rotation is required"
            )
        key = oci.call(
            "iam",
            "customer-secret-key",
            "create",
            "--user-id",
            identity["user"],
            "--display-name",
            f"chatwoot-{purpose}-s3",
        )
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as stream:
            stream.write(
                f"ACTIVE_STORAGE_SERVICE=s3_compatible\nSTORAGE_REGION={region}\nSTORAGE_BUCKET_NAME={buckets[purpose]}\nSTORAGE_ENDPOINT={endpoint}\nSTORAGE_FORCE_PATH_STYLE=true\nSTORAGE_ACCESS_KEY_ID={key['id']}\nSTORAGE_SECRET_ACCESS_KEY={key['key']}\n"
            )
    metadata = {
        "environment": args.environment,
        "compartment": args.compartment,
        "region": region,
        "buckets": buckets,
        "identities": identities,
        "policy": policy_name,
    }
    (output / "resources.json").write_text(json.dumps(metadata, indent=2))
    os.chmod(output / "resources.json", 0o600)
    print(
        json.dumps(
            {
                "buckets": buckets,
                "private": True,
                "versioned": True,
                "credentials_saved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
