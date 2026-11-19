package io.github.saycm.huyaplus;

import java.util.concurrent.atomic.AtomicBoolean;

final class WelfareSignRunner {
    interface Host {
        boolean active();
        boolean claim();
        void log(String state, String detail);
        void send(TaskWire.Struct request, NativeTaskRunner.Reply reply);
        default void later(long delay, Runnable run) {}
    }

    private final Host host;
    private final Runnable finished;
    private final AtomicBoolean done = new AtomicBoolean();

    WelfareSignRunner(Host host, Runnable finished) {
        this.host = host;
        this.finished = finished;
    }

    void start() {
        if (!host.active() || !host.claim()) {
            finish();
            return;
        }
        host.later(20000, () -> {
            if (!done.compareAndSet(false, true)) return;
            host.log("未确认", "签到回执超时，保留提交记录，不重复签到");
            finished.run();
        });
        host.send(new TaskWire.Struct().field(1, 2).field(2, "frontpage"), (body, code) -> {
            if (!done.compareAndSet(false, true)) return;
            Object result = body.get(5);
            boolean success = host.active() && code == 0 && body.number(1) == 0
                    && result instanceof TaskWire.Struct
                    && ((TaskWire.Struct) result).number(1) == 2;
            host.log(success ? "成功" : "未确认",
                    success ? "服务端确认任务中心签到成功" : "签到未获服务端确认，不重复提交");
            finished.run();
        });
    }

    private void finish() {
        if (done.compareAndSet(false, true)) finished.run();
    }
}
