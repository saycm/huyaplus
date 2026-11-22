package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

public final class GlassDashboardActivity extends Activity {
    private static final long DETECT_TIMEOUT_MS = 4000L;
    private Handler handler;
    private boolean frameworkLoaded;
    private boolean requestingRoot;
    private boolean supportedVersion;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_glass_dashboard);
        SystemBarInsets.apply(findViewById(android.R.id.content));

        Button details = (Button) findViewById(R.id.action_app);
        details.setText(R.string.action_detail);
        details.setOnClickListener(view ->
                startActivity(new Intent(this, AppDetailActivity.class)));
        findViewById(R.id.action_authorize_root).setOnClickListener(view -> requestRoot());

        bindLink(R.id.community_channel_row, R.string.channel_url);
        bindLink(R.id.community_discussion_row, R.string.discussion_url);

    }

    @Override protected void onResume() {
        super.onResume();
        if (handler != null) handler.removeCallbacksAndMessages(null);
        checkFrameworkState();
        String version = HuyaVersion.installed(this);
        supportedVersion = HuyaVersion.supports(version);
        TextView appStatus = findViewById(R.id.app_status);
        appStatus.setText(versionStatus(version));
        appStatus.setTextColor(getColor(supportedVersion ? R.color.success_green : R.color.glass_text));
        showRootStatus(false);
    }

    private void showRootStatus(boolean failed) {
        TextView status = findViewById(R.id.root_status);
        boolean authorized = RootAccess.verify(this);
        status.setText(!supportedVersion ? getString(R.string.root_version_required, HuyaVersion.SUPPORTED)
                : getString(requestingRoot ? R.string.root_checking
                : authorized ? R.string.root_configured
                : failed ? R.string.root_failed : R.string.root_required));
        Button action = findViewById(R.id.action_authorize_root);
        action.setText(requestingRoot ? R.string.root_waiting
                : authorized ? R.string.root_verify_again : R.string.root_authorize);
        action.setEnabled(supportedVersion && !requestingRoot);
        action.setAlpha(action.isEnabled() ? 1f : 0.5f);
    }

    private void requestRoot() {
        if (requestingRoot || !supportedVersion) return;
        requestingRoot = true;
        showRootStatus(false);
        new Thread(() -> {
            boolean granted = RootAccess.request(getApplicationContext());
            GlassSettingsBridge.syncRootGrant(getApplicationContext());
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                requestingRoot = false;
                showRootStatus(!granted);
            });
        }, "HuyaPlus-Root").start();
    }

    private void checkFrameworkState() {
        frameworkLoaded = false;
        setFrameworkStatus(false, false);
        GlassSettingsBridge.connect(remote -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            if (remote != null) GlassSettingsBridge.syncRootGrant(getApplicationContext());
            frameworkLoaded = remote != null;
            setFrameworkStatus(remote != null, remote == null);
        }));
        handler = new Handler(Looper.getMainLooper());
        handler.postDelayed(() -> runOnUiThread(
                () -> setFrameworkStatus(false, true)), DETECT_TIMEOUT_MS);
    }

    private void setFrameworkStatus(boolean loaded, boolean timedOut) {
        if (loaded) {
            frameworkLoaded = true;
        }
        if (timedOut && frameworkLoaded) {
            return;
        }
        TextView primary = (TextView) findViewById(R.id.status_primary);
        TextView secondary = (TextView) findViewById(R.id.status_secondary);
        View dot = findViewById(R.id.status_dot);
        if (loaded) {
            primary.setText(R.string.status_ok);
            primary.setTextColor(getColor(R.color.success_green));
            secondary.setText(R.string.status_loaded);
            dot.setBackgroundResource(R.drawable.status_dot);
        } else if (timedOut) {
            primary.setText(R.string.status_not_loaded);
            primary.setTextColor(getColor(R.color.warning_amber));
            secondary.setText(R.string.status_not_loaded_hint);
            dot.setBackgroundResource(R.drawable.status_dot_gray);
        } else {
            primary.setText(R.string.status_checking);
            primary.setTextColor(getColor(R.color.glass_text));
            secondary.setText(R.string.status_checking);
            dot.setBackgroundResource(R.drawable.status_dot);
        }
    }

    @Override
    protected void onDestroy() {
        if (handler != null) {
            handler.removeCallbacksAndMessages(null);
        }
        super.onDestroy();
    }

    private String versionStatus(String version) {
        if (version == null) return getString(R.string.app_missing);
        if (supportedVersion) return getString(R.string.app_supported_version, version);
        if (version.isEmpty()) return getString(R.string.app_unknown_version);
        return getString(R.string.app_unsupported_version, version);
    }

    private void bindLink(int id, int url) {
        View row = findViewById(id);
        row.setOnClickListener(view -> {
            Intent intent = new Intent(Intent.ACTION_VIEW,
                    Uri.parse(getString(url)));
            startActivity(intent);
        });
    }
}
