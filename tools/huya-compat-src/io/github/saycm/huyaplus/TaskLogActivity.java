package io.github.saycm.huyaplus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.Locale;

public final class TaskLogActivity extends Activity {
    private static final long SYNC_POLL_MS = 250L;
    private static final long SYNC_TIMEOUT_MS = 6000L;
    private LinearLayout logs;
    private TextView all;
    private TextView issues;
    private boolean onlyIssues;
    private TextView syncStatus;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable pollSync = this::pollSync;
    private long syncBaseline;
    private long syncStartedAt;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(245, 246, 248));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(root);
        setContentView(scroll);
        SystemBarInsets.apply(findViewById(android.R.id.content));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(18), dp(10), dp(12), dp(10));
        header.setBackgroundColor(Color.WHITE);
        TextView back = text("‹", 28, R.color.huya_accent);
        back.setGravity(Gravity.CENTER_VERTICAL);
        back.setMinWidth(dp(38));
        back.setMinHeight(dp(48));
        back.setOnClickListener(view -> finish());
        header.addView(back);

        LinearLayout heading = new LinearLayout(this);
        heading.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("任务日志", 21, R.color.glass_text);
        title.setTypeface(null, Typeface.BOLD);
        heading.addView(title);
        syncStatus = text("等待同步", 12, R.color.glass_secondary);
        syncStatus.setPadding(0, dp(2), 0, 0);
        heading.addView(syncStatus);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(0, -2, 1);
        headingParams.leftMargin = dp(4);
        header.addView(heading, headingParams);

        Button refresh = action("刷新");
        refresh.setOnClickListener(view -> refreshLogs());
        header.addView(refresh);
        Button clear = action("清空");
        clear.setOnClickListener(view -> new AlertDialog.Builder(this,
                android.R.style.Theme_Material_Light_Dialog_Alert)
                .setMessage("清空日志不会重置今日执行记录，也不会重复打卡或送礼。")
                .setNegativeButton("取消", null)
                .setPositiveButton("清空", (dialog, which) -> {
                    getContentResolver().call(TaskLogProvider.URI, "clear", null, null);
                    renderLogs();
                }).show());
        header.addView(clear);
        root.addView(header);

        LinearLayout filters = new LinearLayout(this);
        filters.setGravity(Gravity.CENTER_VERTICAL);
        filters.setPadding(dp(18), dp(10), dp(18), dp(10));
        all = filter("全部", true);
        issues = filter("异常与跳过", false);
        all.setOnClickListener(view -> { onlyIssues = false; renderLogs(); });
        issues.setOnClickListener(view -> { onlyIssues = true; renderLogs(); });
        filters.addView(all);
        LinearLayout.LayoutParams issueParams = new LinearLayout.LayoutParams(-2, dp(34));
        issueParams.leftMargin = dp(8);
        filters.addView(issues, issueParams);
        filters.addView(new View(this), new LinearLayout.LayoutParams(0, 1, 1));
        TextView explain = text("仅保存在本机", 12, R.color.glass_secondary);
        filters.addView(explain);
        root.addView(filters);

        logs = new LinearLayout(this);
        logs.setOrientation(LinearLayout.VERTICAL);
        logs.setBackground(rounded(Color.WHITE, 14));
        logs.setClipToOutline(true);
        LinearLayout.LayoutParams listParams = new LinearLayout.LayoutParams(-1, -2);
        listParams.leftMargin = dp(16);
        listParams.rightMargin = dp(16);
        root.addView(logs, listParams);

        TextView footnote = text("保留最近 500 条，页面最多显示 300 条", 12, R.color.glass_secondary);
        footnote.setGravity(Gravity.CENTER);
        footnote.setPadding(dp(16), dp(16), dp(16), dp(24));
        root.addView(footnote);
        refreshLogs();
    }

    private void refreshLogs() {
        syncBaseline = lastSync();
        syncStartedAt = SystemClock.uptimeMillis();
        sendBroadcast(new Intent(DailyAutomation.SYNC_LOGS).setPackage("com.duowan.kiwi"));
        renderLogs();
        handler.removeCallbacks(pollSync);
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
        syncStatus.setText("尚未完成同步，请确认虎牙正在运行；未同步的任务记录仍保留在本机。");
    }

    private long lastSync() {
        Bundle result = getContentResolver().call(TaskLogProvider.URI, "read", null, null);
        return result == null ? 0 : result.getLong("last_sync", 0);
    }

    @Override protected void onDestroy() {
        handler.removeCallbacks(pollSync);
        super.onDestroy();
    }

    private void renderLogs() {
        Bundle result = getContentResolver().call(TaskLogProvider.URI, "read", null, null);
        ArrayList<Bundle> entries = result == null ? null : result.getParcelableArrayList("events");
        logs.removeAllViews();
        styleFilter(all, !onlyIssues);
        styleFilter(issues, onlyIssues);
        SimpleDateFormat time = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.CHINA);
        long synced = result == null ? 0 : result.getLong("last_sync", 0);
        syncStatus.setText(synced == 0 ? "等待虎牙同步"
                : "上次同步 " + time.format(new Date(synced)));
        int visible = 0;
        if (entries != null) for (Bundle entry : entries) {
            String state = entry.getString("state", "");
            boolean issue = isIssue(state);
            if (onlyIssues && !issue) continue;
            if (visible > 0) logs.addView(divider());
            visible++;
            logs.addView(logRow(entry, state, issue, time));
        }
        if (visible == 0) logs.addView(emptyRow());
    }

    private LinearLayout logRow(Bundle entry, String state, boolean issue, SimpleDateFormat time) {
        LinearLayout item = new LinearLayout(this);
        item.setOrientation(LinearLayout.VERTICAL);
        item.setPadding(dp(16), dp(14), dp(16), dp(14));

        LinearLayout heading = new LinearLayout(this);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        TextView task = text(entry.getString("task", ""), 15, R.color.glass_text);
        task.setTypeface(null, Typeface.BOLD);
        heading.addView(task, new LinearLayout.LayoutParams(0, -2, 1));
        int color = ("成功".equals(state) || "已打卡".equals(state))
                ? R.color.success_green : issue ? R.color.warning_amber : R.color.huya_accent;
        TextView badge = text(state, 12, color);
        badge.setTypeface(null, Typeface.BOLD);
        heading.addView(badge);
        item.addView(heading);

        String target = entry.getString("target", "");
        String meta = time.format(new Date(entry.getLong("time")))
                + (target.isEmpty() ? "" : " · " + target);
        TextView stamp = text(meta, 12, R.color.glass_secondary);
        stamp.setPadding(0, dp(4), 0, dp(6));
        item.addView(stamp);

        TextView detail = text(entry.getString("detail", ""), 13, R.color.glass_text);
        detail.setTextIsSelectable(true);
        item.addView(detail);
        return item;
    }

    private LinearLayout emptyRow() {
        LinearLayout empty = new LinearLayout(this);
        empty.setOrientation(LinearLayout.VERTICAL);
        empty.setGravity(Gravity.CENTER);
        empty.setPadding(dp(18), dp(34), dp(18), dp(34));
        TextView title = text(onlyIssues ? "暂无异常" : "暂无任务记录", 16, R.color.glass_text);
        title.setTypeface(null, Typeface.BOLD);
        empty.addView(title);
        TextView hint = text(onlyIssues ? "切换到“全部”查看完整记录。"
                : "任务执行后，记录会显示在这里。", 13, R.color.glass_secondary);
        hint.setPadding(0, dp(6), 0, 0);
        empty.addView(hint);
        return empty;
    }

    private View divider() {
        View divider = new View(this);
        divider.setBackgroundColor(Color.rgb(238, 239, 243));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(1));
        params.leftMargin = dp(16);
        params.rightMargin = dp(16);
        divider.setLayoutParams(params);
        return divider;
    }

    private boolean isIssue(String state) {
        return "失败".equals(state) || "未完成".equals(state) || "结果未确认".equals(state)
                || "服务端未确认".equals(state) || "未执行".equals(state)
                || "跳过".equals(state) || "阻止发送".equals(state)
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

    private TextView filter(String title, boolean active) {
        TextView view = text(title, 13, active ? R.color.huya_accent : R.color.glass_secondary);
        view.setGravity(Gravity.CENTER);
        view.setMinHeight(dp(34));
        view.setPadding(dp(12), 0, dp(12), 0);
        styleFilter(view, active);
        return view;
    }

    private void styleFilter(TextView view, boolean active) {
        view.setTextColor(getColor(active ? R.color.huya_accent : R.color.glass_secondary));
        view.setTypeface(null, active ? Typeface.BOLD : Typeface.NORMAL);
        view.setBackground(rounded(active ? 0x167C6AF0 : Color.TRANSPARENT, 17));
    }

    private GradientDrawable rounded(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        return drawable;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
