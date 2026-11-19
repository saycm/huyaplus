package io.github.saycm.huyaplus;

import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class TaskSettingsActivity extends Activity {
    static final String GROUP = "task_group";
    static final String DICE = "dice";
    static final String DAILY = "daily";
    private AutomationPanel panel;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        String group = getIntent().getStringExtra(GROUP);
        if (!DICE.equals(group) && !DAILY.equals(group)) { finish(); return; }
        setContentView(R.layout.activity_task_settings);
        SystemBarInsets.apply(findViewById(android.R.id.content));
        ((TextView) findViewById(R.id.task_settings_title)).setText(
                DICE.equals(group) ? "骰子任务" : "每日赚金币");
        findViewById(R.id.task_settings_back).setOnClickListener(view -> finish());
        panel = new AutomationPanel(this,
                (LinearLayout) findViewById(R.id.task_settings_content), group);
    }

    @Override protected void onResume() {
        super.onResume();
        if (panel == null) return;
        GlassSettingsBridge.connect(remote -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) panel.onRemoteConnected(remote);
        }));
    }

    @Override protected void onDestroy() {
        if (panel != null) panel.destroy();
        super.onDestroy();
    }
}
