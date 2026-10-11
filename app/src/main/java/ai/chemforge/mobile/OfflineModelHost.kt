package ai.chemforge.mobile

import android.app.ActivityManager
import android.content.Context
import android.net.Uri
import android.os.StatFs
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.concurrent.Executors

/** Single-threaded, in-process, network-free LiteRT-LM runner. Student marks never pass through it. */
class OfflineModelHost(private val context: Context, private val listener: Listener) {
    fun interface Listener { fun event(kind: String, requestId: String, payload: String) }

    private val executor = Executors.newSingleThreadExecutor { task ->
        Thread(task, "chemforge-local-inference").apply { isDaemon = true }
    }
    // Conservative opt-in model policy for phones with 4 GB physical RAM.
    // Native libraries and fixed-size KV caches consume much more than the model file.
    private val MIN_AVAILABLE_BYTES = 1_500_000_000L
    private val MAX_MODEL_BYTES = 600_000_000L
    private val model = File(context.filesDir, "chemforge_local.litertlm")
    private var engine: Engine? = null
    private val approvedDigest = BuildConfig.APPROVED_MODEL_SHA256.lowercase(java.util.Locale.ROOT)
    private fun validApprovedDigest(): Boolean = approvedDigest.matches(Regex("[0-9a-f]{64}"))

    private fun verifyInstalledModel() {
        require(validApprovedDigest()) { "approved institutional model not configured" }
        val sha = MessageDigest.getInstance("SHA-256")
        model.inputStream().buffered().use { source ->
            val chunk=ByteArray(256*1024)
            while (true) {
                val count=source.read(chunk)
                if (count<0) break
                sha.update(chunk,0,count)
            }
        }
        val found=sha.digest().joinToString("") { "%02x".format(it) }
        require(found==approvedDigest) { "model file does not match the approved institutional digest" }
    }
    @Volatile private var closed = false

    fun status() {
        listener.event("status", "", if (!validApprovedDigest()) "AI model not authorised: this institutional build has no approved model SHA-256." else if (model.isFile) "Institutional model installed locally; verified before inference." else "No model installed. Import the institution-approved .litertlm file.")
    }

    fun install(uri: Uri) {
        if (closed) return
        executor.execute {
            var tmp: File? = null
            try {
                val initialPolicy = ManagedPolicy.read(context)
                require(initialPolicy.localAi) { "AI model imports disabled by institution policy" }
                require(validApprovedDigest()) { "approved institutional model not configured" }
                listener.event("status", "", "Copying model to app-private storage…")
                val freeBytes = StatFs(context.filesDir.absolutePath).availableBytes
                // Limit import size so a mistaken 10 GB file cannot fill the user's phone.
                val maxBytes = minOf(MAX_MODEL_BYTES, freeBytes - 75_000_000L)
                require(maxBytes > 20_000_000L) { "Not enough free phone storage for a model." }
                val path = context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                } ?: ""
                require(path.lowercase().endsWith(".litertlm")) { "Choose a .litertlm model file, not GGUF or a ZIP." }
                tmp = File.createTempFile("model-import-", ".litertlm", context.filesDir)
                val digest = MessageDigest.getInstance("SHA-256")
                var total = 0L
                val input = context.contentResolver.openInputStream(uri) ?: error("Cannot access the selected file.")
                input.use { src ->
                    tmp!!.outputStream().buffered().use { dest ->
                        val chunk = ByteArray(1024 * 256)
                        while (true) {
                            val n = src.read(chunk)
                            if (n < 0) break
                            total += n
                            require(total <= maxBytes) { "Model too large or phone storage too low." }
                            digest.update(chunk, 0, n)
                            dest.write(chunk, 0, n)
                        }
                    }
                }
                require(total > 20_000_000L) { "Selected file is too small to be a supported model." }
                require(validApprovedDigest()) { "approved institutional model not configured" }
                val hex = digest.digest().joinToString("") { "%02x".format(it) }
                require(hex == approvedDigest) { "model file does not match the approved institutional digest" }
                val currentPolicy = ManagedPolicy.read(context)
                require(currentPolicy.localAi && currentPolicy.tenantId == initialPolicy.tenantId) {
                    "institution policy changed during model import"
                }
                engine?.close()
                engine = null
                try {
                    Files.move(tmp!!.toPath(), model.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
                } catch (_: java.nio.file.AtomicMoveNotSupportedException) {
                    Files.move(tmp!!.toPath(), model.toPath(), StandardCopyOption.REPLACE_EXISTING)
                }
                tmp = null
                listener.event("status", "", "Imported ${total / (1024 * 1024)} MiB locally. SHA-256: ${hex.take(16)}… Model loading will be tested when you ask for an explanation.")
            } catch (ex: Exception) {
                listener.event("error", "", "Model import unsuccessful: ${ex.message ?: "unknown error"}")
            } finally {
                tmp?.delete()
            }
        }
    }

    fun ask(requestId: String, prompt: String) {
        if (closed) return
        if (prompt.length !in 1..11_000) {
            listener.event("error", requestId, "AI prompt must contain 1–11,000 characters.")
            return
        }
        executor.execute {
            try {
                require(model.isFile) { "No model imported. Import the institution-approved .litertlm file first." }
                if (engine == null) {
                    verifyInstalledModel()
                    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                    val mem = ActivityManager.MemoryInfo()
                    manager.getMemoryInfo(mem)
                    if (mem.lowMemory || mem.availMem < MIN_AVAILABLE_BYTES) {
                        listener.event("error", requestId, "Not enough free phone RAM for the experimental AI (${mem.availMem / 1_000_000} MB available). Close other apps and try again. Offline lessons still work.")
                        return@execute
                    }
                    listener.event("progress", requestId, "Loading model into phone memory (may take a while)…")
                    val fresh = Engine(EngineConfig(modelPath = model.absolutePath, backend = Backend.CPU()))
                    try { fresh.initialize(); engine = fresh }
                    catch (ex: Exception) { fresh.close(); throw ex }
                }
                listener.event("progress", requestId, "Generating explanation entirely on your phone…")
                // One-shot conversation prevents cross-question contamination and long context growth.
                val answer = engine!!.createConversation(
                    com.google.ai.edge.litertlm.ConversationConfig(maxOutputToken = 160)
                ).use { conversation ->
                    conversation.sendMessage(prompt).toString()
                }
                listener.event("answer", requestId, answer.take(24_000))
            } catch (err: Exception) {
                listener.event("error", requestId, "Local model unavailable: ${err.message ?: "unknown error"}. Offline practice still works.")
            }
        }
    }

    /** Free native model memory without clearing private study records or the imported file. */
    fun release() {
        if (closed) return
        executor.execute {
            engine?.close()
            engine = null
            listener.event("status", "", "AI model unloaded from RAM. Offline revision remains available.")
        }
    }

    fun close() {
        closed = true
        executor.execute {
            engine?.close()
            engine = null
        }
        executor.shutdown()
    }
}
