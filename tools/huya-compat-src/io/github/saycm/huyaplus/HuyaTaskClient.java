package io.github.saycm.huyaplus;

import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/** Uses Huya's own transport. Session fields remain inside the target process. */
final class HuyaTaskClient {
    private final ClassLoader loader;
    private final AtomicInteger ids = new AtomicInteger(1);
    HuyaTaskClient(ClassLoader loader) { this.loader = loader; }

    long loggedInUid() throws ReflectiveOperationException {
        Class<?> component = loader.loadClass("com.duowan.kiwi.base.login.api.ILoginComponent");
        Object instance = HuyaComponents.get(loader, component);
        Object login = component.getMethod("getLoginModule").invoke(instance);
        Class<?> type = loader.loadClass("com.duowan.kiwi.base.login.api.ILoginModule");
        if (!Boolean.TRUE.equals(type.getMethod("isLogin").invoke(login))) return 0;
        return ((Number) type.getMethod("getUid").invoke(login)).longValue();
    }

    boolean notificationEnabled(Object context) throws ReflectiveOperationException {
        Class<?> contextType = loader.loadClass("android.content.Context");
        Class<?> type = loader.loadClass("com.duowan.kiwi.push.IPushModule");
        Object module = HuyaComponents.get(loader, type);
        return Boolean.TRUE.equals(type.getMethod("isNotificationEnabled", contextType)
                .invoke(module, context));
    }

    void claimDiceVideo(long account, String action, java.util.function.BooleanSupplier enabled,
                        NativeTaskRunner.ActionReply reply) {
        claimDiceVideo(account, action, enabled, reply, 0, Runnable::run);
    }

    void claimDiceVideo(long account, String action, java.util.function.BooleanSupplier enabled,
                        NativeTaskRunner.ActionReply reply, long interval,
                        java.util.function.Consumer<Runnable> afterReply) {
        AtomicBoolean delivered = new AtomicBoolean();
        long deadline = System.nanoTime() + 60000000000L + interval * 1000000L;
        java.util.function.BooleanSupplier active = () -> {
            try { return System.nanoTime() < deadline && enabled.getAsBoolean() && loggedInUid() == account; }
            catch (ReflectiveOperationException | RuntimeException failure) { return false; }
        };
        NativeTaskRunner.ActionReply once = (accepted, detail) -> {
            if (delivered.compareAndSet(false, true)) reply.complete(accepted, detail);
        };
        try {
            java.util.Map<String, String> args = new java.util.LinkedHashMap<>();
            String query = new java.net.URI(action).getRawQuery();
            if (query == null) throw new IllegalArgumentException("Missing ad action");
            for (String part : query.split("&")) {
                String[] pair = part.split("=", 2);
                if (pair.length == 2) args.put(java.net.URLDecoder.decode(pair[0], "UTF-8"),
                        java.net.URLDecoder.decode(pair[1], "UTF-8"));
            }
            if (!"lotteryad".equals(args.get("hyaction")) || !"1".equals(args.get("commonpanelreq"))
                    || !active.getAsBoolean()) {
                once.complete(false, "广告任务参数未适配或任务已关闭，未打开广告");
                return;
            }
            java.util.Map<String, String> params = new java.util.LinkedHashMap<>();
            params.put("iTargetAdType", "2");
            if (args.containsKey("rso")) params.put("rso", args.get("rso"));
            String reqId = args.get("rewardreqid");
            if (reqId == null || reqId.isEmpty()) reqId = java.util.UUID.randomUUID().toString();
            final String requestId = reqId;
            int requestType = Integer.parseInt(args.getOrDefault("rewardreqtype", "2"));
            TaskWire.Struct request = new TaskWire.Struct()
                    .field(1, Integer.parseInt(args.get("rewardappid")))
                    .field(2, new java.util.LinkedHashMap<>())
                    .field(3, Integer.parseInt(args.getOrDefault("commonpanelitemid", "0")))
                    .field(4, 0L)
                    .field(5, Integer.parseInt(args.getOrDefault("commonpanelsource", "0")))
                    .field(6, requestId).field(7, new java.util.LinkedHashMap<>()).field(8, params);
            send(account, "wupui", "getCommAdPannel", request, (body, code) -> {
                if (!active.getAsBoolean()) { once.complete(false, "任务已关闭或账号变化，未继续广告领奖"); return; }
                if (code != 0 || !(body.get(2) instanceof TaskWire.Struct)) {
                    once.complete(false, "未取得服务端广告任务，未提交领奖");
                    return;
                }
                TaskWire.Struct ad = (TaskWire.Struct) body.get(2);
                if (ad.text(0).isEmpty()) { once.complete(false, "服务端广告任务 ID 缺失"); return; }
                afterReply.accept(() -> {
                if (!active.getAsBoolean()) {
                    once.complete(false, "任务已关闭或等待超时，未提交广告领奖");
                    return;
                }
                try {
                    Class<?> requestTypes = loader.loadClass(
                            "com.duowan.kiwi.ad.api.IHyLotteryAdHelper$HYRewardAdReqType");
                    Object types = requestTypes.getField("Companion").get(null);
                    int common = ((Number) types.getClass().getMethod("getAwardCommAdTaskType").invoke(types)).intValue();
                    int reward = ((Number) types.getClass().getMethod("getAwardCommRewardTaskType").invoke(types)).intValue();
                    if (requestType != common && requestType != reward) {
                        once.complete(false, "广告领奖类型未适配"); return;
                    }
                    Class<?> managerType = loader.loadClass("com.duowan.biz.videoad.impl.HyLotteryAdAwardManager");
                    Object companion = managerType.getField("Companion").get(null);
                    Object manager = companion.getClass().getMethod("getInstance").invoke(companion);
                    Class<?> listener = loader.loadClass(
                            "com.duowan.kiwi.ad.api.IHyLotteryAdHelper$HyRewardAdListener");
                    Object callback = Proxy.newProxyInstance(loader, new Class<?>[]{listener}, (proxy, method, values) -> {
                        if (method.getDeclaringClass() == Object.class) {
                            if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
                            if ("equals".equals(method.getName())) return values != null && proxy == values[0];
                            return "FuckADDiceVideoCallback";
                        }
                        if ("onRewarded".equals(method.getName())) {
                            boolean success = active.getAsBoolean() && values != null
                                    && values.length > 0 && Boolean.TRUE.equals(values[0]);
                            once.complete(success, success ? "广告奖励回执已确认，等待骰子任务服务端复核"
                                    : "广告奖励未获确认，未重复请求");
                        } else if ("onError".equals(method.getName())) {
                            once.complete(false, "广告奖励接口返回错误，不重复请求");
                        }
                        return null;
                    });
                    Object ext = ad.get(5);
                    Class<?> gsonType = loader.loadClass("com.google.gson.Gson");
                    Object gson = gsonType.getConstructor().newInstance();
                    String json = (String) gsonType.getMethod("toJson", Object.class).invoke(gson,
                            ext instanceof java.util.Map ? ext : new java.util.LinkedHashMap<>());
                    if (!active.getAsBoolean()) { once.complete(false, "任务已关闭，未提交广告领奖"); return; }
                    managerType.getMethod(requestType == reward ? "onAwardCommonRewardAdTask" : "onAwardCommonAdTask",
                            String.class, java.util.Map.class, int.class, String.class, String.class, listener)
                            .invoke(manager, ad.text(0), new java.util.LinkedHashMap<>(), 0, json, requestId, callback);
                } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
                    once.complete(false, "原生广告领奖接口不匹配，未确认成功");
                }
                });
            });
        } catch (java.net.URISyntaxException | java.io.UnsupportedEncodingException
                 | RuntimeException | LinkageError failure) {
            once.complete(false, "广告任务参数或接口未匹配，未打开广告");
        }
    }

    void send(long account, String servant, String function, TaskWire.Struct body, NativeTaskRunner.Reply reply) {
        AtomicBoolean delivered = new AtomicBoolean();
        try {
            boolean query = "wupui".equals(servant) && "getLiveBoxUserGrowthPage".equals(function);
            boolean reward = "wupui".equals(servant) && "receiveRewardTaskPrize".equals(function);
            boolean userReward = "commui".equals(servant) && "receiveUserLevelTaskPrize".equals(function);
            boolean progress = "commui".equals(servant)
                    && "updateUserLevelTaskProgress".equals(function);
            boolean coop = "wupui".equals(servant)
                    && "reportCoopUserLevelTask".equals(function);
            boolean market = "wupui".equals(servant)
                    && "reportUserTaskClickEvent".equals(function);
            boolean meal = "webActUI".equals(servant)
                    && ("getUserTaskDetailByTaskId".equals(function) || "receivePrize".equals(function));
            boolean dice = "wupui".equals(servant)
                    && ("getJumpGameModule".equals(function)
                    || "getCommAdPannel".equals(function)
                    || "executeUserSign".equals(function)
                    || "getJumpGameTaskList".equals(function)
                    || "claimJumpGameTaskReward".equals(function)
                    || "rollJumpGameDice".equals(function));
            if (!query && !reward && !userReward && !progress && !coop && !market && !dice && !meal) {
                throw new IllegalArgumentException("Unsupported task endpoint");
            }
            verifySession(account);
            Object user = loader.loadClass("com.duowan.biz.wup.WupHelper")
                    .getMethod("getUserId").invoke(null);
            Class<?> outputType = loader.loadClass("com.duowan.taf.jce.JceOutputStream");
            Object output = outputType.getConstructor().newInstance();
            outputType.getMethod("setServerEncoding", String.class).invoke(output, "UTF-8");
            user.getClass().getMethod("writeTo", outputType).invoke(user, output);
            byte[] identity = (byte[]) outputType.getMethod("toByteArray").invoke(output);
            TaskWire.Struct request = new TaskWire.Struct();
            request.putAll(body); request.put(0, TaskWire.decode(identity));
            Class<?> packetType = loader.loadClass("com.duowan.jce.wup.UniPacket");
            Object packet = packetType.getConstructor().newInstance();
            packetType.getMethod("decode", byte[].class).invoke(packet,
                    (Object) TaskWire.packet(servant, function, request, ids.getAndIncrement()));
            Class<?> callbackType = loader.loadClass("com.huya.kiwi.crossplatform.common.wup.HybridJceCallback");
            Object callback = Proxy.newProxyInstance(loader, new Class<?>[]{callbackType}, (proxy, method, args) -> {
                if (method.getDeclaringClass() == Object.class) {
                    if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
                    if ("equals".equals(method.getName())) return args != null && proxy == args[0];
                    return "FuckADTaskCallback";
                }
                if ("onResponse".equals(method.getName()) && delivered.compareAndSet(false, true)) {
                    TaskWire.Reply result;
                    try { result = TaskWire.reply((byte[]) args[0], "tRsp"); }
                    catch (RuntimeException failure) { result = new TaskWire.Reply(new TaskWire.Struct(), -1); }
                    reply.complete(result.body, result.code);
                } else if ("a".equals(method.getName()) && delivered.compareAndSet(false, true)) {
                    reply.complete(new TaskWire.Struct(), -1);
                }
                return null;
            });
            Method requestFactory;
            try {
                requestFactory = loader.loadClass("ryxq.ev6").getMethod(
                        "a", packetType, int.class, int.class, Number.class, callbackType);
            } catch (ClassNotFoundException | NoSuchMethodException oldFactoryAbsent) {
                requestFactory = loader.loadClass("ryxq.d05").getMethod(
                        "a", packetType, int.class, int.class, Number.class, callbackType);
            }
            Object nativeRequest = requestFactory.invoke(null, packet, 0, 15000, null, callback);
            nativeRequest.getClass().getMethod("execute").invoke(nativeRequest);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            if (delivered.compareAndSet(false, true)) reply.complete(new TaskWire.Struct(), -1);
        }
    }

    private void verifySession(long account) throws ReflectiveOperationException {
        if (account <= 0 || loggedInUid() != account) throw new IllegalStateException("Session changed");
        Object user = loader.loadClass("com.duowan.biz.wup.WupHelper")
                .getMethod("getUserId").invoke(null);
        if (user == null || user.getClass().getField("lUid").getLong(user) != account) {
            throw new IllegalStateException("Session changed");
        }
    }
}
