package ai.chemforge.mobile;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Versioned AES-256-GCM envelope bound to institution+content scope via AAD.
 * This Java-only component can be tested without Android. Keys come from AndroidKeyStore.
 * Encryption protects data at rest, not against attacks on an unlocked compromised device.
 */
public final class RecordCipher {
    private static final byte[] MAGIC = {'C','F','R','1'};
    private static final int NONCE_BYTES=12, TAG_BYTES=16, MAX_PLAINTEXT=2_000_000;
    private RecordCipher() { }

    private static byte[] aad(String scope) {
        if (scope==null || scope.length()<1 || scope.length()>256) throw new IllegalArgumentException("invalid record scope");
        byte[] bytes=scope.getBytes(StandardCharsets.UTF_8);
        if(bytes.length>512) throw new IllegalArgumentException("record scope too long");
        return bytes;
    }
    public static byte[] seal(SecretKey key, String scope, byte[] plaintext) throws Exception {
        byte[] associated=aad(scope);
        if (key==null || plaintext==null || plaintext.length>MAX_PLAINTEXT)
            throw new IllegalArgumentException("invalid record plaintext");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        // AndroidKeyStore AES-GCM keys with randomized encryption REQUIRE provider-created IVs.
        // Do not supply a caller-generated nonce to init(ENCRYPT_MODE).
        cipher.init(Cipher.ENCRYPT_MODE,key);
        byte[] iv=cipher.getIV();
        if(iv==null || iv.length!=NONCE_BYTES)
            throw new SecurityException("AES-GCM provider returned an invalid IV");
        cipher.updateAAD(associated);
        byte[] ciphertext=cipher.doFinal(plaintext);
        byte[] result=new byte[MAGIC.length+iv.length+ciphertext.length];
        System.arraycopy(MAGIC,0,result,0,MAGIC.length);
        System.arraycopy(iv,0,result,MAGIC.length,iv.length);
        System.arraycopy(ciphertext,0,result,MAGIC.length+iv.length,ciphertext.length);
        return result;
    }
    public static byte[] open(SecretKey key, String scope, byte[] sealed) throws Exception {
        byte[] associated=aad(scope);
        if(key==null || sealed==null || sealed.length<MAGIC.length+NONCE_BYTES+TAG_BYTES ||
                sealed.length>MAGIC.length+NONCE_BYTES+TAG_BYTES+MAX_PLAINTEXT ||
                !Arrays.equals(Arrays.copyOf(sealed,MAGIC.length),MAGIC))
            throw new IllegalArgumentException("unrecognized encrypted record format");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(8*TAG_BYTES,
            Arrays.copyOfRange(sealed,MAGIC.length,MAGIC.length+NONCE_BYTES)));
        cipher.updateAAD(associated);
        return cipher.doFinal(sealed,MAGIC.length+NONCE_BYTES,sealed.length-MAGIC.length-NONCE_BYTES);
    }
}
