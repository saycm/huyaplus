package io.github.saycm.huyaplus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.HashMap;
import java.util.Map;

public final class AppDetailActivity extends Activity {
    private static final int[] QUALITY_BITRATES = {
            -1, 500, 2000, LiveQuality.BLUE_RAY
    };
    private static final int[] QUALITY_LABELS = {
            R.string.quality_follow,
            R.string.quality_smooth,
            R.string.quality_super,
            R.string.quality_bluray,
    };

    private SharedPreferences prefs;
    private AutomationPanel automation;
    private Button qualityButton;
    private TextView hookStatus;
    private boolean serviceConnected;
    private final Map<String, Boolean> pending = new HashMap<>();
    private final Map<String, Integer> pendingIntegers = new HashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (HuyaVersion.PACKAGE_NAME.equals(getCallingPackage())) {
            TaskLogProvider.saveLiveMenuCatalog(this, getIntent().getBundleExtra(LiveMenu.CATALOG));
        }
        setContentView(R.layout.activity_app_detail);
        SystemBarInsets.apply(findViewById(android.R.id.content));
        hookStatus = (TextView) findViewById(R.id.hook_status_detail);

        findViewById(R.id.detail_back).setOnClickListener(view -> finish());
        findViewById(R.id.action_mine_settings).setOnClickListener(view ->
                startActivity(new Intent(this, MineSettingsActivity.class)));
        findViewById(R.id.action_navigation_settings).setOnClickListener(view ->
                startActivity(new Intent(this, MineSettingsActivity.class)
                        .putExtra(MineSettingsActivity.SHOW_NAVIGATION, true)));
        findViewById(R.id.action_live_menu_settings).setOnClickListener(view ->
                startActivity(new Intent(this, MineSettingsActivity.class)
                        .putExtra(MineSettingsActivity.SHOW_LIVE_MENU, true)));
        automation = new AutomationPanel(this, (LinearLayout) findViewById(R.id.automation_settings));

        String version = HuyaVersion.installed(this);
        boolean installed = version != null;
        TextView appStatus = (TextView) findViewById(R.id.app_status);
        Button openApp = (Button) findViewById(R.id.action_open_app);
        if (installed) {
            boolean supported = HuyaVersion.supports(version);
            appStatus.setText(version.isEmpty() ? getString(R.string.app_unknown_version)
                    : getString(supported ? R.string.app_supported_version
                    : R.string.app_unsupported_version, version));
            appStatus.setTextColor(getColor(supported ? R.color.success_green : R.color.glass_text));
            openApp.setText(R.string.action_open);
            openApp.setOnClickListener(view -> startActivity(launcherIntent()));
        } else {
            appStatus.setText(R.string.app_missing);
            openApp.setText(R.string.app_missing);
            openApp.setEnabled(false);
        }

        Button copy = (Button) findViewById(R.id.copy_diagnostics_detail);
        copy.setOnClickListener(view -> copyDiagnostics(installed));

        prefs = getSharedPreferences(GlassSettings.PREFS, MODE_PRIVATE);
        qualityButton = (Button) findViewById(R.id.action_default_quality);
        qualityButton.setOnClickListener(view -> showQualityDialog());
        updateQualityButton();
        bindSwitch(R.id.switch_ads_value, GlassSettings.KEY_ADS);
        bindSwitch(R.id.switch_recommend_video_value, GlassSettings.KEY_RECOMMEND_VIDEO);
        bindSwitch(R.id.switch_rewards_value, GlassSettings.KEY_REWARDS);
        bindSwitch(R.id.switch_vip_ads_value, GlassSettings.KEY_VIP_ADS);
        bindSwitch(R.id.switch_vip_4k_value, GlassSettings.KEY_VIP_4K);
    }

    @Override protected void onResume() {
        super.onResume();
        updateHookStatus();
        GlassSettingsBridge.connect(remote -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) onRemoteConnected(remote);
        }));
    }

    private void updateHookStatus() {
        try {
            Bundle status = getContentResolver().call(TaskLogProvider.URI, "read_hook_status", null, null);
            hookStatus.setText(HookStatus.describe(status));
        } catch (RuntimeException unavailable) {
            hookStatus.setText("暂时无法读取加载状态；当前功能注册情况未确认。");
        }
    }

    @Override protected void onDestroy() {
        if (automation != null) automation.destroy();
        super.onDestroy();
    }

    private Intent launcherIntent() {
        Intent intent = getPackageManager().getLaunchIntentForPackage("com.duowan.kiwi");
        if (intent != null) {
            return intent;
        }
        intent = new Intent(Intent.ACTION_MAIN);
        intent.setClassName(
                "com.duowan.kiwi", "com.duowan.kiwi.simpleactivity.SplashActivity");
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return intent;
    }

    private void bindSwitch(int id, String key) {
        Switch toggle = (Switch) findViewById(id);
        toggle.setChecked(prefs.getBoolean(key, GlassSettings.defaultEnabled(key)));
        toggle.setOnCheckedChangeListener((button, checked) -> {
            prefs.edit().putBoolean(key, checked).apply();
            if (!serviceConnected) {
                pending.put(key, checked);
            }
        });
    }

    private void onRemoteConnected(SharedPreferences remote) {
        automation.onRemoteConnected(remote);
        if (remote == null) {
            serviceConnected = false;
            prefs = getSharedPreferences(GlassSettings.PREFS, MODE_PRIVATE);
            return;
        }
        prefs = remote;
        serviceConnected = true;
        for (Map.Entry<String, Boolean> entry : pending.entrySet()) {
            remote.edit().putBoolean(entry.getKey(), entry.getValue()).apply();
        }
        pending.clear();
        for (Map.Entry<String, Integer> entry : pendingIntegers.entrySet()) {
            remote.edit().putInt(entry.getKey(), entry.getValue()).apply();
        }
        pendingIntegers.clear();
        syncSwitch(R.id.switch_ads_value, GlassSettings.KEY_ADS);
        syncSwitch(R.id.switch_recommend_video_value, GlassSettings.KEY_RECOMMEND_VIDEO);
        syncSwitch(R.id.switch_rewards_value, GlassSettings.KEY_REWARDS);
        syncSwitch(R.id.switch_vip_ads_value, GlassSettings.KEY_VIP_ADS);
        syncSwitch(R.id.switch_vip_4k_value, GlassSettings.KEY_VIP_4K);
        updateQualityButton();
    }

    private void syncSwitch(int id, String key) {
        Switch toggle = (Switch) findViewById(id);
        toggle.setChecked(prefs.getBoolean(key, GlassSettings.defaultEnabled(key)));
    }

    private void showQualityDialog() {
        String[] labels = new String[QUALITY_LABELS.length];
        for (int index = 0; index < QUALITY_LABELS.length; index++) {
            labels[index] = getString(QUALITY_LABELS[index]);
        }
        int selected = qualityIndex(prefs.getInt(GlassSettings.KEY_LIVE_QUALITY, -1));
        new AlertDialog.Builder(this)
                .setTitle(R.string.default_quality_picker)
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    int bitrate = QUALITY_BITRATES[which];
                    prefs.edit().putInt(GlassSettings.KEY_LIVE_QUALITY, bitrate).apply();
                    if (!serviceConnected) {
                        pendingIntegers.put(GlassSettings.KEY_LIVE_QUALITY, bitrate);
                    }
                    updateQualityButton();
                    dialog.dismiss();
                })
                .setNegativeButton(android.R.string.cancel, null)
                .show();
    }

    private void updateQualityButton() {
        int index = qualityIndex(prefs.getInt(GlassSettings.KEY_LIVE_QUALITY, -1));
        qualityButton.setText(getString(
                R.string.quality_value_format, getString(QUALITY_LABELS[index])));
    }

    private static int qualityIndex(int bitrate) {
        if (bitrate == 0) {
            bitrate = LiveQuality.BLUE_RAY;
        }
        for (int index = 0; index < QUALITY_BITRATES.length; index++) {
            if (QUALITY_BITRATES[index] == bitrate) {
                return index;
            }
        }
        return 0;
    }

    private void copyDiagnostics(boolean installed) {
        int qualityIndex = qualityIndex(
                prefs.getInt(GlassSettings.KEY_LIVE_QUALITY, -1));
        String text = "虎牙直播 · com.duowan.kiwi\n"
                + (installed ? getString(R.string.app_installed)
                             : getString(R.string.app_missing)) + "\n"
                + "ads=" + switchValue(R.id.switch_ads_value) + "\n"
                + "live=" + value(GlassSettings.KEY_LIVE_CARDS) + "\n"
                + "landscapeMark=" + value(GlassSettings.KEY_LIVE_LANDSCAPE_MARK) + "\n"
                + "landscapeSidebar=" + value(GlassSettings.KEY_LIVE_LANDSCAPE_SIDEBAR) + "\n"
                + "cart=" + value(GlassSettings.KEY_LIVE_CART) + "\n"
                + "redPacket=" + value(GlassSettings.KEY_LIVE_RED_PACKET) + "\n"
                + "weekStar=" + value(GlassSettings.KEY_LIVE_WEEK_STAR) + "\n"
                + "rewards=" + switchValue(R.id.switch_rewards_value) + "\n"
                + "vipAds=" + switchValue(R.id.switch_vip_ads_value) + "\n"
                + "vip4k=" + switchValue(R.id.switch_vip_4k_value) + "\n"
                + "quality=" + getString(QUALITY_LABELS[qualityIndex])
                + "\n\n" + hookStatus.getText();
        ClipboardManager clipboard =
                (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText(
                    getString(R.string.app_name), text));
        }
        Toast.makeText(this, R.string.copied_diagnostics, Toast.LENGTH_SHORT).show();
    }

    private boolean switchValue(int id) {
        return ((Switch) findViewById(id)).isChecked();
    }

    private boolean value(String key) {
        return prefs.getBoolean(key, GlassSettings.defaultEnabled(key));
    }
}
