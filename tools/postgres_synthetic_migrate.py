"""Explicit, disposable localhost-only Postgres schema setup for synthetic CI.

Never use on a live school database. Fails if schema has preexisting tables.
"""
import json
import os
from control_plane.postgres_synthetic import apply_synthetic_migration

if __name__ == '__main__':
    try:
        result=apply_synthetic_migration(os.environ)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit('SYNTHETIC_PG_MIGRATION_BLOCKED: '+str(exc)) from None
    print(json.dumps(result,sort_keys=True))
