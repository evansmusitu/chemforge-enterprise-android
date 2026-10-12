package ai.chemforge.mobile;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Manual, opt-in upload only; invoked from the separate connected build.
 * Unverified history cannot certify assessment evidence.
 */
final class InstitutionSyncClient {
    private static final int MAX_BYTES = 2_000_000;
    private static final int MAX_RESPONSE = 4096;
    private static final int connectTimeout = 8000;
    private static final int readTimeout = 15000;
    static boolean validHost(String host) {
        return host != null && host.length() <= 180 && !host.endsWith(".invalid") &&
            host.matches("[a-z0-9-]+(\\.[a-z0-9-]+)+") &&
            !host.equals("localhost") && !host.endsWith(".local");
    }
    static boolean validToken(String token) {
        return token != null && token.length() < 121 && token.matches("cfsync_[A-Za-z0-9_-]{40,60}");
    }
    static int countVerifiedShape(String json,String expectedTenant,String expectedFingerprint) throws Exception {
        if(json == null || json.getBytes(StandardCharsets.UTF_8).length > MAX_BYTES)
            throw new SecurityException("Study backup exceeds local size limit");
        JSONObject body=new JSONObject(json);
        if(!"CHEMFORGE_ANDROID".equals(body.optString("app")) || body.optInt("schema_version")!=1 ||
           !expectedTenant.equals(body.optString("tenant_id")) ||
           !expectedFingerprint.equals(body.optString("content_fingerprint")))
            throw new SecurityException("Study history does not match institution or curriculum");
        JSONArray rows=body.optJSONArray("attempts");
        if(rows==null || rows.length()>1000)throw new SecurityException("Too many study attempts");
        for(int i=0;i<rows.length();i++) {
            JSONObject row=rows.getJSONObject(i);
            if(!expectedTenant.equals(row.optString("tenant_id")) ||
               !expectedFingerprint.equals(row.optString("content_fingerprint")))
                throw new SecurityException("Attempt has a mismatched institution or curriculum");
        }
        return rows.length();
    }
    /** Runs on a worker thread. No redirects, no arbitrary endpoint, and no upload retries. */
    static String upload(String host,String token,String json,String tenant,String fingerprint) throws Exception {
        if(!validHost(host) || !validToken(token))throw new SecurityException("Invalid institutional sync configuration");
        int count=countVerifiedShape(json,tenant,fingerprint);
        if(count==0)return "No study attempts to upload.";
        HttpsURLConnection connection=null;
        try {
            URL url=new URL("https://"+host+"/v1/sync/backups");
            connection=(HttpsURLConnection)url.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(connectTimeout);
            connection.setReadTimeout(readTimeout);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Authorization","Device "+token);
            connection.setRequestProperty("Content-Type","application/json; charset=utf-8");
            connection.setRequestProperty("Cache-Control","no-store");
            connection.setDoOutput(true);
            byte[] bytes=json.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            try(OutputStream out=connection.getOutputStream()){out.write(bytes);}
            int code=connection.getResponseCode();
            if(code==401 || code==403)return "Sync denied: device authorisation is invalid or revoked.";
            if(code==409)return "Sync rejected: conflicting record identifiers. Local records are unchanged.";
            if(code==422)return "Sync rejected: the server requires a different backup format.";
            if(code!=200 && code!=201)return "Sync unavailable (HTTP "+code+"). Local records are unchanged.";
            ByteArrayOutputStream reply=new ByteArrayOutputStream();
            try(InputStream in=connection.getInputStream()){
                byte[] buffer=new byte[512];int n;
                while((n=in.read(buffer))!=-1){
                    if(reply.size()+n>MAX_RESPONSE)throw new SecurityException("Invalid sync response size");
                    reply.write(buffer,0,n);
                }
            }
            JSONObject result=new JSONObject(reply.toString(StandardCharsets.UTF_8.name()));
            if(!result.has("imported") || !result.has("unchanged") || result.optInt("verified",-1)!=0)
                throw new SecurityException("Invalid or improperly certified sync response");
            int imported=result.getInt("imported"), duplicates=result.getInt("unchanged");
            if(imported<0 || duplicates<0 || imported+duplicates!=count)
                throw new SecurityException("Unverifiable sync receipt");
            return "Uploaded "+imported+" unverified study attempts; "+duplicates+" duplicates skipped.";
        } finally {if(connection!=null)connection.disconnect();}
    }
}
