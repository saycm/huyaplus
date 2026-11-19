package io.github.saycm.huyaplus;

import java.util.ArrayDeque;
import java.util.List;

/** Each action and reward is followed by a fresh server task list. */
final class DiceMissionRunner {
    interface Host {
        long uid();
        boolean taskEnabled(DiceTaskCatalog.Task task);
        boolean claim(String key);
        void log(String task, String state, String detail);
        void later(long delay, Runnable run);
        void publish(List<DiceTaskCatalog.Task> tasks);
        default void perform(DiceTaskCatalog.Task task, NativeTaskRunner.ActionReply reply) {
            reply.complete(false, "静默动作不可用");
        }
        default void perform(DiceTaskCatalog.Task task, java.util.function.BooleanSupplier allowed,
                             NativeTaskRunner.ActionReply reply) {
            perform(task, reply);
        }
        void send(String endpoint, TaskWire.Struct request, NativeTaskRunner.Reply reply);
    }

    private final Host host;
    private final long interval;
    private final Runnable finished;
    private final ArrayDeque<DiceTaskCatalog.Task> tasks = new ArrayDeque<>();
    private long account;
    private String date;
    private boolean started, stopped, waiting;
    private int requestId, rounds;

    DiceMissionRunner(Host host, long interval, Runnable finished) {
        if (interval < 5000 || interval > 600000) throw new IllegalArgumentException("Invalid interval");
        this.host = host; this.interval = interval; this.finished = finished;
    }

    void start(long account, String date) {
        if (started) return;
        started = true; this.account = account; this.date = date;
        query(list -> {
            for (DiceTaskCatalog.Task task : list) if (task.type != 9 || task.status != 0) tasks.add(task);
            for (DiceTaskCatalog.Task task : list) if (task.type == 9 && task.status == 0) tasks.add(task);
            next();
        });
    }

    private boolean active() {
        if (stopped) return false;
        if (account <= 0 || host.uid() != account) { stop("账号已退出或变化"); return false; }
        return true;
    }

    private interface CatalogReply { void accept(List<DiceTaskCatalog.Task> list); }

    private void query(CatalogReply reply) {
        send("getJumpGameTaskList", new TaskWire.Struct(), (body, code) -> {
            if (code != 0) { stop("任务查询失败，未继续提交"); return; }
            List<DiceTaskCatalog.Task> list = DiceTaskCatalog.read(body);
            host.publish(list);
            reply.accept(list);
        });
    }

    private void next() {
        if (!active()) return;
        DiceTaskCatalog.Task task = tasks.poll();
        if (task == null) { stop("本轮骰子任务已结束"); return; }
        rounds = 0;
        schedule(task);
    }

    private boolean enabled(DiceTaskCatalog.Task task) {
        if (!active()) return false;
        if (host.taskEnabled(task)) return true;
        host.log(task.title, "已关闭", "任务开关关闭，不执行动作或领取");
        return false;
    }

    private void schedule(DiceTaskCatalog.Task task) {
        if (!enabled(task)) { next(); return; }
        if (task.status == 2 || task.claimed >= task.total) {
            host.log(task.title, "已领取", "服务端已领取或达到今日上限"); next(); return;
        }
        if (++rounds > Math.min(100, task.total + 1)) { next(); return; }
        long delay = interval;
        if (task.status == 0 && task.type == 9) {
            long remaining = Math.max(0L, (long) task.target - task.progress);
            if (remaining > 3600) {
                host.log(task.title, "跳过", "倒计时超过一小时，留待下次打开检查"); next(); return;
            }
            delay = Math.max(interval, remaining * 1000L);
        }
        host.log(task.title, "等待", "等待 " + delay / 1000 + " 秒后按服务端状态处理");
        host.later(delay, () -> {
            if (!enabled(task)) { next(); return; }
            if (task.status == 1) reward(task);
            else if (task.type == 9) refresh(task, false);
            else action(task);
        });
    }

    private String key(String kind, DiceTaskCatalog.Task task) {
        String prefix = "dice-mission-" + kind + "/" + account + "/" + date + "/" + task.id;
        return kind.equals("action") && task.marketVisit() ? prefix : prefix + "/" + task.claimed;
    }

    private void action(DiceTaskCatalog.Task task) {
        if (!host.claim(key("action", task))) {
            host.log(task.title, "跳过", "该轮动作已提交，结果不明时不重复执行"); next(); return;
        }
        int id = ++requestId;
        waiting = true;
        host.later(95000 + interval * 4, () -> {
            if (waiting && requestId == id) stop("动作结果未确认，停止本轮且不重试");
        });
        try {
            host.perform(task, () -> waiting && requestId == id && !stopped
                    && active() && host.taskEnabled(task), (accepted, detail) -> {
                if (!waiting || id != requestId || stopped) return;
                waiting = false;
                if (!enabled(task)) { next(); return; }
                host.log(task.title, accepted ? "已提交" : "未执行", detail);
                if (!accepted) { next(); return; }
                host.later(interval, () -> refresh(task, true));
            });
        } catch (RuntimeException failure) { stop("静默动作接口不可用"); }
    }

    private void refresh(DiceTaskCatalog.Task previous, boolean performed) {
        if (!enabled(previous)) { next(); return; }
        query(list -> {
            DiceTaskCatalog.Task current = null;
            for (DiceTaskCatalog.Task task : list) if (task.id.equals(previous.id)) current = task;
            if (current == null) { host.log(previous.title, "未确认", "服务端已不再返回此任务"); next(); return; }
            if (!enabled(current)) { next(); return; }
            if (current.status == 1) {
                DiceTaskCatalog.Task ready = current;
                host.later(interval, () -> reward(ready));
                return;
            }
            if (current.claimed > previous.claimed) {
                if (previous.marketVisit()) {
                    host.log(current.title, "成功", "服务端确认商城任务已领取奖励");
                }
                if (current.type == 9 && current.status == 0 && !tasks.isEmpty()) {
                    tasks.addLast(current);
                    next();
                } else schedule(current);
                return;
            }
            if (!performed && current.type == 9 && current.progress > previous.progress) {
                schedule(current); return;
            }
            host.log(current.title, "服务端未确认",
                    "当前进度 " + current.progress + "/" + current.target + "，未领取或重复提交");
            next();
        });
    }

    private void reward(DiceTaskCatalog.Task task) {
        if (!enabled(task)) { next(); return; }
        if (!host.claim(key("reward", task))) {
            host.log(task.title, "跳过", "该轮领奖已提交，不重复领取"); next(); return;
        }
        send("claimJumpGameTaskReward", new TaskWire.Struct().field(1, task.id), (body, code) -> {
            long dice = 0;
            if (body.get(1) instanceof List) for (Object value : (List<?>) body.get(1)) {
                if (!(value instanceof TaskWire.Struct)) throw new IllegalArgumentException("Invalid reward");
                TaskWire.Struct reward = (TaskWire.Struct) value;
                if (reward.number(0) == 1 && reward.number(3) > 0) dice += reward.number(3);
            }
            if (code != 0 || dice <= 0) {
                host.log(task.title, "失败", "服务端未返回成功奖励，未自动重试"); stop("领奖未获确认"); return;
            }
            if (task.marketVisit()) {
                host.log(task.title, "已提交", "领奖回执已收到，等待服务端已领次数复核");
                host.later(interval, () -> {
                    if (!enabled(task)) { next(); return; }
                    query(list -> {
                        DiceTaskCatalog.Task current = null;
                        for (DiceTaskCatalog.Task value : list) if (value.id.equals(task.id)) current = value;
                        if (current != null && current.claimed > task.claimed)
                            host.log(task.title, "成功", "服务端确认商城任务已领取奖励");
                        else host.log(task.title, "服务端未确认", "领奖后已领次数未增加");
                        next();
                    });
                });
                return;
            }
            host.log(task.title, "成功", "服务端返回 " + dice + " 次骰子任务奖励");
            host.later(interval, () -> refresh(task, true));
        });
    }

    private void send(String endpoint, TaskWire.Struct request, NativeTaskRunner.Reply reply) {
        if (!active()) return;
        int id = ++requestId;
        waiting = true;
        host.later(20000, () -> {
            if (waiting && requestId == id) stop("请求超时，结果未确认且不重试");
        });
        try {
            host.send(endpoint, request, (body, code) -> {
                if (!waiting || requestId != id || stopped) return;
                waiting = false;
                if (!active()) return;
                try { reply.complete(body, code); }
                catch (RuntimeException failure) { stop("任务回执结构未匹配"); }
            });
        } catch (RuntimeException failure) { stop("任务请求接口不可用"); }
    }

    private void stop(String reason) {
        if (stopped) return;
        stopped = true; waiting = false;
        host.log("骰子任务", "结束", reason);
        finished.run();
    }
}
