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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_glass_dashboard);
        SystemBarInsets.apply(findViewById(android.R.id.content));

        boolean installed = packageInstalled("com.duowan.kiwi");
        TextView appStatus = (TextView) findViewById(R.id.app_status);
        appStatus.setText(installed ? R.string.app_installed : R.string.app_missing);
        Button details = (Button) findViewById(R.id.action_app);
        details.setText(R.string.action_detail);
        details.setOnClickListener(view ->
                startActivity(new Intent(this, AppDetailActivity.class)));

        bindLink(R.id.community_channel_row, R.string.channel_url);
        bindLink(R.id.community_discussion_row, R.string.discussion_url);

    }

    @Override protected void onResume() {
        super.onResume();
        if (handler != null) handler.removeCallbacksAndMessages(null);
        checkFrameworkState();
    }

    private void checkFrameworkState() {
        frameworkLoaded = false;
        setFrameworkStatus(false, false);
        GlassSettingsBridge.connect(remote -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
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

    private boolean packageInstalled(String packageName) {
        try {
            getPackageManager().getApplicationInfo(packageName, 0);
            return true;
        } catch (Throwable ignored) {
            return false;
        }
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
