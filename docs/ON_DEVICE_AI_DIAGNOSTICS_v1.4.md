# CHEMFORGE v1.4 — Offline Model Inference Diagnostics

## Purpose

This release adds a **manual, private, offline AI self-test** intended for institution QA teams to evaluate whether an approved model can actually load and respond on a physical Android device. It does **not** validate Chemistry quality, model safety, curriculum alignment or grading. It never awards marks and is not invoked automatically while a student works.

## Requirements

- Android debug APK compiled with `CHEMFORGE_APPROVED_MODEL_SHA256` set to the SHA-256 of a legitimate, appropriately licensed `.litertlm` model that is compatible with LiteRT-LM 0.17.1. Without the pinned digest, model import/inference is denied.
- Institution managed policy must permit local AI.
- Model imported from device local storage through Android's document picker. Files are checked for extension, size, available storage and SHA-256 digest before moving into app-private storage.
- Memory headroom (currently 1.5 GB available at cold model load). This threshold is provisional and must be benchmarked across representative devices; a 4 GB phone is not guaranteed to meet it.

## Procedure

1. Transfer the institution-approved model to the phone. Installation/import is an explicit user action and should be done before airplane mode, if the file is initially downloaded.
2. Install CHEMFORGE; open the Home screen and import the model using **Import on-device model**.
3. Enable airplane mode and verify data/Wi-Fi are disabled. Model inference does not use a network permission.
4. Press **Run offline AI self-test**. It sends a fixed, non-student Chemistry prompt to the same model runtime used by the tutor with a 32-token response cap. The app reports model initialization time, inference time, file size, available RAM before and after, CPU backend, Android API and a 12-hex SHA-256 prefix. No generated text or student answers are exported or persisted by this probe.
5. Capture results for each handset by human observation (device, Android version, RAM tier, model digest, airplane-mode state, load time, inference latency and crash status). Do not use the app to claim independent academic validation.

## Failure conditions

- Missing or unapproved model → explicit failure, normal Chemistry revision unaffected.
- Insufficient memory → explicit failure and model is not started; normal revision unaffected.
- Malformed model / incompatible LiteRT-LM runtime → explicit failure; no successful result shown.
- Managed AI access revoked → self-test blocked before or during execution.
- Invalid telemetry packet → display `Invalid or unverified offline diagnostic result` rather than fabricated numbers.

## Software testing

`node --test tests/model_diagnostics.test.cjs` checks validation and formatting of instrumented measurements. Android instrumentation includes a no-model self-test boundary asserting no student marks change. A fully successful self-test **requires real model bytes** and a hardware device; emulator tests with no model cannot establish that.

## Release gate for enterprise inference

Before calling local AI validated, run the self-test with a permitted pinned model on at least one real 4 GB, 6 GB and 8 GB Android device. Measure p50/p95 latency across repeated cold/warm runs, crash/OOM rates, peak process memory, battery and thermal conditions, and Chemistry response accuracy on independently reviewed examples. Publish the methods and raw de-identified results.
