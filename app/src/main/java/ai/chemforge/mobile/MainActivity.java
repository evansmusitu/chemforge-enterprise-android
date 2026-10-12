package ai.chemforge.mobile;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.text.InputType;
import android.widget.EditText;
import java.util.concurrent.atomic.AtomicBoolean;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.IntentFilter;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Offline CHEMFORGE study shell. All HTML, JS, and pilot content ship inside the APK.
 * No network permission, remote URLs blocked, local virtual HTTPS asset origin.
 */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String BASE_URL = "https://" + HOST + "/assets/index.html";
    private static final int EXPORT_JSON = 701;
    private static final int IMPORT_JSON = 702;
    private static final int IMPORT_MODEL = 703;
    private static final int IMPORT_PACK = 704;
    private static final int MAX_BACKUP_BYTES = 2_000_000;
    private static final Set<String> ASSETS = Collections.unmodifiableSet(
        new HashSet<>(Arrays.asList("index.html", "styles.css", "data.js", "engine.js", "coach.js", "model_diagnostics.js", "lessons.js", "mock.js", "app.js", "enterprise_pack.js", "enterprise_policy.js")));

    private WebView view;
    private String pendingExport;
    private OfflineModelHost modelHost;
    private AndroidRecordStore recordStore;
    private EnterprisePackManager packManager;
    private volatile ManagedPolicy policy;
    private boolean receiverRegistered;
    private final AtomicBoolean uploading = new AtomicBoolean(false);
    private final BroadcastReceiver restrictionsReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) { refreshPolicy(); }
    };

    private void refreshPolicy() {
        ManagedPolicy next=ManagedPolicy.read(this);
        ManagedPolicy previous=policy;
        policy=next;
        if (previous!=null && (!previous.tenantId.equals(next.tenantId) || previous.localAi!=next.localAi || previous.allowExport!=next.allowExport || previous.allowImport!=next.allowImport || previous.allowContentImport!=next.allowContentImport)) {
            if (!next.localAi && modelHost!=null) modelHost.release();
            // Reload to revalidate current tenant before exposing question data or storage.
            if (view!=null) runOnUiThread(() -> view.loadUrl(BASE_URL));
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        policy = ManagedPolicy.read(this);
        packManager = new EnterprisePackManager(this);
        recordStore = new AndroidRecordStore(this);
        modelHost = new OfflineModelHost(this, (kind, requestId, payload) -> sendModelEvent(kind, requestId, payload));
        view = new WebView(this);
        view.setBackgroundColor(0xff09151b);
        WebView.setWebContentsDebuggingEnabled(false);
        final WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true); // required for local study app
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        if (Build.VERSION.SDK_INT >= 26) settings.setSafeBrowsingEnabled(true);
        view.setWebViewClient(new OfflineAssets());
        view.addJavascriptInterface(new NativeBridge(), "ChemforgeNative");
        setContentView(view);
        view.loadUrl(BASE_URL);
    }

    private static boolean localOrigin(Uri uri) {
        return "https".equals(uri.getScheme()) && HOST.equals(uri.getHost()) && uri.getPort() == -1;
    }

    private static WebResourceResponse denied() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
            Collections.singletonMap("Cache-Control", "no-store"),
            new ByteArrayInputStream("Blocked by CHEMFORGE offline policy".getBytes(StandardCharsets.UTF_8)));
    }

    private final class OfflineAssets extends WebViewClient {
        @Override public WebResourceResponse shouldInterceptRequest(WebView webView, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if (!localOrigin(uri)) return denied();
            final String path = uri.getPath();
            if (path == null || !path.startsWith("/assets/")) return denied();
            final String name = path.substring("/assets/".length());
            if (!ASSETS.contains(name)) return denied();
            try {
                InputStream input;
                if (name.equals("enterprise_pack.js")) {
                    input = new ByteArrayInputStream(packManager.webViewContentScript(policy.tenantId).getBytes(StandardCharsets.UTF_8));
                } else if (name.equals("enterprise_policy.js")) {
                    input = new ByteArrayInputStream(("window.CF_ENTERPRISE_POLICY=JSON.parse(" + JSONObject.quote(browserPolicy()) + ");").getBytes(StandardCharsets.UTF_8));
                } else input = getAssets().open(name);
                String mime = name.endsWith(".css") ? "text/css" : name.endsWith(".js") ? "application/javascript" : "text/html";
                return new WebResourceResponse(mime, "UTF-8", 200, "OK",
                    Collections.singletonMap("Content-Security-Policy",
                        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none'; frame-src 'none'"), input);
            } catch (IOException ex) {
                return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
                    Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }
        }
        @Override public boolean shouldOverrideUrlLoading(WebView webView, WebResourceRequest request) {
            // No external pages, protocols, or deep links may replace trusted app assets.
            return !localOrigin(request.getUrl()) || !BASE_URL.equals(request.getUrl().toString());
        }
        @Override @SuppressWarnings("deprecation") public boolean shouldOverrideUrlLoading(WebView webView, String url) {
            return !BASE_URL.equals(url);
        }
    }

    private void sendModelEvent(String kind, String requestId, String payload) {
        runOnUiThread(() -> {
            if (view != null) view.evaluateJavascript(
                "window.receiveChemforgeModelEvent(" + JSONObject.quote(kind) + "," +
                JSONObject.quote(requestId) + "," + JSONObject.quote(payload) + ")", null);
        });
    }

    private boolean isManualSyncAllowed(ManagedPolicy current) {
        return BuildConfig.SYNC_CONNECTED && current.managed && current.allowExport &&
            !current.tenantId.isEmpty() && InstitutionSyncClient.validHost(BuildConfig.SYNC_HOST);
    }

    private String browserPolicy() {
        try {
            JSONObject response=new JSONObject(policy.asJson());
            response.put("allow_manual_sync",isManualSyncAllowed(policy));
            return response.toString();
        } catch(JSONException ex) { throw new IllegalStateException(ex); }
    }

    private void requestManualSync(String tenant,String fingerprint) {
        ManagedPolicy current=ManagedPolicy.read(this);
        if(!isManualSyncAllowed(current) || !current.tenantId.equals(tenant)) {
            alert("Managed institutional sync is unavailable for this build.");return;
        }
        if(uploading.get()) {alert("A study-history upload is already running.");return;}
        final String payload;
        final int count;
        try {
            payload=recordStore.read(tenant,fingerprint);
            count=InstitutionSyncClient.countVerifiedShape(payload,tenant,fingerprint);
            if(count==0){alert("No local study attempts to upload.");return;}
        } catch(Exception invalid) {alert("Encrypted study history is unavailable or invalid.");return;}
        final EditText secretInput=new EditText(this);
        secretInput.setSingleLine(true);
        secretInput.setHint("cfsync_... device credential");
        secretInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        new AlertDialog.Builder(this)
            .setTitle("Institutional device credential")
            .setMessage("Enter the student-scoped credential issued by your school. It is not stored by CHEMFORGE.")
            .setView(secretInput)
            .setNegativeButton("Cancel",(dialog,which)->secretInput.getText().clear())
            .setPositiveButton("Review upload",(dialog,which)->{
                String deviceToken=secretInput.getText().toString().trim();
                secretInput.getText().clear();
                if(!InstitutionSyncClient.validToken(deviceToken)){
                    alert("Invalid student-scoped device credential.");return;
                }
                new AlertDialog.Builder(this)
                    .setTitle("Send unverified study history?")
                    .setMessage("Send "+count+" study attempts and timestamps from institution " + tenant +
                        " to https://"+BuildConfig.SYNC_HOST+"?\n\n"+
                        "These records remain UNVERIFIED, not official exam marks. Your local copy stays on this device.")
                    .setNegativeButton("Cancel",(d,w)->{})
                    .setPositiveButton("Send now",(d,w)->{
                        if(!uploading.compareAndSet(false,true))return;
                        new Thread(()->{
                            String status;
                            try {
                                ManagedPolicy latest=ManagedPolicy.read(this);
                                if(!isManualSyncAllowed(latest) || !latest.tenantId.equals(tenant))
                                    throw new SecurityException("Institution permissions changed");
                                status=InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,deviceToken,payload,tenant,fingerprint);
                            } catch(Exception failure) {
                                status="Sync could not finish securely. Check connectivity and institutional provisioning.";
                            } finally {uploading.set(false);}
                            alert(status);
                        },"chemforge-manual-sync").start();
                    }).show();
            }).show();
    }

    private boolean matchesRecordTenant(String tenant) {
        ManagedPolicy current = ManagedPolicy.read(this);
        return tenant != null && tenant.equals(current.tenantId);
    }

    private final class NativeBridge {
        @JavascriptInterface public void syncBackup(String tenant,String fingerprint) {
            if(!BuildConfig.SYNC_CONNECTED) {alert("This CHEMFORGE build has no network access.");return;}
            runOnUiThread(()->requestManualSync(tenant,fingerprint));
        }
        /** JSON-envelope so decryption failures cannot masquerade as empty study history. */
        @JavascriptInterface public String loadRecords(String tenant, String fingerprint) {
            try {
                if (!matchesRecordTenant(tenant)) throw new SecurityException("institution mismatch");
                String payload=recordStore.read(tenant,fingerprint);
                JSONObject response=new JSONObject();response.put("ok",true);
                response.put("found",payload!=null);
                if(payload!=null) response.put("payload",payload);
                return response.toString();
            } catch(Exception failure) {
                return "{\"ok\":false,\"error\":\"Encrypted study history unavailable or invalid\"}";
            }
        }
        @JavascriptInterface public boolean saveRecords(String tenant, String fingerprint, String json) {
            try {
                if (!matchesRecordTenant(tenant) || json==null || json.getBytes(StandardCharsets.UTF_8).length>MAX_BACKUP_BYTES)
                    return false;
                JSONObject object=new JSONObject(json);
                if(!"CHEMFORGE_ANDROID".equals(object.optString("app")) || object.optInt("schema_version")!=1 ||
                   !tenant.equals(object.optString("tenant_id")) || !fingerprint.equals(object.optString("content_fingerprint")) ||
                   !object.has("attempts") || !(object.opt("attempts") instanceof org.json.JSONArray)) return false;
                recordStore.write(tenant,fingerprint,json);
                return true;
            } catch(Exception failure) { return false; }
        }

        @JavascriptInterface public void importContentPack() {
            if (!policy.allowContentImport) { alert("Institution policy blocks curriculum imports."); return; }
            runOnUiThread(() -> {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(intent, IMPORT_PACK);
            });
        }
        @JavascriptInterface public void exportJson(String json) {
            if (!policy.allowExport) { alert("Institution policy blocks exporting study records."); return; }
            if (json == null || json.getBytes(StandardCharsets.UTF_8).length > MAX_BACKUP_BYTES) {
                alert("Export exceeds the 2 MB safety limit."); return;
            }
            try {
                JSONObject object = new JSONObject(json);
                if (!"CHEMFORGE_ANDROID".equals(object.optString("app")) || object.optInt("schema_version") != 1) {
                    alert("Export rejected: invalid CHEMFORGE format."); return;
                }
            } catch (JSONException ex) {
                alert("Export rejected: invalid JSON."); return;
            }
            runOnUiThread(() -> {
                pendingExport = json;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/json");
                intent.putExtra(Intent.EXTRA_TITLE, "chemforge-study-backup.json");
                startActivityForResult(intent, EXPORT_JSON);
            });
        }
        @JavascriptInterface public void modelStatus() {
            if (!policy.localAi) {sendModelEvent("status", "", "Local AI disabled by institution policy.");return;}
            modelHost.status();
        }
        @JavascriptInterface public void unloadModel() { modelHost.release(); }
        @JavascriptInterface public void benchmarkModel(String requestId) {
            ManagedPolicy current=ManagedPolicy.read(MainActivity.this);
            if(!current.localAi){sendModelEvent("error", requestId==null?"":requestId, "Offline AI disabled by institution policy.");return;}
            if(requestId==null || requestId.length()>50 || !requestId.matches("bench-[0-9]+")){
                sendModelEvent("error", "", "Invalid model diagnostic request.");return;
            }
            modelHost.benchmark(requestId);
        }
        @JavascriptInterface public void askModel(String requestId, String prompt) {
            if (!policy.localAi) {sendModelEvent("error", requestId==null?"":requestId, "AI disabled by institution policy.");return;}
            if (requestId == null || requestId.length() > 50 || prompt == null || prompt.length() > 11000) {
                sendModelEvent("error", requestId == null ? "" : requestId, "Invalid coaching request.");
                return;
            }
            modelHost.ask(requestId, prompt);
        }
        @JavascriptInterface public void importModel() {
            if (!policy.localAi) {alert("AI model imports disabled by institution policy.");return;}
            runOnUiThread(() -> {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*"); // SAF providers classify .litertlm files differently.
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivityForResult(intent, IMPORT_MODEL);
            });
        }
        @JavascriptInterface public void importJson() {
            if (!policy.allowImport) { alert("Institution policy blocks study backup imports."); return; }
            runOnUiThread(() -> {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/json");
                startActivityForResult(intent, IMPORT_JSON);
            });
        }
    }

    private void alert(String message) {
        runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_LONG).show());
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent result) {
        super.onActivityResult(requestCode, resultCode, result);
        if (resultCode != RESULT_OK || result == null || result.getData() == null) {
            if (requestCode == EXPORT_JSON) pendingExport = null;
            return;
        }
        Uri uri = result.getData();
        policy = ManagedPolicy.read(this);
        if (requestCode == IMPORT_PACK) {
            if (!policy.allowContentImport) {alert("Institution policy changed; pack import blocked.");return;}
            String institution = policy.tenantId;
            packManager.install(uri, institution, (success, message) -> runOnUiThread(() -> {
                alert(message);
                if (success && policy.tenantId.equals(institution) && view!=null) view.loadUrl(BASE_URL);
            }));
        } else if (requestCode == IMPORT_MODEL) {
            if (policy.localAi) modelHost.install(uri);
        } else if (requestCode == EXPORT_JSON && pendingExport != null) {
            if (!policy.allowExport) {pendingExport=null;alert("Institution policy blocks export.");return;}
            try (OutputStream stream = getContentResolver().openOutputStream(uri, "wt")) {
                if (stream == null) throw new IOException("Unable to open target document");
                stream.write(pendingExport.getBytes(StandardCharsets.UTF_8));
                alert("CHEMFORGE backup saved.");
            } catch (IOException ex) { alert("Could not export backup."); }
            finally { pendingExport = null; }
        } else if (requestCode == IMPORT_JSON) {
            if (requestCode == IMPORT_JSON && !policy.allowImport) {
                alert("Institution policy changed; study backup import blocked."); return;
            }
            try (InputStream stream = getContentResolver().openInputStream(uri)) {
                if (stream == null) throw new IOException("Unable to read chosen document");
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192]; int n;
                while ((n = stream.read(buffer)) != -1) {
                    if (output.size()+n > MAX_BACKUP_BYTES) throw new IOException("Backup exceeds 2 MB limit");
                    output.write(buffer,0,n);
                }
                String json = output.toString(StandardCharsets.UTF_8.name());
                view.evaluateJavascript("window.receiveChemforgeImport("+JSONObject.quote(json)+")", null);
            } catch (IOException ex) { alert("Import failed or exceeded 2 MB."); }
        }
    }

    @Override @SuppressWarnings("deprecation") public void onBackPressed() {
        if (view != null && view.canGoBack()) view.goBack();
        else super.onBackPressed();
    }

    @Override public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        if (level >= TRIM_MEMORY_RUNNING_LOW && modelHost != null) modelHost.release();
    }

    @Override protected void onResume() {
        super.onResume();
        refreshPolicy();
        if (!receiverRegistered) {
            IntentFilter filter = new IntentFilter(Intent.ACTION_APPLICATION_RESTRICTIONS_CHANGED);
            if (Build.VERSION.SDK_INT>=33) registerReceiver(restrictionsReceiver,filter,Context.RECEIVER_NOT_EXPORTED);
            else registerReceiver(restrictionsReceiver,filter);
            receiverRegistered = true;
        }
    }
    @Override protected void onPause() {
        if (receiverRegistered) {unregisterReceiver(restrictionsReceiver);receiverRegistered=false;}
        super.onPause();
    }

    @Override protected void onStop() {
        if (modelHost != null) modelHost.release();
        super.onStop();
    }

    @Override protected void onDestroy() {
        if (modelHost != null) { modelHost.close(); modelHost = null; }
        recordStore = null;
        if (packManager != null) {packManager.close();packManager=null;}
        if (view != null) { view.removeJavascriptInterface("ChemforgeNative"); view.destroy(); view = null; }
        super.onDestroy();
    }
}
