"""CHEMFORGE Control pilot API.

A distinct connected teacher/admin service; the Android app still has no
INTERNET permission. No endpoint certifies imported assessment marks.
"""

from pathlib import Path
from fastapi.responses import FileResponse
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Annotated, Literal
from uuid import uuid4
import json
import os
import re
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from .db import Database, new_token, token_digest, utcnow


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TeacherIn(StrictModel):
    label: str = Field(min_length=1,max_length=80)


class TeacherCohortIn(StrictModel):
    cohort: str = Field(min_length=1,max_length=40)


class DeviceIn(StrictModel):
    student_id: str = Field(min_length=10,max_length=64)
    label: str = Field(min_length=1,max_length=80)
    valid_days: int = Field(default=30,ge=1,le=90)


class StudentIn(StrictModel):
    pseudonym: str = Field(min_length=1,max_length=80)
    cohort: str = Field(min_length=1,max_length=40)


class AssignmentIn(StrictModel):
    title: str = Field(min_length=1,max_length=120)
    cohort: str = Field(min_length=1,max_length=40)
    objective_ids: list[str] = Field(min_length=1,max_length=40)
    due_at: datetime | None = None

    @field_validator('objective_ids')
    @classmethod
    def validate_objectives(cls, v):
        if len(set(v)) != len(v) or any(not re.fullmatch(r'[a-zA-Z0-9_.-]{2,80}', x) for x in v):
            raise ValueError('invalid or duplicate objective identifier')
        return v

    @field_validator('due_at')
    @classmethod
    def require_timezone(cls, v):
        if v is not None and (v.tzinfo is None or v.utcoffset() is None):
            raise ValueError('due_at must contain an explicit timezone')
        return v


class EvidenceIn(StrictModel):
    event_id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{2,100}$')
    student_id: str = Field(min_length=10,max_length=64)
    question_id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,100}$')
    assessment_source: Literal['deterministic_key','numeric_tolerance','learner_self_review']
    mark: int = Field(ge=0,le=1000)
    max_marks: int = Field(ge=1,le=1000)
    content_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    recorded_at: datetime

    @field_validator('recorded_at')
    @classmethod
    def explicit_recorded_timezone(cls, v):
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError('recorded_at must contain an explicit timezone')
        return v

    @model_validator(mode='after')
    def sensible_mark(self):
        if self.mark>self.max_marks:
            raise ValueError('mark cannot exceed max_marks')
        return self


class BackupAttempt(StrictModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{2,100}$')
    question_id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,100}$')
    mark: int = Field(ge=0,le=1000)
    max_marks: int = Field(ge=1,le=1000)
    assessment_source: Literal['deterministic_key','numeric_tolerance','learner_self_review']
    mode: Literal['practice','exam','diagnostic']
    hints_used: int = Field(ge=0,le=5)
    recorded_at: datetime
    tenant_id: str
    content_version: str
    content_fingerprint: str
    diagnosis: str | None = Field(default=None, max_length=120)
    outcome: str | None = Field(default=None, max_length=40)
    unverified_import: bool = False

    @model_validator(mode='after')
    def check(self):
        if self.mark>self.max_marks or self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError('Invalid mark or timestamp')
        return self


class BackupIn(StrictModel):
    app: Literal['CHEMFORGE_ANDROID']
    schema_version: Literal[1]
    tenant_id: str
    content_version: str = Field(min_length=1,max_length=120)
    content_fingerprint: str = Field(pattern=r'^(?:[0-9a-f]{64}|pilot-0\.1)$')
    exported_at: datetime | None = None
    attempts: list[BackupAttempt] = Field(max_length=1000)

    @model_validator(mode='after')
    def check(self):
        ids=set()
        for entry in self.attempts:
            if entry.id in ids:
                raise ValueError('Duplicate backup event ID')
            ids.add(entry.id)
            if (entry.tenant_id != self.tenant_id or entry.content_version != self.content_version or
                entry.content_fingerprint != self.content_fingerprint):
                raise ValueError('Backup entry does not match envelope tenant/content')
        return self


class ReleaseIn(StrictModel):
    pack_version: int = Field(ge=1)
    content_version: str = Field(min_length=1,max_length=120)
    pack_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    content_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


def create_app(db_path: str | None = None) -> FastAPI:
    db = Database(db_path or os.environ.get('CHEMFORGE_CONTROL_DB','control.sqlite'))
    app = FastAPI(title='CHEMFORGE Control',version='0.3.0',
                  description='Tenant-isolated administrative pilot; imported marks are unverified.')

    # Same-origin dashboard assets; keep credentials in volatile browser memory only.
    # The shell is public. Every institution data request still uses the API's
    # existing bearer authentication and tenant-level authorization.
    dashboard_dir = Path(__file__).resolve().parent / 'dashboard'
    dashboard_headers = {
        'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; "
                                   "connect-src 'self'; img-src 'self' data:; "
                                   "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
        'X-Frame-Options': 'DENY',
    }

    @app.get('/control/', include_in_schema=False)
    def dashboard_shell():
        return FileResponse(dashboard_dir / 'index.html', media_type='text/html',
                            headers=dashboard_headers)

    @app.get('/control/app.js', include_in_schema=False)
    def dashboard_javascript():
        return FileResponse(dashboard_dir / 'app.js', media_type='text/javascript',
                            headers=dashboard_headers)

    @app.get('/control/styles.css', include_in_schema=False)
    def dashboard_styles():
        return FileResponse(dashboard_dir / 'styles.css', media_type='text/css',
                            headers=dashboard_headers)

    def actor(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401,'Valid Bearer token required',headers={'WWW-Authenticate':'Bearer'})
        secret=authorization[7:]
        if len(secret)>120 or not re.fullmatch(r'cfcp_[A-Za-z0-9_-]{40,60}',secret):
            raise HTTPException(401,'Invalid bearer credential',headers={'WWW-Authenticate':'Bearer'})
        with db.connect() as cx:
            row=cx.execute('''SELECT id,tenant_id,label,role FROM actors
                              WHERE token_hash=? AND revoked_at IS NULL''', (token_digest(secret),)).fetchone()
        if row is None:
            raise HTTPException(401,'Invalid or revoked bearer credential',headers={'WWW-Authenticate':'Bearer'})
        return dict(row)

    def require_admin(a: Annotated[dict,Depends(actor)]):
        if a['role']!='admin':
            raise HTTPException(403,'Institution administrator privilege required')
        return a

    def can_access_cohort(cx, a: dict, cohort: str) -> bool:
        if a['role']=='admin':
            return True
        return cx.execute('''SELECT 1 FROM teacher_cohorts
             WHERE tenant_id=? AND actor_id=? AND cohort=?''',
             (a['tenant_id'],a['id'],cohort)).fetchone() is not None

    def enforce_cohort(cx, a: dict, cohort: str):
        if not can_access_cohort(cx,a,cohort):
            raise HTTPException(403,'Not assigned to this cohort')

    def require_device(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith('Device '):
            raise HTTPException(401,'Device credential required')
        secret=authorization[7:]
        if len(secret)>120 or not re.fullmatch(r'cfsync_[A-Za-z0-9_-]{40,60}',secret):
            raise HTTPException(401,'Invalid device credential')
        with db.connect() as cx:
            row=cx.execute('''SELECT id,tenant_id,student_id,expires_at FROM devices
                               WHERE token_hash=? AND revoked_at IS NULL''',(token_digest(secret),)).fetchone()
        if row is None or datetime.fromisoformat(row['expires_at']) <= datetime.now(timezone.utc):
            raise HTTPException(401,'Expired or revoked device credential')
        return dict(row)

    @app.get('/health')
    def health():
        return {'status':'ok'}

    @app.get('/v1/me')
    def me(a: Annotated[dict,Depends(actor)]):
        return a

    @app.post('/v1/teachers',status_code=201)
    def create_teacher(body: TeacherIn, a: Annotated[dict,Depends(require_admin)]):
        token = new_token()
        actor_id = str(uuid4())
        with db.connect() as cx:
            cx.execute('''INSERT INTO actors(id,tenant_id,label,role,token_hash,created_at)
                          VALUES(?,?,?,?,?,?)''', (actor_id,a['tenant_id'],body.label,'teacher',token_digest(token),utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'teacher.created',actor_id)
        return {'actor_id':actor_id,'token':token,'note':'Credential shown only once; store securely.'}

    @app.post('/v1/teachers/{actor_id}/cohorts',status_code=201)
    def grant_cohort(actor_id: str,body: TeacherCohortIn,a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            teacher=cx.execute('''SELECT id FROM actors WHERE id=? AND tenant_id=?
                                AND role='teacher' AND revoked_at IS NULL''',
                                (actor_id,a['tenant_id'])).fetchone()
            if not teacher:raise HTTPException(404,'Teacher not found')
            cx.execute('''INSERT OR IGNORE INTO teacher_cohorts(tenant_id,actor_id,cohort,granted_at)
                          VALUES(?,?,?,?)''',(a['tenant_id'],actor_id,body.cohort,utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'teacher.cohort_granted',actor_id)
        return {'actor_id':actor_id,'cohort':body.cohort}

    @app.get('/v1/teachers/{actor_id}/cohorts')
    def list_teacher_cohorts(actor_id: str,a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            teacher=cx.execute('''SELECT id FROM actors WHERE id=? AND tenant_id=?
                                AND role='teacher' AND revoked_at IS NULL''',
                                (actor_id,a['tenant_id'])).fetchone()
            if not teacher:raise HTTPException(404,'Teacher not found')
            rows=cx.execute('''SELECT cohort FROM teacher_cohorts
                               WHERE tenant_id=? AND actor_id=? ORDER BY cohort''',
                               (a['tenant_id'],actor_id)).fetchall()
            return [x['cohort'] for x in rows]

    @app.delete('/v1/teachers/{actor_id}/cohorts/{cohort}',status_code=204)
    def remove_cohort(actor_id: str,cohort: str,a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            result=cx.execute('''DELETE FROM teacher_cohorts
                                 WHERE tenant_id=? AND actor_id=? AND cohort=?''',
                                 (a['tenant_id'],actor_id,cohort))
            if not result.rowcount:raise HTTPException(404,'Cohort grant not found')
            db.audit(cx,a['tenant_id'],a['id'],'teacher.cohort_revoked',actor_id)

    @app.get('/v1/teachers')
    def teachers(a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT id,label,role,created_at FROM actors
                               WHERE tenant_id=? AND role='teacher' AND revoked_at IS NULL ORDER BY created_at,id''', (a['tenant_id'],)).fetchall()
        return [dict(r) for r in rows]

    @app.delete('/v1/teachers/{actor_id}',status_code=204)
    def revoke_teacher(actor_id: str, a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            result=cx.execute('''UPDATE actors SET revoked_at=? WHERE id=? AND tenant_id=?
                                 AND role='teacher' AND revoked_at IS NULL''', (utcnow(),actor_id,a['tenant_id']))
            if not result.rowcount:
                raise HTTPException(404,'Teacher not found')
            cx.execute('DELETE FROM teacher_cohorts WHERE tenant_id=? AND actor_id=?',(a['tenant_id'],actor_id))
            db.audit(cx,a['tenant_id'],a['id'],'teacher.revoked',actor_id)

    @app.post('/v1/students',status_code=201)
    def create_student(body: StudentIn, a: Annotated[dict,Depends(actor)]):
        student_id=str(uuid4())
        with db.connect() as cx:
            enforce_cohort(cx,a,body.cohort)
            cx.execute('''INSERT INTO students(id,tenant_id,pseudonym,cohort,created_at)
                          VALUES(?,?,?,?,?)''',(student_id,a['tenant_id'],body.pseudonym,body.cohort,utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'student.created',student_id)
        return {'id':student_id,'pseudonym':body.pseudonym,'cohort':body.cohort}

    @app.get('/v1/students')
    def students(a: Annotated[dict,Depends(actor)],cohort: str | None = None):
        if cohort is not None and len(cohort)>40:
            raise HTTPException(422,'cohort too long')
        with db.connect() as cx:
            clause='''( ?='admin' OR EXISTS (SELECT 1 FROM teacher_cohorts tc
                 WHERE tc.tenant_id=s.tenant_id AND tc.actor_id=? AND tc.cohort=s.cohort))'''
            params=[a['tenant_id'],a['role'],a['id']]
            if cohort is not None:
                clause += ' AND s.cohort=?'
                params.append(cohort)
            rows=cx.execute('SELECT s.id,s.pseudonym,s.cohort,s.created_at FROM students s '
                            'WHERE s.tenant_id=? AND '+clause+' ORDER BY s.cohort,s.pseudonym,s.id LIMIT 1000',params).fetchall()
        return [dict(r) for r in rows]

    @app.delete('/v1/students/{student_id}',status_code=204)
    def delete_student(student_id: str,a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            removed=cx.execute('DELETE FROM students WHERE tenant_id=? AND id=?',(a['tenant_id'],student_id))
            if removed.rowcount == 0:
                raise HTTPException(404,'Student not found')
            db.audit(cx,a['tenant_id'],a['id'],'student.deleted',student_id)

    @app.post('/v1/assignments',status_code=201)
    def create_assignment(body: AssignmentIn,a: Annotated[dict,Depends(actor)]):
        assignment_id=str(uuid4())
        with db.connect() as cx:
            enforce_cohort(cx,a,body.cohort)
            cx.execute('''INSERT INTO assignments(id,tenant_id,title,cohort,objectives_json,due_at,actor_id,created_at)
                          VALUES(?,?,?,?,?,?,?,?)''',(assignment_id,a['tenant_id'],body.title,body.cohort,
                          json.dumps(body.objective_ids),body.due_at.isoformat() if body.due_at else None,a['id'],utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'assignment.created',assignment_id)
        return {'id':assignment_id,'title':body.title,'cohort':body.cohort,'objective_ids':body.objective_ids,
                'due_at':body.due_at.isoformat() if body.due_at else None}

    @app.get('/v1/assignments')
    def assignments(a: Annotated[dict,Depends(actor)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT id,title,cohort,objectives_json,due_at,created_at FROM assignments
                               WHERE tenant_id=? AND (?='admin' OR EXISTS(SELECT 1 FROM teacher_cohorts tc WHERE tc.tenant_id=assignments.tenant_id AND tc.actor_id=? AND tc.cohort=assignments.cohort)) ORDER BY created_at DESC,id DESC LIMIT 1000''', (a['tenant_id'],a['role'],a['id'])).fetchall()
        return [dict(id=r['id'], title=r['title'], cohort=r['cohort'],
                     objective_ids=json.loads(r['objectives_json']), due_at=r['due_at'],
                     created_at=r['created_at']) for r in rows]

    @app.post('/v1/evidence')
    def import_evidence(body: EvidenceIn, a: Annotated[dict,Depends(actor)]):
        # No promoted/verified state: JSON exports are student-controlled and may be edited.
        evidence_payload=body.model_dump(mode='json')
        canonical=json.dumps(evidence_payload,sort_keys=True,separators=(',',':'))
        digest=sha256(canonical.encode()).hexdigest()
        with db.connect() as cx:
            # Serialize writes to avoid a concurrent duplicate insert becoming an internal error.
            cx.execute('BEGIN IMMEDIATE')
            member=cx.execute('SELECT cohort FROM students WHERE tenant_id=? AND id=?',
                              (a['tenant_id'],body.student_id)).fetchone()
            if member is None:
                raise HTTPException(404,'Student not found')
            enforce_cohort(cx,a,member['cohort'])
            previous=cx.execute('''SELECT payload_sha256 FROM evidence
                                   WHERE tenant_id=? AND event_id=?''',(a['tenant_id'],body.event_id)).fetchone()
            if previous is not None:
                if previous['payload_sha256'] != digest:
                    raise HTTPException(409,'Event ID already exists with different content')
                return {'event_id':body.event_id,'verification_status':'unverified_import',
                        'disposition':'already_received'}
            cx.execute('''INSERT INTO evidence(tenant_id,event_id,student_id,question_id,payload_sha256,
                          payload_json,verification_status,received_at) VALUES(?,?,?,?,?,?,?,?)''',
                          (a['tenant_id'],body.event_id,body.student_id,body.question_id,digest,canonical,
                           'unverified_import',utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'evidence.imported',body.event_id)
        return status_response_created({'event_id':body.event_id,'verification_status':'unverified_import','disposition':'received'})

    def ingest_backup(student_id: str,body: BackupIn,tenant_id: str,actor_id: str,
                      cohort_actor: dict | None = None):
        # Atomic, idempotent, unverified. Device-auth never chooses student_id.
        imported=0
        unchanged=0
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            member=cx.execute('SELECT cohort FROM students WHERE tenant_id=? AND id=?',
                              (tenant_id,student_id)).fetchone()
            if member is None:raise HTTPException(404,'Student not found')
            if cohort_actor is not None:enforce_cohort(cx,cohort_actor,member['cohort'])
            if body.tenant_id != tenant_id:
                raise HTTPException(422,'Backup tenant must match your institution')
            for att in body.attempts:
                mapped={'event_id':att.id,'student_id':student_id,'question_id':att.question_id,
                        'mark':att.mark,'max_marks':att.max_marks,
                        'assessment_source':att.assessment_source,'hints_used':att.hints_used,
                        'mode':att.mode,'content_fingerprint':body.content_fingerprint,
                        'content_version':body.content_version,'recorded_at':att.recorded_at.isoformat(),
                        'unverified_import':True}
                canonical=json.dumps(mapped,sort_keys=True,separators=(',',':'))
                digest=sha256(canonical.encode()).hexdigest()
                previous=cx.execute('SELECT payload_sha256 FROM evidence WHERE tenant_id=? AND event_id=?',
                                    (tenant_id,att.id)).fetchone()
                if previous:
                    if previous['payload_sha256']!=digest:
                        raise HTTPException(409,'Existing event conflicts with imported record')
                    unchanged+=1
                    continue
                cx.execute('''INSERT INTO evidence(tenant_id,event_id,student_id,question_id,payload_sha256,
                              payload_json,verification_status,received_at) VALUES(?,?,?,?,?,?,?,?)''',
                           (tenant_id,att.id,student_id,att.question_id,digest,canonical,'unverified_import',utcnow()))
                imported+=1
            db.audit(cx,tenant_id,actor_id,'backup.imported',student_id)
        data={'student_id':student_id,'imported':imported,'unchanged':unchanged,'verified':0,
              'disclaimer':'Student-controlled export; not independently verified or certified.'}
        return status_response_created(data) if imported else data

    @app.post('/v1/students/{student_id}/backups')
    def import_offline_backup(student_id: str,body: BackupIn,a: Annotated[dict,Depends(actor)]):
        return ingest_backup(student_id,body,a['tenant_id'],a['id'],cohort_actor=a)

    @app.post('/v1/devices',status_code=201)
    def register_device(body: DeviceIn,a: Annotated[dict,Depends(require_admin)]):
        secret='cfsync_'+secrets.token_urlsafe(32)
        device_id=str(uuid4())
        expires=(datetime.now(timezone.utc)+timedelta(days=body.valid_days)).isoformat()
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            if not cx.execute('SELECT 1 FROM students WHERE tenant_id=? AND id=?',
                              (a['tenant_id'],body.student_id)).fetchone():
                raise HTTPException(404,'Student not found')
            cx.execute('''INSERT INTO devices(id,tenant_id,student_id,label,token_hash,issued_at,expires_at)
                          VALUES(?,?,?,?,?,?,?)''',
                       (device_id,a['tenant_id'],body.student_id,body.label,token_digest(secret),utcnow(),expires))
            db.audit(cx,a['tenant_id'],a['id'],'device.issued',device_id)
        return {'device_id':device_id,'student_id':body.student_id,'expires_at':expires,
                'token':secret,'note':'Shown once; scope is exactly one student, study imports only.'}

    @app.get('/v1/devices')
    def list_devices(a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT id,student_id,label,issued_at,expires_at FROM devices
                               WHERE tenant_id=? AND revoked_at IS NULL ORDER BY issued_at DESC,id''',
                            (a['tenant_id'],)).fetchall()
        return [dict(row) for row in rows]

    @app.delete('/v1/devices/{device_id}',status_code=204)
    def revoke_device(device_id: str,a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            changed=cx.execute('''UPDATE devices SET revoked_at=? WHERE id=? AND tenant_id=? AND revoked_at IS NULL''',
                               (utcnow(),device_id,a['tenant_id']))
            if not changed.rowcount:raise HTTPException(404,'Device not found')
            db.audit(cx,a['tenant_id'],a['id'],'device.revoked',device_id)

    @app.post('/v1/sync/backups')
    def sync_offline_backup(body: BackupIn, device: Annotated[dict,Depends(require_device)]):
        return ingest_backup(device['student_id'],body,device['tenant_id'],device['id'])

    @app.post('/v1/content/releases',status_code=201)
    def publish_release(body: ReleaseIn,a: Annotated[dict,Depends(require_admin)]):
        """Catalog metadata only; this server never signs or authenticates a cfpack."""
        with db.connect() as cx:
            cx.execute('BEGIN IMMEDIATE')
            previous=cx.execute('SELECT MAX(pack_version) AS rev FROM content_releases WHERE tenant_id=?',
                                (a['tenant_id'],)).fetchone()
            if previous['rev'] is not None and body.pack_version<=previous['rev']:
                raise HTTPException(409,'Pack revision must increase monotonically')
            cx.execute('''INSERT INTO content_releases(tenant_id,pack_version,content_version,pack_sha256,
                          content_fingerprint,actor_id,created_at) VALUES(?,?,?,?,?,?,?)''',
                          (a['tenant_id'],body.pack_version,body.content_version,body.pack_sha256,
                           body.content_fingerprint,a['id'],utcnow()))
            db.audit(cx,a['tenant_id'],a['id'],'content.release_registered',str(body.pack_version))
        return {**body.model_dump(),'status':'metadata_only_not_signature_verified'}

    @app.get('/v1/content/releases')
    def releases(a: Annotated[dict,Depends(actor)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT pack_version,content_version,pack_sha256,content_fingerprint,created_at
                               FROM content_releases WHERE tenant_id=? ORDER BY pack_version DESC LIMIT 100''',
                               (a['tenant_id'],)).fetchall()
        return [dict(r) for r in rows]

    @app.get('/v1/analytics/cohorts')
    def analytics(a: Annotated[dict,Depends(actor)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT s.cohort AS cohort,
                              COUNT(DISTINCT s.id) AS students,
                              COUNT(e.event_id) AS unverified_attempts
                              FROM students s LEFT JOIN evidence e
                                ON s.tenant_id=e.tenant_id AND s.id=e.student_id
                              WHERE s.tenant_id=? AND (?='admin' OR EXISTS (SELECT 1 FROM teacher_cohorts tc WHERE tc.tenant_id=s.tenant_id AND tc.actor_id=? AND tc.cohort=s.cohort)) GROUP BY s.cohort ORDER BY s.cohort''',(a['tenant_id'],a['role'],a['id'])).fetchall()
        return [{**dict(row),'verified_attempts':0} for row in rows]

    @app.get('/v1/audit')
    def audit(a: Annotated[dict,Depends(require_admin)]):
        with db.connect() as cx:
            rows=cx.execute('''SELECT id,actor_id,action,subject_id,occurred_at FROM audit
                               WHERE tenant_id=? ORDER BY id DESC LIMIT 500''',(a['tenant_id'],)).fetchall()
        return [dict(r) for r in rows]

    return app


def status_response_created(payload: dict):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=201,content=payload)

