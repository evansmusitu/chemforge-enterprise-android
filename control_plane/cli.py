"""Operator-only bootstrap. Never expose this function on the public HTTP API."""
import argparse
from .db import Database


def main():
    p=argparse.ArgumentParser(description='Provision CHEMFORGE institutional tenant (prints admin token once)')
    p.add_argument('bootstrap',choices=['bootstrap'])
    p.add_argument('--db',required=True,help='Persistent writable SQLite file')
    p.add_argument('--tenant',required=True,help='lowercase institutional ID')
    p.add_argument('--admin-label',required=True)
    args=p.parse_args()
    token=Database(args.db).bootstrap_tenant(args.tenant,args.admin_label)
    print('Tenant:',args.tenant)
    print('Administrator bearer token (displayed only once):',token)
    print('Securely transfer this token to the authorised institution. Do not save to git or logs.')


if __name__=='__main__':
    main()
