"""Real Chromium against HTTPS FastAPI, using synthetic staging data only.

Unlike the older DOM TestClient bridge, this browser performs normal HTTPS
requests. The ignored test certificate is restricted to this isolated browser
context, and the production dashboard code is unchanged.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
from playwright.sync_api import sync_playwright


def verify_teacher_browser(root: Path, base: str, screenshot: Path | None = None) -> dict:
    bundle = json.loads((Path(root) / 'fixture.json').read_text())
    with sync_playwright() as p:
        browser_opts = {'headless': True, 'args': ['--no-sandbox']}
        if Path('/usr/bin/chromium').exists():
            browser_opts['executable_path'] = '/usr/bin/chromium'
        browser = p.chromium.launch(**browser_opts)
        try:
            context = browser.new_context(ignore_https_errors=True, viewport={'width': 1380, 'height': 920})
            page = context.new_page()
            page_errors = []
            page.on('pageerror', lambda e: page_errors.append(str(e)))
            response = page.goto(base + '/control/', wait_until='domcontentloaded', timeout=15000)
            assert response is not None and response.status == 200
            assert page.get_by_role('heading', name='Welcome to CHEMFORGE Control.').is_visible()
            page.locator('#credential').fill(bundle['teacher'])
            page.get_by_role('button', name='Access workspace').click()
            page.locator('#role-badge').get_by_text('TEACHER').wait_for(timeout=12000)
            page.locator('#cohort-overview').get_by_text('1', exact=True).wait_for(timeout=12000)
            overview = page.locator('#cohort-overview').text_content()
            assert 'U6-A' in overview and 'U6-B' not in overview, overview
            assert 'unverified attempts' in overview.lower(), overview
            assert 'authorised devices or teachers' in page.locator('#view-overview').text_content().lower()
            assert page.locator('button[data-view=teachers]').is_hidden(), 'Teacher saw admin controls'
            assert page.locator('button[data-view=devices]').is_hidden(), 'Teacher saw device secrets panel'
            page.locator('button[data-view=students]').click()
            page.locator('#students-body').get_by_text('Synthetic Student A').wait_for(timeout=12000)
            assert 'Synthetic Student B' not in page.locator('#students-body').text_content()
            if screenshot is not None:
                screenshot = Path(screenshot)
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.locator('button[data-view=overview]').click()
                page.locator('#cohort-overview').get_by_text('1', exact=True).wait_for(timeout=12000)
                page.screenshot(path=str(screenshot), full_page=True)
            assert not page_errors, page_errors
            return {'teacher_role': 'TEACHER', 'cohort': 'U6-A', 'unverified_attempts': 1,
                    'unassigned_cohort_hidden': True, 'administration_hidden': True,
                    'actual_https_browser': True}
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True)
    parser.add_argument('--url', default='https://127.0.0.1')
    parser.add_argument('--screenshot')
    args = parser.parse_args()
    result = verify_teacher_browser(Path(args.dir), args.url,
                                    Path(args.screenshot) if args.screenshot else None)
    print('Real HTTPS teacher Chromium dashboard: PASS', result)

if __name__ == '__main__':
    main()
