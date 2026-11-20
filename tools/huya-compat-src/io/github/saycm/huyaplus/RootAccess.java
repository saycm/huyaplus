package io.github.saycm.huyaplus;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

final class RootAccess {
    private RootAccess() {}

    static boolean wasAuthorized(Context context) {
        return settings(context).getBoolean(GlassSettings.ROOT_GRANTED, false);
    }

    static boolean request(Context context) {
        boolean granted = checkUid(30_000);
        return settings(context).edit().putBoolean(GlassSettings.ROOT_GRANTED, granted).commit()
                && granted;
    }

    static boolean verify(Context context) {
        if (!wasAuthorized(context)) return false;
        if (checkUid(1_500)) return true;
        settings(context).edit().remove(GlassSettings.ROOT_GRANTED).apply();
        return false;
    }

    private static SharedPreferences settings(Context context) {
        return context.getSharedPreferences("root_access", Context.MODE_PRIVATE);
    }

    private static boolean checkUid(long timeoutMillis) {
        java.lang.Process process = null;
        try {
            process = new ProcessBuilder("su", "-c", "exec /system/bin/id -u")
                    .redirectErrorStream(true).start();
            if (!process.waitFor(timeoutMillis, TimeUnit.MILLISECONDS) || process.exitValue() != 0) {
                return false;
            }
            try (BufferedReader output = new BufferedReader(new InputStreamReader(
                    process.getInputStream(), StandardCharsets.UTF_8))) {
                return "0".equals(output.readLine());
            }
        } catch (IOException | SecurityException failure) {
            return false;
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            return false;
        } finally {
            if (process != null && process.isAlive()) process.destroyForcibly();
        }
    }
}
