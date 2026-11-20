package io.github.saycm.huyaplus;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Server task IDs are strings and are independent of the daily coin task IDs. */
final class DiceTaskCatalog {
    static final class Task {
        final String id, title, action;
        final int type, progress, target, claimed, total, status;

        Task(TaskWire.Struct row) {
            id = row.text(0); title = row.text(1); action = row.text(4);
            type = (int) row.number(5); progress = (int) row.number(6);
            target = (int) row.number(7); claimed = (int) row.number(8);
            total = (int) row.number(9); status = (int) row.number(10);
            if (id.isEmpty() || id.length() > 128 || title.isEmpty()
                    || progress < 0 || target < 0 || claimed < 0 || total < claimed
                    || total > 100 || status < 0 || status > 2) {
                throw new IllegalArgumentException("Invalid dice task");
            }
        }

        String key() { return "dice/" + id; }
        String settingsKey() { return switchKey(key()); }
        boolean freeGrain() {
            return type == 2 && title.contains("虎粮") && !title.contains("打赏")
                    && !title.contains("购买") && !title.contains("充值");
        }
        boolean marketVisit() {
            return type == 5 && title.equals("浏览游戏商城15s")
                    && action.contains("hyaction=welfarepage")
                    && action.contains("taskid=" + id);
        }
        boolean supportsAutomation() { return freeGrain() || marketVisit() || type == 6 || type == 9; }
        String statusLabel() {
            if (status == 2 || claimed >= total) return "已领取";
            if (status == 1) return "可领奖";
            return "可自动执行";
        }
        String statusDetail() {
            String scope;
            if (freeGrain()) scope = "共用每日自定义赠送额度，符合条件时拆成三笔，服务端达标后领取。";
            else if (marketVisit()) scope = "后台提交商城任务事件；只有服务端进度及已领次数增加才算完成。";
            else if (type == 6) scope = "尝试后台奖励回调，无广告画面；服务端确认后领取，失败不重试。";
            else scope = "按服务端剩余倒计时后台等待，再复核并领取。";
            return "进度 " + progress + "/" + target + " · 已领 " + claimed + "/" + total + "。\n" + scope;
        }
    }

    static String switchKey(String key) { return "dice_task_enabled_v1/" + key.substring("dice/".length()); }

    static List<Task> read(TaskWire.Struct response) {
        Object list = response.get(0);
        if (!(list instanceof List)) throw new IllegalArgumentException("Missing dice task list");
        List<Task> tasks = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        for (Object row : (List<?>) list) {
            if (!(row instanceof TaskWire.Struct)) throw new IllegalArgumentException("Invalid dice task row");
            Task task = new Task((TaskWire.Struct) row);
            if (!ids.add(task.id)) throw new IllegalArgumentException("Duplicate dice task ID");
            if (task.supportsAutomation()) tasks.add(task);
        }
        return tasks;
    }
}
