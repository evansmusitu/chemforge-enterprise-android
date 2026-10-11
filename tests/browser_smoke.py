"""Offline CHEMFORGE UI smoke test using a local Chromium engine.

Uses set_content + injected script text because browser navigation is blocked in
some hosted sandboxes; does NOT simulate Android WebView or the native SAF bridge.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / 'app/src/main/assets'


def main():
    html = (ASSETS/'index.html').read_text()
    html = html.replace('<link rel="stylesheet" href="styles.css" />',
                        '<style>'+(ASSETS/'styles.css').read_text()+'</style>')
    for name in ('data.js', 'enterprise_pack.js', 'enterprise_policy.js', 'engine.js', 'coach.js', 'lessons.js', 'mock.js', 'app.js'):
        html = html.replace(f'<script defer src="{name}"></script>', '')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'], **({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').exists() else {}))
        page = browser.new_page(viewport={'width': 393,'height': 852})
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('dialog', lambda dialog: dialog.accept())
        page.set_content(html)
        # Deterministic encrypted-record bridge stand-in for a sandbox where
        # about:blank localStorage access is denied. Android Keystore is tested separately.
        page.add_script_tag(content="""Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem(){return null},setItem(){},removeItem(){}}});
          window.ChemforgeNative={loadRecords(){return JSON.stringify({ok:true,found:false})},saveRecords(t,f,payload){window.storedStudy=payload;return true}};""")
        for name in ('data.js','enterprise_pack.js','enterprise_policy.js','engine.js','coach.js','lessons.js','mock.js','app.js'):
            page.add_script_tag(content=(ASSETS/name).read_text())
        assert 'Score smarter' in page.locator('#screen-home h1').inner_text()
        assert 'Bundled unreviewed pilot' in page.locator('#institution-status').inner_text()
        assert page.locator('#stat-attempts').inner_text() == '0'
        assert 'import' in page.locator('#model-status').inner_text().lower() or 'preview' in page.locator('#model-status').inner_text().lower()
        page.click('#model-import')
        assert 'Android' in page.locator('#model-status').inner_text()
        page.click('[data-screen="learn"]')
        assert page.locator('.micro-lesson').count() >= 10
        assert 'unreviewed' in page.locator('#screen-learn').inner_text().lower()
        page.click('[data-screen="home"]')
        page.click('#start-study')
        assert page.locator('#question-area h2').count() == 1
        assert page.locator('[data-choice]').count() == 4
        assert page.locator('#coach-panel').evaluate('(e)=>e.classList.contains("hidden")')
        page.locator('[data-choice]').first.click()
        page.click('#submit-answer')
        assert not page.locator('#feedback').evaluate('(x)=>x.classList.contains("hidden")')
        assert not page.locator('#coach-panel').evaluate('(e)=>e.classList.contains("hidden")')
        page.locator('#coach-request').fill('Explain the chemistry in simpler language')
        page.click('#coach-ask')
        assert 'requires the Android version' in page.locator('#coach-output').inner_text()
        page.click('[data-screen="journal"]')
        assert 'CF-001' in page.locator('#history-list').inner_text()
        page.click('[data-screen="map"]')
        assert page.locator('.objective').count() == 28
        page.click('[data-screen="practice"]')
        page.locator('[data-mode="exam"]').click()
        assert page.locator('#show-hint').count() == 0
        page.select_option('#filter-paper','P3')
        assert page.locator('textarea#answer-input').count() == 1
        page.locator('textarea#answer-input').fill('The temperature alters the equilibrium position.')
        page.click('#submit-answer')
        assert 'Self-review required' in page.locator('#feedback').inner_text()
        page.locator('[data-mark="1"]').click()
        assert 'Recorded 1/' in page.locator('#feedback').inner_text()
        assert page.locator('.objective').count() == 28
        page.click('[data-screen="journal"]')
        assert 'Self-reviewed' in page.locator('#history-list').inner_text()
        page.evaluate('''() => { window.ChemforgeNative = {exportJson(s){window.savedJson=s;}, importJson(){}} }''')
        page.click('#export')
        exported = page.evaluate('window.savedJson')
        assert len(__import__('json').loads(exported)['attempts']) == 2
        page.evaluate('(s)=>window.receiveChemforgeImport(s)', exported)
        assert '2 records' in page.locator('#journal-count').inner_text()
        page.click('[data-screen="mock"]')
        page.click('#mock-start')
        assert page.locator('#mock-question h2').count()==1
        assert 'Editorial answer' not in page.locator('#mock-question').inner_text()
        page.locator('input[name="mock-answer"]').first.check()
        page.click('#mock-next')
        assert 'Editorial answer' not in page.locator('#mock-running').inner_text()
        page.click('#mock-finish')
        assert 'Automatically scored' in page.locator('#mock-results').inner_text()
        assert 'Editorial answer' in page.locator('#mock-results').inner_text()
        assert page.locator('#mock-running').evaluate('(el)=>el.classList.contains("hidden")')
        assert not errors, errors
        # Simulate an enterprise-managed screen (not Android MDM integration test).
        restricted=browser.new_page(viewport={'width':393,'height':852})
        restricted.on('pageerror', lambda err: errors.append(str(err)))
        restricted.set_content(html)
        for name in ('data.js','enterprise_pack.js','engine.js','coach.js','lessons.js','mock.js'):
            restricted.add_script_tag(content=(ASSETS/name).read_text())
        restricted.add_script_tag(content='window.CF_ENTERPRISE_POLICY={tenant_id:"school-A",enable_local_ai:false,allow_data_export:false,allow_data_import:false,allow_content_import:false};')
        restricted.add_script_tag(content=(ASSETS/'app.js').read_text())
        assert restricted.locator('#model-card').evaluate('(el)=>el.classList.contains("hidden")')
        assert restricted.locator('#export').is_disabled()
        assert restricted.locator('#import').is_disabled()
        restricted.evaluate('window.receiveChemforgeImport("{}")')
        assert restricted.locator('#stat-attempts').inner_text() == '0'
        assert restricted.locator('#pack-import').is_disabled()
        assert 'Managed institution: school-A' in restricted.locator('#institution-status').inner_text()
        restricted.click('#start-study')
        restricted.locator('[data-choice]').first.click()
        restricted.click('#submit-answer')
        assert restricted.locator('#coach-panel').evaluate('(el)=>el.classList.contains("hidden")')
        assert not errors, errors
        restricted.close()
        browser.close()
    print('Chromium UI smoke: PASS — diagnostic, offline AI boundary, constructed review, skills, export, import; managed data import restrictions, no JS errors.')

if __name__ == '__main__': main()
