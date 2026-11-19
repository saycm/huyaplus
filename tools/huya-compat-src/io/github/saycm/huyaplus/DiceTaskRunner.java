package io.github.saycm.huyaplus;

import java.util.List;

/** Uses existing dice only; each roll waits for a receipt and a fresh server map. */
final class DiceTaskRunner {
    interface Host {
        boolean enabled();
        long uid();
        boolean claim(String key);
        void log(String state, String detail);
        void later(long millis, Runnable run);
        void send(String function, TaskWire.Struct request, NativeTaskRunner.Reply reply);
    }

    private final Host host;
    private final long interval;
    private final Runnable finished;
    private long account;
    private String day;
    private boolean started, stopped, waiting;
    private int requestId, rolls;
    private String rollKey;

    DiceTaskRunner(Host host, long interval, Runnable finished) {
        if (interval < 5000 || interval > 600000) throw new IllegalArgumentException("Invalid task interval");
        this.host = host; this.interval = interval; this.finished = finished;
    }

    void start(long uid, String date) {
        if (started) return;
        started = true; account = uid; day = date;
        if (!active()) return;
        host.log("开始", "查询服务端骰子库存，仅使用已有次数，不购买骰子");
        query();
    }

    private boolean active() {
        if (stopped) return false;
        if (!host.enabled() || account <= 0 || host.uid() != account) {
            stop("停止", "功能关闭或账号发生变化，停止本轮");
            return false;
        }
        return true;
    }

    private void query() {
        send("getJumpGameModule", new TaskWire.Struct(), (body, code) -> {
            if (code != 0 || !(body.get(0) instanceof Number)
                    || !(body.get(1) instanceof Number) || !(body.get(2) instanceof TaskWire.Struct)) {
                stop("失败", "骰子活动返回异常或结构不匹配，未继续投骰");
                return;
            }
            long remaining = body.number(0);
            if (remaining == 0) { stop("结束", "骰子次数已用完，本轮成功投骰 " + rolls + " 次"); return; }
            if (remaining < 0 || remaining > 100 || rolls >= 100) {
                stop("停止", "库存或本轮次数超出上限，未继续投骰"); return;
            }
            TaskWire.Struct map = (TaskWire.Struct) body.get(2);
            String mapId = map.text(0);
            long pos = body.number(1), max = -1;
            if (map.get(4) instanceof List) {
                for (Object grid : (List<?>) map.get(4)) {
                    if (!(grid instanceof TaskWire.Struct)
                            || !(((TaskWire.Struct) grid).get(0) instanceof Number)) {
                        stop("失败", "棋盘格数据不匹配，未投骰"); return;
                    }
                    max = Math.max(max, ((TaskWire.Struct) grid).number(0));
                }
            }
            if (mapId.isEmpty() || pos < 0 || max < pos || max > Integer.MAX_VALUE) {
                stop("失败", "棋盘或位置数据无效，未投骰"); return;
            }
            TaskWire.Struct request = new TaskWire.Struct()
                    .field(1, mapId).field(2, pos).field(3, max);
            rollKey = "dice-state/" + account + "/" + day + "/"
                    + java.util.UUID.nameUUIDFromBytes(TaskWire.encode(
                            new TaskWire.Struct().field(1, mapId).field(2, pos)
                                    .field(3, max).field(4, remaining)));
            roll(request);
        });
    }

    private void roll(TaskWire.Struct request) {
        if (!active()) return;
        if (!host.claim(rollKey)) {
            stop("停止", "该次投骰已提交，结果不明时不重试"); return;
        }
        send("rollJumpGameDice", request, (body, code) -> {
            if (code != 0 || !(body.get(0) instanceof Number)
                    || body.number(0) < 1 || body.number(0) > 6
                    || !(body.get(1) instanceof Number) || body.number(1) < 0) {
                stop("失败", "服务端未确认投骰成功（返回代码 " + code + "），未重试"); return;
            }
            rolls++;
            host.log("成功", "第 " + rolls + " 次投出 " + body.number(0) + " 点；"
                    + "奖励类型 " + body.number(7) + "，数量 " + body.number(2)
                    + "；已收到服务端回执，重新核对棋盘与库存");
            host.later(interval, this::query);
        });
    }

    private void send(String function, TaskWire.Struct request, NativeTaskRunner.Reply reply) {
        if (!active()) return;
        int id = ++requestId;
        waiting = true;
        host.log("请求已发出", "rollJumpGameDice".equals(function) ? "等待投骰回执" : "读取棋盘与骰子次数");
        host.later(20000, () -> {
            if (waiting && requestId == id) stop("结果未确认", "请求超时，本轮停止且不重试");
        });
        try {
            host.send(function, request, (body, code) -> {
                if (!waiting || id != requestId || stopped) return;
                waiting = false;
                if (!active()) return;
                try { reply.complete(body, code); }
                catch (RuntimeException failure) { stop("失败", "回执数据不匹配，停止本轮"); }
            });
        } catch (RuntimeException failure) { stop("失败", "原生请求不可用，未确认成功"); }
    }

    private void stop(String state, String detail) {
        if (stopped) return;
        stopped = true; waiting = false;
        host.log(state, detail);
        finished.run();
    }
}
