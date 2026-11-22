package io.github.saycm.huyaplus;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import io.github.libxposed.service.XposedService;
import io.github.libxposed.service.XposedServiceHelper;

public final class GlassSettingsBridge {
    private static final String TAG = "FuckAD";
    private static volatile SharedPreferences connected;
    private static volatile XposedService boundService;
    private static volatile Connected callback;
    private static boolean registered;

    public interface Connected {
        void onConnected(SharedPreferences prefs);
    }

    private GlassSettingsBridge() {
    }

    public static synchronized void connect(Connected current) {
        callback = current;
        SharedPreferences prefs = connected;
        if (prefs != null) {
            if (current != null) {
                current.onConnected(prefs);
            }
            return;
        }
        if (registered) {
            return;
        }
        registered = true;
        XposedServiceHelper.registerListener(new XposedServiceHelper.OnServiceListener() {
            @Override
            public void onServiceBind(XposedService service) {
                try {
                    boundService = service;
                    connected = service.getRemotePreferences(GlassSettings.PREFS);
                    Connected listener = callback;
                    if (listener != null) {
                        listener.onConnected(connected);
                    }
                } catch (RuntimeException failure) {
                    Log.w(TAG, "remote preferences unavailable", failure);
                }
            }

            @Override
            public void onServiceDied(XposedService service) {
                if (boundService != service) return;
                boundService = null;
                connected = null;
                Connected listener = callback;
                if (listener != null) listener.onConnected(null);
            }
        });
    }

    public static SharedPreferences get() {
        return connected;
    }

    static void syncRootGrant(Context context) {
        XposedService service = boundService;
        if (service == null) return;
        try {
            if (!RootAccess.syncTo(context, service.getRemotePreferences(GlassSettings.ROOT_PREFS))) {
                Log.w(TAG, "Root authorization was not saved to LSPosed");
            }
        } catch (RuntimeException | LinkageError failure) {
            Log.w(TAG, "Root authorization could not sync to LSPosed", failure);
        }
    }
}
