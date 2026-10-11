# CHEMFORGE v1.5-alpha — Verification Record

Date: 2026-10-11. Scope: `control_plane/` enterprise administration pilot, not a new Android APK.

## Local checks executed in this development session

- `python -m pytest -q tests/control_plane/test_control_plane.py`: **10 passed**.
- `python -m pytest -q tests`: **34 passed, 7 subtests passed**.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **24 passed**.
- `node --test tests/*.test.cjs`: **40 passed, 0 failed**.
- `TestClient(create_app(temp_db)).get('/openapi.json')`: **HTTP 200, 12 API paths**.
- Database bootstrap was tested against duplicate institution creation; revoked teacher token receives HTTP 401; teacher-only access to admin endpoints receives HTTP 403; cross-tenant student access returns HTTP 404; externally supplied tenant override receives HTTP 422.
- Idempotent and conflicting offline backup import and transactional rollback tested; all evidence retains `verification_status = unverified_import`.

## Not tested

- GitHub Actions on remote runners (results must be checked separately).
- Real production IdP / multi-factor sign-in, retention operations at scale, vulnerability scans, penetration testing, institutional data protection assessment or genuine school load.
- A new Android runtime, LiteRT-LM inference, model weights or physical Android hardware were **not** tested for this separate server-side feature.

## Release conclusion

These checks support a tested **server-side pilot API**, not a certified enterprise platform. Imported attempt data are editable and cannot be treated as authoritative grades. Existing Android v1.4 APK remains separate and offline-first.
