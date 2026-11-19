package io.github.saycm.huyaplus;

import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TimeZone;

import io.github.libxposed.api.XposedModule;

final class NativeTaskAutomation {
    private static final long DICE_CHECK_INTERVAL = 15 * 60 * 1000L;
    private final XposedModule module;
    private final SharedPreferences prefs;
    private final LocalTaskStore store;
    private final HuyaTaskClient client;
    private final DailyAutomation gifts;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Set<String> seen = new HashSet<>();
    private Object context;
    private boolean running;
    private String diceMonitor;

    NativeTaskAutomation(XposedModule module, SharedPreferences prefs, ClassLoader loader,
                         LocalTaskStore store, DailyAutomation gifts) {
        this.module = module; this.prefs = prefs; this.store = store;
        this.gifts = gifts; client = new HuyaTaskClient(loader);
    }

    void onActivity(Object current) {
        if (current != null) context = current;
    }

    void onReady(long account) {
        onReady(account, () -> {});
    }

    void onReady(long account, Runnable finished) {
        if (prefs == null) { finished.run(); return; }
        if (running) return;
        String date = currentDate();
        int seconds;
        try { seconds = NativeTaskCatalog.intervalSeconds(prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30")); }
        catch (IllegalArgumentException failure) {
            log("配置", "失败", "执行间隔无效，本轮未执行");
            finished.run();
            return;
        }
        long interval = seconds * 1000L;
        if (!seen.add(account + "/" + date)) {
            finished.run();
            monitorDice(account, date, interval);
            return;
        }
        running = true;
        Runnable complete = () -> {
            running = false;
            finished.run();
            monitorDice(account, date, interval);
        };
        Runnable tasks = () -> runTasks(account, date, interval, complete);
        if (prefs.getBoolean(GlassSettings.KEY_DICE_WELFARE_SIGN, false)) {
            new WelfareSignRunner(new WelfareSignRunner.Host() {
                @Override public boolean active() {
                    try {
                        return date.equals(currentDate())
                                && prefs.getBoolean(GlassSettings.KEY_DICE_WELFARE_SIGN, false)
                                && client.loggedInUid() == account;
                    } catch (ReflectiveOperationException | RuntimeException failure) { return false; }
                }
                @Override public boolean claim() {
                    try { return store.claim("dice-welfare-sign/" + account + "/" + date); }
                    catch (RuntimeException failure) { return false; }
                }
                @Override public void log(String state, String detail) {
                    NativeTaskAutomation.this.log("任务中心签到", state, detail);
                }
                @Override public void send(TaskWire.Struct request, NativeTaskRunner.Reply reply) {
                    client.send(account, "wupui", "executeUserSign", request,
                            (body, code) -> handler.post(() -> reply.complete(body, code)));
                }
                @Override public void later(long delay, Runnable run) { handler.postDelayed(run, delay); }
            }, () -> handler.postDelayed(tasks, interval)).start();
        } else tasks.run();
    }

    private void runTasks(long account, String date, long interval, Runnable finished) {
        NativeTaskRunner runner = new NativeTaskRunner(new NativeTaskRunner.Host() {
            @Override public boolean enabled() { return prefs.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false); }
            @Override public long uid() {
                try { return client.loggedInUid(); }
                catch (ReflectiveOperationException | RuntimeException failure) { return 0; }
            }
            @Override public boolean claim(String key) {
                try { return store.claim(key); }
                catch (RuntimeException failure) { log("去重", "失败", "记录不可用，未执行任务"); return false; }
            }
            @Override public boolean taskEnabled(NativeTaskCatalog.Task task) {
                try { return prefs.getBoolean(task.settingsKey(), true); }
                catch (RuntimeException failure) {
                    log(task.title, "失败", "读取任务开关失败，本轮不执行该任务");
                    return false;
                }
            }
            @Override public void publish(List<NativeTaskCatalog.Task> tasks) {
                try { store.replaceTasks(tasks); }
                catch (RuntimeException failure) {
                    log("任务列表", "失败", "任务清单保存失败，仍按当前开关执行");
                }
            }
            @Override public void log(String title, String state, String detail) { NativeTaskAutomation.this.log(title, state, detail); }
            @Override public void later(long millis, Runnable run) { handler.postDelayed(run, millis); }
            @Override public void perform(NativeTaskCatalog.Task task,
                                          NativeTaskRunner.ActionReply reply) {
                performTask(account, task,
                        (accepted, detail) -> handler.post(() -> reply.complete(accepted, detail)));
            }
            @Override public void send(String servant, String function, TaskWire.Struct body, NativeTaskRunner.Reply reply) {
                client.send(account, servant, function, body,
                        (result, code) -> handler.post(() -> reply.complete(result, code)));
            }
        }, interval, finished);
        Runnable coins = () -> {
            try {
                if (prefs.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false)) {
                    handler.postDelayed(() -> runner.start(account, date), interval);
                } else finished.run();
            } catch (RuntimeException failure) {
                log("任务中心", "失败", "读取配置失败，本轮未执行");
                finished.run();
            }
        };
        Runnable roll = () -> {
            if (!prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false)) {
                coins.run();
                return;
            }
            handler.postDelayed(() -> rollDice(account, date, interval, coins), interval);
        };
        new DiceMissionRunner(new DiceMissionRunner.Host() {
            @Override public long uid() {
                try { return date.equals(currentDate()) ? client.loggedInUid() : 0; }
                catch (ReflectiveOperationException | RuntimeException failure) { return 0; }
            }
            @Override public boolean taskEnabled(DiceTaskCatalog.Task task) {
                return prefs.getBoolean(GlassSettings.KEY_DICE_MISSIONS, false)
                        && date.equals(currentDate())
                        && prefs.getBoolean(task.settingsKey(), false);
            }
            @Override public boolean claim(String key) {
                try { return store.claim(key); }
                catch (RuntimeException failure) { return false; }
            }
            @Override public void publish(List<DiceTaskCatalog.Task> tasks) { store.replaceDiceTasks(tasks); }
            @Override public void log(String title, String state, String detail) { NativeTaskAutomation.this.log(title, state, detail); }
            @Override public void later(long delay, Runnable run) { handler.postDelayed(run, delay); }
            @Override public void send(String endpoint, TaskWire.Struct request, NativeTaskRunner.Reply reply) {
                client.send(account, "wupui", endpoint, request,
                        (body, code) -> handler.post(() -> reply.complete(body, code)));
            }
            @Override public void perform(DiceTaskCatalog.Task task,
                                          java.util.function.BooleanSupplier allowed,
                                          NativeTaskRunner.ActionReply reply) {
                if (task.freeGrain()) {
                    try {
                        java.util.Map<Long, Integer> rooms = AutomationRules.parse(
                                prefs.getString(GlassSettings.KEY_DICE_GIFT_ROOMS, ""));
                        for (java.util.Map.Entry<Long, Integer> room : rooms.entrySet()) {
                            for (int index = 0; index < room.getValue(); index++) {
                                String key = account + "/" + date + "/" + room.getKey() + "/" + index;
                                if (!store.claim("dice-grain-quota/" + key)) continue;
                                gifts.sendDiceGrain(account, date, room.getKey(), key,
                                        allowed, reply);
                                return;
                            }
                        }
                        reply.complete(false, "未配置优先房间，或已达该房间每日赠送上限；未送礼");
                    } catch (IllegalArgumentException failure) {
                        reply.complete(false, "骰子任务的直播间配置无效，未送礼");
                    }
                    return;
                }
                if (task.type == 6 && prefs.getBoolean(GlassSettings.KEY_REWARDS, true)) {
                    client.claimDiceVideo(account, task.action, allowed,
                            (accepted, detail) -> handler.post(() -> reply.complete(accepted, detail)),
                            interval, run -> handler.postDelayed(run, interval));
                    return;
                }
                if (task.marketVisit()) {
                    int taskId;
                    try { taskId = Integer.parseInt(task.id); }
                    catch (NumberFormatException failure) {
                        reply.complete(false, "商城任务 ID 无效，未执行"); return;
                    }
                    client.send(account, "wupui", "reportUserTaskClickEvent",
                            new TaskWire.Struct().field(1, taskId).field(2, task.action),
                            (body, code) -> handler.post(() -> reply.complete(code == 0,
                                    code == 0 ? "商城任务事件已提交，等待服务端复核"
                                            : "商城任务事件未获确认，未领奖")));
                    return;
                }
                reply.complete(false, "奖励跳过开关关闭，或该任务尚无静默动作");
            }
        }, interval, roll).start(account, date);
    }

    private void rollDice(long account, String date, long interval, Runnable finished) {
        new DiceTaskRunner(new DiceTaskRunner.Host() {
            @Override public boolean enabled() {
                return date.equals(currentDate()) && prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false);
            }
            @Override public long uid() {
                try { return client.loggedInUid(); }
                catch (ReflectiveOperationException | RuntimeException failure) { return 0; }
            }
            @Override public boolean claim(String key) {
                try { return store.claim(key); }
                catch (RuntimeException failure) { return false; }
            }
            @Override public void log(String state, String detail) {
                NativeTaskAutomation.this.log("每日投骰子", state, detail);
            }
            @Override public void later(long delay, Runnable run) { handler.postDelayed(run, delay); }
            @Override public void send(String function, TaskWire.Struct body, NativeTaskRunner.Reply reply) {
                client.send(account, "wupui", function, body,
                        (result, code) -> handler.post(() -> reply.complete(result, code)));
            }
        }, interval, finished).start(account, date);
    }

    private void monitorDice(long account, String date, long interval) {
        String key = account + "/" + date;
        if (key.equals(diceMonitor) || !prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false)) return;
        diceMonitor = key;
        Runnable check = new Runnable() {
            @Override public void run() {
                if (!key.equals(diceMonitor)) return;
                try {
                    if (!date.equals(currentDate()) || client.loggedInUid() != account
                            || !prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false)) {
                        diceMonitor = null;
                        return;
                    }
                    if (!running && gifts.isIdle()) {
                        running = true;
                        rollDice(account, date, interval, () -> {
                            running = false;
                            handler.postDelayed(this, DICE_CHECK_INTERVAL);
                        });
                        return;
                    }
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    log("每日投骰子", "未确认", "库存复核失败，本轮未投骰");
                    running = false;
                }
                handler.postDelayed(this, DICE_CHECK_INTERVAL);
            }
        };
        handler.postDelayed(check, DICE_CHECK_INTERVAL);
    }

    boolean isIdle() { return !running; }

    private static String currentDate() {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
        format.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        return format.format(new Date());
    }

    private void performTask(long account, NativeTaskCatalog.Task task,
                             NativeTaskRunner.ActionReply reply) {
        try {
            switch (task.automationAction()) {
                case NOTIFICATION:
                    if (context == null || !client.notificationEnabled(context)) {
                        reply.complete(false, "系统通知未开启，未提交通知任务");
                        return;
                    }
                    client.send(account, "commui", "updateUserLevelTaskProgress",
                            task.progressRequest(),
                            (body, code) -> reply.complete(code == 0 && body.number(0) == 1,
                                    code == 0 && body.number(0) == 1
                                            ? "服务端已接收通知授权状态"
                                            : "服务端未接收通知任务进度"));
                    return;
                case DEEPLINK:
                    client.send(account, "commui", "updateUserLevelTaskProgress",
                            task.progressRequest(),
                            (body, code) -> reply.complete(code == 0 && body.number(0) == 1,
                                    code == 0 && body.number(0) == 1
                                            ? "服务端已接收跳转任务进度"
                                            : "服务端未接收跳转任务进度"));
                    return;
                case COOP:
                    client.send(account, "wupui", "reportCoopUserLevelTask",
                            new TaskWire.Struct().field(1, task.coopParams()),
                            (body, code) -> reply.complete(code == 0,
                                    code == 0
                                            ? "服务端已接收合作任务回流，等待进度复核"
                                            : "合作任务回流未获确认（返回代码 " + code + "），未领奖"));
                    return;
                default:
                    reply.complete(false, "该任务没有可用的静默动作");
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            reply.complete(false, "原生动作不可用，未提交完成事件");
        }
    }

    private void log(String title, String state, String detail) {
        try { store.append("虎牙任务中心", title, state, detail); }
        catch (RuntimeException failure) { module.log(Log.WARN, "FuckAD", "Task center journal unavailable"); }
    }
}
