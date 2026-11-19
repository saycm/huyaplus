package io.github.saycm.huyaplus;

final class QualitySession {
    private int generation;
    private boolean finished;
    private boolean queued;

    synchronized int enter() {
        finished = false;
        queued = false;
        return ++generation;
    }

    synchronized int current() {
        return generation;
    }

    synchronized boolean pending(int token) {
        return token == generation && !finished;
    }

    synchronized boolean queue(int token) {
        if (!pending(token) || queued) return false;
        queued = true;
        return true;
    }

    synchronized void dequeue(int token) {
        if (token == generation) queued = false;
    }

    synchronized boolean claim(int token) {
        if (!pending(token)) return false;
        finished = true;
        return true;
    }

    synchronized void manualSelection() {
        finished = true;
    }
}
