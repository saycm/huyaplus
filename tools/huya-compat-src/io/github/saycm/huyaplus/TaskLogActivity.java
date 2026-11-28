package io.github.saycm.huyaplus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;

public final class TaskLogActivity extends Activity {
    private static final long SYNC_POLL_MS = 250L;
    private static final long SYNC_TIMEOUT_MS = 6000L;
    private final Map<String, Map<String, List<Bundle>>> groups = new LinkedHashMap<>();
    private String selectedType = "";
    private String selectedDate = "";
    private ScrollView scroll;
    private TextView logs;
    private Button typeButton;
    private Button dateButton;
    private LinearLayout syncHint;
    private TextView syncStatus;
    private TextView resultSummary;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable pollSync = this::pollSync;
    private final SimpleDateFormat dayFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.CHINA);
    private final SimpleDateFormat timeFormat = new SimpleDateFormat("HH:mm:ss.SSS", Locale.CHINA);
    private long displayedSync = -1;
    private long syncBaseline;
    private long syncStartedAt;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            selectedType = state.getString("log_type", "");
            selectedDate = state.getString("log_date", "");
        }
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundResource(R.drawable.dashboard_background);
        root.setPadding(dp(18), dp(16), dp(18), dp(16));
        setContentView(root);
        SystemBarInsets.apply(findViewById(android.R.id.content));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView back = text("‹ 返回", 16, R.color.huya_accent);
        back.setTypeface(null, Typeface.BOLD);
        back.setGravity(Gravity.CENTER_VERTICAL);
        back.setMinHeight(dp(48));
        back.setPadding(0, 0, dp(12), 0);
        back.setOnClickListener(view -> finish());
        header.addView(back);

        LinearLayout heading = new LinearLayout(this);
        heading.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("任务日志", 19, R.color.glass_text);
        title.setTypeface(null, Typeface.BOLD);
        heading.addView(title);
        syncStatus = text("等待同步", 12, R.color.glass_secondary);
        syncStatus.setSingleLine(true);
        syncStatus.setEllipsize(TextUtils.TruncateAt.END);
        syncStatus.setPadding(0, dp(2), 0, 0);
        heading.addView(syncStatus);
        header.addView(heading, new LinearLayout.LayoutParams(0, -2, 1));

        Button refresh = action("刷新");
        refresh.setBackgroundResource(R.drawable.accent_button);
        refresh.setTextColor(getColor(R.color.hero_text));
        refresh.setOnClickListener(view -> refreshLogs(false));
        header.addView(refresh);
        Button more = action("⋮");
        more.setContentDescription("日志操作");
        more.setMinWidth(dp(40));
        more.setOnClickListener(view -> showActions());
        header.addView(more);
        root.addView(header);

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackgroundResource(R.drawable.glass_card);
        panel.setPadding(dp(10), dp(10), dp(10), dp(8));
        LinearLayout.LayoutParams panelParams = new LinearLayout.LayoutParams(-1, 0, 1);
        panelParams.topMargin = dp(14);
        root.addView(panel, panelParams);

        LinearLayout filters = new LinearLayout(this);
        typeButton = action("日志类型");
        typeButton.setBackgroundResource(R.drawable.glass_card);
        typeButton.setSingleLine(true);
        typeButton.setEllipsize(TextUtils.TruncateAt.END);
        typeButton.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        typeButton.setOnClickListener(view -> choose("日志类型", new ArrayList<>(groups.keySet()),
                selectedType, value -> {
                    selectedType = value;
                    selectedDate = "";
                    showSelection(true);
                }));
        filters.addView(typeButton, new LinearLayout.LayoutParams(0, -2, 1));
        dateButton = action("日志日期");
        dateButton.setBackgroundResource(R.drawable.glass_card);
        dateButton.setOnClickListener(view -> choose("日志日期",
                new ArrayList<>(groups.get(selectedType).keySet()), selectedDate, value -> {
                    selectedDate = value;
                    showSelection(true);
                }));
        LinearLayout.LayoutParams dateParams = new LinearLayout.LayoutParams(-2, -2);
        dateParams.leftMargin = dp(6);
        filters.addView(dateButton, dateParams);
        panel.addView(filters);
        resultSummary = text("", 12, R.color.glass_secondary);
        resultSummary.setPadding(dp(2), dp(8), dp(2), dp(2));
        panel.addView(resultSummary);

        syncHint = new LinearLayout(this);
        syncHint.setGravity(Gravity.CENTER_VERTICAL);
        syncHint.setPadding(dp(2), 0, 0, 0);
        TextView hint = text("同步超时，当前显示本机记录。", 12, R.color.glass_secondary);
        syncHint.addView(hint, new LinearLayout.LayoutParams(0, -2, 1));
        Intent launchHuya = getPackageManager().getLaunchIntentForPackage("com.duowan.kiwi");
        if (launchHuya != null) {
            Button open = action("打开虎牙");
            open.setOnClickListener(view -> startActivity(launchHuya));
            syncHint.addView(open);
        }
        syncHint.setVisibility(View.GONE);
        panel.addView(syncHint);

        scroll = new ScrollView(this);
        logs = text("", 13, R.color.glass_text);
        logs.setTypeface(Typeface.MONOSPACE);
        logs.setTextIsSelectable(true);
        logs.setPadding(dp(2), dp(10), dp(2), dp(8));
        scroll.addView(logs);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    }

    @Override protected void onResume() {
        super.onResume();
        refreshLogs(true);
    }

    @Override protected void onPause() {
        handler.removeCallbacks(pollSync);
        super.onPause();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("log_type", selectedType);
        state.putString("log_date", selectedDate);
        super.onSaveInstanceState(state);
    }

    private void showActions() {
        String[] actions = groups.isEmpty() ? new String[]{"清空所有日志"}
                : new String[]{"复制当前日志", "清空所有日志"};
        new AlertDialog.Builder(this, android.R.style.Theme_Material_Light_Dialog_Alert)
                .setTitle("日志操作")
                .setItems(actions, (dialog, index) -> {
                    if ("复制当前日志".equals(actions[index])) {
                        getSystemService(ClipboardManager.class).setPrimaryClip(ClipData.newPlainText(
                                "任务日志", selectedType + "." + selectedDate + ".log\n" + logs.getText()));
                    } else {
                        new AlertDialog.Builder(this, android.R.style.Theme_Material_Light_Dialog_Alert)
                                .setMessage("清空所有类型的日志？今日执行记录会保留。")
                                .setNegativeButton("取消", null)
                                .setPositiveButton("清空", (confirm, which) -> {
                                    getContentResolver().call(TaskLogProvider.URI, "clear", null, null);
                                    renderLogs();
                                }).show();
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void choose(String title, List<String> options, String selected, Consumer<String> select) {
        new AlertDialog.Builder(this, android.R.style.Theme_Material_Light_Dialog_Alert)
                .setTitle(title)
                .setSingleChoiceItems(options.toArray(new String[0]), options.indexOf(selected),
                        (dialog, index) -> {
                            select.accept(options.get(index));
                            dialog.dismiss();
                        })
                .setNegativeButton("取消", null)
                .show();
    }

    private void refreshLogs(boolean resumed) {
        long previousSync = displayedSync;
        renderLogs();
        syncHint.setVisibility(View.GONE);
        handler.removeCallbacks(pollSync);
        if (resumed && previousSync >= 0 && displayedSync > previousSync) return;
        syncBaseline = displayedSync;
        syncStatus.setText(syncBaseline == 0 ? "同步中…" : "同步中 · 上次 " + syncTime(syncBaseline));
        syncStartedAt = SystemClock.uptimeMillis();
        sendBroadcast(new Intent(DailyAutomation.SYNC_LOGS).setPackage("com.duowan.kiwi"));
        handler.postDelayed(pollSync, SYNC_POLL_MS);
    }

    private void pollSync() {
        if (lastSync() > syncBaseline) {
            renderLogs();
            return;
        }
        if (SystemClock.uptimeMillis() - syncStartedAt < SYNC_TIMEOUT_MS) {
            handler.postDelayed(pollSync, SYNC_POLL_MS);
            return;
        }
        renderLogs();
        syncHint.setVisibility(View.VISIBLE);
    }

    private long lastSync() {
        Bundle result = getContentResolver().call(TaskLogProvider.URI, "sync_status", null, null);
        return result == null ? 0 : result.getLong("last_sync", 0);
    }

    private String syncTime(long millis) {
        return new SimpleDateFormat("MM-dd HH:mm:ss", Locale.CHINA).format(new Date(millis));
    }

    private void renderLogs() {
        Bundle result = getContentResolver().call(TaskLogProvider.URI, "read", null, null);
        ArrayList<Bundle> entries = result == null ? null : result.getParcelableArrayList("events");
        displayedSync = result == null ? 0 : result.getLong("last_sync", 0);
        syncStatus.setText(displayedSync == 0 ? "尚未同步" : "上次同步 " + syncTime(displayedSync));
        groups.clear();
        if (entries != null) for (Bundle entry : entries) {
            String type = entry.getString("task", "");
            String day = dayFormat.format(new Date(entry.getLong("time")));
            groups.computeIfAbsent(type.isEmpty() ? "其他" : type, key -> new LinkedHashMap<>())
                    .computeIfAbsent(day, key -> new ArrayList<>()).add(entry);
        }
        showSelection(false);
    }

    private void showSelection(boolean resetScroll) {
        boolean hasLogs = !groups.isEmpty();
        typeButton.setEnabled(hasLogs);
        dateButton.setEnabled(hasLogs);
        if (!hasLogs) {
            typeButton.setText("日志类型");
            dateButton.setText("日志日期");
            logs.setText("暂无任务日志");
            resultSummary.setText("当前筛选：暂无日志");
            return;
        }
        if (!groups.containsKey(selectedType)) {
            selectedType = groups.keySet().stream().filter(type -> !"日志同步".equals(type))
                    .findFirst().orElse(groups.keySet().iterator().next());
            selectedDate = "";
            resetScroll = true;
        }
        Map<String, List<Bundle>> days = groups.get(selectedType);
        if (!days.containsKey(selectedDate)) {
            selectedDate = days.keySet().iterator().next();
            resetScroll = true;
        }
        typeButton.setText(selectedType + " ▾");
        dateButton.setText(selectedDate + " ▾");
        List<Bundle> entries = days.get(selectedDate);
        resultSummary.setText("当前筛选：" + selectedType + " · " + selectedDate + "\n" + summarize(entries)
                + "\n仅统计已保留日志，最多显示最近 300 条；同一任务可有多条记录。");
        SpannableStringBuilder text = new SpannableStringBuilder();
        for (int index = entries.size() - 1; index >= 0; index--) {
            Bundle entry = entries.get(index);
            if (text.length() > 0) text.append('\n');
            text.append(timeFormat.format(new Date(entry.getLong("time")))).append("  ");
            String state = entry.getString("state", "");
            if (!state.isEmpty()) {
                int start = text.length();
                text.append('[').append(state).append("] ");
                if (isIssue(state)) {
                    text.setSpan(new ForegroundColorSpan(0xFFAE4028), start, text.length(),
                            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                }
            }
            String target = entry.getString("target", "");
            String detail = entry.getString("detail", "");
            text.append(target);
            if (!target.isEmpty() && !detail.isEmpty()) text.append(" · ");
            text.append(detail);
        }
        logs.setText(text);
        if (resetScroll) scroll.scrollTo(0, 0);
    }

    static String summarize(List<Bundle> entries) {
        int success = 0, failed = 0, uncertain = 0;
        for (Bundle entry : entries) {
            String state = entry.getString("state", "");
            if ("成功".equals(state)) success++;
            else if ("失败".equals(state)) failed++;
            else if ("未确认".equals(state) || "结果未确认".equals(state)
                    || "服务端未确认".equals(state) || "未完成".equals(state)) uncertain++;
        }
        return entries.size() + " 条日志 · 成功 " + success + " · 失败 " + failed
                + " · 未确认/未完成 " + uncertain
                + "\n其他事件 " + (entries.size() - success - failed - uncertain)
                + "（检查、请求、已领取、跳过等）";
    }

    private boolean isIssue(String state) {
        return "失败".equals(state) || "未完成".equals(state) || "结果未确认".equals(state)
                || "服务端未确认".equals(state) || "未确认".equals(state)
                || "未执行".equals(state) || "阻止发送".equals(state)
                || "取消".equals(state) || "停止".equals(state);
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(getColor(color));
        view.setLineSpacing(dp(2), 1.12f);
        return view;
    }

    private Button action(String title) {
        Button view = new Button(this);
        view.setText(title);
        view.setTextSize(13);
        view.setAllCaps(false);
        view.setTextColor(getColor(R.color.huya_accent));
        view.setBackgroundColor(Color.TRANSPARENT);
        view.setStateListAnimator(null);
        view.setMinWidth(0);
        view.setMinimumWidth(0);
        view.setMinHeight(dp(40));
        view.setMinimumHeight(dp(40));
        view.setPadding(dp(8), 0, dp(8), 0);
        return view;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
