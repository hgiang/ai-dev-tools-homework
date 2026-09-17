# Homework 3 — Containerize and Deploy

Starter: [alexeygrigorev/agent-relay](https://github.com/alexeygrigorev/agent-relay) (FastAPI + SQLite + uv),
copied into `agent-relay/` and extended question by question.

## Answers

| Q | Question | Answer |
|---|---|---|
| 1 | Project architecture | **Agents claim tasks from a DB through an HTTP API** |
| 2 | Task status the sender sees after the result is submitted | **`completed`** |
| 3 | Docker option that publishes a port | **`-p`** |
| 4 | Hostname the API uses for the `postgres` service | **`postgres`** |
| 5 | Resource that keeps replicas running and manages updates | **`Deployment`** |
| 6 | What happens when a test fails | **Keep the existing version running and stop the deployment** |

> **Status:** Q1–Q5 are built and verified. Q6's workflow and act wrapper are written but have not
> been run end to end yet — see the checklist at the bottom.

## Q1 — Understand the project

```
Worker (separate process)              FastAPI (main.py)            SQLite
  │                                          │                        │
  ├─ POST /api/v1/tasks/claim ──────────────►│ claim_one() ──────────►│ SELECT status='queued'
  │◄─ 200 {task_id, input, claim_token} ─────┤                        │ UPDATE status='processing'
  ├─ POST .../heartbeat ────────────────────►│ extend 60s lease       │
  └─ POST .../complete {output} ────────────►│ commit_terminal() ────►│ status='completed'

Dashboard (browser) ──► GET /api/v1/tasks ──► reads the DB
```

- **No message broker.** Workers poll `POST /api/v1/tasks/claim` (`main.py:219`); the server
  selects the oldest `queued` row and flips it to `processing`.
- **Agents never talk to each other directly.** Everything goes through the HTTP API and the DB.
- **Lease-based, at-least-once delivery** (`storage.py:143`). A claim issues a `claim_token` and a
  60s lease. If a worker dies, `recovery_loop` (`main.py:88`) requeues the task and the next claim
  gets a new token with an incremented `attempt_count`.
- **Auth**: bearer tokens, stored only as SHA-256 hashes. The token is shown once, at registration.
- **`immediate_transaction()`** serializes writers because SQLite has no `FOR UPDATE SKIP LOCKED`.
  This is the seam replaced in Q4.

Task lifecycle: `queued → processing → completed | failed`. There is no `delivered` state.

## Q2 — Register agents and test the task flow

SPEC.md acceptance scenario 1: two agents exchange a task and its result.

Manual run (server on `http://127.0.0.1:8000`):

```bash
alice=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"alice"}')
bob=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"uppercase"}')
# alice POSTs /api/v1/tasks -> queued
# bob's worker claims, uppercases, completes
# alice GETs /api/v1/tasks/{id} -> completed, output "HELLO RELAY"
```

Automated: [`agent-relay/test_integration.py`](agent-relay/test_integration.py).

Unlike `test_agent_relay.py`, which drives the ASGI app in-process with `TestClient`, this suite
speaks real HTTP to a running server and whatever database it is configured with, so the same file
verifies the dev server, the Q3 container, the Q4 Compose stack, and the Q5 Kubernetes deployment:

```bash
uv run pytest test_integration.py -q                                  # local dev server
RELAY_BASE_URL=http://127.0.0.1:8080 uv run pytest test_integration.py -q   # container / compose / k8s
```

It registers uniquely named agents on every run and never drops or recreates tables, so it is safe
to run repeatedly against a database holding real data.

Tests:

1. `test_two_agents_exchange_a_task_and_its_result` — the full lifecycle, plus the persisted
   attempt history, and asserts the claim token never appears in API responses.
2. `test_completion_is_idempotent_and_a_stale_token_is_rejected` — replaying the exact terminal
   request is a no-op; a different result or an unknown token is `409`.
3. `test_another_agent_cannot_read_or_claim_someone_elses_task` — a third agent gets `404` on the
   task and `204` on claim; unauthenticated reads get `401`.

## Q3 — Containerization

[`agent-relay/Dockerfile`](agent-relay/Dockerfile) + [`agent-relay/.dockerignore`](agent-relay/.dockerignore).

```bash
cd agent-relay
docker build -t agent-relay:local .
docker run -d --name relay -p 8080:8000 agent-relay:local
curl -sS http://127.0.0.1:8080/ready
RELAY_BASE_URL=http://127.0.0.1:8080 uv run pytest test_integration.py -q
```

`-p <host port>:<container port>` publishes the port. `--expose` only documents one, `-v` mounts a
volume, `--name` labels the container.

Notes:

- **`--host 0.0.0.0`** in `CMD` is required. Each container has its own network namespace, so a
  server bound to `127.0.0.1` inside it is unreachable through `-p`.
- **Two build stages.** `uv` resolves dependencies into `/app/.venv` in the build stage; the runtime
  stage copies only that venv, leaving uv and its cache out of the shipped image. Dependency
  manifests are copied before the sources so editing a `.py` file does not re-resolve dependencies.
- **`/data` for SQLite**, not the source directory, so a volume can be mounted there. Q4 overrides
  `RELAY_DATABASE_URL` with a PostgreSQL URL.
- **Runs as uid 10001**, not root, so Kubernetes can enforce `runAsNonRoot` in Q5.

## Q4 — Docker Compose and PostgreSQL

[`agent-relay/compose.yaml`](agent-relay/compose.yaml), plus the storage port in `database.py` and
`storage.py`.

```bash
cd agent-relay
docker compose up --build
RELAY_BASE_URL=http://127.0.0.1:8080 uv run pytest test_integration.py -q
docker compose exec postgres psql -U relay -d relay \
  -c "select id, status, left(output,30) from tasks order by created_at desc limit 5;"
```

The API reaches the database at **`postgres`**, the service name: Compose puts both services on one
network and registers each service name in its DNS. `localhost` would be the app container itself;
`host.docker.internal` would be the host machine (and does not exist under Colima).

### Porting the storage layer

`claim_one()` in `storage.py` is the seam SPEC.md anticipated:

```python
select(Task).where(...).order_by(...).limit(1).with_for_update(skip_locked=True)
```

On PostgreSQL this compiles to `SELECT ... FOR UPDATE SKIP LOCKED`, so a concurrent claim skips a
locked row and takes the next queued task instead of blocking or receiving a second lease on the
same one. SQLAlchemy's SQLite dialect drops the clause entirely, where `BEGIN IMMEDIATE` already
serializes writers — one statement, both backends correct. The same clause guards lease recovery in
`recover_expired_in_session()`; `heartbeat()` and `commit_terminal()` take a blocking row lock
because they act on one specific task.

Supporting changes in `database.py`:

- `normalize_database_url()` rewrites `postgres://` and `postgresql://` to `postgresql+psycopg://`.
  Without it SQLAlchemy looks for psycopg2, which is not a dependency.
- `immediate_transaction()` issues `BEGIN IMMEDIATE` only on SQLite; it is not valid PostgreSQL.
- `init_db()` retries until the server accepts connections (the API container usually starts before
  PostgreSQL is ready) and wraps `create_all` in `pg_advisory_xact_lock`, so concurrent replicas in
  Q5 cannot race to create the same tables and crash-loop on `DuplicateTable`.

And in `storage.py`, `create_task()` now catches `IntegrityError`: PostgreSQL runs the idempotency
check at READ COMMITTED, so two requests with the same `Idempotency-Key` can both find nothing and
both insert. `uq_task_sender_idempotency` stops the second, and the right response is the row the
winner committed rather than a 500.

## Q5 — Deploy to Kubernetes

Manifests in [`agent-relay/k8s/`](agent-relay/k8s): Namespace, Secret, PostgreSQL (Service +
StatefulSet + PVC), Agent Relay (Service + Deployment).

```bash
cd agent-relay
kind create cluster --name agent-relay
kind load docker-image agent-relay:local --name agent-relay
kubectl apply -f k8s/
kubectl -n agent-relay rollout status statefulset/postgres --timeout=180s
kubectl -n agent-relay rollout status deployment/agent-relay --timeout=180s
kubectl -n agent-relay port-forward svc/agent-relay 8081:8000
RELAY_BASE_URL=http://127.0.0.1:8081 uv run pytest test_integration.py -q
```

The **Deployment** is what holds the replica count, keeps that many Pods running through a
ReplicaSet, and drives rolling updates when the pod template changes. A Service only routes traffic;
ConfigMaps and Secrets only hold data.

Decisions worth noting:

- **`imagePullPolicy: IfNotPresent`** is mandatory. `agent-relay:local` exists in no registry —
  `kind load` side-loads it into the node's image store — so any pull attempt is `ErrImagePull`.
- **PostgreSQL is a StatefulSet, not a Deployment.** Its `volumeClaimTemplate` gives the Pod a PVC
  with a stable identity, so a rescheduled Pod returns to the same disk. A Deployment would share
  one PVC across replicas. `replicas: 1` is deliberate: replicating PostgreSQL needs streaming
  replication and a failover controller, so raising it would only corrupt data.
- **Three probes, three jobs.** `startupProbe` covers the slow first start, where `init_db()` waits
  for PostgreSQL and takes an advisory lock before creating tables. `readinessProbe` hits `/ready`,
  which queries the real tables, so a Pod that lost its database leaves the Service instead of
  serving 500s. `livenessProbe` hits `/health` and deliberately *not* `/ready`: if liveness checked
  the database, one PostgreSQL outage would restart every API Pod in a loop, fixing nothing and
  slowing recovery.
- **`maxUnavailable: 0`** means a new Pod must pass readiness before an old one is removed, so the
  dashboard stays up through an update.

## Q6 — CI/CD

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (repository root) and
[`scripts/act-ci.sh`](scripts/act-ci.sh).

```bash
chmod +x 03-deployment/scripts/act-ci.sh
./03-deployment/scripts/act-ci.sh -j test     # one job
./03-deployment/scripts/act-ci.sh             # test, then deploy
```

If a test fails, **the existing version keeps running and the deployment stops**. The mechanism is
`needs: test` on the deploy job: GitHub Actions never starts it, so nothing is built, nothing is
loaded into kind, and the Pods already serving are untouched.

- **Unique tag per run**: `$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)`. A bare SHA is not
  enough — re-running on the same commit would reuse the tag, `kubectl set image` would be a no-op,
  and nothing would roll out, silently.
- **`rollout status --timeout=180s`** so the job cannot go green while the rollout is still in
  progress, or still failing.
- **`act-ci.sh` bridges two access problems.** act runs each job in a container, which needs (1) a
  Docker socket — Colima's lives at `~/.colima/default/docker.sock`, not the usual path; and (2) a
  kubeconfig that works from inside a container. The host's points at `127.0.0.1:<port>`, which
  inside the job is the job itself, so the script uses `kind get kubeconfig --internal` and joins
  the container to kind's Docker network. That kubeconfig holds a cluster cert and token, so `.act/`
  is gitignored.

### Remaining

- [ ] Run `./03-deployment/scripts/act-ci.sh -j test`
- [ ] Run the full workflow and confirm the rollout finishes
- [ ] Change `dashboard.html` line 18 to `<h1>Agent Relay v2</h1>`, re-run, and verify the new
      heading through `kubectl -n agent-relay port-forward svc/agent-relay 8081:8000`
- [ ] Optional: break an assertion, re-run, and confirm `deploy` never starts and the Deployment
      still points at the previous image

## Running the starter

```bash
cd agent-relay
uv sync
uv run uvicorn main:app --reload     # dashboard at http://127.0.0.1:8000/
uv run pytest -q                     # starter suite + integration tests
```

## Toolchain

Docker via [Colima](https://colima.run) instead of Docker Desktop:

```bash
brew install colima docker docker-compose kubectl kind act
colima start --cpu 4 --memory 8 --disk 60
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"   # needed by act
```
