import ai.chemforge.mobile.SignedContentVerifier;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.Arrays;

public final class ContentVerifierHarness {
  public static void main(String[] args) throws Exception {
    KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
    g.initialize(256);
    KeyPair key = g.generateKeyPair();
    byte[] payload = "a verified content bundle".getBytes(StandardCharsets.UTF_8);
    byte[] manifest = ("{\"content_sha256\":\"" + SignedContentVerifier.sha256(payload) + "\"}").getBytes(StandardCharsets.UTF_8);
    Signature signer = Signature.getInstance("SHA256withECDSA");
    signer.initSign(key.getPrivate()); signer.update(manifest);
    byte[] signature = signer.sign();
    SignedContentVerifier.check(key.getPublic(), manifest, payload, signature, SignedContentVerifier.sha256(payload));
    byte[] tampered = Arrays.copyOf(payload,payload.length);tampered[0] ^= 1;
    try {SignedContentVerifier.check(key.getPublic(), manifest, tampered, signature, SignedContentVerifier.sha256(payload)); throw new AssertionError("content tampering accepted");}
    catch(SecurityException expected) {}
    try {SignedContentVerifier.check(key.getPublic(), manifest, payload, signature, "0".repeat(64)); throw new AssertionError("hash mismatch accepted");}
    catch(SecurityException expected) {}
    byte[] forged = Arrays.copyOf(manifest,manifest.length); forged[0] ^= 1;
    try {SignedContentVerifier.check(key.getPublic(), forged, payload, signature, SignedContentVerifier.sha256(payload)); throw new AssertionError("manifest tampering accepted");}
    catch(SecurityException expected) {}
    System.out.println("ECDSA signed manifest verifier: PASS (valid + tampering cases)");
  }
}
