package io.github.saycm.huyaplus;

import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
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
    private final Set<String> diceListsRead = new HashSet<>();
    private final Set<String> coinListsRead = new HashSet<>();
    private final Set<String> pendingGrainChecks = new HashSet<>();
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

    void invalidateTaskLists() {
        diceListsRead.clear();
        coinListsRead.clear();
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
            log("配置", "", "失败", "执行间隔无效，本轮未执行");
            finished.run();
            return;
        }
        long interval = seconds * 1000L;
        Runnable complete = () -> finishRun(() -> {
            finished.run();
            monitorDice(account, date, interval);
        });
        String dayKey = account + "/" + date;
        boolean first = seen.add(dayKey);
        if (!first && diceListsRead.contains(dayKey)) {
            if (shouldRecheckGrain(dayKey)) {
                running = true;
                handler.postDelayed(() -> runDiceMissions(account, date, interval, true,
                        () -> runCoins(account, date, interval, complete)), interval);
            } else if (!coinListsRead.contains(dayKey) && prefs.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false)) {
                running = true;
                runCoins(account, date, interval, complete);
            } else complete.run();
            return;
        }
        running = true;
        Runnable tasks = () -> runDiceMissions(account, date, interval, false, () -> {
            Runnable coins = () -> runCoins(account, date, interval, complete);
            if (first && prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false)) {
                handler.postDelayed(() -> rollDice(account, date, interval, coins), interval);
            } else coins.run();
        });
        if (first && prefs.getBoolean(GlassSettings.KEY_DICE_WELFARE_SIGN, false)) {
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
                    NativeTaskAutomation.this.log("任务中心签到", "", state, detail);
                }
                @Override public void send(TaskWire.Struct request, NativeTaskRunner.Reply reply) {
                    client.send(account, "wupui", "executeUserSign", request,
                            (body, code) -> handler.post(() -> reply.complete(body, code)));
                }
                @Override public void later(long delay, Runnable run) { handler.postDelayed(run, delay); }
            }, () -> handler.postDelayed(tasks, interval)).start();
        } else tasks.run();
    }

    private void finishRun(Runnable finished) {
        running = false;
        finished.run();
        gifts.resumePendingLogin();
    }

    private NativeTaskRunner coinRunner(long account, String date, long interval, Runnable finished) {
        return new NativeTaskRunner(new NativeTaskRunner.Host() {
            @Override public boolean enabled() { return prefs.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false); }
            @Override public long uid() {
                try { return date.equals(currentDate()) ? client.loggedInUid() : 0; }
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
                coinListsRead.add(account + "/" + date);
                try { store.replaceTasks(account + "/" + date, tasks); }
                catch (RuntimeException failure) {
                    log("任务列表", "失败", "任务清单保存失败，仍按当前开关执行");
                }
            }
            @Override public void log(String title, String state, String detail) {
                NativeTaskAutomation.this.log("每日赚金币", title, state, detail);
            }
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
    }

    private void runCoins(long account, String date, long interval, Runnable finished) {
        try {
            if (!coinListsRead.contains(account + "/" + date)
                    && prefs.getBoolean(GlassSettings.KEY_NATIVE_TASKS, false)) {
                NativeTaskRunner runner = coinRunner(account, date, interval, finished);
                handler.postDelayed(() -> runner.start(account, date), interval);
                return;
            }
        } catch (RuntimeException failure) {
            log("每日赚金币", "任务中心", "失败", "读取配置失败，本轮未执行");
        }
        finished.run();
    }

    private void runDiceMissions(long account, String date, long interval, boolean grainOnly, Runnable finished) {
        String dayKey = account + "/" + date;
        class DiceMissions implements DiceMissionRunner.Host {
            private final ArrayDeque<AutomationRules.GrainPart> grainPlan = new ArrayDeque<>();
            private DiceTaskCatalog.Task grainTask;
            private boolean grainTaskComplete;
            private boolean listRead;

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
            @Override public void publish(List<DiceTaskCatalog.Task> tasks) {
                listRead = true;
                diceListsRead.add(dayKey);
                store.replaceDiceTasks(dayKey, tasks);
                if (grainTask == null && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false)) {
                    for (DiceTaskCatalog.Task task : tasks) {
                        if (task.freeGrain() && taskEnabled(task)) {
                            List<AutomationRules.GrainPart> saved = store.diceGrainPlan(dayKey);
                            if (saved != null) loadGrainPlan(task, saved);
                            break;
                        }
                    }
                }
                if (grainTask == null) return;
                grainTaskComplete = false;
                for (DiceTaskCatalog.Task task : tasks) {
                    if (task.id.equals(grainTask.id)) {
                        grainTaskComplete = task.status == 2 || task.claimed >= task.total;
                        return;
                    }
                }
            }
            @Override public void log(String title, String state, String detail) {
                NativeTaskAutomation.this.log("骰子任务", title, state, detail);
            }
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
                        if (grainTask == null && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false)) {
                            List<AutomationRules.GrainPart> planned = AutomationRules.planDiceGrain(AutomationRules.parse(
                                    prefs.getString(GlassSettings.KEY_GIFT_ROOMS, "")),
                                    bound -> java.util.concurrent.ThreadLocalRandom.current().nextInt(bound));
                            loadGrainPlan(task, store.saveDiceGrainPlan(dayKey, planned));
                        }
                        sendNextGrain(allowed, reply);
                    } catch (IllegalArgumentException failure) {
                        reply.complete(false, "自定义赠送的直播间配置无效，未送礼");
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

            private void loadGrainPlan(DiceTaskCatalog.Task task, List<AutomationRules.GrainPart> plan) {
                if (!AutomationRules.matchesGrainPlan(plan, AutomationRules.parse(
                        prefs.getString(GlassSettings.KEY_GIFT_ROOMS, "")))) return;
                grainTask = task;
                for (AutomationRules.GrainPart part : plan) {
                    if (!store.hasClaim(AutomationRules.confirmedGrainPart(dayKey, part.room, part.number))) {
                        grainPlan.add(part);
                    }
                }
            }

            private void sendNextGrain(java.util.function.BooleanSupplier allowed,
                                       NativeTaskRunner.ActionReply reply) {
                AutomationRules.GrainPart part = grainPlan.poll();
                if (part == null) {
                    boolean started = grainTask != null && store.hasClaim("dice-grain-started/" + dayKey);
                    reply.complete(false, started ? "已无待发送的计划笔数，等待虎牙更新进度"
                            : "未开启自定义赠送，或当前配置不支持三笔赠送");
                    return;
                }
                gifts.sendDiceGrain(account, date, part,
                        () -> prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false) && allowed.getAsBoolean(),
                        (accepted, detail) -> {
                            if (!accepted) grainPlan.clear();
                            reply.complete(accepted, detail);
                        });
            }

            private void finish() {
                // If today's task had prior progress, send the rest of the already configured allotment.
                if (grainTaskComplete && !grainPlan.isEmpty() && uid() == account && taskEnabled(grainTask)) {
                    sendNextGrain(() -> uid() == account && taskEnabled(grainTask),
                            (accepted, detail) -> {
                                log(grainTask.title, accepted ? "已提交" : "未执行", detail);
                                handler.postDelayed(this::finish, interval);
                            });
                    return;
                }
                try {
                    if (grainTask != null && !grainTaskComplete && taskEnabled(grainTask)
                            && store.hasClaim("dice-grain-started/" + dayKey)) {
                        pendingGrainChecks.add(dayKey);
                    } else if (listRead) {
                        pendingGrainChecks.remove(dayKey);
                    }
                } catch (RuntimeException failure) {
                    log("虎粮赠送", "未确认", "赠送记录读取失败");
                }
                finished.run();
            }
        }
        DiceMissions missions = new DiceMissions();
        new DiceMissionRunner(missions, interval, missions::finish).start(account, date, grainOnly);
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
                NativeTaskAutomation.this.log("每日投骰子", "", state, detail);
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
        if (key.equals(diceMonitor) || !diceMonitoringNeeded(key)) return;
        diceMonitor = key;
        Runnable check = new Runnable() {
            @Override public void run() {
                if (!key.equals(diceMonitor)) return;
                try {
                    if (!date.equals(currentDate()) || client.loggedInUid() != account || !diceMonitoringNeeded(key)) {
                        diceMonitor = null;
                        return;
                    }
                    if (!running && gifts.isIdle()) {
                        running = true;
                        Runnable checked = () -> finishRun(() -> {
                            if (!key.equals(diceMonitor)) return;
                            if (diceMonitoringNeeded(key)) handler.postDelayed(this, DICE_CHECK_INTERVAL);
                            else diceMonitor = null;
                        });
                        Runnable roll = () -> {
                            if (prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false)) {
                                rollDice(account, date, interval, checked);
                            } else checked.run();
                        };
                        if (shouldRecheckGrain(key)) runDiceMissions(account, date, interval, true, roll);
                        else roll.run();
                        return;
                    }
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    log("每日投骰子", "", "未确认", "库存复核失败，本轮未投骰");
                    running = false;
                }
                handler.postDelayed(this, DICE_CHECK_INTERVAL);
            }
        };
        handler.postDelayed(check, DICE_CHECK_INTERVAL);
    }

    private boolean diceMonitoringNeeded(String dayKey) {
        return prefs.getBoolean(GlassSettings.KEY_AUTO_DICE, false) || shouldRecheckGrain(dayKey);
    }

    private boolean shouldRecheckGrain(String dayKey) {
        return pendingGrainChecks.contains(dayKey)
                && prefs.getBoolean(GlassSettings.KEY_DICE_MISSIONS, false)
                && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false);
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

    private void log(String type, String title, String state, String detail) {
        try { store.append(type, title, state, detail); }
        catch (RuntimeException failure) { module.log(Log.WARN, "FuckAD", "Task center journal unavailable"); }
    }
}
