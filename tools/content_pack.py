#!/usr/bin/env python3
"""Offline, institution-authorised CHEMFORGE content pack signer/verifier.

Signing proves which private key authorised the data. It does NOT prove a
Chemistry expert checked the content or that ZIMSEC endorsed it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ITEMS={'manifest.json','content.json','signature.der'}
MAX_CONTENT=5_000_000
DOMAINS={'Physical','Inorganic','Organic','Applied','Practical'}

def validate_content(data: dict) -> None:
    if not isinstance(data,dict): raise ValueError('content must be an object')
    if data.get('product')!='CHEMFORGE':raise ValueError('wrong product')
    if not isinstance(data.get('content_version'),str) or not 1<=len(data['content_version'])<=80:
        raise ValueError('invalid content version')
    if not isinstance(data.get('scope'),str) or not data['scope']:
        raise ValueError('missing disclosure scope')
    objectives=data.get('objectives'); questions=data.get('questions')
    if not isinstance(objectives,list) or not 1<=len(objectives)<=1000:raise ValueError('invalid objectives')
    if not isinstance(questions,list) or not 1<=len(questions)<=3000:raise ValueError('invalid questions')
    oids=set(); qids=set()
    for obj in objectives:
        if not isinstance(obj,dict) or not isinstance(obj.get('id'),str) or not obj['id'] or obj['id'] in oids:raise ValueError('duplicate or missing objective id')
        oids.add(obj['id'])
        if obj.get('domain') not in DOMAINS or not isinstance(obj.get('title'),str) or not isinstance(obj.get('competency'),str):raise ValueError('invalid objective metadata')
        if not isinstance(obj.get('prerequisites'),list):raise ValueError('invalid prerequisite links')
    graph={obj['id']:obj['prerequisites'] for obj in objectives}
    for obj in objectives:
        if any(not isinstance(parent,str) or parent not in oids or parent==obj['id'] for parent in obj['prerequisites']):
            raise ValueError('broken objective prerequisite')
    colors={}
    def visit(node):
        if colors.get(node)==1:raise ValueError('cyclic objective prerequisites')
        if colors.get(node)==2:return
        colors[node]=1
        for parent in graph[node]:visit(parent)
        colors[node]=2
    for objective_id in graph:visit(objective_id)
    for q in questions:
        if not isinstance(q,dict) or not isinstance(q.get('id'),str) or not q['id'] or q['id'] in qids:raise ValueError('duplicate or missing question id')
        qids.add(q['id'])
        if q.get('objective_id') not in oids:raise ValueError('question has unknown objective')
        if q.get('paper') not in {'P1','P2','P3','P4'} or q.get('type') not in {'mcq','numeric','constructed'}:raise ValueError('invalid question type or paper')
        if not isinstance(q.get('stem'),str) or not q['stem'] or not isinstance(q.get('explanation'),str):raise ValueError('invalid question prose')
        if not isinstance(q.get('max_marks'),int) or not 1<=q['max_marks']<=25:raise ValueError('invalid marks')
        if not isinstance(q.get('difficulty'),int) or not 1<=q['difficulty']<=5:raise ValueError('invalid difficulty')
        if not isinstance(q.get('review_status'),str):raise ValueError('review status required')
        if q['type']=='mcq':
            ids=[c['id'] for c in q.get('choices',[]) if isinstance(c,dict) and 'id' in c]
            if not 2<=len(ids)<=6 or ids!=list('ABCDEF'[:len(ids)]) or q.get('answer') not in ids:raise ValueError('invalid MCQ answer/choices')
        elif q['type']=='numeric':
            if type(q.get('answer')) not in {int,float} or type(q.get('tolerance')) not in {int,float} or q['tolerance']<0 or not math.isfinite(q['answer']) or not math.isfinite(q['tolerance']):raise ValueError('invalid numeric marking')
            unit=q.get('unit','unitless')
            if not isinstance(unit,str) or not 1<=len(unit)<=60:raise ValueError('invalid numeric unit')
            alt=q.get('accepted_units',[])
            if not isinstance(alt,list) or len(alt)>12:raise ValueError('invalid accepted units')
            seen={unit.strip().lower().replace(' ','')}
            for conversion in alt:
                if not isinstance(conversion,dict) or not isinstance(conversion.get('unit'),str) or not 1<=len(conversion['unit'])<=60:
                    raise ValueError('invalid unit conversion')
                name=conversion['unit'].strip().lower().replace(' ','')
                mult=conversion.get('multiplier')
                if not name or name in seen or type(mult) not in {int,float} or not math.isfinite(mult) or mult<=0:
                    raise ValueError('invalid unit conversion')
                seen.add(name)
        else:
            rubric=q.get('rubric')
            if not isinstance(rubric,list) or not rubric or any(not isinstance(p,dict) or not isinstance(p.get('marks'),int) or p['marks']<=0 or not isinstance(p.get('text'),str) or not p['text'] for p in rubric) or sum(p['marks'] for p in rubric)!=q['max_marks']:raise ValueError('invalid written rubric')

    lessons=data.get('lessons',[])
    if not isinstance(lessons,list) or len(lessons)>1000:raise ValueError('invalid lesson count')
    lseen=set()
    for lesson in lessons:
        if not isinstance(lesson,dict) or lesson.get('objective_id') not in oids or lesson['objective_id'] in lseen:
            raise ValueError('orphaned or duplicate lesson')
        lseen.add(lesson['objective_id'])
        linked=next(item for item in objectives if item['id']==lesson['objective_id'])
        if lesson.get('domain')!=linked['domain']:raise ValueError('lesson domain mismatch')
        for key in ('title','principle','example','common_error','review_status'):
            text=lesson.get(key)
            if not isinstance(text,str) or not 1<=len(text)<=4000:
                raise ValueError('invalid lesson field '+key)

def _serialise(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def create_pack(content_path:Path,private_key_path:Path,output_path:Path,tenant:str,version:int):
    if not tenant or len(tenant)>100 or not re.fullmatch(r'[A-Za-z0-9._-]+',tenant):raise ValueError('invalid tenant id')
    if type(version)!=int or version<1:raise ValueError('pack version must be positive')
    raw=content_path.read_bytes()
    if len(raw)>MAX_CONTENT:raise ValueError('content too large')
    data=json.loads(raw)
    validate_content(data)
    manifest={'schema':'CHEMFORGE_SIGNED_PACK_V1','tenant_id':tenant,'pack_version':version,
              'content_version':data['content_version'],'content_sha256':hashlib.sha256(raw).hexdigest(),
              'signature_algorithm':'SHA256withECDSA-P256'}
    manifest_bytes=_serialise(manifest)
    key=serialization.load_pem_private_key(private_key_path.read_bytes(),password=None)
    if not isinstance(key,ec.EllipticCurvePrivateKey) or not isinstance(key.curve,ec.SECP256R1):
        raise ValueError('signing key must be P-256 ECDSA')
    signature=key.sign(manifest_bytes,ec.ECDSA(hashes.SHA256()))
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output_path,'w',ZIP_DEFLATED) as z:
        z.writestr('manifest.json',manifest_bytes)
        z.writestr('content.json',raw)
        z.writestr('signature.der',signature)
    return manifest

def verify_pack(package:Path,public_key_path:Path,tenant:str|None=None):
    with ZipFile(package) as z:
        names=z.namelist()
        if len(names)!=3 or set(names)!=ITEMS:raise ValueError('invalid pack entries')
        for member in z.infolist():
            if member.file_size > (MAX_CONTENT if member.filename=='content.json' else 8192):raise ValueError('oversized pack entry')
        manifest_bytes=z.read('manifest.json');content=z.read('content.json');signature=z.read('signature.der')
    manifest=json.loads(manifest_bytes)
    if manifest.get('schema')!='CHEMFORGE_SIGNED_PACK_V1' or manifest.get('signature_algorithm')!='SHA256withECDSA-P256':raise ValueError('unsupported manifest')
    if type(manifest.get('pack_version'))!=int or manifest['pack_version']<1:raise ValueError('invalid pack version')
    if tenant and manifest.get('tenant_id')!=tenant:raise ValueError('tenant mismatch')
    pub=serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(pub,ec.EllipticCurvePublicKey) or not isinstance(pub.curve,ec.SECP256R1):raise ValueError('wrong public key type')
    try:pub.verify(signature,manifest_bytes,ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as ex:raise ValueError('invalid signature') from ex
    if hashlib.sha256(content).hexdigest()!=manifest.get('content_sha256'):raise ValueError('digest mismatch')
    data=json.loads(content)
    validate_content(data)
    if manifest.get('content_version')!=data['content_version']:raise ValueError('content version mismatch')
    return {'tenant_id':manifest['tenant_id'],'pack_version':manifest['pack_version'],
            'content_version':data['content_version'],'questions':len(data['questions']),'objectives':len(data['objectives'])}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('sign'); a.add_argument('--content',type=Path,required=True);a.add_argument('--private-key',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--tenant',required=True);a.add_argument('--version',type=int,required=True)
    b=sub.add_parser('verify');b.add_argument('--pack',type=Path,required=True);b.add_argument('--public-key',type=Path,required=True);b.add_argument('--tenant')
    v=p.parse_args()
    result=create_pack(v.content,v.private_key,v.output,v.tenant,v.version) if v.command=='sign' else verify_pack(v.pack,v.public_key,v.tenant)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
