"""Browser DOM functional test with actual TestClient API; no browser network socket.

This environment forbids Chromium localhost navigation. The page HTML/CSS/JS are
loaded from disk, the API calls are bridged to real FastAPI TestClient requests,
and HTTPS-origin enforcement is bypassed ONLY inside the test's in-memory script.
Production code is never modified.

Run: python tests/control_plane/dashboard_browser_smoke.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import sys

from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from control_plane.app import create_app
from control_plane.db import Database

root = Path(__file__).resolve().parents[2]
assets = root / 'control_plane' / 'dashboard'
out = Path(os.environ.get('CHEMFORGE_DASHBOARD_CAPTURE', '/mnt/data/CHEMFORGE_v1.6_Dashboard_Preview.png'))

with TemporaryDirectory() as temp:
    dbfile = str(Path(temp) / 'control.sqlite')
    admin = Database(dbfile).bootstrap_tenant('pilot-academy', 'Principal')
    with TestClient(create_app(dbfile)) as client:
        def api_bridge(path, options):
            method = options.get('method','GET')
            headers = options.get('headers',{})
            body = options.get('body')
            result = client.request(method, path, headers=headers, content=body)
            return {'status':result.status_code, 'body':result.text}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda err: errors.append(str(err)))
            page.expose_function('pyApiBridge',api_bridge)
            page.set_content((assets/'index.html').read_text(),wait_until='domcontentloaded')
            page.add_style_tag(content=(assets/'styles.css').read_text())
            page.evaluate('''() => {window.fetch = async (path,options) => {
              const r = await window.pyApiBridge(path,options);
              return new Response(r.body,{status:r.status,headers:{'Content-Type':'application/json'}});
            }}''')
            js=(assets/'app.js').read_text()
            old="return window.location.protocol === 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);"
            assert old in js
            js = js.replace(old, 'return true; /* Harness only: secure-origin check is covered by source checks. */')
            page.add_script_tag(content=js)
            assert page.get_by_role('heading', name='Welcome to CHEMFORGE Control.').is_visible()
            page.locator('#credential').fill(admin)
            page.get_by_role('button',name='Access workspace').click()
            page.locator('#tenant-sidebar').get_by_text('pilot-academy').wait_for()
            page.locator('button[data-view=students]').click()
            page.get_by_placeholder('Learner 001').fill('<img src=x onerror=alert(1)>')
            page.get_by_placeholder('Upper 6 - A').first.fill('U6-A')
            page.get_by_role('button',name='Add student').click()
            page.get_by_text('<img src=x onerror=alert(1)>').wait_for()
            assert page.locator('img[src="x"]').count()==0, 'Student label injected HTML'
            page.locator('button[data-view=assignments]').click()
            page.get_by_placeholder('Energetics revision').fill('Equilibrium check-in')
            page.get_by_placeholder('Upper 6 - A').last.fill('U6-A')
            page.get_by_placeholder('CH-CHEM-001, CH-CHEM-002').fill('CH-CHEM-001')
            page.get_by_role('button',name='Create assignment').click()
            page.get_by_text('Equilibrium check-in').wait_for()
            page.locator('button[data-view=teachers]').click()
            page.get_by_placeholder('Chemistry Teacher').fill('Teacher A')
            page.get_by_role('button',name='Issue credential').click()
            page.locator('#new-token-value').get_by_text('cfcp_', exact=False).wait_for()
            teacher = page.locator('#new-token-value').text_content()
            assert teacher.startswith('cfcp_')
            page.get_by_role('button',name='Dismiss credential').click()
            assert page.locator('#new-token-value').text_content()==''
            page.locator('button[data-view=imports]').click()
            page.locator('#backup-student option').nth(1).wait_for(state='attached')
            page.locator('#backup-student').select_option(index=1)
            backup={'app':'CHEMFORGE_ANDROID','schema_version':1,'tenant_id':'pilot-academy',
                'content_version':'pilot-0.1','content_fingerprint':'pilot-0.1',
                'attempts':[{'id':'v16-event-001','question_id':'CF-Q-001','mark':1,'max_marks':1,
                  'assessment_source':'deterministic_key','recorded_at':'2026-10-12T07:00:00Z',
                  'tenant_id':'pilot-academy','content_version':'pilot-0.1',
                  'content_fingerprint':'pilot-0.1','mode':'practice','hints_used':0}]}
            page.locator('#backup-file').set_input_files({'name':'demo-backup.json', 'mimeType':'application/json','buffer':json.dumps(backup).encode()})
            page.get_by_role('button',name='Import JSON backup').click()
            page.get_by_text('Import processed: 1 new and 0 already received. Verified marks: 0.').wait_for()
            page.locator('button[data-view=overview]').click()
            page.locator('#overview-cards').get_by_text('Unverified attempts').wait_for()
            assert page.locator('#cohort-overview').get_by_text('1',exact=True).count()>0
            out.parent.mkdir(exist_ok=True,parents=True)
            page.screenshot(path=str(out),full_page=True)
            # A 390px viewport must remain usable without page-level horizontal overflow.
            page.set_viewport_size({'width':390,'height':840})
            page.wait_for_timeout(250)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2'), 'Mobile page overflows'
            mobile = out.with_name('CHEMFORGE_v1.6_Dashboard_Mobile_Preview.png')
            page.screenshot(path=str(mobile),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('#signout').click()
            assert page.locator('#credential').input_value()==''
            page.locator('#credential').fill(teacher)
            page.get_by_role('button',name='Access workspace').click()
            page.locator('#role-badge').get_by_text('TEACHER').wait_for()
            assert page.locator('button[data-view=teachers]').is_hidden()
            assert page.locator('button[data-view=audit]').is_hidden()
            assert not errors, errors
            browser.close()
        print('Dashboard Chromium DOM/API smoke: PASS — admin, roster, XSS, assignment, teacher, backup, roles')
        print('Note: browser localhost blocked; TestClient bridges real API; secure-origin check bypassed in test only')
        print('Preview:',out)
