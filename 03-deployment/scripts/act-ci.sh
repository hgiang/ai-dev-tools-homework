#!/usr/bin/env bash
# Run .github/workflows/ci.yml locally with act, against the local kind cluster.
#
#   ./03-deployment/scripts/act-ci.sh            # the whole workflow
#   ./03-deployment/scripts/act-ci.sh -j test    # one job
#
# act runs each job inside a container, which creates two problems this script
# solves:
#
#   1. Docker access.  The deploy job builds an image and calls `kind load`, so
#      it needs a Docker socket.  Colima's socket is not at the usual path, so
#      it is passed explicitly.
#   2. Cluster access.  The kubeconfig on the host points at 127.0.0.1:<port>,
#      which inside the job container is the container itself.  `kind get
#      kubeconfig --internal` instead emits the address the control plane has
#      on Docker's own network, and joining that network makes it reachable.
set -euo pipefail

CLUSTER="${KIND_CLUSTER:-agent-relay}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${REPO_ROOT}/.act"

command -v act >/dev/null || { echo "act is not installed: brew install act" >&2; exit 1; }
command -v kind >/dev/null || { echo "kind is not installed: brew install kind" >&2; exit 1; }

# Locate a Docker socket.  Colima's is under $HOME; Docker Desktop and Linux
# use /var/run/docker.sock.
DOCKER_SOCKET="${DOCKER_HOST#unix://}"
if [ -z "$DOCKER_SOCKET" ] || [ ! -S "$DOCKER_SOCKET" ]; then
  for candidate in "$HOME/.colima/default/docker.sock" /var/run/docker.sock; do
    [ -S "$candidate" ] && DOCKER_SOCKET="$candidate" && break
  done
fi
[ -S "${DOCKER_SOCKET:-}" ] || { echo "no Docker socket found; is colima running?" >&2; exit 1; }

kind get clusters | grep -qx "$CLUSTER" || {
  echo "kind cluster '$CLUSTER' not found. Create it with:" >&2
  echo "  kind create cluster --name $CLUSTER" >&2
  exit 1
}

# The kind network is where the control-plane container lives.
NETWORK="$(docker inspect "${CLUSTER}-control-plane" \
  --format '{{range $k, $_ := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1)"

mkdir -p "$WORK_DIR"
# Contains a cluster certificate and token: keep it out of git (see .gitignore).
kind get kubeconfig --internal --name "$CLUSTER" > "$WORK_DIR/kubeconfig"
chmod 600 "$WORK_DIR/kubeconfig"

echo "cluster:  $CLUSTER (network: $NETWORK)"
echo "docker:   $DOCKER_SOCKET"
echo

exec act \
  --container-daemon-socket "$DOCKER_SOCKET" \
  --network "$NETWORK" \
  --container-options "-v ${DOCKER_SOCKET}:/var/run/docker.sock -v ${WORK_DIR}/kubeconfig:/root/.kube/config:ro" \
  --env KUBECONFIG=/root/.kube/config \
  --workflows "${REPO_ROOT}/.github/workflows/ci.yml" \
  "$@"
