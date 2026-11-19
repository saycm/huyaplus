package io.github.saycm.huyaplus;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class NativeTaskCatalog {
    static final int VERSION = 3;
    private static final String HOURLY_GOLD = "整点领金币";
    private static final String MEAL_GOLD = "饭点领金币补贴";
    private static final String MEAL_PAGE = "https://zt.huya.com/b3f393e7/mobile/index.html";
    private static final String[] DAILY_GOLD_TASKS = {
            HOURLY_GOLD, MEAL_GOLD
    };
    enum AutomationAction { NONE, NOTIFICATION, DEEPLINK, COOP }

    static final class Task {
        final long id;
        final String title, kind, blocked;
        final int target, progress, received, canComplete;
        final Map<String, String> extra;
        final int goldType;
        final String action, bizId;
        Task(long id, String title, String kind, int target, int progress, int received,
             int canComplete, Map<String, String> extra, String blocked) {
            this(id, title, kind, target, progress, received, canComplete, extra, blocked,
                    0, "", "");
        }
        Task(long id, String title, String kind, int target, int progress, int received,
             int canComplete, Map<String, String> extra, String blocked,
             int goldType, String action, String bizId) {
            this.id = id; this.title = title; this.kind = kind;
            this.target = target; this.progress = progress; this.received = received;
            this.canComplete = canComplete; this.extra = extra; this.blocked = blocked;
            this.goldType = goldType; this.action = action; this.bizId = bizId;
        }
        String key() { return kind + "/" + id; }
        String settingsKey() { return switchKey(this); }
        boolean isMealReward() {
            return MEAL_GOLD.equals(title) && goldType == 34
                    && (MEAL_PAGE.equals(action) || action.startsWith(MEAL_PAGE + "?"));
        }
        String statusLabel() {
            if (received != 0) return "已领取";
            if (!skipReason().isEmpty()) return "暂不支持";
            if (isMealReward()) return "等待餐段确认";
            if (target > 0 && progress >= target) return "可领奖";
            if (automationAction() != AutomationAction.NONE) return "可自动执行";
            return "等待条件";
        }
        String statusDetail() {
            String reason = skipReason();
            if (reason.isEmpty() && isMealReward()) return "以虎牙活动页返回的餐段状态为准";
            String progressText = target > 0
                    ? "进度 " + progress + "/" + target : "按服务端任务状态";
            if (!reason.isEmpty()) return progressText + " · " + reason;
            if (target > 0 && progress >= target) {
                return progressText + " · 服务端已完成，可领取奖励";
            }
            return progressText + " · " + actionDescription();
        }
        AutomationAction automationAction() {
            if (goldType == 20) return AutomationAction.NOTIFICATION;
            if (isDeeplinkAction(action)) return AutomationAction.DEEPLINK;
            if (goldType == 7 && isCoopAction(action)) return AutomationAction.COOP;
            return AutomationAction.NONE;
        }
        boolean permanentlyUnsupported() {
            if (goldType == 7 || goldType == 41 || goldType == 65) return true;
            String text = (title + " " + action + " " + blocked).toLowerCase(Locale.ROOT);
            for (String word : new String[]{
                    "下载", "安装", "download", "install",
                    "充值", "任充", "购买", "交易", "售出", "估值", "代售",
                    "注册", "邀请", "弹幕", "发消息"}) {
                if (text.contains(word)) return true;
            }
            return false;
        }
        String actionDescription() {
            switch (automationAction()) {
                case NOTIFICATION: return "提交真实系统通知授权状态";
                case DEEPLINK: return "提交虎牙跳转任务的进度，不打开厂商应用";
                case COOP: return "调用虎牙合作任务回流，不打开厂商应用";
                default: return "领取已完成奖励";
            }
        }
        TaskWire.Struct progressRequest() {
            long taskId = id;
            String taskBizId = bizId;
            if (isDeeplinkAction(action)) {
                String explicitTaskId = actionQueryValue("taskid");
                try {
                    if (!explicitTaskId.isEmpty()) taskId = Long.parseLong(explicitTaskId);
                } catch (NumberFormatException ignored) { }
                String explicitBizId = actionQueryValue("bizid");
                if (!explicitBizId.isEmpty()) taskBizId = explicitBizId;
            }
            return new TaskWire.Struct()
                    .field(1, taskBizId.isEmpty() ? "0" : taskBizId)
                    .field(2, taskId)
                    .field(3, 0)
                    .field(4, 1)
                    .field(5, System.currentTimeMillis() / 1000L);
        }
        private String actionQueryValue(String name) {
            return uriQueryValue(action, name);
        }
        private String uriQueryValue(String uri, String name) {
            int query = uri.indexOf('?');
            if (query < 0 || query + 1 >= uri.length()) return "";
            String params = uri.substring(query + 1);
            int fragment = params.indexOf('#');
            if (fragment >= 0) params = params.substring(0, fragment);
            for (String pair : params.split("&")) {
                int equals = pair.indexOf('=');
                String key = equals >= 0 ? pair.substring(0, equals) : pair;
                if (name.equalsIgnoreCase(key)) {
                    return equals >= 0 ? decodeUriQuery(pair.substring(equals + 1)) : "";
                }
            }
            return "";
        }
        String coopParams() {
            if (!isCoopAction(action)) return "";
            String link = actionQueryValue("banneraction");
            if (link.isEmpty()) {
                link = uriQueryValue(actionQueryValue("h5link"), "callback");
            }
            if (!"cooptask".equals(uriQueryValue(link, "report_type"))) return "";
            int query = link.indexOf('?');
            if (query < 0 || query + 1 >= link.length()) return "";
            String params = link.substring(query + 1);
            int fragment = params.indexOf('#');
            if (fragment >= 0) params = params.substring(0, fragment);
            return decodeUriQuery(params);
        }
        String skipReason() {
            if (!blocked.isEmpty()) return blocked;
            if (received != 0) return "服务端标记已领取，不重复领取";
            if (id > 0 && isMealReward()) return "";
            String text = (title + " " + action).toLowerCase(Locale.ROOT);
            for (String word : new String[]{"下载", "安装", "download", "install"}) {
                if (text.contains(word)) return "下载或安装任务已跳过，不下载、不安装";
            }
            for (String word : new String[]{
                    "充值", "任充", "购买", "交易", "售出", "估值",
                    "注册", "邀请", "弹幕", "发消息"}) {
                if (text.contains(word)) return "需要单独完成的操作，不自动提交";
            }
            if (goldType == 65) return "虎牙代售交易任务需要真实业务操作，不伪造结果";
            if (automationAction() != AutomationAction.NONE) {
                if (id <= 0 || target <= 0) return "任务标识或目标无效，不提交动作";
                if (automationAction() == AutomationAction.COOP && coopParams().isEmpty()) {
                    return "需要厂商完成回调；仅伪装安装或等待不能确认完成，未提交";
                }
                return "";
            }
            if (goldType == 63) return "需要前台浏览计时，未伪造浏览完成";
            if (goldType == 60 || goldType == 61) {
                return "需要虎牙页面内计时或预约业务状态，未伪造完成";
            }
            if (id <= 0 || target <= 0 || progress < target || canComplete != 1) {
                return "服务端条件未满足，不提交完成事件或领奖请求";
            }
            return "";
        }
        String servant() { return "user".equals(kind) ? "commui" : "wupui"; }
        String function() { return "user".equals(kind) ? "receiveUserLevelTaskPrize" : "receiveRewardTaskPrize"; }
        TaskWire.Struct request() {
            return new TaskWire.Struct().field(1, id).field(2, 1).field(3, "").field(4, extra);
        }
    }

    static String switchKey(Task task) {
        return switchKey(task.key());
    }

    static String switchKey(String taskKey) {
        return GlassSettings.KEY_TASK_ENABLED_PREFIX + taskKey;
    }

    static int intervalSeconds(String input) {
        try {
            int seconds = Integer.parseInt(input.trim());
            if (seconds >= 5 && seconds <= 600) return seconds;
        } catch (NumberFormatException ignored) { }
        throw new IllegalArgumentException("请填写 5–600 之间的整数秒数");
    }

    static List<Task> read(TaskWire.Struct response) {
        return read(response, false);
    }

    static List<Task> readDailyGold(TaskWire.Struct response) {
        return read(response, true);
    }

    static boolean isDailyGoldTask(String title) {
        for (String selected : DAILY_GOLD_TASKS) {
            if (selected.equals(title)) return true;
        }
        return false;
    }

    private static List<Task> read(TaskWire.Struct response, boolean dailyGoldOnly) {
        Map<String, Task> result = new LinkedHashMap<>();
        boolean found = false;
        for (Object raw : list(response.get(1))) {
            TaskWire.Struct module = structure(raw);
            if (module.number(0) != 14) continue;
            found = true;
            TaskWire.Struct data = data(module.get(1));
            for (Object entry : list(data.get(0))) {
                TaskWire.Struct group = structure(entry);
                String title = label(group.text(0), "未命名任务组");
                int type = (int) group.number(2);
                if (excludedGroup(title, type)) continue;
                if (type == 1) {
                    for (Object task : list(group.get(1))) addUser(result, structure(task), dailyGoldOnly);
                } else if (type == 6) {
                    for (Object task : list(group.get(4))) {
                        TaskWire.Struct mixed = structure(task);
                        if (mixed.number(0) == 0) addUser(result, data(mixed.get(1)), dailyGoldOnly);
                        else if (!dailyGoldOnly) {
                            add(result, blocked(title + " · 类型 " + mixed.number(0), "此嵌套任务需单独适配，未执行"));
                        }
                    }
                } else if (!dailyGoldOnly) {
                    add(result, blocked(title + " · 类型 " + type, "此任务组需单独适配，未打开外部页面、下载或执行任务"));
                }
            }
        }
        if (!found) throw new IllegalArgumentException("未找到已适配的任务模块");
        if (dailyGoldOnly) {
            for (String title : DAILY_GOLD_TASKS) {
                boolean present = result.values().stream().anyMatch(task -> title.equals(task.title));
                if (!present) {
                    Task placeholder = blocked(title, "当前任务列表未返回此项目");
                    result.put(placeholder.key(), placeholder);
                }
            }
        }
        return new ArrayList<>(result.values());
    }

    static boolean excludedGroup(String title, int type) {
        if (type == 12 || type == 15 || type == 19) return true;
        String name = title.replaceAll("\\s+", "").toLowerCase(Locale.ROOT);
        return name.contains("玩游戏赚金币") || name.contains("小游戏")
                || name.contains("限时活动") || name.contains("浏览app赚金币")
                || name.contains("流量app赚金币");
    }

    private static Task user(TaskWire.Struct task) {
        String blocked = "";
        int goldType = (int) task.number(28);
        String action = task.text(14);
        boolean cooperation = goldType == 7 && isCoopAction(action);
        boolean nativeAction = goldType == 20
                || isDeeplinkAction(action)
                || cooperation;
        TaskWire.Struct link = task.get(20) instanceof TaskWire.Struct ? structure(task.get(20)) : new TaskWire.Struct();
        if (!link.text(1).isEmpty()) blocked = "下载任务已跳过，不下载、不安装";
        else if (!cooperation
                && ("coop_task".equals(task.text(21)) || !link.text(0).isEmpty())) {
            blocked = "需要合作 App 验证，未跳转或伪造回流";
        }
        else if (!nativeAction && (task.number(4) != 0 || !task.text(16).isEmpty() || task.number(18) != 0)) {
            blocked = "需要独立跳转或激励流程，未使用通用领奖接口";
        }
        return new Task(task.number(0), label(task.text(5), "普通任务"), "user",
                (int) task.number(1), (int) task.number(2), (int) task.number(3), 1,
                strings(task.get(32)), blocked, goldType,
                action, task.text(13));
    }

    private static void addUser(Map<String, Task> result, TaskWire.Struct raw, boolean dailyGoldOnly) {
        if (!dailyGoldOnly) {
            add(result, user(raw));
            return;
        }
        String title = label(raw.text(5), "");
        if (!isDailyGoldTask(title)) return;
        Task task = user(raw);
        TaskWire.Struct link = raw.get(20) instanceof TaskWire.Struct
                ? structure(raw.get(20)) : new TaskWire.Struct();
        String reason;
        boolean standalone = raw.number(4) == 2 && raw.text(16).isEmpty() && raw.number(18) == 0
                && !"coop_task".equals(raw.text(21)) && link.text(0).isEmpty() && link.text(1).isEmpty();
        if (standalone && ((HOURLY_GOLD.equals(title) && raw.number(28) == 1 && task.action.isEmpty())
                || task.isMealReward())) {
            reason = "";
        } else {
            reason = "此任务的独立领奖流程待适配";
        }
        Task selected = new Task(task.id, title, task.kind, task.target, task.progress, task.received,
                task.canComplete, task.extra, reason, task.goldType, task.action, task.bizId);
        Task previous = result.get(selected.key());
        if (previous == null || !selected.skipReason().isEmpty()) result.put(selected.key(), selected);
    }

    private static Task blocked(String title, String reason) {
        return new Task(0, label(title, "未知任务"), "blocked/" + title, 0, 0, 0, 0, Collections.emptyMap(), reason);
    }

    private static void add(Map<String, Task> out, Task task) {
        if (out.size() >= 300) throw new IllegalArgumentException("任务数量超过本轮上限");
        if (task.permanentlyUnsupported()) return;
        Task old = out.get(task.key());
        // A duplicate must never turn a blocked entry into an eligible one.
        if (old == null || !task.skipReason().isEmpty()) out.put(task.key(), task);
    }

    private static TaskWire.Struct structure(Object value) {
        if (!(value instanceof TaskWire.Struct)) throw new IllegalArgumentException("任务结构不匹配");
        return (TaskWire.Struct) value;
    }
    private static TaskWire.Struct data(Object value) {
        if (!(value instanceof byte[])) throw new IllegalArgumentException("任务数据缺失");
        return TaskWire.decode((byte[]) value);
    }
    private static List<?> list(Object value) {
        if (value == null) return Collections.emptyList();
        if (!(value instanceof List)) throw new IllegalArgumentException("任务列表结构不匹配");
        return (List<?>) value;
    }
    private static Map<String, String> strings(Object value) {
        Map<String, String> strings = new LinkedHashMap<>();
        if (value == null) return strings;
        if (!(value instanceof Map)) throw new IllegalArgumentException("任务扩展数据不匹配");
        for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
            if (!(entry.getKey() instanceof String) || !(entry.getValue() instanceof String)) {
                throw new IllegalArgumentException("任务扩展字段不匹配");
            }
            strings.put((String) entry.getKey(), (String) entry.getValue());
        }
        return strings;
    }
    private static String label(String text, String fallback) {
        String value = text.isEmpty() ? fallback : text.replace('\n', ' ').replace('\r', ' ');
        return value.substring(0, Math.min(value.length(), 80));
    }
    private static boolean isCoopAction(String action) {
        return action != null
                && action.toLowerCase(Locale.ROOT).contains("hyaction=launchcooptask");
    }
    private static boolean isDeeplinkAction(String action) {
        return action != null
                && action.toLowerCase(Locale.ROOT).contains("hyaction=launchdeeplink");
    }
    private static String decodeUriQuery(String value) {
        StringBuilder result = new StringBuilder();
        ByteArrayOutputStream encoded = new ByteArrayOutputStream();
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if (current == '%' && index + 2 < value.length()) {
                int high = Character.digit(value.charAt(index + 1), 16);
                int low = Character.digit(value.charAt(index + 2), 16);
                if (high >= 0 && low >= 0) {
                    encoded.write((high << 4) | low);
                    index += 2;
                    continue;
                }
            }
            if (encoded.size() > 0) {
                result.append(new String(encoded.toByteArray(), StandardCharsets.UTF_8));
                encoded.reset();
            }
            result.append(current);
        }
        if (encoded.size() > 0) {
            result.append(new String(encoded.toByteArray(), StandardCharsets.UTF_8));
        }
        return result.toString();
    }
}
