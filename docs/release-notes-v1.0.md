# API Health Checker v1.0.0

Release notes prepared on 18 October 2026. This document is a release draft;
it does not create a Git tag or publish a GitHub release.

## Overview

The first release brings together API checks, incident history, a readable web
dashboard, monitoring alerts, and a tested Docker-volume recovery workflow.
It is a local application-support and service-reliability portfolio project.

## Included in this release

- HTTP endpoint monitoring with timeouts, configurable intervals, and optional
  bearer-token or API-key authentication through environment variables.
- `UP`, `SLOW` and `FAIL` observations, response times, rotating logs, JSON reports,
  CSV history, and persisted checker notification state.
- Incident start, recovery and observed duration derived from retained checks.
- A dark dashboard with API health tables, incident history, filters, CSV export,
  demo data, and warnings for overdue observations or future timestamps.
- A shared Docker image, a full Docker Compose monitoring stack, and separate
  single-replica Kubernetes manifests for the checker and dashboard.
- Prometheus metrics and alert rules for overdue monitoring, an unreachable
  exporter, and repeated fresh API failures; a provisioned Grafana dashboard.
- Alertmanager firing/resolved notifications through local Mailpit capture or
  the Brevo SMTP override. Optional checker notifications use Brevo's HTTP API.
- Checksum-verified monitoring-volume backups and restore into an empty volume.
- Unit tests and CI checks for containers, metrics, dashboards, alert delivery,
  and backup/restore using isolated test data.

## Final review improvements

- Reject duplicate endpoint names so failure counters cannot be shared by two
  configured endpoints; reject invalid or blank names.
- Replace built-in checker email addresses with `ALERT_SENDER_EMAIL` and
  `ALERT_RECIPIENT_EMAIL`. Missing settings prevent sending and report an error.
- Use `requirements.txt` for Docker, CI and documented Python installation; add
  a dependency compatibility check to CI.
- Document SMTP-enabled startup and recreation commands to preserve real-inbox
  delivery instead of inadvertently restoring the base Mailpit configuration.

## Validation recorded

- All 63 unit tests passed after the final review changes, and the PR's GitHub
  Actions workflow passed before merging.
- `pip check` passed. On 18 October 2026, pip-audit 2.10.1 reported no known
  vulnerabilities in the six resolved runtime packages. This is a point-in-time
  Python dependency check, not an audit of container OS packages.
- SMTP-enabled Compose configuration and Kubernetes manifest rendering passed.
- Deployed tests demonstrated monitoring freshness warnings and recovery,
  Kubernetes history retention across Pod replacement, and firing/resolved
  notifications reaching a real inbox through Brevo SMTP.
- A live backup containing 1,064 checks was verified, restored into a separate
  volume and read by the statistics tool. A later backup containing 1,210 checks
  was verified locally and uploaded to private Google Drive storage; uploaded
  byte size matched. The later backup was not independently restore-tested.

## Start or update

From the repository folder, with Docker Desktop running in Linux containers mode
and the local SMTP files configured as described in the README:

```powershell
docker compose -f compose.yaml -f compose.email.yaml up --build -d
docker compose -f compose.yaml -f compose.email.yaml ps
```

Open the API dashboard at http://127.0.0.1:8080 and Grafana at
http://127.0.0.1:3000. Keep both Compose files when recreating the SMTP-enabled
stack. For a deliberate local-only Mailpit demo, use the base file alone.

Users of checker Brevo HTTP API notifications must configure `BREVO_API_KEY`,
`ALERT_SENDER_EMAIL` and `ALERT_RECIPIENT_EMAIL` before recreating the checker.
These settings do not change Alertmanager's separate SMTP configuration.

## Known limitations

- This is a single-writer, file-based monitor, without high availability.
  Kubernetes Pod replacement briefly interrupts the checker and dashboard.
- Status and response times are last recorded observations. Stale data means
  current health is unknown; incident durations are bounded by recorded checks.
- CSV history grows without automatic retention. Prometheus scrapes snapshots
  and does not backfill individual historical response-time observations.
- Monitoring-volume backups exclude configuration, credentials, Prometheus,
  Grafana, Alertmanager, Mailpit and Kubernetes PVCs. ZIPs are not encrypted.
- Google Drive copies have been verified manually. The scheduled Codex backup
  remains blocked by Docker access permissions; unattended backup has not passed
  an end-to-end test and must not be relied on yet.
- The full Prometheus/Grafana/Alertmanager stack is supplied for Compose;
  Kubernetes manifests deploy only the checker and dashboard.
- Enabling both checker API emails and Alertmanager emails can duplicate API
  failure notifications. The stack does not independently detect Prometheus
  itself stopping.

See [the project summary and architecture](project-summary.md),
[README](../README.md), and [backup/restore guide](backup-restore.md).
