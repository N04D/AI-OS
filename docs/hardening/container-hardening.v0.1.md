# Container Hardening v0.1 (Telegram Ingress)

## Purpose
This hardening profile isolates Telegram webhook ingress in a dedicated container
while keeping plugin runner/dispatch/event processing outside the containerized
execution boundary.

## Threat Model
Why containerize:
- Reduce blast radius of webhook-facing code.
- Limit filesystem and privilege access of ingress process.
- Enforce a single-purpose runtime boundary.

Mitigated in this POC:
- Accidental root execution in ingress process.
- Unnecessary Linux capability exposure.
- Privilege escalation via setuid/setcap paths (`no-new-privileges`).
- Broad filesystem write access (read-only root FS + narrow RW mounts).

Not fully mitigated in v0.1:
- Kernel/container escape class vulnerabilities.
- Misconfiguration at reverse proxy/TLS layer.
- Compromised host runtime or Docker daemon.
- Denial-of-service from high-rate ingress traffic.

## Implemented Artifacts
- `docker/Dockerfile.webhook`
- `docker/docker-compose.yml`

## Security Controls Mapping
### Non-root user
Dockerfile creates `aios` user (`uid/gid 10001`) and runs app as that user.

### Read-only root filesystem
Compose sets `read_only: true` to prevent writes to image filesystem.

### Dropped capabilities
Compose sets:
- `cap_drop: [ALL]`

### No new privileges
Compose sets:
- `security_opt: ["no-new-privileges:true"]`

### tmpfs for `/tmp`
Compose sets:
- `/tmp:rw,noexec,nosuid,nodev,size=64m`

### Restricted writable mounts
Only these host paths are writable in container:
- `../state -> /app/state`
- `../logs -> /app/logs`

No runner service or plugin executor is containerized here.

## Environment Variables
Required:
- `AIOS_TELEGRAM_WEBHOOK_SECRET`
- `AIOS_TELEGRAM_ALLOWED_CHAT_IDS`
- `AIOS_TELEGRAM_BOT_TOKEN`
- `AIOS_TELEGRAM_WEBHOOK_URL`
- `AIOS_VALIDATE_WEBHOOK_ON_STARTUP`

Optional (defaults shown in compose):
- `AIOS_REGISTRY_PATH` (default `/app/state/plugins/registry.json`)
- `AIOS_CONFIG_PATH` (default `/app/state/plugins/config.json`)
- `AIOS_EVENT_AUDIT_LOG_PATH` (default `/app/logs/control/kernel-events.jsonl`)
- `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default `/app/logs/control/channel-telegram.jsonl`)

## Build and Run
```bash
cd docker
docker compose up -d --build
```

## Observability (v0.1)
Ingress exposes local JSON endpoints:
- `GET /health`
- `GET /metrics`

Example:
```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/metrics
```

Health payload:
- `ok`, `service`, `timestamp`
- Returns `ok:false` with `reason=WEBHOOK_INVALID` when runtime webhook validation fails.

Metrics payload (local JSON only):
- `uptime_seconds`
- `events_processed`
- `replays_blocked`
- `plugins_enabled`
- `plugins_unhealthy`

Notes:
- No Prometheus/exporter integration in v0.1.
- Metrics are process-local and reset on restart.
- Suitable for reverse-proxy health checks and basic dashboards.

## Hardening Verification
```bash
docker inspect telegram-ingress --format '{{.Config.User}}'
docker inspect telegram-ingress --format '{{.HostConfig.ReadonlyRootfs}}'
docker inspect telegram-ingress --format '{{json .HostConfig.CapDrop}}'
docker inspect telegram-ingress --format '{{json .HostConfig.SecurityOpt}}'
docker inspect telegram-ingress --format '{{json .HostConfig.Tmpfs}}'
```

Container health probe example:
```bash
curl -f http://127.0.0.1:8080/health
```

Expected highlights:
- user is non-root
- readonly rootfs is `true`
- cap drop contains `ALL`
- security options include `no-new-privileges:true`
- `/tmp` tmpfs present with `noexec,nosuid`

## Reverse Proxy + TLS
Do not publish container directly to the internet in production.
Recommended deployment:
1. Place Nginx/Caddy/Traefik in front of `telegram-ingress`.
2. Terminate TLS at proxy.
3. Forward only `POST /webhook/telegram` to container port 8080.
4. Restrict source IPs where possible (Telegram CIDRs or edge ACLs).

## Known Limitations (v0.1)
- No container-level seccomp/apparmor profile customization yet.
- No mTLS between proxy and container.
- No resource quotas/cgroup limits defined in compose.
- Runner remains outside container by design in this phase.
