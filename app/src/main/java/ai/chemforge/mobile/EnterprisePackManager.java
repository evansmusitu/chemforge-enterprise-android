package ai.chemforge.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Bounded, authenticated offline institutional content delivery.
 * Installing a signed pack does not constitute independent expert review.
 * No embedded signing private key; the public trust anchor is injected at build time.
 */
public final class EnterprisePackManager {
    public interface Listener { void onComplete(boolean success, String message); }
    private static final int MAX_ZIP_BYTES = 6_000_000;
    private static final int MAX_CONTENT_BYTES = 5_000_000;
    private final Context context;
    private final File active;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final SharedPreferences prefs;

    EnterprisePackManager(Context context) {
        this.context = context.getApplicationContext();
        this.active = new File(context.getFilesDir(), "institution-content.cfpack");
        this.prefs = context.getSharedPreferences("cf-pack-versions", Context.MODE_PRIVATE);
    }
    static final class Pack {
        final JSONObject manifest;
        final JSONObject content;
        Pack(JSONObject manifest, JSONObject content) { this.manifest = manifest; this.content = content; }
    }
    private static byte[] limitedRead(InputStream input, int max) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192]; int n;
        while ((n = input.read(buf)) != -1) {
            if (out.size() + n > max) throw new SecurityException("package exceeded byte limit");
            out.write(buf, 0, n);
        }
        return out.toByteArray();
    }
    private static PublicKey pinnedKey() throws Exception {
        String encoded = BuildConfig.CONTENT_PUBLIC_KEY_B64;
        if (encoded.isEmpty()) throw new SecurityException("no organisation signing key configured in this build");
        byte[] keyBytes = Base64.decode(encoded, Base64.DEFAULT);
        PublicKey publicKey = KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(keyBytes));
        if (!(publicKey instanceof java.security.interfaces.ECPublicKey)) throw new SecurityException("unexpected signing key type");
        java.security.spec.ECParameterSpec params = ((java.security.interfaces.ECPublicKey)publicKey).getParams();
        if (params.getCurve().getField().getFieldSize() != 256) throw new SecurityException("only P-256 public keys supported");
        return publicKey;
    }
    private static boolean safeTenant(String value) {
        return value != null && value.matches("[A-Za-z0-9._-]{1,100}");
    }
    private static void validateContent(JSONObject content) throws Exception {
        if (!"CHEMFORGE".equals(content.optString("product"))) throw new SecurityException("invalid product");
        String version = content.optString("content_version", "");
        if (version.isEmpty() || version.length() > 80 || content.optString("scope", "").isEmpty())
            throw new SecurityException("invalid content metadata");
        JSONArray objectives = content.getJSONArray("objectives");
        JSONArray questions = content.getJSONArray("questions");
        if (objectives.length() == 0 || objectives.length() > 1000 || questions.length() == 0 || questions.length() > 3000)
            throw new SecurityException("invalid corpus size");
        Set<String> ids = new HashSet<>();
        Set<String> domains = new HashSet<>(java.util.Arrays.asList("Physical", "Inorganic", "Organic", "Applied", "Practical"));
        for (int i = 0; i < objectives.length(); i++) {
            JSONObject obj = objectives.getJSONObject(i);
            String id = obj.getString("id");
            if (id.isEmpty() || !ids.add(id) || !domains.contains(obj.getString("domain"))) throw new SecurityException("invalid objective");
            if (obj.getString("title").isEmpty() || obj.getString("competency").isEmpty()) throw new SecurityException("empty objective");
        }
        for (int i = 0; i < objectives.length(); i++) {
            JSONObject obj = objectives.getJSONObject(i);
            JSONArray pre = obj.getJSONArray("prerequisites");
            for (int j = 0; j < pre.length(); j++) {
                String parent = pre.getString(j);
                if (!ids.contains(parent) || parent.equals(obj.getString("id"))) throw new SecurityException("invalid prerequisites");
            }
        }
        // Reject cyclic dependencies that would make curriculum traversal unsafe.
        java.util.Map<String,java.util.List<String>> prerequisiteGraph = new HashMap<>();
        for (int i = 0; i < objectives.length(); i++) {
            JSONObject obj = objectives.getJSONObject(i);
            JSONArray parents = obj.getJSONArray("prerequisites");
            java.util.List<String> links = new java.util.ArrayList<>();
            for (int j = 0; j < parents.length(); j++) links.add(parents.getString(j));
            prerequisiteGraph.put(obj.getString("id"), links);
        }
        Map<String,Integer> graphColors = new HashMap<>();
        for (String objectiveId : prerequisiteGraph.keySet()) validateAcyclic(objectiveId,prerequisiteGraph,graphColors);
        Set<String> questionsSeen = new HashSet<>();
        for (int i = 0; i < questions.length(); i++) {
            JSONObject q = questions.getJSONObject(i);
            String id = q.getString("id");
            if (id.isEmpty() || !questionsSeen.add(id) || !ids.contains(q.getString("objective_id")))
                throw new SecurityException("invalid question mapping");
            if (!java.util.Arrays.asList("P1", "P2", "P3", "P4").contains(q.getString("paper"))) throw new SecurityException("invalid paper");
            int maxMarks = q.getInt("max_marks"); int diff = q.getInt("difficulty");
            if (maxMarks < 1 || maxMarks > 25 || diff < 1 || diff > 5 || q.getString("stem").isEmpty() || q.getString("explanation").isEmpty() || q.getString("review_status").isEmpty())
                throw new SecurityException("invalid question fields");
            switch(q.getString("type")) {
                case "mcq":
                    JSONArray choices = q.getJSONArray("choices");
                    Set<String> answerIds = new HashSet<>();
                    for (int j=0; j<choices.length(); j++) {
                        String optionId = choices.getJSONObject(j).getString("id");
                        if (!optionId.equals(String.valueOf((char)('A'+j)))) throw new SecurityException("MCQ option ids must run A–F in order");
                        answerIds.add(optionId);
                    }
                    if (choices.length() < 2 || choices.length() > 6 || answerIds.size()!=choices.length() || !answerIds.contains(q.getString("answer")))
                        throw new SecurityException("invalid MCQ choices");
                    break;
                case "numeric":
                    double ans = q.getDouble("answer"), tol = q.getDouble("tolerance");
                    if (!Double.isFinite(ans) || !Double.isFinite(tol) || tol < 0) throw new SecurityException("invalid numeric answer");
                    String unit=q.optString("unit","unitless");
                    if (unit.trim().isEmpty() || unit.length()>60) throw new SecurityException("invalid numeric unit");
                    JSONArray conversions=q.optJSONArray("accepted_units");
                    if (q.has("accepted_units") && conversions==null) throw new SecurityException("invalid unit conversions");
                    if (conversions!=null) {
                        if (conversions.length()>12) throw new SecurityException("too many unit conversions");
                        Set<String> uniqueUnits=new HashSet<>();
                        uniqueUnits.add(unit.replace(" ","").toLowerCase(java.util.Locale.ROOT));
                        for (int j=0;j<conversions.length();j++) {
                            JSONObject conversion=conversions.getJSONObject(j);
                            String other=conversion.getString("unit");
                            String otherKey=other.replace(" ","").toLowerCase(java.util.Locale.ROOT);
                            Object rawFactor=conversion.opt("multiplier");
                            if (!(rawFactor instanceof Number)) throw new SecurityException("invalid unit conversion factor type");
                            double factor=((Number)rawFactor).doubleValue();
                            if (other.trim().isEmpty() || other.length()>60 || !uniqueUnits.add(otherKey) || !Double.isFinite(factor) || factor<=0)
                                throw new SecurityException("invalid unit conversion");
                        }
                    }
                    break;
                case "constructed":
                    JSONArray rubric = q.getJSONArray("rubric"); int sum = 0;
                    for (int j=0; j<rubric.length(); j++) {
                        JSONObject criterion = rubric.getJSONObject(j);
                        int points = criterion.getInt("marks");
                        if (points <= 0 || criterion.getString("text").isEmpty()) throw new SecurityException("invalid rubric point");
                        sum += points;
                    }
                    if (rubric.length()==0 || sum!=maxMarks) throw new SecurityException("invalid rubric");
                    break;
                default:throw new SecurityException("unknown question type");
            }
        }
        // Optional institution-authored micro-lessons are bounded and objective-linked.
        JSONArray lessons=content.optJSONArray("lessons");
        if (content.has("lessons") && lessons==null) throw new SecurityException("invalid lessons");
        if (lessons!=null) {
            if (lessons.length()>1000) throw new SecurityException("too many lessons");
            Set<String> assigned=new HashSet<>();
            Map<String,String> domainById=new HashMap<>();
            for(int i=0;i<objectives.length();i++){
                JSONObject obj=objectives.getJSONObject(i);
                domainById.put(obj.getString("id"),obj.getString("domain"));
            }
            for(int i=0;i<lessons.length();i++){
                JSONObject lesson=lessons.getJSONObject(i);
                String objectiveId=lesson.getString("objective_id");
                if (!ids.contains(objectiveId) || !assigned.add(objectiveId) || !domainById.get(objectiveId).equals(lesson.getString("domain")))
                    throw new SecurityException("invalid lesson mapping");
                for(String key:new String[]{"title","principle","example","common_error","review_status"}){
                    String value=lesson.getString(key);
                    if(value.isEmpty() || value.length()>4000)throw new SecurityException("invalid lesson prose");
                }
            }
        }
    }
    private static void validateAcyclic(String node, Map<String,java.util.List<String>> graph, Map<String,Integer> colors) {
        int state=colors.getOrDefault(node,0);
        if (state==1) throw new SecurityException("cyclic objective dependencies");
        if (state==2) return;
        colors.put(node,1);
        for (String parent:graph.get(node)) validateAcyclic(parent,graph,colors);
        colors.put(node,2);
    }
    private Pack parseVerified(byte[] archive, String requiredTenant) throws Exception {
        Map<String, byte[]> entries = new HashMap<>();
        try (ZipInputStream zin = new ZipInputStream(new java.io.ByteArrayInputStream(archive))) {
            ZipEntry entry;
            while ((entry=zin.getNextEntry()) != null) {
                String name = entry.getName();
                if (entry.isDirectory() || !(name.equals("manifest.json") || name.equals("content.json") || name.equals("signature.der")) || entries.containsKey(name))
                    throw new SecurityException("unknown or duplicate package member");
                int cap = name.equals("content.json") ? MAX_CONTENT_BYTES : 8192;
                entries.put(name, limitedRead(zin,cap));
            }
        }
        if (entries.size()!=3) throw new SecurityException("pack must contain three named members");
        byte[] manifestBytes = entries.get("manifest.json"), contentBytes = entries.get("content.json");
        JSONObject manifest = new JSONObject(new String(manifestBytes,StandardCharsets.UTF_8));
        if (!"CHEMFORGE_SIGNED_PACK_V1".equals(manifest.optString("schema")) ||
            !"SHA256withECDSA-P256".equals(manifest.optString("signature_algorithm")))
            throw new SecurityException("unsupported pack format");
        String tenant = manifest.getString("tenant_id");
        if (!safeTenant(tenant) || (!requiredTenant.isEmpty() && !tenant.equals(requiredTenant)))
            throw new SecurityException("pack tenant does not match managed institution");
        if (manifest.getInt("pack_version") < 1) throw new SecurityException("invalid pack version");
        SignedContentVerifier.check(pinnedKey(),manifestBytes,contentBytes,entries.get("signature.der"),manifest.getString("content_sha256"));
        JSONObject content = new JSONObject(new String(contentBytes, StandardCharsets.UTF_8));
        validateContent(content);
        if (!manifest.getString("content_version").equals(content.getString("content_version")))
            throw new SecurityException("pack and content versions differ");
        return new Pack(manifest,content);
    }
    /** UI selects package with SAF; verification and storage occur off the UI thread. */
    void install(Uri uri, String tenant, Listener listener) {
        worker.execute(() -> {
            File temporary = null;
            try {
                byte[] raw;
                try (InputStream src = context.getContentResolver().openInputStream(uri)) {
                    if (src == null) throw new SecurityException("cannot open selected pack");
                    raw = limitedRead(src, MAX_ZIP_BYTES);
                }
                Pack checked = parseVerified(raw, tenant);
                String org = checked.manifest.getString("tenant_id");
                int version = checked.manifest.getInt("pack_version");
                if (version <= prefs.getInt("last-"+org,0)) throw new SecurityException("rollback or repeated pack version rejected");
                ManagedPolicy current = ManagedPolicy.read(context);
                if (!current.allowContentImport || !current.tenantId.equals(tenant))
                    throw new SecurityException("institution policy changed during package verification");
                temporary = File.createTempFile("verified-content-", ".cfpack", context.getFilesDir());
                Files.write(temporary.toPath(),raw);
                try {Files.move(temporary.toPath(),active.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
                catch (java.nio.file.AtomicMoveNotSupportedException ignored) {Files.move(temporary.toPath(),active.toPath(),StandardCopyOption.REPLACE_EXISTING);}
                temporary = null;
                // Commit monotonic high-water mark synchronously; no silent preference write failure.
                if (!prefs.edit().putInt("last-"+org, version).commit()) throw new SecurityException("cannot record pack revision");
                listener.onComplete(true, "Installed signed offline content: " + checked.content.getString("content_version") + ". Independent scientific review remains the institution's responsibility.");
            } catch (Exception err) {
                listener.onComplete(false,"Institution pack rejected: " + (err.getMessage()==null?"invalid input":err.getMessage()));
            } finally { if (temporary!=null) temporary.delete(); }
        });
    }
    /** Cached package is re-authenticated on each WebView load and filtered against current organisation. */
    String webViewContentScript(String tenant) {
        if (!active.isFile() || active.length()>MAX_ZIP_BYTES) return "window.CF_PACK_INFO=null;";
        try {
            Pack pack = parseVerified(Files.readAllBytes(active.toPath()),tenant);
            String org = pack.manifest.getString("tenant_id");
            if (pack.manifest.getInt("pack_version") != prefs.getInt("last-"+org,0)) throw new SecurityException("installed content has inconsistent version");
            JSONObject info = new JSONObject();
            info.put("tenant_id",org);
            info.put("content_version",pack.content.getString("content_version"));
            info.put("content_sha256",pack.manifest.getString("content_sha256"));
            info.put("pack_version",pack.manifest.getInt("pack_version"));
            return "window.CF_DATA=JSON.parse("+JSONObject.quote(pack.content.toString())+");window.CF_PACK_INFO=JSON.parse("+JSONObject.quote(info.toString())+");";
        } catch(Exception ignored) { return "window.CF_PACK_INFO=null;"; }
    }
    void close() { worker.shutdown(); }
}
