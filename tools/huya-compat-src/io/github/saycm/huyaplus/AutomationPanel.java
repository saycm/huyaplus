package io.github.saycm.huyaplus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.Map;

final class AutomationPanel {
    private final Activity activity;
    private SharedPreferences prefs;
    private LinearLayout roomList;
    private Switch sign;
    private Switch gift;
    private Switch nativeTasks;
    private Switch dice;
    private Switch diceMissions;
    private Switch welfareSign;
    private final boolean dicePage;
    private LinearLayout taskList;
    private TextView taskSummary;
    private Button interval;
    private Button add;
    private Button refreshTasks;
    private boolean syncing;
    private final Handler handler = new Handler(Looper.getMainLooper());

    AutomationPanel(Activity activity, LinearLayout root) {
        this(activity, root, null);
    }

    AutomationPanel(Activity activity, LinearLayout root, String taskGroup) {
        this.activity = activity;
        dicePage = TaskSettingsActivity.DICE.equals(taskGroup);
        if (TaskSettingsActivity.DICE.equals(taskGroup)) {
            dice = toggle(root, "每日自动投骰子", GlassSettings.KEY_AUTO_DICE);
            label(root, "每天首次打开虎牙后，按执行间隔使用已有免费骰子，不购买次数。", 13);
            diceMissions = toggle(root, "执行骰子任务及领取奖励", GlassSettings.KEY_DICE_MISSIONS);
            welfareSign = toggle(root, "任务中心每日签到", GlassSettings.KEY_DICE_WELFARE_SIGN);
            label(root, "开启要自动执行的任务。修改后强制停止虎牙再打开。", 13);
            label(root, "送虎粮任务共用每日自动任务里的自定义赠送。配置允许时拆成 3 笔，每个直播间每日总量按原配置。", 13);
            taskSummary = label(root, "骰子任务 · 等待虎牙同步", 14);
            refreshTasks = button(root, "刷新任务列表", view -> syncTasks());
            refreshTasks.setEnabled(false);
            taskList = column();
            root.addView(taskList);
            return;
        }
        if (TaskSettingsActivity.DAILY.equals(taskGroup)) {
            nativeTasks = toggle(root, "每日赚金币自动任务", GlassSettings.KEY_NATIVE_TASKS);
            label(root, "每天首次打开虎牙后，执行已开启且已适配的任务，按服务端状态领取奖励。", 13);
            taskSummary = label(root, "任务列表 · 等待虎牙同步", 14);
            refreshTasks = button(root, "刷新任务列表", view -> syncTasks());
            refreshTasks.setEnabled(false);
            taskList = column();
            root.addView(taskList);
            label(root, "每项任务可单独开启。达标后才会领取奖励。", 13);
            return;
        }
        label(root, "每日自动任务", 19);
        label(root, "每天首次打开虎牙、登录就绪后在后台执行，不切换直播间。", 14);
        sign = toggle(root, "已有粉丝牌自动打卡", GlassSettings.KEY_AUTO_SIGN);
        gift = toggle(root, "指定直播间赠送免费虎粮", GlassSettings.KEY_AUTO_GIFT);
        label(root, "只使用免费库存；不足时跳过，不购买。修改后请强制停止虎牙再打开。", 13);
        roomList = column();
        root.addView(roomList);
        add = button(root, "添加直播间", view -> editRoom(null, null));
        add.setEnabled(false);
        label(root, "虎牙任务中心", 19);
        button(root, "骰子任务", view -> openTasks(TaskSettingsActivity.DICE));
        button(root, "每日赚金币", view -> openTasks(TaskSettingsActivity.DAILY));
        interval = button(root, "任务执行间隔 · 30 秒", view -> editInterval());
        interval.setEnabled(false);
        label(root, "任务中心串行处理，收到回执后再等待设定间隔；超时或安全校验时停止本轮。", 13);
        button(root, "查看任务日志", view ->
                activity.startActivity(new Intent(activity, TaskLogActivity.class)));
    }

    private void openTasks(String group) {
        activity.startActivity(new Intent(activity, TaskSettingsActivity.class)
                .putExtra(TaskSettingsActivity.GROUP, group));
    }

    void onRemoteConnected(SharedPreferences remote) {
            prefs = remote;
            if (remote == null) {
                for (View control : new View[]{sign, gift, nativeTasks, dice, diceMissions,
                        welfareSign, add, interval, refreshTasks}) {
                    if (control != null) control.setEnabled(false);
                }
                if (taskList != null) taskList.removeAllViews();
                if (roomList != null) roomList.removeAllViews();
                if (taskSummary != null) taskSummary.setText("框架已断开，等待重新连接");
                return;
            }
            syncing = true;
            if (sign != null) sign.setChecked(remote.getBoolean(GlassSettings.KEY_AUTO_SIGN, false));
            if (gift != null) gift.setChecked(remote.getBoolean(GlassSettings.KEY_AUTO_GIFT, false));
            if (nativeTasks != null) nativeTasks.setChecked(remote.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false));
            if (dice != null) dice.setChecked(remote.getBoolean(GlassSettings.KEY_AUTO_DICE, false));
            if (diceMissions != null) diceMissions.setChecked(remote.getBoolean(GlassSettings.KEY_DICE_MISSIONS, false));
            if (welfareSign != null) welfareSign.setChecked(remote.getBoolean(GlassSettings.KEY_DICE_WELFARE_SIGN, false));
            syncing = false;
            if (sign != null) sign.setEnabled(true);
            if (gift != null) gift.setEnabled(true);
            if (add != null) add.setEnabled(true);
            if (nativeTasks != null) nativeTasks.setEnabled(true);
            if (dice != null) dice.setEnabled(true);
            if (diceMissions != null) diceMissions.setEnabled(true);
            if (welfareSign != null) welfareSign.setEnabled(true);
            if (interval != null) { interval.setEnabled(true); showInterval(); }
            if (refreshTasks != null) { refreshTasks.setEnabled(true); syncTasks(); }
            if (roomList != null) renderRooms();
    }

    void destroy() { handler.removeCallbacksAndMessages(null); }

    private void syncTasks() {
        renderTasks();
        try {
            activity.sendBroadcast(new Intent(DailyAutomation.SYNC_LOGS)
                    .setPackage("com.duowan.kiwi"));
        } catch (RuntimeException ignored) {
        }
        handler.postDelayed(this::renderTasks, 600L);
        handler.postDelayed(this::renderTasks, 2500L);
    }

    private void renderTasks() {
        if (prefs == null || taskList == null) return;
        Bundle result;
        try {
            result = activity.getContentResolver().call(
                    TaskLogProvider.URI, "read_tasks", null, null);
        } catch (RuntimeException failure) {
            taskSummary.setText("任务列表 · 读取失败");
            return;
        }
        ArrayList<Bundle> tasks = result == null ? null : result.getParcelableArrayList("tasks");
        taskList.removeAllViews();
        if (tasks == null || tasks.isEmpty()) {
            taskSummary.setText("任务列表 · 尚未同步");
            TextView empty = label(taskList,
                    "先打开虎牙并保持登录，任务中心读取完成后会自动同步到这里。", 13);
            empty.setTextColor(activity.getColor(R.color.glass_secondary));
            return;
        }
        int visible = 0;
        for (Bundle task : tasks) {
            String key = task.getString("key", "");
            if (key.isEmpty()) continue;
            if (dicePage != key.startsWith("dice/")) continue;
            if (!dicePage && !NativeTaskCatalog.isDailyGoldTask(task.getString("title", ""))) continue;
            if (taskList.getChildCount() > 0) taskList.addView(divider());
            taskList.addView(taskRow(task, key));
            visible++;
        }
        taskSummary.setText((dicePage ? "骰子任务" : "每日赚金币") + " · 共 " + visible + " 项");
        if (visible == 0) label(taskList, "暂无任务，请打开虎牙后刷新。", 13);
    }

    private LinearLayout taskRow(Bundle task, String key) {
        LinearLayout row = column();
        row.setPadding(0, dp(8), 0, dp(8));
        LinearLayout heading = new LinearLayout(activity);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setOrientation(LinearLayout.HORIZONTAL);
        TextView title = new TextView(activity);
        title.setText(task.getString("title", "未命名任务"));
        title.setTextSize(15);
        title.setTextColor(activity.getColor(R.color.glass_text));
        title.setTypeface(null, Typeface.BOLD);
        title.setPadding(0, dp(6), dp(8), dp(6));
        heading.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Switch toggle = new Switch(activity);
        String setting = dicePage ? DiceTaskCatalog.switchKey(key) : NativeTaskCatalog.switchKey(key);
        String status = task.getString("status", "");
        boolean unsupported = !dicePage && "暂不支持".equals(status);
        toggle.setChecked(!unsupported && prefs.getBoolean(setting, !dicePage));
        toggle.setEnabled(!unsupported);
        toggle.setOnCheckedChangeListener((button, enabled) -> {
            if (prefs != null) prefs.edit().putBoolean(setting, enabled).apply();
        });
        heading.addView(toggle);
        row.addView(heading);

        int color = ("已领取".equals(status) || "可领奖".equals(status))
                ? R.color.success_green
                : ("可自动执行".equals(status) ? R.color.huya_accent : R.color.glass_secondary);
        TextView statusView = label(row, status, 12);
        statusView.setTextColor(activity.getColor(color));
        statusView.setTypeface(null, Typeface.BOLD);
        TextView detail = label(row, task.getString("detail", ""), 13);
        detail.setTextColor(activity.getColor(R.color.glass_secondary));
        return row;
    }

    private View divider() {
        View divider = new View(activity);
        divider.setBackgroundColor(0x1F7C6AF0);
        divider.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(1)));
        return divider;
    }

    private void showInterval() {
        interval.setText("任务执行间隔 · " + prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30") + " 秒");
    }

    private void editInterval() {
        EditText input = new EditText(activity);
        input.setInputType(InputType.TYPE_CLASS_NUMBER);
        input.setTextColor(activity.getColor(R.color.glass_text));
        input.setText(prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30"));
        input.setSelectAllOnFocus(true);
        int pad = dp(20);
        input.setPadding(pad, pad, pad, pad);
        AlertDialog dialog = new AlertDialog.Builder(activity, android.R.style.Theme_Material_Light_Dialog_Alert)
                .setTitle("任务执行间隔（5–600 秒）").setView(input)
                .setNegativeButton("取消", null).setPositiveButton("保存", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            if (prefs == null) { dialog.dismiss(); return; }
            try {
                int seconds = NativeTaskCatalog.intervalSeconds(input.getText().toString());
                prefs.edit().putString(GlassSettings.KEY_TASK_INTERVAL, Integer.toString(seconds)).apply();
                showInterval(); dialog.dismiss();
            } catch (IllegalArgumentException failure) { input.setError("请填写 5–600 之间的整数秒数"); }
        }));
        dialog.show();
    }

    private Switch toggle(LinearLayout root, String title, String key) {
        Switch view = new Switch(activity);
        view.setText(title);
        view.setTextColor(activity.getColor(R.color.glass_text));
        view.setTextSize(15);
        view.setPadding(0, dp(16), 0, dp(16));
        view.setEnabled(false);
        view.setOnCheckedChangeListener((button, enabled) -> {
            if (!syncing && prefs != null) prefs.edit().putBoolean(key, enabled).apply();
        });
        root.addView(view);
        return view;
    }

    private Map<Long, Integer> rooms() {
        return new LinkedHashMap<>(AutomationRules.parse(
                prefs.getString(GlassSettings.KEY_GIFT_ROOMS, "")));
    }

    private void renderRooms() {
        roomList.removeAllViews();
        for (Map.Entry<Long, Integer> room : rooms().entrySet()) {
            LinearLayout row = column();
            String amount = room.getValue() == AutomationRules.ALL_FREE_GRAIN
                    ? "赠送剩余免费虎粮" : "每天 " + room.getValue() + " 个免费虎粮";
            label(row, "直播间 " + room.getKey() + " · " + amount, 15);
            button(row, "修改", view -> editRoom(room.getKey(), room.getValue()));
            button(row, "删除", view -> {
                Map<Long, Integer> values = rooms();
                values.remove(room.getKey());
                saveRooms(values);
            });
            roomList.addView(row);
        }
    }

    private void editRoom(Long oldRoom, Integer oldCount) {
        LinearLayout fields = column();
        fields.setPadding(dp(24), dp(12), dp(24), 0);
        EditText room = new EditText(activity);
        room.setHint("直播间房间号");
        room.setTextColor(activity.getColor(R.color.glass_text));
        room.setHintTextColor(activity.getColor(R.color.glass_secondary));
        room.setInputType(InputType.TYPE_CLASS_NUMBER);
        EditText count = new EditText(activity);
        count.setHint("每天赠送数量");
        count.setTextColor(activity.getColor(R.color.glass_text));
        count.setHintTextColor(activity.getColor(R.color.glass_secondary));
        count.setInputType(InputType.TYPE_CLASS_NUMBER);
        if (oldRoom != null) room.setText(oldRoom.toString());
        if (oldCount != null && oldCount != AutomationRules.ALL_FREE_GRAIN) count.setText(oldCount.toString());
        CheckBox all = new CheckBox(activity);
        all.setText("赠送剩余免费虎粮");
        all.setTextColor(activity.getColor(R.color.glass_text));
        all.setChecked(oldCount != null && oldCount == AutomationRules.ALL_FREE_GRAIN);
        count.setVisibility(all.isChecked() ? View.GONE : View.VISIBLE);
        all.setOnCheckedChangeListener((button, checked) -> count.setVisibility(checked ? View.GONE : View.VISIBLE));
        fields.addView(room);
        fields.addView(all);
        fields.addView(count);
        label(fields, "仅可为一个直播间启用。固定数量的房间先执行，剩余免费虎粮最后送出。", 13);
        AlertDialog dialog = new AlertDialog.Builder(activity,
                android.R.style.Theme_Material_Light_Dialog_Alert).setTitle("免费虎粮赠送")
                .setView(fields).setNegativeButton("取消", null)
                .setPositiveButton("保存", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(view -> {
                    if (prefs == null) { dialog.dismiss(); return; }
                    try {
                        Map<Long, Integer> values = rooms();
                        Map<Long, Integer> single = AutomationRules.parse(
                                room.getText().toString() + "=" + (all.isChecked() ? "all" : count.getText()));
                        long id = single.keySet().iterator().next();
                        if (values.containsKey(id) && !Long.valueOf(id).equals(oldRoom)) {
                            throw new IllegalArgumentException("该直播间已添加");
                        }
                        if (oldRoom != null) values.remove(oldRoom);
                        if (all.isChecked() && values.containsValue(AutomationRules.ALL_FREE_GRAIN)) {
                            Toast.makeText(activity, "已有直播间设置赠送剩余免费虎粮", Toast.LENGTH_SHORT).show();
                            return;
                        }
                        values.putAll(single);
                        saveRooms(values);
                        dialog.dismiss();
                    } catch (IllegalArgumentException failure) {
                        Toast.makeText(activity, "请填写有效且不重复的房间号和正整数数量", Toast.LENGTH_SHORT).show();
                    }
                }));
        dialog.show();
    }

    private void saveRooms(Map<Long, Integer> values) {
        if (prefs == null) return;
        StringBuilder text = new StringBuilder();
        for (Map.Entry<Long, Integer> room : values.entrySet()) {
            text.append(room.getKey()).append('=').append(AutomationRules.savedCount(room.getValue())).append('\n');
        }
        prefs.edit().putString(GlassSettings.KEY_GIFT_ROOMS, text.toString()).apply();
        renderRooms();
    }

    private LinearLayout column() {
        LinearLayout view = new LinearLayout(activity);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }

    private TextView label(LinearLayout parent, String text, int size) {
        TextView view = new TextView(activity);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(activity.getColor(R.color.glass_text));
        view.setPadding(0, dp(10), 0, dp(10));
        parent.addView(view);
        return view;
    }

    private Button button(LinearLayout parent, String text, View.OnClickListener listener) {
        Button view = new Button(activity);
        view.setText(text);
        view.setTextSize(14);
        view.setAllCaps(false);
        boolean delete = "删除".equals(text);
        view.setBackgroundResource(delete ? R.drawable.glass_card : R.drawable.accent_button);
        view.setTextColor(activity.getColor(delete ? R.color.glass_secondary : R.color.hero_text));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(46));
        params.topMargin = dp(10);
        view.setLayoutParams(params);
        view.setOnClickListener(listener);
        parent.addView(view);
        return view;
    }

    private int dp(int value) { return Math.round(value * activity.getResources().getDisplayMetrics().density); }
}
