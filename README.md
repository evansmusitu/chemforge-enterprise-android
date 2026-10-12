# CHEMFORGE Enterprise — Android and Control Plane (v1.6 alpha)

**CHEMFORGE Student** is an offline-only Android application for experimental A-Level Chemistry revision. **CHEMFORGE Control** is a separate connected institutional administration service, now with a same-origin browser dashboard. These are separate processes: **no automatic Android-to-server synchronisation is implemented**.

## Current entry points

- Android: `app/` — APK build and emulator CI are configured separately.
- Institution server: `control_plane/` — SQLite-backed pilot API, `GET /control/` dashboard.
- Administration: `python -m control_plane.cli bootstrap --db ... --tenant school-demo --admin-label 'Principal'` creates the one-time administrator credential (do not commit credentials).
- Local UI: `CHEMFORGE_CONTROL_DB=... uvicorn control_plane.app:create_app --factory --host 127.0.0.1 --port 8020` then open `http://127.0.0.1:8020/control/`. Use HTTPS for any non-loopback pilot.
- Server verification: `python -m pytest -q tests/control_plane`.

**Security and scientific limitations:** Control remains a private pilot, without OIDC/SSO, MFA, classroom-granular teacher permissions, secure production deployment, or independent content validation. Android exports are editable by students; imported marks and cohort analytics are **unverified** and never certified assessment records. Content registry entries are metadata, not signatures. Learn more in `control_plane/README.md` and `docs/RELEASE_v1.6.md`.

## Qualifications achieved vs. pending

Android source and emulator build gates were completed in v1.4; they are not repeated by this dashboard change. On-device AI model behavior and Chemistry correctness require separately documented, reproducible evidence. The pilot question bank is not a complete reviewed ZIMSEC syllabus. The server is not ready for public institutional student-data collection.
