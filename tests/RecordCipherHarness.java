import ai.chemforge.mobile.RecordCipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public final class RecordCipherHarness {
    private static void expectRejected(Checked action) throws Exception {
        try { action.run(); throw new AssertionError("expected authentication or input rejection"); }
        catch (javax.crypto.AEADBadTagException | java.lang.IllegalArgumentException | java.lang.SecurityException ok) { }
    }
    @FunctionalInterface interface Checked { void run() throws Exception; }
    public static void main(String[] args) throws Exception {
        KeyGenerator kg=KeyGenerator.getInstance("AES");kg.init(256);
        SecretKey key=kg.generateKey(), other=kg.generateKey();
        String scope="tenant-schoolA\n" + "a".repeat(64);
        byte[] input="{\"private\":true,\"score\":3}".getBytes(StandardCharsets.UTF_8);
        byte[] c1=RecordCipher.seal(key,scope,input);
        byte[] c2=RecordCipher.seal(key,scope,input);
        if(Arrays.equals(c1,input) || Arrays.equals(c1,c2))throw new AssertionError("plaintext exposure or reused nonce");
        if(!Arrays.equals(input, RecordCipher.open(key,scope,c1))) throw new AssertionError("decrypt mismatch");
        expectRejected(()->RecordCipher.open(key,"tenant-schoolB\n"+"a".repeat(64),c1));
        expectRejected(()->RecordCipher.open(key,"tenant-schoolA\n"+"b".repeat(64),c1));
        expectRejected(()->RecordCipher.open(other,scope,c1));
        byte[] altered=c1.clone();altered[altered.length-1]^=1;
        expectRejected(()->RecordCipher.open(key,scope,altered));
        expectRejected(()->RecordCipher.open(key,scope,new byte[]{1,2}));
        expectRejected(()->RecordCipher.seal(key,"",input));
        expectRejected(()->RecordCipher.seal(key,scope,new byte[2_000_001]));
        System.out.println("RecordCipher tests: PASS (AEAD, tenant/content binding, tampering, bounds, unique IV)");
    }
}
