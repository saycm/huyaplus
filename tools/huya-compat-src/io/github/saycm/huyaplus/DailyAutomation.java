package io.github.saycm.huyaplus;

import android.content.Context;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TimeZone;
import java.util.concurrent.CancellationException;
import java.util.concurrent.atomic.AtomicBoolean;

import io.github.libxposed.api.XposedModule;

final class DailyAutomation {
    private static final long GIFT_CHECK_INTERVAL = 30 * 60 * 1000L;
    private static final String BADGE_SIGN = "粉丝牌打卡";
    private static final String BADGE_GRAIN = "粉丝团每日虎粮";
    private static final int GRAIN_CLAIMABLE = 3;
    private static final int GRAIN_CLAIMED = 4;
    private static final int CLAIM_FANS_BOX = 3;
    static final String SYNC_LOGS = "io.github.saycm.huyaplus.SYNC_LOGS";
    private final XposedModule module;
    private final SharedPreferences prefs;
    private final ClassLoader loader;
    private final HuyaTaskClient taskClient;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<Object, Pending> requests = Collections.synchronizedMap(new IdentityHashMap<>());
    private final Set<String> seen = new HashSet<>();
    private final ArrayDeque<Long> badges = new ArrayDeque<>();
    private final ArrayDeque<Map.Entry<Long, Integer>> giftRooms = new ArrayDeque<>();
    private final Set<Long> attemptedGiftRooms = new HashSet<>();
    private final Map<Object, GiftLimit> guardedGifts = Collections.synchronizedMap(new IdentityHashMap<>());
    private long grainBudget = -1;
    private boolean giftGuardInstalled;
    private Context context;
    private LocalTaskStore store;
    private NativeTaskAutomation nativeTasks;
    private boolean syncRegistered;
    private final AtomicBoolean syncingLogs = new AtomicBoolean();
    private final AtomicBoolean logsDirty = new AtomicBoolean();
    private BroadcastReceiver syncReceiver;
    private boolean polling;
    private boolean callbacksInstalled;
    private boolean openedLogged;
    private long account;
    private long phaseAccount;
    private long pendingLogin;
    private String activeDay;
    private int signed;
    private int alreadySigned;
    private int failed;
    private boolean giftActive;
    private Runnable giftCheck;
    private volatile GiftRound giftRound;
    private DailyAutomation diceSender;
    private NativeTaskRunner.ActionReply diceGiftReply;
    private java.util.function.BooleanSupplier diceGiftAllowed;
    private AutomationRules.GrainPart diceGrainPart;
    private Runnable afterBadges;
    private volatile String taskSnapshotScope = "";
    private long requestInterval = 30000L;
    private boolean requestGap;
    private int queuedRequests;
    private volatile boolean syncFailureLogged;

    private static final class GiftRound {
        final long account;
        final String day;

        GiftRound(long account, String day) {
            this.account = account;
            this.day = day;
        }
    }

    private static final class GiftLimit {
        final GiftRound round;
        final long presenter;
        final int count;
        final long freeCount;
        volatile boolean blocked;
        GiftLimit(GiftRound round, long presenter, int count, long freeCount) {
            this.round = round;
            this.presenter = presenter; this.count = count; this.freeCount = freeCount;
        }
    }

    private interface Result { void accept(Object response); }
    private static final class Pending {
        final Result callback;
        final String task;
        final String target;
        final long account;
        final GiftRound round;
        Pending(Result callback, String task, String target, long account, GiftRound round) {
            this.callback = callback; this.task = task; this.target = target; this.account = account;
            this.round = round;
        }
    }

    DailyAutomation(XposedModule module, SharedPreferences prefs, ClassLoader loader) {
        this.module = module; this.prefs = prefs; this.loader = loader;
        taskClient = new HuyaTaskClient(loader);
    }

    void onOpen(Context current) {
        context = current.getApplicationContext();
        if (prefs != null) {
            try { requestInterval = NativeTaskCatalog.intervalSeconds(
                    prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30")) * 1000L; }
            catch (IllegalArgumentException failure) {
                module.log(Log.WARN, "FuckAD", "Invalid automation interval");
            }
        }
        if (store == null) store = new LocalTaskStore(context, this::requestLogSync);
        if (nativeTasks == null) nativeTasks = new NativeTaskAutomation(module, prefs, loader, store, this);
        nativeTasks.onActivity(current);
        if (!syncRegistered) {
            syncReceiver = new BroadcastReceiver() {
                @Override public void onReceive(Context sender, Intent intent) {
                    if (SYNC_LOGS.equals(intent.getAction())) {
                        try { updateTaskSnapshotScope(loggedInUid()); }
                        catch (ReflectiveOperationException | RuntimeException failure) { updateTaskSnapshotScope(0); }
                        requestLogSync();
                    }
                }
            };
            IntentFilter filter = new IntentFilter(SYNC_LOGS);
            if (Build.VERSION.SDK_INT >= 33) {
                context.registerReceiver(syncReceiver, filter, Context.RECEIVER_EXPORTED);
            } else {
                context.registerReceiver(syncReceiver, filter);
            }
            syncRegistered = true;
        }
        if (!openedLogged) {
            openedLogged = true;
            log("每日任务", "", "检查", "收到虎牙打开事件，正在等待登录状态");
        } else if (syncFailureLogged) {
            requestLogSync();
        }
        if (polling) return;
        polling = true;
        pollLogin(0);
    }

    private void pollLogin(int attempt) {
        try {
            long uid = loggedInUid();
            updateTaskSnapshotScope(uid);
            if (uid != account) {
                giftCheck = null;
                if (giftRound != null) continueGiftRound(giftRound);
            }
            if (uid > 0) {
                polling = false;
                if (giftCheck == null && afterBadges == null && giftAllowed()
                        && callbacksInstalled && dayKey(uid).equals(activeDay) && !nativeTasks.isIdle()) {
                    startGiftChecks(uid, activeDay);
                }
                if (nativeTasks.isIdle() && afterBadges == null) {
                    pendingLogin = 0;
                    runOnce(uid);
                } else if (uid != phaseAccount) pendingLogin = uid;
                return;
            }
        } catch (ReflectiveOperationException | RuntimeException failure) {
            updateTaskSnapshotScope(0);
            if (attempt == 29) log("每日任务", "", "失败", "登录接口不可用，未执行任务");
        }
        if (attempt < 29) handler.postDelayed(() -> pollLogin(attempt + 1), 1000L);
        else {
            polling = false;
            log("每日任务", "", "跳过", "等待登录超时，未执行任何打卡或送礼");
        }
    }

    private long loggedInUid() throws ReflectiveOperationException {
        Class<?> type = loader.loadClass("com.duowan.kiwi.base.login.api.ILoginComponent");
        Object component = HuyaComponents.get(loader, type);
        Object login = type.getMethod("getLoginModule").invoke(component);
        Class<?> loginType = loader.loadClass("com.duowan.kiwi.base.login.api.ILoginModule");
        if (!Boolean.TRUE.equals(loginType.getMethod("isLogin").invoke(login))) return 0;
        return ((Number) loginType.getMethod("getUid").invoke(login)).longValue();
    }

    private static String dayKey(long uid) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
        format.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        return uid + "/" + format.format(new Date());
    }

    private void updateTaskSnapshotScope(long uid) {
        String scope = uid > 0 ? dayKey(uid) : "";
        if (scope.equals(taskSnapshotScope)) return;
        try {
            store.selectTaskScope(scope);
        } catch (RuntimeException failure) {
            scope = "";
        }
        taskSnapshotScope = scope;
        nativeTasks.invalidateTaskLists();
        pendingLogin = uid;
        requestLogSync();
    }

    private void runOnce(long uid) {
        try {
            if (loggedInUid() != uid) return;
        } catch (ReflectiveOperationException | RuntimeException failure) {
            return;
        }
        String day = dayKey(uid);
        if (afterBadges != null || (day.equals(activeDay) && !isIdle())) return;
        phaseAccount = uid;
        boolean first = seen.add(day);
        boolean sign = prefs != null && prefs.getBoolean(GlassSettings.KEY_AUTO_SIGN, false);
        boolean gift = prefs != null && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false);
        if (!sign && !gift) {
            if (first && claim("disabled/" + day)) log("每日任务", "", "跳过", "两个自动任务开关均未开启");
            startNativeTasks(uid, () -> {});
            return;
        }
        try { requestInterval = NativeTaskCatalog.intervalSeconds(
                prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30")) * 1000L; }
        catch (IllegalArgumentException failure) {
            log("配置", "", "失败", "执行间隔无效，未执行每日任务");
            return;
        }
        if (!day.equals(activeDay)) {
            account = uid;
            activeDay = day;
            badges.clear();
            giftRooms.clear();
            attemptedGiftRooms.clear();
            giftActive = false;
            giftCheck = null;
            giftRound = null;
            requests.clear();
            for (GiftLimit limit : guardedGifts.values()) limit.blocked = true;
            grainBudget = -1;
        }
        if (first) log("每日任务", "", "开始", "今日首次打开，登录已就绪");
        Runnable nativePhase = () -> startNativeTasks(uid, () -> {
            if (gift && giftAllowed()) startGiftChecks(uid, day);
        });
        try {
            boolean runSign = sign && !store.hasClaim("badge-tasks/" + day);
            if (runSign || gift) installCallbacks();
            if (runSign) {
                signed = 0;
                alreadySigned = 0;
                failed = 0;
                afterBadges = nativePhase;
                fetchBadges();
            } else {
                nativePhase.run();
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            log("每日任务", "", "失败", "接口初始化失败：" + failure.getClass().getSimpleName());
            if (afterBadges == null) startNativeTasks(uid, () -> {});
            else finishBadges();
        }
    }

    private void startNativeTasks(long uid, Runnable finished) {
        try {
            if (loggedInUid() == uid) {
                nativeTasks.onReady(uid, () -> handler.postDelayed(finished, requestInterval));
                return;
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            log("虎牙任务中心", "", "失败", "任务中心接口不可用");
            finished.run();
        }
        resumePendingLogin();
    }

    void resumePendingLogin() {
        if (pendingLogin == 0 || afterBadges != null || !nativeTasks.isIdle()) return;
        long uid = pendingLogin;
        pendingLogin = 0;
        runOnce(uid);
    }

    private boolean claim(String key) {
        try {
            return store.claim(key);
        } catch (RuntimeException failure) {
            module.log(Log.WARN, "FuckAD", "Huya local task journal unavailable; automation disabled");
            return false;
        }
    }

    private void log(String task, String target, String state, String detail) {
        try {
            store.append(task, target, state, detail);
        } catch (RuntimeException failure) {
            module.log(Log.WARN, "FuckAD", "Task journal unavailable: " + state);
        }
    }

    private void requestLogSync() {
        logsDirty.set(true);
        if (!syncingLogs.compareAndSet(false, true)) return;
        new Thread(this::syncLogs, "FuckAD-log-sync").start();
    }

    private void syncLogs() {
        boolean failed = false;
        try {
            while (logsDirty.getAndSet(false)) {
                String scope = taskSnapshotScope;
                ArrayList<Bundle> tasks = store.tasks(scope);
                Bundle taskBatch = new Bundle();
                taskBatch.putParcelableArrayList("tasks", scope.equals(taskSnapshotScope) ? tasks : new ArrayList<>());
                context.getContentResolver().call(TaskLogProvider.URI, "import_tasks", null, taskBatch);
                ArrayList<Bundle> events = store.events();
                for (int start = 0; start < events.size(); start += 50) {
                    Bundle batch = new Bundle();
                    batch.putParcelableArrayList("events", new ArrayList<>(
                            events.subList(start, Math.min(start + 50, events.size()))));
                    context.getContentResolver().call(TaskLogProvider.URI, "import", null, batch);
                }
            }
            context.getContentResolver().call(TaskLogProvider.URI, "sync_complete", null, null);
            syncFailureLogged = false;
        } catch (RuntimeException failure) {
            failed = true;
            if (!syncFailureLogged) {
                syncFailureLogged = true;
                module.log(Log.WARN, "FuckAD", "Log display sync unavailable; records remain in Huya", failure);
                try { store.append("日志同步", "", "失败", "模块日志页暂不可用："
                        + failure.getClass().getSimpleName() + "，原始记录保留在虎牙本地"); }
                catch (RuntimeException journalFailure) {
                    module.log(Log.WARN, "FuckAD", "Sync failure could not be journaled", journalFailure);
                }
            }
        } finally {
            syncingLogs.set(false);
            if (!failed && logsDirty.get() && syncingLogs.compareAndSet(false, true)) {
                new Thread(this::syncLogs, "FuckAD-log-sync").start();
            }
        }
    }

    private void installCallbacks() throws ReflectiveOperationException {
        if (callbacksInstalled) return;
        Class<?> response = loader.loadClass("com.duowan.taf.jce.JceStruct");
        Class<?> error = loader.loadClass("com.huya.mtp.data.exception.DataException");
        Method success;
        Method failedMethod;
        try {
            success = loader.loadClass("ryxq.jd8").getDeclaredMethod("onResponse", response, boolean.class);
            failedMethod = loader.loadClass("ryxq.oe6").getDeclaredMethod("onError", error, boolean.class);
        } catch (ClassNotFoundException | NoSuchMethodException oldCallbacksAbsent) {
            success = loader.loadClass("ryxq.yy5").getDeclaredMethod("onResponse", response, boolean.class);
            failedMethod = loader.loadClass("ryxq.xp4").getDeclaredMethod("onError", error, boolean.class);
        }
        module.hook(success).intercept(chain -> {
            Pending pending = requests.get(chain.getThisObject());
            if (pending == null) return chain.proceed();
            if (Boolean.TRUE.equals(chain.getArg(1))) return null;
            requests.remove(chain.getThisObject());
            Object data = chain.getArg(0);
            handler.post(() -> complete(pending, data, false));
            return null;
        });
        module.hook(failedMethod).intercept(chain -> {
            Pending pending = requests.remove(chain.getThisObject());
            if (pending == null) return chain.proceed();
            handler.post(() -> complete(pending, null, false));
            return null;
        });
        callbacksInstalled = true;
    }

    private void complete(Pending pending, Object response, boolean timedOut) {
        try {
            if (pending.round != null && !continueGiftRound(pending.round)) return;
            if (account != pending.account || loggedInUid() != pending.account) {
                log(pending.task, pending.target, "取消", "账号已退出或切换，不继续执行");
                if (pending.round == null && account == pending.account) finishBadges();
                return;
            }
            if (timedOut) log(pending.task, pending.target, "结果未确认", "请求超时，不自动重复发送");
            pending.callback.accept(response);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            log(pending.task, pending.target, "失败", "处理回执失败：" + failure.getClass().getSimpleName());
            if (pending.round == null && account == pending.account) finishBadges();
        }
    }

    private void request(String requestClass, Object body, String task, String target, Result result)
            throws ReflectiveOperationException {
        request(requestClass, body, task, target, null, result);
    }

    private void request(String requestClass, Object body, String task, String target,
                         GiftRound round, Result result) throws ReflectiveOperationException {
        Object request = loader.loadClass(requestClass).getConstructor(body.getClass()).newInstance(body);
        sendRequest(request, task, target, round, result);
    }

    private void sendRequest(Object request, String task, String target, GiftRound round, Result result)
            throws ReflectiveOperationException {
        if (requestGap) {
            queuedRequests++;
            handler.postDelayed(() -> {
                queuedRequests--;
                try { executeRequest(request, task, target, round, result); }
                catch (ReflectiveOperationException failure) { result.accept(null); }
            }, requestInterval);
        } else executeRequest(request, task, target, round, result);
    }

    private void executeRequest(Object request, String task, String target, GiftRound round, Result result)
            throws ReflectiveOperationException {
        if (round != null) {
            if (!continueGiftRound(round)) return;
        } else if (loggedInUid() != account) {
            result.accept(null);
            return;
        }
        if (round == null && !badgeTasksActive(activeDay)) {
            result.accept(null);
            return;
        }
        requestGap = true;
        Pending pending = new Pending(result, task, target, account, round);
        requests.put(request, pending);
        log(task, target, "请求已发出", "等待服务端回执，尚未确认成功");
        handler.postDelayed(() -> {
            Pending removed = requests.remove(request);
            if (removed != null) complete(removed, null, true);
        }, 20000L);
        try {
            request.getClass().getMethod("execute").invoke(request);
        } catch (ReflectiveOperationException failure) {
            requests.remove(request);
            throw failure;
        }
    }

    private Object userId() throws ReflectiveOperationException {
        return loader.loadClass("com.duowan.biz.wup.WupHelper").getMethod("getUserId").invoke(null);
    }

    private Object value(Object target, String field) throws ReflectiveOperationException {
        return target.getClass().getField(field).get(target);
    }

    private void fetchBadges() throws ReflectiveOperationException {
        Object body = loader.loadClass("com.duowan.HUYA.BadgeInfoListReq").getConstructor().newInstance();
        body.getClass().getField("lToUid").setLong(body, account);
        request("com.duowan.biz.wup.gamelive.GameLiveWupFunction$j0", body, "粉丝牌列表", "", response -> {
            try {
                if (response == null || ((Number) value(response, "lUid")).longValue() != account) {
                    log("粉丝牌列表", "", "失败", "未获取到当前账号的列表，未执行打卡");
                    finishBadges();
                    return;
                }
                Object items = value(response, "vBadgeInfo");
                if (!(items instanceof List)) {
                    log("粉丝牌列表", "", "失败", "列表缺失，未执行打卡");
                    finishBadges();
                    return;
                }
                Set<Long> unique = new HashSet<>();
                for (Object badge : (List<?>) items) {
                    long uid = 0;
                    try {
                        Object channel = badge == null ? null : value(badge, "tChannelInfo");
                        Object rawUid = channel == null ? null : value(channel, "lUid");
                        if (rawUid instanceof Number) uid = ((Number) rawUid).longValue();
                    } catch (ReflectiveOperationException failure) {
                        // One malformed entry should not block the remaining badges.
                    }
                    if (uid <= 0 || uid == account) {
                        failed++;
                        log(BADGE_SIGN, "", "跳过", "粉丝牌缺少有效的主播信息");
                    } else if (unique.add(uid)) badges.add(uid);
                }
                log("粉丝牌列表", "", "成功", "获取 " + badges.size() + " 个已有粉丝牌");
                nextBadge();
            } catch (ReflectiveOperationException | RuntimeException failure) {
                log("粉丝牌列表", "", "失败", "列表结构不匹配，未执行打卡");
                finishBadges();
            }
        });
    }

    private void nextBadge() {
        if (!badgeTasksActive(activeDay)) {
            finishBadges();
            return;
        }
        Long presenter = badges.poll();
        if (presenter == null) {
            if (failed == 0) claim("badge-tasks/" + activeDay);
            log(BADGE_SIGN, "", "结束", "成功 " + signed + "，已打卡 " + alreadySigned
                    + "，粉丝牌任务失败或待确认 " + failed);
            finishBadges();
            return;
        }
        String day = activeDay;
        Runnable welfare = () -> checkBadgeWelfare(day, presenter);
        String target = "主播 " + presenter;
        try {
            Object body = badgeRequest("GetFansSignReq", presenter);
            request("com.duowan.kiwi.badge.wupfunction.BadgeWupFunction$GetFansSign", body,
                    "粉丝牌打卡状态", target, response -> {
                try {
                    if (response != null && ((Number) value(response, "iCode")).intValue() == 0) {
                        Object status = value(response, "tSign");
                        if (status != null) {
                            long flags = ((Number) value(status, "lSignInFlag")).longValue();
                            int position = ((Number) value(status, "iPos")).intValue();
                            if (flags == 0 || (position >= 1 && position <= 32)) {
                                if (flags != 0 && (flags & (1L << (position - 1))) != 0) {
                                    badgeAlreadySigned(target);
                                    welfare.run();
                                } else signBadge(presenter, target, welfare);
                                return;
                            }
                        }
                    }
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    log(BADGE_SIGN, target, "失败", "打卡状态结构不匹配");
                }
                failed++;
                log(BADGE_SIGN, target, "未完成", "未取得有效的打卡状态");
                welfare.run();
            });
        } catch (ReflectiveOperationException failure) {
            failed++;
            log(BADGE_SIGN, target, "失败", "打卡状态接口不匹配");
            welfare.run();
        }
    }

    private Object badgeRequest(String name, long presenter) throws ReflectiveOperationException {
        Object body = loader.loadClass("com.duowan.HUYA." + name).getConstructor().newInstance();
        body.getClass().getField("tId").set(body, userId());
        body.getClass().getField("lPid").setLong(body, presenter);
        return body;
    }

    private void signBadge(long presenter, String target, Runnable finished) {
        try {
            Object body = badgeRequest("FansSignReq", presenter);
            String attempt = "badge-sign/" + activeDay + "/" + presenter;
            if (!claim(attempt)) {
                failed++;
                log(BADGE_SIGN, target, "未确认", "已提交过，当前状态未确认，不重复打卡");
                finished.run();
                return;
            }
            request("com.duowan.kiwi.inputbar.impl.wup.InputBarWupFunction$SetFansSign", body,
                    BADGE_SIGN, target, response -> {
                try {
                    if (response != null && ((Number) value(response, "iCode")).intValue() == 0) {
                        signed++;
                        log(BADGE_SIGN, target, "成功", "收到服务端成功回执");
                    } else if (response != null && ((Number) value(response, "iCode")).intValue() == -1
                            && "请勿重复打卡".equals(value(response, "sMsg"))) {
                        badgeAlreadySigned(target);
                    } else {
                        failed++;
                        if (response == null) {
                            log(BADGE_SIGN, target, "未完成", "无有效回执，下次先复核打卡状态");
                        } else {
                            Object message = value(response, "sMsg");
                            if (!(message instanceof String)) throw new IllegalArgumentException("Invalid response message");
                            store.release(attempt);
                            log(BADGE_SIGN, target, "未完成", "服务端返回代码 "
                                    + value(response, "iCode") + "：" + message);
                        }
                    }
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    failed++;
                    log(BADGE_SIGN, target, "失败", "回执结构不匹配");
                }
                finished.run();
            });
        } catch (ReflectiveOperationException failure) {
            failed++;
            log(BADGE_SIGN, target, "失败", "请求接口不匹配");
            finished.run();
        }
    }

    private void badgeAlreadySigned(String target) {
        alreadySigned++;
        log(BADGE_SIGN, target, "已打卡", "服务端确认今日已经打卡");
    }

    private boolean badgeTasksActive(String day) {
        try {
            return afterBadges != null && day.equals(dayKey(account))
                    && prefs.getBoolean(GlassSettings.KEY_AUTO_SIGN, false) && loggedInUid() == account;
        } catch (ReflectiveOperationException | RuntimeException failure) {
            return false;
        }
    }

    private void checkBadgeWelfare(String day, long presenter) {
        String target = "主播 " + presenter;
        badgeWelfareRequest(day, presenter, "queryFansGroupTaskInfo", 3, (body, code) -> {
            Object welfare = body.get(7);
            long state = welfare instanceof TaskWire.Struct ? ((TaskWire.Struct) welfare).number(0) : -1;
            if (code != 0 || body.number(0) != 0 || body.number(1) != account
                    || body.number(2) != presenter || state < 1 || state > GRAIN_CLAIMED) {
                failed++;
                log(BADGE_GRAIN, target, "未确认", "未取得有效的每日福利状态");
            } else if (state == GRAIN_CLAIMABLE) {
                badgeWelfareRequest(day, presenter, "operateFansBox", CLAIM_FANS_BOX, (reply, result) -> {
                    if (result == 0 && reply.number(0) == 0 && reply.number(1) == presenter
                            && reply.number(3) == GRAIN_CLAIMED && reply.number(5) == 10) {
                        log(BADGE_GRAIN, target, "成功", "服务端确认领取 10 个虎粮");
                    } else {
                        failed++;
                        log(BADGE_GRAIN, target, "未确认", "未取得成功回执，下次先复核领取状态");
                    }
                    nextBadge();
                });
                return;
            } else if (state == GRAIN_CLAIMED) {
                log(BADGE_GRAIN, target, "已领取", "服务端确认今日已经领取");
            } else {
                if (state == 2) failed++;
                log(BADGE_GRAIN, target, "跳过", "每日福利暂不可领取");
            }
            nextBadge();
        });
    }

    private void badgeWelfareRequest(String day, long presenter, String function, int requestFlag,
                                     NativeTaskRunner.Reply reply) {
        handler.postDelayed(() -> {
            if (!badgeTasksActive(day)) {
                finishBadges();
                return;
            }
            if ("operateFansBox".equals(function) && !claim("badge-welfare/" + day + "/" + presenter)) {
                reply.complete(new TaskWire.Struct(), -1);
                return;
            }
            AtomicBoolean delivered = new AtomicBoolean();
            NativeTaskRunner.Reply finish = (response, code) -> {
                if (!delivered.compareAndSet(false, true)) return;
                try {
                    if (badgeTasksActive(day)) reply.complete(response, code);
                    else finishBadges();
                } catch (RuntimeException | LinkageError failure) {
                    log(BADGE_GRAIN, "", "失败", "福利回执无法处理，结束本轮粉丝牌任务");
                    finishBadges();
                }
            };
            handler.postDelayed(() -> finish.complete(new TaskWire.Struct(), -1), 20000L);
            taskClient.send(account, "wupui", function, new TaskWire.Struct()
                    .field(1, presenter).field(2, requestFlag),
                    (response, code) -> handler.post(() -> finish.complete(response, code)));
        }, requestInterval);
    }

    private void startGiftChecks(long uid, String day) {
        if (giftCheck != null || !day.equals(activeDay)) return;
        giftCheck = new Runnable() {
            @Override public void run() {
                if (giftCheck == this) checkGifts(uid, day, this);
            }
        };
        giftCheck.run();
    }

    private void checkGifts(long uid, String day, Runnable check) {
        long delay = GIFT_CHECK_INTERVAL;
        try {
            if (!day.equals(dayKey(uid)) || !giftAllowed() || loggedInUid() != uid) {
                giftCheck = null;
                if (giftRound != null) continueGiftRound(giftRound);
                return;
            }
            if (isIdle() && nativeTasks.isIdle()) beginGifts(uid, day);
            else delay = requestInterval;
        } catch (ReflectiveOperationException | RuntimeException failure) {
            log("免费虎粮", "", "失败", "库存检查未启动：" + failure.getClass().getSimpleName());
        }
        handler.postDelayed(check, delay);
    }

    private void beginGifts(long uid, String day) {
        Map<Long, Integer> rooms = AutomationRules.parse(prefs.getString(GlassSettings.KEY_GIFT_ROOMS, ""));
        if (rooms.isEmpty()) log("免费虎粮", "", "跳过", "未配置直播间和数量");
        else {
            if (store.hasClaim("dice-grain-started/" + day)) {
                List<AutomationRules.GrainPart> plan = store.diceGrainPlan(day);
                if (plan != null && AutomationRules.matchesGrainPlan(plan, rooms)) {
                    for (AutomationRules.GrainPart part : plan) rooms.remove(part.room);
                }
            }
            for (Map.Entry<Long, Integer> room : rooms.entrySet()) {
                if (!attemptedGiftRooms.contains(room.getKey())) giftRooms.add(room);
            }
            if (giftRooms.isEmpty()) return;
            giftActive = true;
            giftRound = new GiftRound(uid, day);
            nextGiftRoom(giftRound);
        }
    }

    void sendDiceGrain(long uid, String day, AutomationRules.GrainPart part,
                       java.util.function.BooleanSupplier allowed, NativeTaskRunner.ActionReply reply) {
        if (giftActive || diceSender != null && diceSender.diceGiftReply != null) {
            reply.complete(false, "其他免费虎粮任务仍在处理，本轮不并发送礼");
            return;
        }
        if (!allowed.getAsBoolean()) { reply.complete(false, "任务开关已关闭"); return; }
        if (diceSender == null) diceSender = new DailyAutomation(module, prefs, loader);
        DailyAutomation sender = diceSender;
        sender.context = context; sender.store = store; sender.account = uid;
        sender.activeDay = uid + "/" + day; sender.grainBudget = -1;
        sender.requestInterval = NativeTaskCatalog.intervalSeconds(
                prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30")) * 1000L;
        sender.diceGiftAllowed = allowed; sender.diceGrainPart = part;
        sender.diceGiftReply = reply;
        sender.giftRound = new GiftRound(uid, sender.activeDay);
        sender.giftRooms.add(new java.util.AbstractMap.SimpleImmutableEntry<>(part.room, part.count));
        try {
            sender.installCallbacks();
            sender.nextGiftRoom(sender.giftRound);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            sender.finishDiceGift(false, "免费虎粮接口不可用");
        }
        handler.postDelayed(() -> {
            if (sender.diceGiftReply == reply) sender.finishDiceGift(false, "赠送结果未确认，不自动重发");
        }, 85000L + sender.requestInterval * 4);
    }

    private void finishDiceGift(boolean success, String detail) {
        NativeTaskRunner.ActionReply reply = diceGiftReply;
        if (reply == null) return;
        diceGiftReply = null; diceGiftAllowed = () -> false;
        giftRound = null;
        giftRooms.clear(); requests.clear();
        for (GiftLimit limit : guardedGifts.values()) limit.blocked = true;
        reply.complete(success, detail);
    }

    private Object service(String className) throws ReflectiveOperationException {
        Class<?> type = loader.loadClass(className);
        return HuyaComponents.get(loader, type);
    }

    private Object propsModule() throws ReflectiveOperationException {
        Class<?> type = loader.loadClass("com.duowan.kiwi.props.api.component.IPropsComponent");
        return type.getMethod("getPropsModule").invoke(service(type.getName()));
    }

    private boolean isGiftRoundCurrent(GiftRound round) {
        if (giftRound != round || !round.day.equals(dayKey(round.account))) return false;
        try {
            return loggedInUid() == round.account && giftAllowed() && giftRound == round;
        } catch (ReflectiveOperationException | RuntimeException failure) {
            return false;
        }
    }

    private boolean continueGiftRound(GiftRound round) {
        if (giftRound != round) return false;
        if (isGiftRoundCurrent(round)) return true;
        String reason = "账号、日期或任务开关已变更，未继续赠送";
        log("免费虎粮", "", "取消", reason);
        skipRemainingGifts(reason);
        finishDiceGift(false, reason);
        return false;
    }

    private void nextGiftRoomLater(GiftRound round, long delay) {
        handler.postDelayed(() -> nextGiftRoom(round), delay);
    }

    private void nextGiftRoom(GiftRound round) {
        if (!continueGiftRound(round)) return;
        Map.Entry<Long, Integer> room = giftRooms.poll();
        if (room == null) {
            giftActive = false;
            giftRound = null;
            if (diceGiftReply != null) {
                finishDiceGift(false, "本次未收到免费虎粮成功回执，不领取骰子奖励");
                return;
            }
            log("免费虎粮", "", "结束", "本轮任务结束，请按各房间记录核对结果");
            return;
        }
        String target = "直播间 " + room.getKey();
        try {
            Object query = loader.loadClass(
                    "com.duowan.kiwi.liveinfo.wupfunction.WupFunction$GameLiveWupFunction$getLivingInfo")
                    .getConstructor(long.class, long.class, long.class, long.class, String.class, String.class)
                    .newInstance(0L, 0L, 0L, room.getKey(), "", "");
            sendRequest(query, "直播间信息", target, round, response -> {
                try {
                    Object notice = response == null ? null : value(response, "tNotice");
                    if (notice != null) {
                        log("直播间信息", target, "已解析", "服务端返回房间号 " + value(notice, "iRoomId")
                                + "；主播信息" + (((Number) value(notice, "lPresenterUid")).longValue() > 0 ? "有效" : "缺失"));
                    }
                    if (notice == null || !AutomationRules.isResolvedRoom(room.getKey(),
                            ((Number) value(notice, "iRoomId")).longValue(),
                            ((Number) value(notice, "lPresenterUid")).longValue())) {
                        log("免费虎粮", target, "跳过", "无法核实房间对应的主播，没有发送礼物");
                        nextGiftRoomLater(round, 1200L);
                        return;
                    }
                    long presenter = ((Number) value(notice, "lPresenterUid")).longValue();
                    String key = dailyGiftKey(round, presenter);
                    if (diceGrainPart != null) {
                        if (store.hasClaim(grainPartKey(key, diceGrainPart.number))) {
                            finishAlreadySubmittedGrain(round, diceGrainPart);
                            return;
                        }
                        if (!hasPreviousGrainAttempt(round, key, diceGrainPart)) {
                            finishDiceGift(false, "无法确认上一笔的赠送对象，未继续赠送");
                            return;
                        }
                    } else if (store.hasClaim(key)) {
                        log("免费虎粮", target, "跳过", "今日已提交过该主播的赠送");
                        attemptedGiftRooms.add(room.getKey());
                        nextGiftRoomLater(round, 1200L);
                        return;
                    }
                    fetchGrain(round, room.getKey(), presenter, room.getValue());
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    log("免费虎粮", target, "失败", "送礼接口不匹配，没有继续发送");
                    nextGiftRoomLater(round, 1200L);
                }
            });
        } catch (ReflectiveOperationException | RuntimeException failure) {
            log("免费虎粮", target, "失败", "准备送礼失败：" + failure.getClass().getSimpleName());
            nextGiftRoomLater(round, 1200L);
        }
    }

    private void fetchGrain(GiftRound round, long room, long presenter, int count)
            throws ReflectiveOperationException {
        Object body = loader.loadClass("com.duowan.HUYA.GetUserCardPackageReq").getConstructor().newInstance();
        body.getClass().getField("tId").set(body, userId());
        body.getClass().getField("lPid").setLong(body, presenter);
        body.getClass().getField("lHomeOwnerUid").setLong(body, presenter);
        body.getClass().getField("eTempleteType").setInt(body,
                cardPackageOption("ryxq.mfg", "ryxq.ozb", "d"));
        body.getClass().getField("eSource").setInt(body,
                cardPackageOption("ryxq.nh3", "ryxq.nn2", "f"));
        String target = "直播间 " + room;
        request("com.duowan.biz.wup.gamelive.GameLiveWupFunction$z", body, "免费库存", target, round, response -> {
            try {
                Object entries = response == null ? null : value(response, "vUserCardItemCountLists");
                if (!(entries instanceof List)) {
                    log("免费虎粮", target, "跳过", "未收到有效的免费背包库存，没有发送礼物");
                    nextGiftRoomLater(round, 1200L);
                    return;
                }
                long free = 0;
                boolean found = false;
                for (Object entry : (List<?>) entries) {
                    if (((Number) value(entry, "iItemType")).intValue() != 4) continue;
                    if (found) throw new IllegalStateException("Ambiguous inventory");
                    found = true;
                    free = ((Number) value(entry, "iItemCount")).longValue();
                }
                grainBudget = free;
                log("免费库存", target, "成功", "服务端返回可用免费虎粮 " + Math.max(0, free));
                int required = diceGrainPart == null ? Math.max(1, count) : diceGrainPart.remaining;
                int amount = AutomationRules.giftCount(count, required, free);
                if (amount == 0) {
                    log("免费虎粮", target, "跳过", free < required
                            ? "免费库存不足，需要 " + required + "，当前可用 " + Math.max(0, free)
                            : "免费库存超出单笔支持范围");
                    nextGiftRoomLater(round, 1200L);
                } else prepareGrain(round, room, presenter, amount, free);
            } catch (ReflectiveOperationException | RuntimeException failure) {
                Throwable cause = failure.getCause() == null ? failure : failure.getCause();
                log("免费虎粮", target, "失败", "免费库存或送礼接口不匹配："
                        + cause.getClass().getSimpleName() + " · " + cause.getMessage());
                nextGiftRoomLater(round, 1200L);
            }
        });
    }

    private int cardPackageOption(String legacyClass, String currentClass, String field)
            throws ReflectiveOperationException {
        try {
            return cardPackageOption(legacyClass, field);
        } catch (ClassNotFoundException | NoSuchFieldException | NoSuchMethodException oldOptionAbsent) {
            return cardPackageOption(currentClass, field);
        }
    }

    private int cardPackageOption(String className, String field) throws ReflectiveOperationException {
        Class<?> type = loader.loadClass(className);
        Object option = type.getField(field).get(null);
        return ((Number) type.getMethod("a").invoke(option)).intValue();
    }

    private void installGiftGuard() throws ReflectiveOperationException {
        if (giftGuardInstalled) return;
        Class<?> params = loader.loadClass("com.duowan.kiwi.props.api.request.SendGiftParam");
        Method create = loader.loadClass("com.duowan.kiwi.props.impl.request.SendGiftService")
                .getDeclaredMethod("createSendGiftReq", params, String.class, long.class);
        module.hook(create).setExceptionMode(XposedModule.ExceptionMode.PASSTHROUGH).intercept(chain -> {
            GiftLimit limit = guardedGifts.get(chain.getArg(0));
            if (limit == null) return chain.proceed();
            try {
                Object request = chain.proceed();
                Object pay = value(request, "tPayPloy");
                boolean valid = !limit.blocked && isGiftRoundCurrent(limit.round)
                    && ((Number) value(request, "lGiftUid")).longValue() == limit.presenter
                    && ((Number) value(request, "lRoomUid")).longValue() == limit.presenter
                    && ((Number) value(request, "iItemCount")).intValue() == limit.count
                    && pay != null && AutomationRules.isFreeGrain(
                            ((Number) value(request, "iItemType")).intValue(), limit.count,
                            Math.min(limit.freeCount, grainBudget),
                            ((Number) value(pay, "iPayPloy")).intValue(),
                            ((Number) value(pay, "lPayCount")).longValue(),
                            ((Number) value(pay, "lNewCoinDeduction")).longValue());
                if (valid) return request;
            } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
                // Missing or changed fields must not turn into a paid request.
            }
            limit.blocked = true;
            log("免费虎粮", "", "阻止发送", "最终请求不符合免费库存或目标主播限制");
            throw new CancellationException("Automatic gift must use free grain only");
        });
        giftGuardInstalled = true;
    }

    private void prepareGrain(GiftRound round, long room, long presenter, int count, long freeCount) {
        handler.postDelayed(() -> {
            if (!continueGiftRound(round)) return;
            try { executePrepareGrain(round, room, presenter, count, freeCount); }
            catch (ReflectiveOperationException | RuntimeException failure) {
                log("免费虎粮", "", "失败", "道具接口不可用，未送礼");
                nextGiftRoom(round);
            }
        }, requestInterval);
    }

    private void executePrepareGrain(GiftRound round, long room, long presenter, int count, long freeCount)
            throws ReflectiveOperationException {
        Class<?> propsType = loader.loadClass("com.duowan.kiwi.props.api.component.IPropsModule");
        Object prop = propsType.getMethod("getPropAnyWay", int.class).invoke(propsModule(), 4);
        Class<?> propType = loader.loadClass("com.duowan.kiwi.props.api.bean.PropItem");
        if (prop != null && Boolean.TRUE.equals(propType.getMethod("isTigerFoodId").invoke(prop))) {
            sendGrain(round, room, presenter, count, freeCount, prop);
            return;
        }
        Class<?> builderType = loader.loadClass("com.duowan.kiwi.props.api.request.SendGiftParam$Builder");
        Object builder = builderType.getConstructor(int.class, int.class).newInstance(4, count);
        builderType.getMethod("roomUid", long.class).invoke(builder, presenter);
        builderType.getMethod("receiveUid", long.class).invoke(builder, presenter);
        Object partial = builderType.getMethod("build").invoke(builder);
        Class<?> continuationType = loader.loadClass("kotlin.coroutines.Continuation");
        Object empty = loader.loadClass("kotlin.coroutines.EmptyCoroutineContext").getField("INSTANCE").get(null);
        final boolean[] finished = {false};
        String target = "直播间 " + room;
        Result accept = info -> {
            if (finished[0]) return;
            finished[0] = true;
            if (!continueGiftRound(round)) return;
            try {
                if (info == null || !propType.isInstance(info)
                        || !Boolean.TRUE.equals(propType.getMethod("isTigerFoodId").invoke(info))) {
                    log("虎粮道具信息", target, "失败", "未获取到有效的虎粮道具资料，没有送礼");
                    nextGiftRoomLater(round, 1200L);
                } else {
                    log("虎粮道具信息", target, "成功", "已核实为虎粮道具");
                    sendGrain(round, room, presenter, count, freeCount, info);
                }
            } catch (ReflectiveOperationException | RuntimeException failure) {
                Throwable cause = failure.getCause() == null ? failure : failure.getCause();
                log("免费虎粮", target, "失败", cause.getClass().getSimpleName() + " · " + cause.getMessage());
                nextGiftRoomLater(round, 1200L);
            }
        };
        Object continuation = Proxy.newProxyInstance(loader, new Class<?>[]{continuationType}, (proxy, method, args) -> {
            if ("getContext".equals(method.getName())) return empty;
            if ("resumeWith".equals(method.getName())) {
                Object info = args == null ? null : args[0];
                handler.post(() -> accept.accept(info));
                return null;
            }
            if ("toString".equals(method.getName())) return "FuckADGrainMetadata";
            if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
            if ("equals".equals(method.getName())) return proxy == args[0];
            return null;
        });
        log("虎粮道具信息", target, "请求已发出", "后台查询虎粮资料，不打开直播间");
        Object returned = loader.loadClass("com.duowan.kiwi.props.impl.request.util.SendGiftConfirmDialogUtilKt")
                .getMethod("access$fetchGiftBasicInfo", partial.getClass(), continuationType)
                .invoke(null, partial, continuation);
        Object suspended = loader.loadClass("kotlin.coroutines.intrinsics.IntrinsicsKt")
                .getMethod("getCOROUTINE_SUSPENDED").invoke(null);
        if (returned != suspended) handler.post(() -> accept.accept(returned));
        handler.postDelayed(() -> {
            if (!finished[0]) {
                finished[0] = true;
                if (!continueGiftRound(round)) return;
                log("虎粮道具信息", target, "结果未确认", "道具资料查询超时，没有送礼");
                nextGiftRoomLater(round, 1200L);
            }
        }, 30000L);
    }

    private void sendGrain(GiftRound round, long room, long presenter, int count, long freeCount, Object prop) {
        handler.postDelayed(() -> {
            if (!continueGiftRound(round)) return;
            try { executeSendGrain(round, room, presenter, count, freeCount, prop); }
            catch (ReflectiveOperationException | RuntimeException failure) {
                log("免费虎粮", "", "未确认", "送礼接口不可用，本轮停止");
                skipRemainingGifts("送礼接口异常，未继续发送");
                giftActive = false;
                finishDiceGift(false, "送礼接口不可用");
            }
        }, requestInterval);
    }

    private void executeSendGrain(GiftRound round, long room, long presenter, int count, long freeCount, Object prop)
            throws ReflectiveOperationException {
        installGiftGuard();
        Class<?> propType = loader.loadClass("com.duowan.kiwi.props.api.bean.PropItem");
        Object pay = loader.loadClass("com.duowan.kiwi.props.api.utils.SendGiftPayPloyUtil")
                .getMethod("createPayPloy", float.class, float.class, long.class, boolean.class)
                .invoke(null, 0f, 0f, 0L, true);
        if (!AutomationRules.isFreeGrain(4, count, Math.min(freeCount, grainBudget),
                ((Number) value(pay, "iPayPloy")).intValue(),
                ((Number) value(pay, "lPayCount")).longValue(),
                ((Number) value(pay, "lNewCoinDeduction")).longValue())) {
            throw new IllegalStateException("Free payment unavailable");
        }
        Class<?> builderType = loader.loadClass("com.duowan.kiwi.props.api.request.SendGiftParam$Builder");
        Object builder = builderType.getConstructor(int.class, int.class).newInstance(4, count);
        builderType.getMethod("giftInfo", propType).invoke(builder, prop);
        builderType.getMethod("roomUid", long.class).invoke(builder, presenter);
        builderType.getMethod("receiveUid", long.class).invoke(builder, presenter);
        builderType.getMethod("payPloy", pay.getClass()).invoke(builder, pay);
        Object params = builderType.getMethod("build").invoke(builder);
        GiftLimit limit = new GiftLimit(round, presenter, count, freeCount);
        guardedGifts.put(params, limit);
        String target = "直播间 " + room + " · " + count + " 个免费虎粮";
        Class<?> callbackType = loader.loadClass("com.duowan.kiwi.props.api.request.ISendGiftCallback");
        AutomationRules.GrainPart part = diceGrainPart;
        final boolean[] finished = {false};
        Object callback = Proxy.newProxyInstance(loader, new Class<?>[]{callbackType}, (proxy, method, args) -> {
            if ("onResult".equals(method.getName())) {
                Object result = args == null || args.length == 0 ? null : args[0];
                handler.post(() -> {
                    boolean success = result != null && result.getClass().getName().equals(
                            "com.duowan.kiwi.props.api.request.SendGiftResult$Success");
                    boolean recorded = !success || part == null || claim(
                            AutomationRules.confirmedGrainPart(round.day, part.room, part.number));
                    if (finished[0]) return;
                    finished[0] = true;
                    limit.blocked = true;
                    if (!continueGiftRound(round)) {
                        log("免费虎粮", target, "结果未确认", "任务已中断，请核对原账号的赠送记录");
                        return;
                    }
                    if (success) {
                        grainBudget -= count;
                        log("免费虎粮", target, "成功", "收到虎牙送礼成功回执");
                        finishDiceGift(true, recorded
                                ? "已收到 " + count + " 个免费虎粮的赠送回执，等待骰子任务进度复核"
                                : "已收到赠送回执，回执记录写入失败，查询虎牙任务进度");
                    } else {
                        log("免费虎粮", target, "未完成", result == null ? "回执缺失" : result.getClass().getSimpleName());
                        if (part != null) {
                            finishDiceGift(true, "这笔赠送缺少成功回执，查询虎牙任务进度");
                            return;
                        }
                        skipRemainingGifts("前一笔赠送未成功，本轮停止后续赠送");
                        log("免费虎粮", "", "停止", "本次送礼未成功，保留剩余免费虎粮");
                    }
                    nextGiftRoomLater(round, 1500L);
                });
                return null;
            }
            if ("toString".equals(method.getName())) return "FuckADFreeGrainCallback";
            if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
            if ("equals".equals(method.getName())) return proxy == args[0];
            return null;
        });
        Class<?> serviceType = loader.loadClass("com.duowan.kiwi.props.api.request.ISendGiftService");
        Method send = serviceType.getMethod("sendGiftCompat", params.getClass(), callbackType);
        Object giftService = service(serviceType.getName());
        if (giftService == null) throw new IllegalStateException("Gift service unavailable");
        if (!continueGiftRound(round)) return;
        String key = dailyGiftKey(round, presenter);
        if (part != null) {
            if (!hasPreviousGrainAttempt(round, key, part)) {
                finishDiceGift(false, "无法确认上一笔的赠送对象，未继续赠送");
                return;
            }
            key = grainPartKey(key, part.number);
        }
        boolean reserved = part != null && part.number == 1
                ? store.claimFirstGrainPart(key, round.day, part.room) : claim(key);
        if (!reserved) {
            limit.blocked = true;
            if (part != null && store.hasClaim(key)) {
                finishAlreadySubmittedGrain(round, part);
                return;
            }
            log("免费虎粮", target, "跳过", "今日已经提交过该主播的赠送，不重复发送");
            nextGiftRoomLater(round, 1200L);
            return;
        }
        if (diceGrainPart == null) attemptedGiftRooms.add(room);
        log("免费虎粮", target, "请求已发出", "仅使用背包免费库存，等待回执");
        send.invoke(giftService, params, callback);
        handler.postDelayed(() -> {
            if (!finished[0]) {
                finished[0] = true;
                limit.blocked = true;
                if (giftRound != round) return;
                if (part != null) {
                    log("免费虎粮", target, "结果未确认", "等待回执超时，查询虎牙任务进度");
                    finishDiceGift(true, "这笔赠送已提交，回执超时，查询虎牙任务进度");
                    return;
                }
                skipRemainingGifts("前一笔赠送结果未确认，本轮停止后续赠送");
                log("免费虎粮", target, "结果未确认", "等待回执超时，停止后续赠送，不自动重发");
            }
        }, 30000L);
    }

    private String dailyGiftKey(GiftRound round, long presenter) {
        return "gift-send/" + round.day + "/" + presenter;
    }

    private static String grainPartKey(String giftKey, int number) {
        return number == 1 ? giftKey : giftKey + "/part/" + number;
    }

    private boolean hasPreviousGrainAttempt(GiftRound round, String giftKey, AutomationRules.GrainPart part) {
        int previous = part.number - 1;
        return previous == 0 || (store.hasClaim(grainPartKey(giftKey, previous))
                && (previous != 1 || ownsFirstGrainPart(round, part.room)));
    }

    private void finishAlreadySubmittedGrain(GiftRound round, AutomationRules.GrainPart part) {
        if (part.number > 1 || ownsFirstGrainPart(round, part.room)) {
            finishDiceGift(true, "该笔赠送已提交，查询虎牙任务进度");
        } else finishDiceGift(false, "已有赠送记录，无法确认是否属于拆分计划，保留剩余额度");
    }

    private boolean ownsFirstGrainPart(GiftRound round, long room) {
        if (store.hasClaim("dice-grain-room/" + round.day + "/" + room)
                || store.hasClaim(AutomationRules.confirmedGrainPart(round.day, room, 1))) return true;
        if (!store.hasClaim("dice-grain-started/" + round.day)) return false;
        // Older journals only identify the first part when the whole split belonged to one room.
        List<AutomationRules.GrainPart> saved = store.diceGrainPlan(round.day);
        return saved != null && saved.size() == 3 && saved.stream().allMatch(part -> part.room == room);
    }

    private void skipRemainingGifts(String reason) {
        giftActive = false;
        giftRound = null;
        Map.Entry<Long, Integer> pending;
        while ((pending = giftRooms.poll()) != null) {
            String amount = pending.getValue() == AutomationRules.ALL_FREE_GRAIN
                    ? "剩余免费虎粮" : pending.getValue() + " 个免费虎粮";
            log("免费虎粮", "直播间 " + pending.getKey() + " · " + amount, "未执行", reason);
        }
    }

    private boolean giftAllowed() {
        return diceGiftAllowed != null ? diceGiftAllowed.getAsBoolean()
                : prefs != null && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false);
    }

    private void finishBadges() {
        badges.clear();
        Runnable next = afterBadges;
        afterBadges = null;
        if (next != null) {
            queuedRequests++;
            handler.postDelayed(() -> {
                queuedRequests--;
                next.run();
            }, requestInterval);
        }
    }

    boolean isIdle() {
        return badges.isEmpty() && giftRooms.isEmpty() && requests.isEmpty()
                && !giftActive && afterBadges == null && queuedRequests == 0
                && (diceSender == null || diceSender.diceGiftReply == null);
    }
}
