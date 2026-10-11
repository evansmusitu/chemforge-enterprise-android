import ai.chemforge.mobile.EnterpriseEntitlements;
import java.util.HashMap;
import java.util.Map;

public class EntitlementsHarness {
    private static void must(boolean ok, String reason) { if (!ok) throw new AssertionError(reason); }
    private static Map<String,Object> config(Object... keysAndValues) {
        Map<String,Object> map = new HashMap<>();
        for (int i=0;i<keysAndValues.length;i+=2)map.put((String)keysAndValues[i],keysAndValues[i+1]);
        return map;
    }
    public static void main(String[] args) {
        EnterpriseEntitlements standalone=EnterpriseEntitlements.evaluate(config(), false);
        must(!standalone.managed && standalone.allowImport && standalone.allowExport && standalone.localAi,
            "standalone installation retains explicit local offline study controls");
        EnterpriseEntitlements required=EnterpriseEntitlements.evaluate(config(), true);
        must(required.managed && !required.allowImport && !required.allowExport && !required.localAi && !required.allowContentImport,
            "enterprise build without managed settings must fail closed");
        EnterpriseEntitlements unassigned=EnterpriseEntitlements.evaluate(config("enable_local_ai",true,"allow_data_import",true),false);
        must(!unassigned.allowImport && !unassigned.localAi && unassigned.managed,
            "managed settings without tenant must fail closed");
        EnterpriseEntitlements configured=EnterpriseEntitlements.evaluate(config("tenant_id","School-X", "enable_local_ai",true,
            "allow_content_import",true,"allow_data_export",true,"allow_data_import",false),true);
        must(configured.managed && configured.localAi && configured.allowExport && !configured.allowImport && configured.allowContentImport,
            "managed actions must be granted independently");
        EnterpriseEntitlements badType=EnterpriseEntitlements.evaluate(config("tenant_id","School-X", "allow_data_import","true"),true);
        must(!badType.allowImport, "strings must not be coerced to permissions");
        EnterpriseEntitlements badTenant=EnterpriseEntitlements.evaluate(config("tenant_id","../School", "allow_data_export",true),true);
        must(!badTenant.allowExport, "invalid tenant must fail closed");
        System.out.println("Enterprise entitlements: PASS (standalone, required provisioning, malformed tenant, strict permissions)");
    }
}
