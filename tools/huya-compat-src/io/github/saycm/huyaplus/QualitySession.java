package io.github.saycm.huyaplus;

import java.util.HashSet;
import java.util.Set;

final class QualitySession {
    private static final int MAX_ATTEMPTS = 5;
    private int generation;
    private int attempts;
    private boolean finished;
    private boolean queued;
    private boolean switching;
    private final Set<Integer> rejectedRates = new HashSet<>();
    private boolean noticeShown;
    private long noticeAfter;
    private long room;

    synchronized int enter() {
        return reset(0L);
    }

    synchronized int enterRoom(long roomId) {
        return roomId <= 0L || roomId == room ? 0 : reset(roomId);
    }

    synchronized long roomId(int token) {
        return token == generation ? room : -1L;
    }

    synchronized boolean matchesRoom(int token, long playId) {
        return token == generation && (room == 0L || playId == room);
    }

    private int reset(long roomId) {
        room = roomId;
        attempts = 0;
        finished = false;
        queued = false;
        switching = false;
        rejectedRates.clear();
        noticeShown = false;
        noticeAfter = Long.MIN_VALUE;
        return ++generation;
    }

    synchronized int current() {
        return generation;
    }

    synchronized boolean pending(int token) {
        return token == generation && !finished;
    }

    synchronized boolean queue(int token) {
        if (!pending(token) || queued || switching || attempts >= MAX_ATTEMPTS) return false;
        queued = true;
        return true;
    }

    synchronized boolean beginAttempt(int token) {
        if (!pending(token)) return false;
        attempts++;
        return true;
    }

    synchronized void dequeue(int token) {
        if (token == generation) queued = false;
    }

    synchronized boolean claim(int token) {
        if (!pending(token)) return false;
        finished = true;
        switching = false;
        return true;
    }

    synchronized void manualSelection() {
        finished = true;
        switching = false;
    }

    synchronized void startSwitch(int token) {
        if (pending(token)) switching = true;
    }

    synchronized void endSwitch(int token, int rejectedRate) {
        if (!pending(token)) return;
        switching = false;
        if (rejectedRate >= 0) rejectedRates.add(rejectedRate);
    }

    synchronized boolean rejected(int token, int bitrate) {
        return token == generation && rejectedRates.contains(bitrate);
    }

    synchronized void deferNotice(int token, long time) {
        if (token == generation) noticeAfter = time;
    }

    synchronized boolean noticePending(int token) {
        return token == generation && !noticeShown;
    }

    synchronized boolean noticeReady(int token, long now) {
        return noticePending(token) && !queued && !switching && now >= noticeAfter;
    }

    synchronized boolean claimNotice(int token, long now) {
        if (!noticeReady(token, now)) return false;
        noticeShown = true;
        return true;
    }
}
