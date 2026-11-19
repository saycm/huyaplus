package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.LinkedHashMap;
import java.util.Map;

public final class MineSettingsActivity extends Activity {
    static final String SHOW_NAVIGATION = "show_navigation_settings";
    private static final int[] GROUP_LABELS = {
            R.string.mine_shortcuts, R.string.mine_game_services, R.string.mine_more_services
    };
    private final Map<String, Switch> switches = new LinkedHashMap<>();
    private TextView status;
    private boolean syncing;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_task_settings);
        SystemBarInsets.apply(findViewById(android.R.id.content));
        boolean navigation = getIntent().getBooleanExtra(SHOW_NAVIGATION, false);
        ((TextView) findViewById(R.id.task_settings_title)).setText(
                navigation ? R.string.navigation_settings_title : R.string.mine_settings_title);
        findViewById(R.id.task_settings_back).setOnClickListener(view -> finish());
        LinearLayout content = findViewById(R.id.task_settings_content);
        status = new TextView(this);
        status.setTextColor(getColor(R.color.glass_secondary));
        status.setTextSize(13);
        content.addView(status);

        if (navigation) {
            for (GlassSettings.NavigationEntry entry : GlassSettings.NavigationEntry.values()) {
                addSwitch(content, entry.key, entry.title);
            }
        } else {
            int group = -1;
            for (GlassSettings.MineEntry entry : GlassSettings.MineEntry.values()) {
                if (entry.group != group) {
                    group = entry.group;
                    TextView heading = new TextView(this);
                    heading.setText(GROUP_LABELS[group]);
                    heading.setTextColor(getColor(R.color.glass_secondary));
                    heading.setTextSize(13);
                    heading.setPadding(0, dp(16), 0, dp(4));
                    content.addView(heading);
                }
                addSwitch(content, entry.key, entry.title);
            }
        }
        sync(GlassSettingsBridge.get());
    }

    private void addSwitch(LinearLayout content, String key, String title) {
        Switch toggle = new Switch(this);
        toggle.setText(title);
        toggle.setTextColor(getColor(R.color.glass_text));
        toggle.setTextSize(15);
        toggle.setMinHeight(dp(48));
        toggle.setOnCheckedChangeListener((button, checked) -> {
            if (!syncing) save(key, checked);
        });
        content.addView(toggle);
        switches.put(key, toggle);
    }

    @Override protected void onResume() {
        super.onResume();
        sync(GlassSettingsBridge.get());
        GlassSettingsBridge.connect(remote -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) sync(GlassSettingsBridge.get());
        }));
    }

    private void save(String key, boolean hidden) {
        SharedPreferences remote = GlassSettingsBridge.get();
        if (remote != null) {
            try {
                if (remote.edit().putBoolean(key, hidden).commit()) return;
            } catch (RuntimeException ignored) {
                // The framework can disconnect while a preference is being saved.
            }
        }
        sync(GlassSettingsBridge.get());
        Toast.makeText(this, R.string.mine_settings_save_failed, Toast.LENGTH_SHORT).show();
    }

    private void sync(SharedPreferences remote) {
        syncing = true;
        try {
            status.setText(remote == null ? R.string.mine_settings_disconnected : R.string.mine_settings_hint);
            for (Map.Entry<String, Switch> item : switches.entrySet()) {
                Switch toggle = item.getValue();
                if (remote != null) toggle.setChecked(remote.getBoolean(item.getKey(), false));
                toggle.setEnabled(remote != null);
            }
        } finally {
            syncing = false;
        }
    }

    private int dp(int size) {
        return Math.round(size * getResources().getDisplayMetrics().density);
    }
}
