"""Optional real Chromium smoke using intercepted HTTP and live FastAPI TestClient.

This is a browser DOM and API integration test; no external network or live server.
Install Playwright/Chromium separately. It does not test a deployed TLS reverse proxy.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from control_plane.app import create_app
from control_plane.db import Database


def run():
    with TemporaryDirectory() as temp:
        db_file = str(Path(temp) / 'smoke.sqlite')
        db = Database(db_file)
        admin = db.bootstrap_tenant('school-chemforge', 'Smoke Admin')
        with TestClient(create_app(db_file)) as backend, sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,
                                               args=['--no-sandbox','--no-proxy-server'])
            context=browser.new_context(viewport={'width':1366,'height':900},device_scale_factor=1)
            page=context.new_page()
            console_dir=Path(__file__).parents[2] / 'control_plane' / 'console'
            html=(console_dir / 'index.html').read_text()
            html=html.replace('<link rel="stylesheet" href="/console/style.css">','')
            html=html.replace('<script src="/console/app.js" defer></script>','')
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            # Chromium in this runner prohibits all navigation (even file:// and localhost).
            # Inject the same UI script via set_content and bridge API requests to real TestClient.
            # Only the location-origin check is bypassed in this isolated, originless test harness;
            # the unchanged production check is verified by source-contract tests.
            def bridge(source, path, options):
                options = options or {}
                headers={'Authorization':options.get('headers',{}).get('Authorization','')}
                if 'body' in options:headers['Content-Type']='application/json'
                result=backend.request(options.get('method','GET'),path,headers=headers,
                                       content=options.get('body'))
                return {'status':result.status_code,'payload':result.json() if result.status_code!=204 else None}
            page.expose_binding('apiRequest',bridge)
            page.set_content(html)
            page.add_style_tag(content=(console_dir / 'style.css').read_text())
            page.evaluate("""(() => { window.fetch = async (path, options) => {
                 const result = await window.apiRequest(path,options);
                 return {status:result.status,ok:result.status>=200&&result.status<300,
                         json:async()=>result.payload};
               }; return true; })();""")
            script=(console_dir / 'app.js').read_text()
            assert "window.location.protocol!=='https:' && host!=='127.0.0.1' && host!=='localhost'" in script
            script=script.replace("window.location.protocol!=='https:' && host!=='127.0.0.1' && host!=='localhost'","false /* no origin in browser harness */")
            page.add_script_tag(content=script)
            assert page.get_by_text('Connect your institution').count()==1
            page.locator('#credential').fill(admin)
            page.locator('#login-form button').click()
            page.get_by_text('Registered learners').wait_for(timeout=8000)
            assert not page.locator('#login').is_visible(), 'signed-in console must hide credential entry'
            assert page.get_by_text('STATUS: ALL IMPORTED SCORES UNVERIFIED').is_visible()
            page.get_by_role('button',name='Students').click()
            page.get_by_label('Student display name').fill('<img src=x onerror=alert(1)>')
            page.get_by_label('Cohort / class').fill('L6-A')
            page.get_by_role('button',name='Add student +').click()
            page.get_by_role('cell',name='<img src=x onerror=alert(1)>').wait_for()
            assert page.locator('img[src="x"]').count()==0,'unsafe HTML injection'
            page.get_by_role('button',name='Assignments').click()
            page.get_by_label('Assignment title').fill('Chemical equilibrium')
            page.get_by_label('Cohort',exact=True).fill('L6-A')
            page.get_by_label('Objective IDs (comma separated)').fill('CHEM-001')
            page.get_by_role('button',name='Create assignment +').click()
            page.get_by_text('Chemical equilibrium').wait_for()
            page.get_by_role('button',name='Teachers').click()
            page.get_by_label('Teacher label').fill('Chemistry Instructor')
            page.get_by_role('button',name='Issue teacher credential +').click()
            page.get_by_text('Credential shown only once').wait_for()
            teacher_token=page.locator('output.secret').inner_text()
            assert teacher_token.startswith('cfcp_')
            page.get_by_role('button',name='Dismiss credential').click()
            assert page.locator('output.secret').count()==0
            page.get_by_role('button',name='Sign out').click()
            assert page.get_by_text('Connect your institution').is_visible()
            page.locator('#credential').fill(teacher_token)
            page.locator('#login-form button').click()
            page.get_by_text('Registered learners').wait_for()
            assert page.get_by_role('button',name='Teachers').count()==0
            assert page.get_by_role('button',name='Audit').count()==0
            page.get_by_role('button',name='Students').click()
            page.get_by_role('cell',name='<img src=x onerror=alert(1)>').wait_for()
            page.get_by_role('button',name='Overview').click()
            page.get_by_text('Registered learners').wait_for()
            screenshot='/mnt/data/CHEMFORGE_v1.6_Control_Dashboard.png'
            page.screenshot(path=screenshot,full_page=True)
            assert not errors, errors
            print('BROWSER SMOKE PASS — login, student/assignment/teacher CRUD, XSS escaping, role separation, logout/relogin')
            browser.close()

if __name__=='__main__':run()
