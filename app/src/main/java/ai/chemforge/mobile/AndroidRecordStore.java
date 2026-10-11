package ai.chemforge.mobile;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.KeyStore;
import java.security.MessageDigest;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;

/** AndroidKeyStore-backed encrypted study history; no network or external storage permissions.
 * Records are private to an Android app install and are NOT portable without explicit JSON export.
 */
final class AndroidRecordStore {
    private static final String ALIAS="chemforge-records-aes256-v1";
    private static final int MAX_RECORD_BYTES=2_000_000;
    private final Context context;

    AndroidRecordStore(Context context) { this.context=context.getApplicationContext(); }
    private static String scope(String tenant,String fingerprint) {
        if(tenant==null || !tenant.matches("[A-Za-z0-9._-]{0,100}") || fingerprint==null ||
            !(fingerprint.equals("pilot-0.1") || fingerprint.matches("[a-f0-9]{64}")))
            throw new SecurityException("invalid institution or content fingerprint");
        return tenant+"\n"+fingerprint;
    }
    private File fileFor(String scope) throws Exception {
        // File path contains only a SHA digest; no institution name leaks in filenames.
        String hash=SignedContentVerifier.sha256(scope.getBytes(StandardCharsets.UTF_8));
        return new File(context.getFilesDir(), "studies-"+hash+".cfrecord");
    }
    private static synchronized SecretKey encryptionKey() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(ks.containsAlias(ALIAS)) {
            KeyStore.Entry entry=ks.getEntry(ALIAS,null);
            if(!(entry instanceof KeyStore.SecretKeyEntry)) throw new SecurityException("invalid device storage key");
            return ((KeyStore.SecretKeyEntry)entry).getSecretKey();
        }
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
            KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)
            .build());
        return generator.generateKey();
    }
    synchronized String read(String tenant,String fingerprint) throws Exception {
        String scope=scope(tenant,fingerprint);
        File source=fileFor(scope);
        if(!source.exists())return null;
        if(!source.isFile()||source.length()>MAX_RECORD_BYTES+64)throw new SecurityException("invalid encrypted record size");
        byte[] plaintext=RecordCipher.open(encryptionKey(),scope,Files.readAllBytes(source.toPath()));
        return new String(plaintext,StandardCharsets.UTF_8);
    }
    synchronized void write(String tenant,String fingerprint,String json) throws Exception {
        String scope=scope(tenant,fingerprint);
        if(json==null)throw new IllegalArgumentException("missing records");
        byte[] plaintext=json.getBytes(StandardCharsets.UTF_8);
        if(plaintext.length>MAX_RECORD_BYTES)throw new SecurityException("record exceeds 2 MB limit");
        byte[] sealed=RecordCipher.seal(encryptionKey(),scope,plaintext);
        File destination=fileFor(scope);
        File temporary=File.createTempFile("studies-", ".tmp", context.getFilesDir());
        try {
            try(FileOutputStream output=new FileOutputStream(temporary)) {
                output.write(sealed);
                output.getFD().sync();
            }
            try { Files.move(temporary.toPath(),destination.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING); }
            catch (java.nio.file.AtomicMoveNotSupportedException ex) {
                Files.move(temporary.toPath(),destination.toPath(),StandardCopyOption.REPLACE_EXISTING);
            }
        } finally { temporary.delete(); }
    }
}
