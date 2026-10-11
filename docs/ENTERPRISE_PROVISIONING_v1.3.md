# CHEMFORGE Enterprise — Offline Provisioning v1.3-alpha

## Security properties in this source release

A **standalone debug** build is useful for offline editorial learning. It does not enroll the student in an institution. It permits backup import/export and local AI import when an approved model hash is compiled in, but institutional content import is unavailable unless explicitly authorised and signed.

An **enforced enterprise build** must be compiled with `CHEMFORGE_REQUIRE_PROVISIONING=true` and `CHEMFORGE_PACK_PUBLIC_KEY_BASE64` containing the institution's DER-encoded P-256 *public* signing key in base64. A missing/invalid-length public key prevents the Gradle build configuration from proceeding. The source never bundles a private signing key.

On an enforced build with no app restrictions, or when any managed restrictions are supplied without a valid `tenant_id`, the app runs in restricted mode: model inference, backups import/export, and curriculum imports are disabled. Offline editorial study remains available; institution-verified claims and enrollment are not made.

When Android Enterprise supplies a valid `tenant_id`, permissions are granted only when the exact boolean `true` is present in the managed restrictions bundle:

| Restriction | Effect | Managed default |
| --- | --- | --- |
| `tenant_id` | Must be 1–100 characters `[A-Za-z0-9._-]` | Required |
| `enable_local_ai` | Local `.litertlm` import and inference | Deny |
| `allow_data_export` | JSON learning-history export | Deny |
| `allow_data_import` | Unverified learning-history import | Deny |
| `allow_content_import` | Institution-signed `.cfpack` import | Deny |

An imported study history is not automatically authenticated or accepted as evidence of mastered competencies. Hardware attacks, compromised devices and fraudulent client-side score generation remain outside the security guarantees of the offline app. This is not a high-stakes examination platform.

### Example enterprise build

```bash
export CHEMFORGE_REQUIRE_PROVISIONING=true
export CHEMFORGE_PACK_PUBLIC_KEY_BASE64='BASE64_OF_DER_PUBLIC_KEY_FROM_INSTITUTION_PUBLISHER'
# If local AI is permitted, configure an approved model digest as well:
export CHEMFORGE_APPROVED_MODEL_SHA256='64_LOWERCASE_HEX_SHA256'
bash scripts/build_debug_apk.sh
```

Replace the illustrative values above with actual authorised deployment values. The debug APK remains a developer build, not a production-signed release.

### Before rollout

Institution policy must be tested against the selected enterprise mobility management (EMM) system. Validate rollback, key rotation, device loss/recovery, compromised-device assumptions, export policy and consent for learner data. Production app signing, independent security review and authorised curriculum licensing are still required.
