package ai.chemforge.mobile;

import android.Manifest;
import android.content.Context;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import android.content.pm.PackageManager;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Runs inside Android instrumentation, unlike the host-only JS smoke suite. */
@RunWith(AndroidJUnit4.class)
public class OfflineLaunchTest {
    private WebView webView(ActivityScenario<MainActivity> scenario) {
        AtomicReference<WebView> result = new AtomicReference<>();
        scenario.onActivity(activity -> {
            ViewGroup content = activity.findViewById(android.R.id.content);
            View first = content.getChildAt(0);
            assertTrue("MainActivity must present a WebView", first instanceof WebView);
            result.set((WebView)first);
        });
        return result.get();
    }
    private String js(WebView webView, String expression) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> value = new AtomicReference<>("null");
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() ->
            webView.evaluateJavascript(expression, output -> {value.set(output);done.countDown();}));
        assertTrue("evaluateJavascript callback timed out",done.await(8,TimeUnit.SECONDS));
        return value.get();
    }
    private void eventuallyTrue(WebView webView,String expression) throws Exception {
        long deadline = System.currentTimeMillis()+20_000;
        String actual="null";
        while(System.currentTimeMillis()<deadline){
            actual=js(webView,expression);
            if("true".equals(actual))return;
            Thread.sleep(250);
        }
        fail("WebView condition did not become true: "+expression+" returned "+actual);
    }
    @Test public void assertInstitutionSyncValidationWithoutNetwork() throws Exception {
        assertFalse(InstitutionSyncClient.validHost("localhost"));
        assertFalse(InstitutionSyncClient.validHost("sync.example.invalid"));
        assertFalse(InstitutionSyncClient.validHost("http://school.example.org"));
        assertTrue(InstitutionSyncClient.validHost("sync.school.example.org"));
        assertFalse(InstitutionSyncClient.validToken("admin-password"));
        String record="{\"app\":\"CHEMFORGE_ANDROID\",\"schema_version\":1," +
            "\"tenant_id\":\"school-one\",\"content_fingerprint\":\"pilot-0.1\"," +
            "\"attempts\":[{\"tenant_id\":\"school-one\",\"content_fingerprint\":\"pilot-0.1\"}]}";
        assertEquals(1,InstitutionSyncClient.countVerifiedShape(record,"school-one","pilot-0.1"));
        boolean rejected=false;
        try {InstitutionSyncClient.countVerifiedShape(record,"school-two","pilot-0.1");}
        catch(SecurityException expected){rejected=true;}
        assertTrue("Native client must deny a wrong institution",rejected);
    }

    @Test public void assertOfflineHomeLoads() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            WebView web=webView(scenario);
            eventuallyTrue(web,"!!(window.ChemEngine && document.querySelector('#stat-attempts') && document.querySelector('#start-study'))");
            assertEquals("Only the connected build may request INTERNET permission",
                BuildConfig.SYNC_CONNECTED ? PackageManager.PERMISSION_GRANTED : PackageManager.PERMISSION_DENIED,
                InstrumentationRegistry.getInstrumentation().getTargetContext().checkSelfPermission(Manifest.permission.INTERNET));
            assertEquals("true",js(web,"document.querySelector('#screen-home').classList.contains('active')"));
        }
    }
    @Test public void assertAndroidKeystoreRecordIntegrity() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        String tenant="androidtest-"+System.nanoTime();
        String fingerprint="pilot-0.1";
        String records="{\"app\":\"CHEMFORGE_ANDROID\",\"schema_version\":1,\"attempts\":[]}";
        String scope=tenant+"\n"+fingerprint;
        String digest=SignedContentVerifier.sha256(scope.getBytes(StandardCharsets.UTF_8));
        File file=new File(context.getFilesDir(),"studies-"+digest+".cfrecord");
        try {
            AndroidRecordStore first=new AndroidRecordStore(context);
            first.write(tenant,fingerprint,records);
            byte[] sealed=Files.readAllBytes(file.toPath());
            assertFalse("Records must not persist in plaintext",new String(sealed,StandardCharsets.UTF_8).contains("attempts"));
            AndroidRecordStore reopened=new AndroidRecordStore(context);
            assertEquals(records,reopened.read(tenant,fingerprint));
            sealed[sealed.length-1]^=0x01;
            Files.write(file.toPath(),sealed);
            boolean rejected=false;
            try {reopened.read(tenant,fingerprint);}catch(Exception expected){rejected=true;}
            assertTrue("Tampering must reject record instead of returning empty history",rejected);
        } finally {file.delete();}
    }
    @Test public void assertModelSelfTestDoesNotChangeLearningHistory() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            WebView web=webView(scenario);
            eventuallyTrue(web,"!!(window.ChemModelDiagnostics && document.querySelector('#model-benchmark'))");
            final String before=js(web,"document.querySelector('#stat-attempts').textContent");
            assertEquals("true", js(web,"(document.querySelector('#model-benchmark').click(),true)"));
            eventuallyTrue(web,"document.querySelector('#model-diagnostics').textContent.length>0");
            assertEquals("A model diagnostic must not change assessment evidence",before,
                js(web,"document.querySelector('#stat-attempts').textContent"));
        }
    }

    @Test public void assertLearnNavigation() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            WebView web=webView(scenario);
            eventuallyTrue(web,"!!(window.ChemEngine && document.querySelector('[data-screen=learn]'))");
            assertEquals("true",js(web,"(document.querySelector('[data-screen=learn]').click(),true)"));
            eventuallyTrue(web,"document.querySelector('#screen-learn').classList.contains('active') && document.querySelectorAll('.micro-lesson').length>0");
        }
    }
}
