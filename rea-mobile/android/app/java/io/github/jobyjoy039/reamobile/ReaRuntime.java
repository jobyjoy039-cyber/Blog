package io.github.jobyjoy039.reamobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.text.TextUtils;
import android.util.Base64;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Runs REA on the phone: unpacks the bundled REA runtime on first launch, then starts
 * Termux's Android build of Node.js with REA Mobile's server on 127.0.0.1.
 *
 * Executables (node, ps) ship as lib*.so files so Android installs them into the app's
 * native library directory, the one app location it allows programs to run from.
 */
final class ReaRuntime {
    private static final String RUNTIME_ASSET = "rea-runtime.zip";
    private static final String LIBS_ASSET_PREFIX = "rea-libs-";
    private static final String VERSION_ASSET = "rea-runtime.json";

    private static ReaRuntime instance;

    private final Context context;
    private final File runtimeDir;
    private final File logFile;
    private final String token;
    private final SharedPreferences prefs;
    private volatile String status = "not started";
    private volatile int port;
    private Process process;
    private boolean stopping;

    static synchronized ReaRuntime get(Context context) {
        if (instance == null) instance = new ReaRuntime(context.getApplicationContext());
        return instance;
    }

    private ReaRuntime(Context context) {
        this.context = context;
        this.runtimeDir = new File(context.getFilesDir(), "runtime");
        this.logFile = new File(context.getFilesDir(), "rea-runtime.log");
        this.prefs = context.getSharedPreferences("rea", Context.MODE_PRIVATE);
        this.token = loadToken(prefs);
        // The interface is served at this address, so keep it stable across launches.
        this.port = prefs.getInt("port", 0);
        if (port == 0) savePort(20000 + new SecureRandom().nextInt(40000));
    }

    String status() {
        return status;
    }

    String baseUrl() {
        return "http://127.0.0.1:" + port;
    }

    int port() {
        return port;
    }

    String token() {
        return token;
    }

    File logFile() {
        return logFile;
    }

    /** Unpack (if needed) and start REA. Blocks; call from a background thread. */
    synchronized void start() {
        if (process != null && isAlive(process)) return;
        stopping = false;
        try {
            prepare();
            launch();
        } catch (Exception error) {
            status = "error " + error.getMessage();
            appendLog("\n[rea-mobile] " + error + "\n");
        }
    }

    synchronized void stop() {
        stopping = true;
        if (process != null) process.destroy();
        process = null;
        status = "stopped";
    }

    // ---- First-launch unpacking ----

    private void prepare() throws IOException {
        String bundled = readAsset(VERSION_ASSET);
        File stamp = new File(runtimeDir, ".bundle.json");
        if (stamp.exists() && bundled.equals(readFile(stamp))) return;

        deleteRecursively(runtimeDir);
        if (!runtimeDir.mkdirs()) throw new IOException("cannot create " + runtimeDir);
        String abi = nativeAbi();
        status = "unpacking 0%";
        int[] done = {0};
        int total = Math.max(1, countEntries(RUNTIME_ASSET) + countEntries(LIBS_ASSET_PREFIX + abi + ".zip"));
        unzipAsset(RUNTIME_ASSET, runtimeDir, done, total);
        unzipAsset(LIBS_ASSET_PREFIX + abi + ".zip", runtimeDir, done, total);
        try (OutputStream out = new FileOutputStream(stamp)) {
            out.write(bundled.getBytes(StandardCharsets.UTF_8));
        }
    }

    /** The ABI whose native libraries Android installed for this app. */
    private String nativeAbi() throws IOException {
        File libDir = new File(context.getApplicationInfo().nativeLibraryDir);
        for (String abi : Build.SUPPORTED_ABIS) {
            if (assetExists(LIBS_ASSET_PREFIX + abi + ".zip") && new File(libDir, "libnode.so").exists()) return abi;
        }
        throw new IOException("this APK has no REA runtime for " + TextUtils.join(", ", Build.SUPPORTED_ABIS));
    }

    private int countEntries(String asset) throws IOException {
        int count = 0;
        try (ZipInputStream zip = new ZipInputStream(context.getAssets().open(asset))) {
            while (zip.getNextEntry() != null) count++;
        }
        return count;
    }

    private void unzipAsset(String asset, File dest, int[] done, int total) throws IOException {
        String root = dest.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[64 * 1024];
        try (ZipInputStream zip = new ZipInputStream(context.getAssets().open(asset))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                File out = new File(dest, entry.getName());
                if (!out.getCanonicalPath().startsWith(root)) throw new IOException("bad entry " + entry.getName());
                if (entry.isDirectory()) {
                    out.mkdirs();
                } else {
                    out.getParentFile().mkdirs();
                    try (OutputStream file = new FileOutputStream(out)) {
                        int n;
                        while ((n = zip.read(buffer)) > 0) file.write(buffer, 0, n);
                    }
                }
                done[0]++;
                status = "unpacking " + (done[0] * 100 / total) + "%";
            }
        }
    }

    // ---- Launch ----

    private void launch() throws Exception {
        status = "starting";
        String libDir = context.getApplicationInfo().nativeLibraryDir;
        File binDir = new File(context.getFilesDir(), "bin");
        File home = new File(context.getFilesDir(), "home");
        File tmp = new File(context.getCacheDir(), "tmp");
        File uploads = new File(context.getFilesDir(), "files");
        for (File dir : new File[] {binDir, home, tmp, uploads}) dir.mkdirs();
        // REA finds `node` and `ps` on PATH; point them at the installed native-library copies.
        link(new File(libDir, "libnode.so"), new File(binDir, "node"));
        link(new File(libDir, "libps.so"), new File(binDir, "ps"));

        // Another app holds our port: move to a free one (the interface follows via getConfig()).
        if (!isPortFree(port)) savePort(freePort());
        ProcessBuilder builder = new ProcessBuilder(
                new File(libDir, "libnode.so").getPath(),
                new File(runtimeDir, "app/server.mjs").getPath());
        builder.directory(home);
        builder.redirectErrorStream(true);
        Map<String, String> env = builder.environment();
        env.put("HOME", home.getPath());
        env.put("TMPDIR", tmp.getPath());
        env.put("XDG_CACHE_HOME", new File(home, ".cache").getPath());
        env.put("PATH", binDir.getPath() + ":/system/bin");
        env.put("LD_LIBRARY_PATH", new File(runtimeDir, "lib").getPath());
        env.put("HOST", "127.0.0.1");
        env.put("PORT", String.valueOf(port));
        env.put("REA_MOBILE_TOKEN", token);
        env.put("REA_BIN", new File(runtimeDir, "rea/node_modules/rea-agents/scripts/rea.mjs").getPath());
        env.put("REA_MOBILE_UPLOADS", uploads.getPath());

        try (OutputStream log = new FileOutputStream(logFile)) {
            log.write(("[rea-mobile] starting REA on 127.0.0.1:" + port + "\n").getBytes(StandardCharsets.UTF_8));
        }
        final Process started = builder.start();
        process = started;
        Thread pump = new Thread(() -> pumpLog(started), "rea-log");
        pump.setDaemon(true);
        pump.start();

        // The server is ready once it accepts connections.
        long deadline = System.currentTimeMillis() + 120_000;
        while (System.currentTimeMillis() < deadline) {
            if (!isAlive(started)) throw new IOException("REA exited during startup: " + lastLogLine());
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress("127.0.0.1", port), 500);
                status = "running";
                return;
            } catch (IOException notYet) {
                Thread.sleep(300);
            }
        }
        throw new IOException("REA did not start within 2 minutes: " + lastLogLine());
    }

    private void pumpLog(Process running) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(running.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) appendLog(line + "\n");
        } catch (IOException ignored) {
            // process ended
        }
        if (!stopping && running == process) {
            status = "error REA stopped unexpectedly: " + lastLogLine();
        }
    }

    // ---- Helpers ----

    private static void link(File target, File linkFile) throws Exception {
        if (linkFile.exists() || isSymlink(linkFile)) linkFile.delete();
        Os.symlink(target.getPath(), linkFile.getPath());
    }

    private static boolean isSymlink(File file) {
        try {
            return OsConstants.S_ISLNK(Os.lstat(file.getPath()).st_mode);
        } catch (ErrnoException e) {
            return false;
        }
    }

    private void savePort(int value) {
        port = value;
        prefs.edit().putInt("port", value).apply();
    }

    private static boolean isPortFree(int candidate) {
        try (ServerSocket socket = new ServerSocket(candidate, 1, java.net.InetAddress.getByName("127.0.0.1"))) {
            return true;
        } catch (IOException taken) {
            return false;
        }
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) {
            return socket.getLocalPort();
        }
    }

    private static boolean isAlive(Process p) {
        try {
            p.exitValue();
            return false;
        } catch (IllegalThreadStateException running) {
            return true;
        }
    }

    private static String loadToken(SharedPreferences prefs) {
        String saved = prefs.getString("token", null);
        if (saved != null) return saved;
        byte[] bytes = new byte[24];
        new SecureRandom().nextBytes(bytes);
        String token = Base64.encodeToString(bytes, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
        prefs.edit().putString("token", token).apply();
        return token;
    }

    private synchronized void appendLog(String text) {
        try (OutputStream out = new FileOutputStream(logFile, true)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
            // logging is best effort
        }
    }

    /** Last non-empty log line, for error messages. */
    String lastLogLine() {
        try (RandomAccessFile file = new RandomAccessFile(logFile, "r")) {
            long length = file.length();
            int size = (int) Math.min(length, 4096);
            byte[] tail = new byte[size];
            file.seek(length - size);
            file.readFully(tail);
            String[] lines = new String(tail, StandardCharsets.UTF_8).trim().split("\n");
            return lines.length == 0 ? "" : lines[lines.length - 1];
        } catch (IOException e) {
            return "";
        }
    }

    private boolean assetExists(String name) {
        try (InputStream ignored = context.getAssets().open(name)) {
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private String readAsset(String name) throws IOException {
        try (InputStream in = context.getAssets().open(name)) {
            return readAll(in);
        }
    }

    private static String readFile(File file) throws IOException {
        try (InputStream in = new java.io.FileInputStream(file)) {
            return readAll(in);
        }
    }

    private static String readAll(InputStream in) throws IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int n;
        while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
        return out.toString("UTF-8");
    }

    private static void deleteRecursively(File file) {
        // Never follow links out of the runtime folder.
        if (file.isDirectory() && !isSymlink(file)) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursively(child);
        }
        file.delete();
    }
}
