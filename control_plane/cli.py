"""Operator-only identity provisioning. No matching public HTTP mutation routes."""
import argparse
from .db import Database


def main():
    p=argparse.ArgumentParser(description='CHEMFORGE Control offline operator commands')
    commands=p.add_subparsers(dest='command',required=True)
    bootstrap=commands.add_parser('bootstrap',help='Create new institution and first pilot admin')
    bootstrap.add_argument('--db',required=True,help='Writable SQLite database file')
    bootstrap.add_argument('--tenant',required=True,help='Institution ID')
    bootstrap.add_argument('--admin-label',required=True)

    link=commands.add_parser('link-oidc',help='Link provider identity to an EXISTING local staff actor')
    link.add_argument('--db',required=True,help='Writable SQLite database file')
    link.add_argument('--tenant',required=True,help='Institution ID')
    link.add_argument('--actor-id',required=True,help='Pre-authorised local admin/teacher actor ID')
    link.add_argument('--issuer',required=True,help='Exact configured HTTPS issuer')
    link.add_argument('--subject',required=True,help='Immutable issuer subject (not email)')

    args=p.parse_args()
    db=Database(args.db)
    if args.command=='bootstrap':
        token=db.bootstrap_tenant(args.tenant,args.admin_label)
        print('Tenant:',args.tenant)
        print('Administrator bearer token (displayed only once):',token)
        print('Pilot only: disabled when CHEMFORGE_STAFF_AUTH=oidc.')
    else:
        db.link_oidc_subject(args.tenant,args.actor_id,args.issuer,args.subject)
        print('Existing staff account linked to OIDC identity (subject withheld).')
        print('No new staff actor or bearer token was created.')


if __name__=='__main__':
    main()
