#!/usr/bin/env bash
#
# Read-only survey of a target machine. Installs nothing, changes nothing.
# Run this before deploying to an unfamiliar server, and paste the output to
# faculty IT if anything looks wrong.
#
# For a deployment-specific preflight, use:  ./deploy.sh check

set -u

echo "=== OS ==="
grep -E '^(NAME|VERSION)=' /etc/os-release || true
echo "kernel: $(uname -r)   arch: $(uname -m)"

echo -e "\n=== CPU / RAM / disk ==="
lscpu | grep -E 'Model name|^CPU\(s\)' || true
free -h | head -2
df -h . | tail -1

echo -e "\n=== AMD GPU ==="
if [ -e /dev/kfd ] && [ -d /dev/dri ]; then
  echo "/dev/kfd present"
  ls -l /dev/dri
else
  echo "MISSING: /dev/kfd and/or /dev/dri - the amdgpu driver is not active."
  echo "Ask faculty IT. Do NOT install ROCm or a custom kernel yourself."
fi
lspci 2>/dev/null | grep -iE 'vga|display|3d' || true

echo -e "\n=== GPU group IDs (machine-specific, needed in .env) ==="
echo "render = $(getent group render | cut -d: -f3 || echo 'MISSING')"
echo "video  = $(getent group video  | cut -d: -f3 || echo 'MISSING')"

echo -e "\n=== Docker ==="
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker compose version 2>/dev/null || echo "compose plugin MISSING"
  docker info >/dev/null 2>&1 && echo "daemon reachable as $(id -un)" \
    || echo "daemon NOT reachable - you may not be in the 'docker' group"
else
  echo "Docker not installed - ask faculty IT."
fi

echo -e "\n=== Existing containers on this shared machine (do not disturb) ==="
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null || true

echo -e "\n=== Port 18501 ==="
ss -ltn 2>/dev/null | grep ':18501 ' || echo "free"

echo -e "\n=== Knowledge base ==="
if [ -f data/chroma_db/chroma.sqlite3 ]; then
  echo "found: $(du -h data/chroma_db/chroma.sqlite3 | cut -f1)"
else
  echo "NOT FOUND at data/chroma_db/chroma.sqlite3"
  echo "(wrong folder, or unzipped one level too deep)"
fi
