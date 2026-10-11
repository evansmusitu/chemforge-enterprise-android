package ai.chemforge.mobile;

import java.util.Map;

/**
 * Pure policy evaluator: an EMM-configured install never inherits permissive
 * standalone defaults. The host-side tests exercise the same code as Android.
 */
public final class EnterpriseEntitlements {
    public final String tenantId;
    public final boolean managed;
    public final boolean localAi;
    public final boolean allowExport;
    public final boolean allowImport;
    public final boolean allowContentImport;

    private EnterpriseEntitlements(String tenant, boolean managed, boolean ai,
            boolean export, boolean recordImport, boolean contentImport) {
        tenantId = tenant;
        this.managed = managed;
        localAi = ai;
        allowExport = export;
        allowImport = recordImport;
        allowContentImport = contentImport;
    }

    /** Empty restrictions may use standalone defaults only in explicitly non-enterprise builds. */
    public static EnterpriseEntitlements evaluate(Map<String, ?> restrictions,
            boolean requireManagedProvisioning) {
        boolean managed = requireManagedProvisioning || !restrictions.isEmpty();
        if (!managed) return new EnterpriseEntitlements("", false, true, true, true, false);
        Object proposed = restrictions.get("tenant_id");
        String tenant = proposed instanceof String ? (String) proposed : "";
        if (tenant.isEmpty() || tenant.length() > 100 || !tenant.matches("[A-Za-z0-9._-]+")) {
            return new EnterpriseEntitlements("invalid-managed-tenant", true,
                false, false, false, false);
        }
        // Permissions are never coerced from strings, numbers or absent keys.
        return new EnterpriseEntitlements(tenant, true,
            Boolean.TRUE.equals(restrictions.get("enable_local_ai")),
            Boolean.TRUE.equals(restrictions.get("allow_data_export")),
            Boolean.TRUE.equals(restrictions.get("allow_data_import")),
            Boolean.TRUE.equals(restrictions.get("allow_content_import")));
    }
}
