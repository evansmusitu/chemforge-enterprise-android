package ai.chemforge.mobile;

import android.content.Context;
import android.content.RestrictionsManager;
import android.os.Bundle;
import org.json.JSONObject;
import java.util.HashMap;
import java.util.Map;

/** Native policy snapshot from the Android Enterprise configuration. */
final class ManagedPolicy {
    final String tenantId;
    final boolean managed;
    final boolean localAi;
    final boolean allowExport;
    final boolean allowImport;
    final boolean allowContentImport;

    private ManagedPolicy(EnterpriseEntitlements policy) {
        tenantId = policy.tenantId;
        managed = policy.managed;
        localAi = policy.localAi;
        allowExport = policy.allowExport;
        allowImport = policy.allowImport;
        allowContentImport = policy.allowContentImport;
    }

    static ManagedPolicy read(Context context) {
        RestrictionsManager manager = (RestrictionsManager)context.getSystemService(Context.RESTRICTIONS_SERVICE);
        Bundle b = manager == null ? null : manager.getApplicationRestrictions();
        Map<String,Object> values = new HashMap<>();
        if (b != null) for (String key : b.keySet()) values.put(key,b.get(key));
        return new ManagedPolicy(EnterpriseEntitlements.evaluate(values,
            BuildConfig.REQUIRE_ENTERPRISE_PROVISIONING));
    }

    String asJson() {
        JSONObject out = new JSONObject();
        try {
            out.put("tenant_id", tenantId);
            out.put("managed", managed);
            out.put("enable_local_ai", localAi);
            out.put("allow_data_export", allowExport);
            out.put("allow_data_import", allowImport);
            out.put("allow_content_import", allowContentImport);
        } catch (org.json.JSONException ex) { throw new IllegalStateException(ex); }
        return out.toString();
    }
}
