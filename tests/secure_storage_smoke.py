"""Simulates Android NativeBridge behavior in Chromium to verify JS privacy transitions.
This is NOT an AndroidKeyStore/Android device test. RecordCipherHarness covers pure crypto.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json

ASSETS=Path(__file__).resolve().parents[1]/'app/src/main/assets'
HTML=(ASSETS/'index.html').read_text()
for name in ('data.js','enterprise_pack.js','enterprise_policy.js','engine.js','coach.js','app.js'):
    HTML=HTML.replace(f'<script defer src="{name}"></script>','')
seed=json.loads((ASSETS/'data.json').read_text())


def boot(browser, setup_js):
    page=browser.new_page(viewport={'width':400,'height':820})
    errs=[]
    page.on('pageerror',lambda e:errs.append(str(e)))
    page.on('dialog',lambda d:d.accept())
    page.set_content(HTML)
    page.evaluate(setup_js)
    for name in ('data.js','enterprise_pack.js','enterprise_policy.js','engine.js','coach.js','app.js'):
        page.add_script_tag(content=(ASSETS/name).read_text())
    assert not errs,errs
    return page,errs


def main():
    sample={
        'app':'CHEMFORGE_ANDROID','schema_version':1,'content_version':'pilot-0.1',
        'content_fingerprint':'pilot-0.1','tenant_id':'','attempts':[
            {'id':'old-1','question_id':seed['questions'][0]['id'],'mark':1,'max_marks':1,
             'recorded_at':'2026-10-11T10:00:00Z','hints_used':0,
             'assessment_source':'deterministic_key','mode':'practice'}
        ]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'], **({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').exists() else {}))
        setup='''() => {
          const previous = %s;
          window.plain=new Map([['CHEMFORGE_ANDROID_V1',JSON.stringify(previous)]]);
          Object.defineProperty(window,'localStorage',{configurable:true,value:{
            getItem:k=>window.plain.get(k)||null,
            setItem:(k,v)=>window.plain.set(k,v),
            removeItem:k=>window.plain.delete(k)
          }});
          window.sealed=null;window.saves=0;
          window.ChemforgeNative={
            loadRecords(){return JSON.stringify({ok:true,found:!!window.sealed,payload:window.sealed})},
            saveRecords(t,f,v){window.saves++;window.sealed=v;return t===''&&f==='pilot-0.1'},
            modelStatus(){},unloadModel(){},importContentPack(){},importJson(){},exportJson(){}
          };
        }'''%json.dumps(sample)
        page,errors=boot(browser,setup)
        assert page.locator('#stat-attempts').inner_text()=='1', 'migrated history not read'
        assert page.evaluate('window.saves')==1, 'migration did not encrypt via native bridge'
        assert page.evaluate("window.plain.size")==0,'plaintext history was not deleted after encrypting'
        page.click('#start-study')
        page.locator('[data-choice]').first.click()
        page.click('#submit-answer')
        assert page.evaluate('window.saves')==2,'native save not used for a new attempt'
        assert page.evaluate("window.plain.size")==0,'plaintext localStorage must remain empty'
        assert len(json.loads(page.evaluate('window.sealed'))['attempts'])==2
        page.click('[data-screen="journal"]')
        assert '2 records' in page.locator('#journal-count').inner_text()
        assert not errors,errors
        page.close()

        bad='''() => {
          window.saves=0;
          Object.defineProperty(window,'localStorage',{configurable:true,value:{
            getItem(){return null},setItem(){throw Error('PLAINTEXT WRITE')},removeItem(){}
          }});
          window.ChemforgeNative={
            loadRecords(){return JSON.stringify({ok:false,error:'AEAD authentication failed'})},
            saveRecords(){window.saves++;return true},modelStatus(){},unloadModel(){}
          };
        }'''
        page,errors=boot(browser,bad)
        page.click('#start-study')
        page.locator('[data-choice]').first.click()
        page.click('#submit-answer')
        page.click('[data-screen="journal"]')
        assert 'Secure local storage is unavailable' in page.locator('#storage-message').inner_text()
        assert page.evaluate('window.saves')==0,'auth failure must never overwrite stored ciphertext'
        assert not errors,errors
        page.close()

        external='''() => {
          window.sealed=null;
          Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem(){return null},setItem(){throw Error('plaintext write')},removeItem(){}}});
          window.ChemforgeNative={
            loadRecords(){return JSON.stringify({ok:true,found:false})},
            saveRecords(t,f,v){window.sealed=v;return true},modelStatus(){}
          }
        }'''
        page,errors=boot(browser,external)
        page.evaluate('(v)=>window.receiveChemforgeImport(v)',json.dumps(sample))
        imported=json.loads(page.evaluate('window.sealed'))['attempts']
        assert imported[0]['unverified_import'] is True
        assert page.locator('#stat-assessed').inner_text().startswith('0'), 'imported score unexpectedly contributed mastery'
        assert not errors,errors
        page.close()
        browser.close()
    print('Secure storage browser simulations: PASS — migration and plaintext cleanup, native-only saves, AEAD-failure lock, unverified imports')

if __name__=='__main__':main()
