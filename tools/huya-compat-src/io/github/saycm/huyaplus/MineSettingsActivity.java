package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class MineSettingsActivity extends Activity {
    static final String SHOW_NAVIGATION = "show_navigation_settings";
    static final String SHOW_LIVE_MENU = "show_live_menu_settings";
    private static final int[] GROUP_LABELS = {
            R.string.mine_shortcuts, R.string.mine_game_services, R.string.mine_more_services
    };
    private final Map<String, Switch> switches = new LinkedHashMap<>();
    private final Map<String, List<String>> activityKeys = new LinkedHashMap<>();
    private SharedPreferences liveMenuVisibility;
    private LinearLayout liveActivities;
    private TextView status;
    private boolean syncing;
    private boolean liveMenu;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_task_settings);
        SystemBarInsets.apply(findViewById(android.R.id.content));
        boolean navigation = getIntent().getBooleanExtra(SHOW_NAVIGATION, false);
        liveMenu = getIntent().getBooleanExtra(SHOW_LIVE_MENU, false);
        int title = liveMenu ? R.string.live_menu_settings_title
                : navigation ? R.string.navigation_settings_title : R.string.mine_settings_title;
        ((TextView) findViewById(R.id.task_settings_title)).setText(title);
        findViewById(R.id.task_settings_back).setOnClickListener(view -> finish());
        LinearLayout content = findViewById(R.id.task_settings_content);
        status = new TextView(this);
        status.setTextColor(getColor(R.color.glass_secondary));
        status.setTextSize(13);
        content.addView(status);

        if (liveMenu) {
            liveMenuVisibility = getSharedPreferences(LiveMenu.VISIBILITY, MODE_PRIVATE);
            addHeading(content, R.string.live_menu_activities);
            TextView activityHint = new TextView(this);
            activityHint.setTextColor(getColor(R.color.glass_secondary));
            activityHint.setTextSize(13);
            activityHint.setText(R.string.live_menu_activity_hint);
            content.addView(activityHint);
            liveActivities = new LinearLayout(this);
            liveActivities.setOrientation(LinearLayout.VERTICAL);
            content.addView(liveActivities);
            addHeading(content, R.string.live_menu_tools);
            for (LiveMenu.Tool entry : LiveMenu.Tool.values()) {
                addSwitch(content, entry.key, entry.title);
            }
        } else if (navigation) {
            for (GlassSettings.NavigationEntry entry : GlassSettings.NavigationEntry.values()) {
                addSwitch(content, entry.key, entry.title);
            }
        } else {
            int group = -1;
            for (GlassSettings.MineEntry entry : GlassSettings.MineEntry.values()) {
                if (entry.group != group) {
                    group = entry.group;
                    addHeading(content, GROUP_LABELS[group]);
                }
                addSwitch(content, entry.key, entry.title);
            }
        }
        sync(liveMenu ? null : GlassSettingsBridge.get());
    }

    private void addHeading(LinearLayout content, int label) {
        TextView heading = new TextView(this);
        heading.setText(label);
        heading.setTextColor(getColor(R.color.glass_secondary));
        heading.setTextSize(13);
        heading.setPadding(0, dp(16), 0, dp(4));
        content.addView(heading);
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
        if (liveActivities != null) loadLiveActivities();
        SharedPreferences remote = GlassSettingsBridge.get();
        if (!liveMenu || remote == null) sync(remote);
        GlassSettingsBridge.connect(connected -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) sync(GlassSettingsBridge.get());
        }));
    }

    private void loadLiveActivities() {
        Map<String, ?> catalog = getSharedPreferences(LiveMenu.CATALOG, MODE_PRIVATE).getAll();
        for (String key : activityKeys.keySet()) switches.remove(key);
        activityKeys.clear();
        liveActivities.removeAllViews();
        for (Map.Entry<String, List<String>> group : LiveMenu.activityGroups(catalog).entrySet()) {
            String title = group.getKey();
            String key = LiveMenu.activityTitleKey(title);
            activityKeys.put(key, group.getValue());
            addSwitch(liveActivities, key, title);
        }
    }

    private void migrateActivityVisibility(SharedPreferences remote) {
        SharedPreferences.Editor migration = null;
        for (Map.Entry<String, List<String>> group : activityKeys.entrySet()) {
            if (remote.contains(group.getKey()) || liveMenuVisibility.contains(group.getKey())) continue;
            for (String oldKey : group.getValue()) {
                if (remote.getBoolean(oldKey, false)) {
                    if (migration == null) migration = remote.edit();
                    migration.putBoolean(group.getKey(), true);
                    break;
                }
            }
        }
        if (migration != null) {
            try {
                migration.commit();
            } catch (RuntimeException ignored) {
                // The connection listener refreshes the switches when LSPosed reconnects.
            }
        }
    }

    private void save(String key, boolean hidden) {
        SharedPreferences remote = GlassSettingsBridge.get();
        if (liveMenu) {
            if (liveMenuVisibility.edit().putBoolean(key, hidden).commit()) {
                sync(remote);
            } else {
                sync(null);
                Toast.makeText(this, R.string.mine_settings_save_failed, Toast.LENGTH_SHORT).show();
            }
            return;
        }
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
            boolean published = true;
            if (remote != null && liveMenu) {
                try {
                    migrateActivityVisibility(remote);
                    published = LiveMenu.syncVisibility(liveMenuVisibility, remote);
                } catch (RuntimeException failure) {
                    published = false;
                    Log.w("FuckAD", "Live-room menu preferences could not sync", failure);
                }
            }
            status.setText(!published ? R.string.live_menu_sync_pending
                    : remote == null ? R.string.mine_settings_disconnected
                    : liveMenu ? R.string.live_menu_settings_hint : R.string.mine_settings_hint);
            for (Map.Entry<String, Switch> item : switches.entrySet()) {
                Switch toggle = item.getValue();
                String key = item.getKey();
                if (liveMenu && liveMenuVisibility.contains(key)) {
                    toggle.setChecked(liveMenuVisibility.getBoolean(key, false));
                } else if (remote != null) {
                    toggle.setChecked(remote.getBoolean(key, false));
                }
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
