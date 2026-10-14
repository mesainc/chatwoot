#!/bin/sh
# Export tested compiled UI, without rebuilding on the shared pilot host.
set -eu
image=${1:?Supply the tested Mesa image tag}
output=${2:?Supply an absolute output archive path}
work=$(mktemp -d)
container=$(docker create "$image" true)
cleanup() { docker rm -v "$container" >/dev/null; rm -rf "$work"; }
trap cleanup EXIT INT TERM
mkdir -p "$work/public"
for dir in vite assets mesa; do docker cp "$container:/app/public/$dir" "$work/public/"; done
docker cp "$container:/app/app/views/layouts/vueapp.html.erb" "$work/vueapp.html.erb"
docker cp "$container:/app/.git_sha" "$work/.git_sha"
cp "$(dirname "$0")/Dockerfile.runtime" "$work/Dockerfile"
tar -C "$work" -czf "$output" .
echo 'Tested Mesa UI packaged for installation and backup.'
