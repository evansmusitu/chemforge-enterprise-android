package ai.chemforge.mobile;

import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.GeneralSecurityException;

/** Standard Java only: cryptographic guard shared with a pure-JDK harness. */
public final class SignedContentVerifier {
    private SignedContentVerifier() {}
    public static String sha256(byte[] data) throws GeneralSecurityException {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder hex = new StringBuilder(digest.length * 2);
        for (byte b : digest) hex.append(Character.forDigit((b >> 4) & 15, 16)).append(Character.forDigit(b & 15, 16));
        return hex.toString();
    }
    public static void check(PublicKey key, byte[] manifest, byte[] content,
                             byte[] signature, String declaredDigest) throws GeneralSecurityException {
        if (key == null || !"EC".equals(key.getAlgorithm())) throw new SecurityException("invalid pinned verification key");
        Signature verifier = Signature.getInstance("SHA256withECDSA");
        verifier.initVerify(key);
        verifier.update(manifest);
        if (!verifier.verify(signature)) throw new SecurityException("pack signature rejected");
        if (!MessageDigest.isEqual(sha256(content).getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                declaredDigest.getBytes(java.nio.charset.StandardCharsets.US_ASCII)))
            throw new SecurityException("pack digest mismatch");
    }
}
