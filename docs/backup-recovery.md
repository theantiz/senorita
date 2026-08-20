# Señorita AI — Backup and Recovery

## Database Backups

Señorita relies exclusively on PostgreSQL (`pgvector`) for state.

### Automated Backups
In a production deployment, use `pg_dump` via a cron job, or rely on managed database automated backups (e.g., AWS RDS, GCP Cloud SQL).

Example manual logical backup:
```bash
pg_dump -U senorita -h localhost -p 5432 -F c -f senorita_backup_$(date +%F).dump senorita
```

### Critical Tables
The following tables contain highly sensitive user data and must be protected in backups:
- `integrations` (contains encrypted OAuth tokens)
- `memory_entries` (contains vectorized personal data)
- `tool_invocations` (contains command histories and arguments)

## Recovery Procedures

### Restoring from Backup
```bash
pg_restore -U senorita -h localhost -p 5432 -d senorita -1 senorita_backup_YYYY-MM-DD.dump
```

### Stale Agent Runs
If the server crashes abruptly, some `agent_runs` and `tool_invocations` may be stuck in a `RUNNING` status.
**Recovery:** Automatic. The `stale_run_recovery_loop` background worker will detect these upon startup (or within 2 minutes) and transition them to `FAILED`.

### OAuth Token Revocation
If `ENCRYPTION_KEY` is compromised:
1. Issue a rotation of the key.
2. The old tokens in the `integrations` table will fail to decrypt. Users will need to re-authenticate their Slack and Gmail connections.

### Event Replay
The frontend relies on `lastSequence` from the WebSocket. If the frontend is disconnected, it will reconnect and send `last_sequence=N`. The backend will automatically replay all `agent_events` where `sequence_number > N`. No manual intervention is needed for dropped connections.
