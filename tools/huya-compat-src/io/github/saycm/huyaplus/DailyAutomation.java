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
    static final String SYNC_LOGS = "io.github.saycm.huyaplus.SYNC_LOGS";
    private final XposedModule module;
    private final SharedPreferences prefs;
    private final ClassLoader loader;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<Object, Pending> requests = Collections.synchronizedMap(new IdentityHashMap<>());
    private final Set<String> seen = new HashSet<>();
    private final ArrayDeque<Long> badges = new ArrayDeque<>();
    private final ArrayDeque<Map.Entry<Long, Integer>> giftRooms = new ArrayDeque<>();
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
    private String activeDay;
    private int signed;
    private int alreadySigned;
    private int failed;
    private boolean giftActive;
    private DailyAutomation diceSender;
    private NativeTaskRunner.ActionReply diceGiftReply;
    private java.util.function.BooleanSupplier diceGiftAllowed;
    private String diceGiftKey;
    private Runnable afterBadges;
    private long requestInterval = 30000L;
    private boolean requestGap;
    private int queuedRequests;
    private boolean syncFailureLogged;

    private static final class GiftLimit {
        final long presenter;
        final int count;
        final long freeCount;
        volatile boolean blocked;
        GiftLimit(long presenter, int count, long freeCount) {
            this.presenter = presenter; this.count = count; this.freeCount = freeCount;
        }
    }

    private interface Result { void accept(Object response); }
    private static final class Pending {
        final Result callback;
        final String task;
        final String target;
        final long account;
        Pending(Result callback, String task, String target, long account) {
            this.callback = callback; this.task = task; this.target = target; this.account = account;
        }
    }

    DailyAutomation(XposedModule module, SharedPreferences prefs, ClassLoader loader) {
        this.module = module; this.prefs = prefs; this.loader = loader;
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
                    if (SYNC_LOGS.equals(intent.getAction())) requestLogSync();
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
        }
        if (polling) return;
        polling = true;
        pollLogin(0);
    }

    private void pollLogin(int attempt) {
        try {
            long uid = loggedInUid();
            if (uid > 0) {
                polling = false;
                try { nativeTasks.onReady(uid, () -> handler.postDelayed(
                        () -> runOnce(uid), requestInterval)); }
                catch (RuntimeException | LinkageError failure) {
                    log("虎牙任务中心", "", "失败", "新任务接口不可用，未影响原有每日任务");
                    runOnce(uid);
                }
                return;
            }
        } catch (ReflectiveOperationException | RuntimeException failure) {
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
        Object component = loader.loadClass("ryxq.xxe").getMethod("i", Class.class).invoke(null, type);
        Object login = type.getMethod("getLoginModule").invoke(component);
        Class<?> loginType = loader.loadClass("com.duowan.kiwi.base.login.api.ILoginModule");
        if (!Boolean.TRUE.equals(loginType.getMethod("isLogin").invoke(login))) return 0;
        return ((Number) loginType.getMethod("getUid").invoke(login)).longValue();
    }

    private void runOnce(long uid) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
        format.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        String day = uid + "/" + format.format(new Date());
        if (!seen.add(day)) return;
        boolean sign = prefs != null && prefs.getBoolean(GlassSettings.KEY_AUTO_SIGN, false);
        boolean gift = prefs != null && prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false);
        if (!sign && !gift) {
            if (claim("disabled/" + day)) log("每日任务", "", "跳过", "两个自动任务开关均未开启");
            return;
        }
        boolean runSign = sign && claim("sign/" + day);
        boolean runGift = gift && claim("gift/" + day);
        if (!runSign && !runGift) {
            log("每日任务", "", "跳过", "今日已触发过，防止重复执行；未确认结果请查看之前的日志");
            return;
        }
        account = uid;
        activeDay = day;
        badges.clear();
        giftRooms.clear();
        requests.clear();
        for (GiftLimit limit : guardedGifts.values()) limit.blocked = true;
        grainBudget = -1;
        signed = 0;
        alreadySigned = 0;
        failed = 0;
        try { requestInterval = NativeTaskCatalog.intervalSeconds(
                prefs.getString(GlassSettings.KEY_TASK_INTERVAL, "30")) * 1000L; }
        catch (IllegalArgumentException failure) {
            log("配置", "", "失败", "执行间隔无效，未执行每日任务");
            return;
        }
        log("每日任务", "", "开始", "今日首次打开，登录已就绪");
        try {
            installCallbacks();
            Runnable gifts = () -> {
                if (runGift) beginGifts();
                else log("免费虎粮", "", "跳过", gift ? "今日已触发过，不重复执行" : "功能未开启");
            };
            if (runSign) {
                afterBadges = gifts;
                fetchBadges();
            } else {
                log("粉丝牌打卡", "", "跳过", sign ? "今日已触发过，不重复执行" : "功能未开启");
                gifts.run();
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            log("每日任务", "", "失败", "接口初始化失败：" + failure.getClass().getSimpleName());
            finishBadges();
        }
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
                ArrayList<Bundle> tasks = store.tasks();
                Bundle taskBatch = new Bundle();
                taskBatch.putParcelableArrayList("tasks", tasks);
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
            module.log(Log.WARN, "FuckAD", "Log display sync unavailable; records remain in Huya", failure);
            if (!syncFailureLogged) {
                syncFailureLogged = true;
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
        Method success = loader.loadClass("ryxq.jd8").getDeclaredMethod("onResponse", response, boolean.class);
        module.hook(success).intercept(chain -> {
            Pending pending = requests.get(chain.getThisObject());
            if (pending == null) return chain.proceed();
            if (Boolean.TRUE.equals(chain.getArg(1))) return null;
            requests.remove(chain.getThisObject());
            Object data = chain.getArg(0);
            handler.post(() -> complete(pending, data, false));
            return null;
        });
        Class<?> error = loader.loadClass("com.huya.mtp.data.exception.DataException");
        Method failedMethod = loader.loadClass("ryxq.oe6").getDeclaredMethod("onError", error, boolean.class);
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
            if (account != pending.account || loggedInUid() != pending.account) {
                log(pending.task, pending.target, "取消", "账号已退出或切换，不继续执行");
                return;
            }
            if (timedOut) log(pending.task, pending.target, "结果未确认", "请求超时，不自动重复发送");
            pending.callback.accept(response);
        } catch (ReflectiveOperationException | RuntimeException failure) {
            log(pending.task, pending.target, "失败", "处理回执失败：" + failure.getClass().getSimpleName());
        }
    }

    private void request(String requestClass, Object body, String task, String target, Result result)
            throws ReflectiveOperationException {
        Object request = loader.loadClass(requestClass).getConstructor(body.getClass()).newInstance(body);
        sendRequest(request, task, target, result);
    }

    private void sendRequest(Object request, String task, String target, Result result)
            throws ReflectiveOperationException {
        if (requestGap) {
            queuedRequests++;
            handler.postDelayed(() -> {
                queuedRequests--;
                try { executeRequest(request, task, target, result); }
                catch (ReflectiveOperationException failure) { result.accept(null); }
            }, requestInterval);
        } else executeRequest(request, task, target, result);
    }

    private void executeRequest(Object request, String task, String target, Result result)
            throws ReflectiveOperationException {
        if (loggedInUid() != account) { result.accept(null); return; }
        if ("粉丝牌打卡".equals(task) && !prefs.getBoolean(GlassSettings.KEY_AUTO_SIGN, false)) {
            result.accept(null);
            return;
        }
        if (("直播间信息".equals(task) || "免费库存".equals(task)) && !giftAllowed()) {
            result.accept(null);
            return;
        }
        requestGap = true;
        Pending pending = new Pending(result, task, target, account);
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
                    Object channel = value(badge, "tChannelInfo");
                    long uid = channel == null ? 0 : ((Number) value(channel, "lUid")).longValue();
                    if (uid <= 0 || uid == account) {
                        log("粉丝牌打卡", "", "跳过", "粉丝牌缺少有效的主播信息");
                    } else if (unique.add(uid)) badges.add(uid);
                }
                log("粉丝牌列表", "", "成功", "获取 " + badges.size() + " 个已有粉丝牌");
                nextBadge();
            } catch (ReflectiveOperationException failure) {
                log("粉丝牌列表", "", "失败", "列表结构不匹配，未执行打卡");
                finishBadges();
            }
        });
    }

    private void nextBadge() {
        if (!prefs.getBoolean(GlassSettings.KEY_AUTO_SIGN, false)) {
            badges.clear();
            log("粉丝牌打卡", "", "取消", "功能已关闭，停止剩余打卡");
        }
        Long presenter = badges.poll();
        if (presenter == null) {
            log("粉丝牌打卡", "", "结束", "成功 " + signed + "，已打卡 " + alreadySigned
                    + "，失败或未确认 " + failed);
            finishBadges();
            return;
        }
        try {
            if (loggedInUid() != account) {
                log("粉丝牌打卡", "", "取消", "账号发生变化，剩余任务不执行");
                finishBadges();
                return;
            }
            Object body = loader.loadClass("com.duowan.HUYA.FansSignReq").getConstructor().newInstance();
            body.getClass().getField("tId").set(body, userId());
            body.getClass().getField("lPid").setLong(body, presenter);
            request("com.duowan.kiwi.inputbar.impl.wup.InputBarWupFunction$SetFansSign", body,
                    "粉丝牌打卡", "主播 " + presenter, response -> {
                try {
                    if (response != null && ((Number) value(response, "iCode")).intValue() == 0) {
                        signed++;
                        log("粉丝牌打卡", "主播 " + presenter, "成功", "收到服务端成功回执");
                    } else if (response != null && ((Number) value(response, "iCode")).intValue() == -1
                            && "请勿重复打卡".equals(value(response, "sMsg"))) {
                        alreadySigned++;
                        log("粉丝牌打卡", "主播 " + presenter, "已打卡", "服务端确认今日已经打卡，不再重复提交");
                    } else {
                        failed++;
                        log("粉丝牌打卡", "主播 " + presenter, "未完成",
                                response == null ? "无有效回执，不重复提交" : "服务端返回代码 "
                                        + value(response, "iCode") + "：" + value(response, "sMsg"));
                    }
                } catch (ReflectiveOperationException failure) {
                    failed++;
                    log("粉丝牌打卡", "主播 " + presenter, "失败", "回执结构不匹配");
                }
                handler.postDelayed(this::nextBadge, 1200L);
            });
        } catch (ReflectiveOperationException failure) {
            failed++;
            log("粉丝牌打卡", "主播 " + presenter, "失败", "请求接口不匹配");
            handler.postDelayed(this::nextBadge, 1200L);
        }
    }

    private void beginGifts() {
        if (!prefs.getBoolean(GlassSettings.KEY_AUTO_GIFT, false)) return;
        Map<Long, Integer> rooms = AutomationRules.parse(prefs.getString(GlassSettings.KEY_GIFT_ROOMS, ""));
        if (rooms.isEmpty()) log("免费虎粮", "", "跳过", "未配置直播间和数量");
        else {
            giftActive = true;
            giftRooms.addAll(rooms.entrySet());
            nextGiftRoom();
        }
    }

    void sendDiceGrain(long uid, String day, long room, String operationKey,
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
        sender.diceGiftAllowed = allowed; sender.diceGiftKey = operationKey;
        sender.diceGiftReply = reply;
        sender.giftRooms.add(new java.util.AbstractMap.SimpleImmutableEntry<>(room, 1));
        try {
            sender.installCallbacks();
            sender.nextGiftRoom();
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            sender.finishDiceGift(false, "免费虎粮接口不可用");
        }
        handler.postDelayed(() -> {
            if (sender.diceGiftReply == reply) sender.finishDiceGift(false, "赠送结果未确认，不自动重发");
        }, 85000L + sender.requestInterval * 3);
    }

    private void finishDiceGift(boolean success, String detail) {
        NativeTaskRunner.ActionReply reply = diceGiftReply;
        if (reply == null) return;
        diceGiftReply = null; diceGiftAllowed = () -> false;
        giftRooms.clear(); requests.clear();
        for (GiftLimit limit : guardedGifts.values()) limit.blocked = true;
        reply.complete(success, detail);
    }

    private Object service(String className) throws ReflectiveOperationException {
        Class<?> type = loader.loadClass(className);
        return loader.loadClass("ryxq.xxe").getMethod("i", Class.class).invoke(null, type);
    }

    private Object propsModule() throws ReflectiveOperationException {
        Class<?> type = loader.loadClass("com.duowan.kiwi.props.api.component.IPropsComponent");
        return type.getMethod("getPropsModule").invoke(service(type.getName()));
    }

    private void nextGiftRoom() {
        if (!giftAllowed()) {
            skipRemainingGifts("功能已关闭，剩余房间不再赠送");
            giftActive = false;
            finishDiceGift(false, "任务开关已关闭，未继续赠送");
            return;
        }
        Map.Entry<Long, Integer> room = giftRooms.poll();
        if (room == null) {
            giftActive = false;
            if (diceGiftReply != null) {
                finishDiceGift(false, "本次未收到免费虎粮成功回执，不领取骰子奖励");
                return;
            }
            log("免费虎粮", "", "结束", "本轮任务结束，请按各房间记录核对结果");
            return;
        }
        String target = "直播间 " + room.getKey();
        try {
            if (loggedInUid() != account) {
                log("免费虎粮", "", "取消", "账号发生变化，剩余房间不再执行");
                skipRemainingGifts("账号已改变，未继续赠送");
                return;
            }
            Object query = loader.loadClass(
                    "com.duowan.kiwi.liveinfo.wupfunction.WupFunction$GameLiveWupFunction$getLivingInfo")
                    .getConstructor(long.class, long.class, long.class, long.class, String.class, String.class)
                    .newInstance(0L, 0L, 0L, room.getKey(), "", "");
            sendRequest(query, "直播间信息", target, response -> {
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
                        handler.postDelayed(this::nextGiftRoom, 1200L);
                        return;
                    }
                    fetchGrain(room.getKey(), ((Number) value(notice, "lPresenterUid")).longValue(), room.getValue());
                } catch (ReflectiveOperationException | RuntimeException failure) {
                    log("免费虎粮", target, "失败", "送礼接口不匹配，没有继续发送");
                    handler.postDelayed(this::nextGiftRoom, 1200L);
                }
            });
        } catch (ReflectiveOperationException | RuntimeException failure) {
            log("免费虎粮", target, "失败", "准备送礼失败：" + failure.getClass().getSimpleName());
            handler.postDelayed(this::nextGiftRoom, 1200L);
        }
    }

    private void fetchGrain(long room, long presenter, int count) throws ReflectiveOperationException {
        Object body = loader.loadClass("com.duowan.HUYA.GetUserCardPackageReq").getConstructor().newInstance();
        body.getClass().getField("tId").set(body, userId());
        body.getClass().getField("lPid").setLong(body, presenter);
        body.getClass().getField("lHomeOwnerUid").setLong(body, presenter);
        Class<?> template = loader.loadClass("ryxq.mfg");
        Object templateMode = template.getField("d").get(null);
        body.getClass().getField("eTempleteType").setInt(body,
                ((Number) template.getMethod("a").invoke(templateMode)).intValue());
        Class<?> source = loader.loadClass("ryxq.nh3");
        Object sourceMode = source.getField("f").get(null);
        body.getClass().getField("eSource").setInt(body,
                ((Number) source.getMethod("a").invoke(sourceMode)).intValue());
        String target = "直播间 " + room;
        request("com.duowan.biz.wup.gamelive.GameLiveWupFunction$z", body, "免费库存", target, response -> {
            try {
                Object entries = response == null ? null : value(response, "vUserCardItemCountLists");
                if (!(entries instanceof List)) {
                    log("免费虎粮", target, "跳过", "未收到有效的免费背包库存，没有发送礼物");
                    handler.postDelayed(this::nextGiftRoom, 1200L);
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
                if (free < count) {
                    log("免费虎粮", target, "跳过", "免费库存不足，需要 " + count + "，当前可用 " + Math.max(0, free));
                    handler.postDelayed(this::nextGiftRoom, 1200L);
                } else prepareGrain(room, presenter, count, free);
            } catch (ReflectiveOperationException | RuntimeException failure) {
                Throwable cause = failure.getCause() == null ? failure : failure.getCause();
                log("免费虎粮", target, "失败", "免费库存或送礼接口不匹配："
                        + cause.getClass().getSimpleName() + " · " + cause.getMessage());
                handler.postDelayed(this::nextGiftRoom, 1200L);
            }
        });
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
                boolean valid = !limit.blocked && loggedInUid() == account
                    && giftAllowed()
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

    private void prepareGrain(long room, long presenter, int count, long freeCount) {
        handler.postDelayed(() -> {
            if (!giftAllowed()) { nextGiftRoom(); return; }
            try { executePrepareGrain(room, presenter, count, freeCount); }
            catch (ReflectiveOperationException | RuntimeException failure) {
                log("免费虎粮", "", "失败", "道具接口不可用，未送礼");
                nextGiftRoom();
            }
        }, requestInterval);
    }

    private void executePrepareGrain(long room, long presenter, int count, long freeCount)
            throws ReflectiveOperationException {
        Class<?> propsType = loader.loadClass("com.duowan.kiwi.props.api.component.IPropsModule");
        Object prop = propsType.getMethod("getPropAnyWay", int.class).invoke(propsModule(), 4);
        Class<?> propType = loader.loadClass("com.duowan.kiwi.props.api.bean.PropItem");
        if (prop != null && Boolean.TRUE.equals(propType.getMethod("isTigerFoodId").invoke(prop))) {
            sendGrain(room, presenter, count, freeCount, prop);
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
        long metadataAccount = account;
        Result accept = info -> {
            if (finished[0]) return;
            finished[0] = true;
            if (account != metadataAccount) return;
            try {
                if (info == null || !propType.isInstance(info)
                        || !Boolean.TRUE.equals(propType.getMethod("isTigerFoodId").invoke(info))) {
                    log("虎粮道具信息", target, "失败", "未获取到有效的虎粮道具资料，没有送礼");
                    handler.postDelayed(this::nextGiftRoom, 1200L);
                } else {
                    log("虎粮道具信息", target, "成功", "已核实为虎粮道具");
                    sendGrain(room, presenter, count, freeCount, info);
                }
            } catch (ReflectiveOperationException | RuntimeException failure) {
                Throwable cause = failure.getCause() == null ? failure : failure.getCause();
                log("免费虎粮", target, "失败", cause.getClass().getSimpleName() + " · " + cause.getMessage());
                handler.postDelayed(this::nextGiftRoom, 1200L);
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
                log("虎粮道具信息", target, "结果未确认", "道具资料查询超时，没有送礼");
                if (account == metadataAccount) handler.postDelayed(this::nextGiftRoom, 1200L);
            }
        }, 30000L);
    }

    private void sendGrain(long room, long presenter, int count, long freeCount, Object prop) {
        handler.postDelayed(() -> {
            try { executeSendGrain(room, presenter, count, freeCount, prop); }
            catch (ReflectiveOperationException | RuntimeException failure) {
                log("免费虎粮", "", "未确认", "送礼接口不可用，本轮停止");
                skipRemainingGifts("送礼接口异常，未继续发送");
                giftActive = false;
                finishDiceGift(false, "送礼接口不可用");
            }
        }, requestInterval);
    }

    private void executeSendGrain(long room, long presenter, int count, long freeCount, Object prop)
            throws ReflectiveOperationException {
        installGiftGuard();
        if (loggedInUid() != account || !giftAllowed()) {
            throw new IllegalStateException("Account or gift switch changed");
        }
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
        GiftLimit limit = new GiftLimit(presenter, count, freeCount);
        guardedGifts.put(params, limit);
        final long giftAccount = account;
        String target = "直播间 " + room + " · " + count + " 个免费虎粮";
        Class<?> callbackType = loader.loadClass("com.duowan.kiwi.props.api.request.ISendGiftCallback");
        final boolean[] finished = {false};
        Object callback = Proxy.newProxyInstance(loader, new Class<?>[]{callbackType}, (proxy, method, args) -> {
            if ("onResult".equals(method.getName())) {
                Object result = args == null ? null : args[0];
                handler.post(() -> {
                    if (finished[0]) return;
                    finished[0] = true;
                    limit.blocked = true;
                    if (account != giftAccount) {
                        log("免费虎粮", target, "结果未确认", "任务执行期间已切换账号，请核对原账号记录");
                        return;
                    }
                    if (result != null && result.getClass().getName().equals(
                            "com.duowan.kiwi.props.api.request.SendGiftResult$Success")) {
                        grainBudget -= count;
                        log("免费虎粮", target, "成功", "收到虎牙送礼成功回执");
                        finishDiceGift(true, "已收到 1 个免费虎粮赠送回执，等待骰子任务进度复核");
                    } else {
                        log("免费虎粮", target, "未完成", result == null ? "回执缺失" : result.getClass().getSimpleName());
                        skipRemainingGifts("前一笔赠送未成功，本轮停止后续赠送");
                        log("免费虎粮", "", "停止", "本次送礼未成功，保留剩余免费虎粮");
                    }
                    handler.postDelayed(this::nextGiftRoom, 1500L);
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
        if (!claim(diceGiftKey == null ? "gift-send/" + activeDay + "/" + presenter
                : "dice-gift-send/" + activeDay + "/" + diceGiftKey)) {
            limit.blocked = true;
            log("免费虎粮", target, "跳过", "今日已经提交过该主播的赠送，不重复发送");
            handler.postDelayed(this::nextGiftRoom, 1200L);
            return;
        }
        log("免费虎粮", target, "请求已发出", "仅使用背包免费库存，等待回执");
        send.invoke(giftService, params, callback);
        handler.postDelayed(() -> {
            if (!finished[0]) {
                finished[0] = true;
                limit.blocked = true;
                if (account == giftAccount) skipRemainingGifts("前一笔赠送结果未确认，本轮停止后续赠送");
                log("免费虎粮", target, "结果未确认", "等待回执超时，停止后续赠送，不自动重发");
            }
        }, 30000L);
    }

    private void skipRemainingGifts(String reason) {
        giftActive = false;
        Map.Entry<Long, Integer> pending;
        while ((pending = giftRooms.poll()) != null) {
            log("免费虎粮", "直播间 " + pending.getKey() + " · " + pending.getValue() + " 个免费虎粮",
                    "未执行", reason);
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
