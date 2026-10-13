"""Offline-only, synthetic SQLite pilot preflight. NOT a production DB migrator."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import stat
from sqlite3 import connect


def check(path: Path, *, synthetic: bool = False) -> dict:
    if not synthetic:
        raise ValueError('Explicit --synthetic-only acknowledgement is required; do not run on real student data')
    if not path.is_file() or path.is_symlink():
        raise ValueError('Pilot database must be an existing regular non-symlink file')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Pilot database must be owner-only (0600)')
    with connect(f'file:{path.resolve()}?mode=ro',uri=True) as cx:
        integrity=cx.execute('PRAGMA integrity_check').fetchone()[0]
        foreign=cx.execute('PRAGMA foreign_key_check').fetchall()
        tables={row[0] for row in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed={'actors','tenants','oidc_actor_links','oidc_auth_flows','oidc_browser_sessions',
                'students','devices','teacher_cohorts','evidence','audit'}
        if integrity != 'ok' or foreign or not needed.issubset(tables):
            raise ValueError('Pilot database has integrity, foreign-key or schema problems')
    return {'status':'pass','environment':'synthetic-only-local-sqlite',
            'sqlite_integrity':'ok','foreign_key_errors':0,
            'production_postgresql':'NOT_CONFIGURED',
            'production_readiness':'NOT_ASSESSED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--synthetic-only',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(check(args.db,synthetic=args.synthetic_only),sort_keys=True))
    except (ValueError,OSError) as exc:
        parser.exit(2,'STAGING PRECHECK BLOCKED: '+str(exc)+'\n')


if __name__=='__main__':
    main()
