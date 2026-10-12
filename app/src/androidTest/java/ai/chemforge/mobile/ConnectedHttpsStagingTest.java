package ai.chemforge.mobile;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Assume;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLException;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManagerFactory;

import static org.junit.Assert.*;

/** Real network-to-FastAPI HTTPS staging, never a mock server.
 * ONLY runs in the connected QA variant when ephemeral synthetic fixtures exist.
 * The test certificate is loaded from the test APK; production trust is NEVER weakened.
 */
@RunWith(AndroidJUnit4.class)
public class ConnectedHttpsStagingTest {
    private JSONObject readFixture(Context ctx) throws Exception {
        try (InputStream input = ctx.getAssets().open("ci_staging_fixture.json")) {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] data = new byte[1024]; int n;
            while ((n=input.read(data)) != -1) {
                if (output.size()+n > 4000) throw new SecurityException("Oversize test fixture");
                output.write(data,0,n);
            }
            return new JSONObject(output.toString(StandardCharsets.UTF_8.name()));
        }
    }
    private SSLSocketFactory temporaryStagingTrust(Context ctx) throws Exception {
        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        Certificate stagingCert;
        try(InputStream in = ctx.getAssets().open("ci_staging_cert.pem")) {
            stagingCert = cf.generateCertificate(in);
        }
        KeyStore store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null,null);
        store.setCertificateEntry("ephemeral-synthetic-staging-only",stagingCert);
        TrustManagerFactory factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        factory.init(store);
        SSLContext ssl = SSLContext.getInstance("TLS");
        ssl.init(null,factory.getTrustManagers(),null);
        return ssl.getSocketFactory();
    }

    @Test public void uploadViaRealHttpsAndVerifyReceipts() throws Exception {
        Assume.assumeTrue("Connected CI only",BuildConfig.SYNC_CONNECTED);
        assertEquals("QA build must target Android emulator host", "10.0.2.2", BuildConfig.SYNC_HOST);
        Context context = InstrumentationRegistry.getInstrumentation().getContext();
        JSONObject fixture = readFixture(context);
        String backup=fixture.getJSONObject("backup").toString();
        String tenant=fixture.getString("tenant");
        String good=fixture.getString("token");
        String revoked=fixture.getString("revoked_token");
        String foreign=fixture.getString("foreign_token");
        SSLSocketFactory regular = HttpsURLConnection.getDefaultSSLSocketFactory();
        try {
            // A self-signed staging server MUST fail on a stock Android trust store.
            try {
                InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,good,backup,tenant,"pilot-0.1");
                fail("The CI staging TLS certificate was unexpectedly trusted by Android");
            } catch(SSLException expected) {
                // expected: unknown staging trust anchor
            }
            HttpsURLConnection.setDefaultSSLSocketFactory(temporaryStagingTrust(context));
            assertEquals("Uploaded 1 unverified study attempts; 0 duplicates skipped.",
                InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,good,backup,tenant,"pilot-0.1"));
            assertEquals("Uploaded 0 unverified study attempts; 1 duplicates skipped.",
                InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,good,backup,tenant,"pilot-0.1"));
            assertEquals("Sync denied: device authorisation is invalid or revoked.",
                InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,revoked,backup,tenant,"pilot-0.1"));
            assertEquals("Sync rejected: the server requires a different backup format.",
                InstitutionSyncClient.upload(BuildConfig.SYNC_HOST,foreign,backup,tenant,"pilot-0.1"));
        } finally {
            HttpsURLConnection.setDefaultSSLSocketFactory(regular);
        }
    }
}
