package com.productvideostudio.service;

import android.os.Handler;
import android.os.Looper;

import java.util.concurrent.CopyOnWriteArrayList;

/** Process-wide state of the current render, observed by the UI on the main thread. */
public final class RenderState {
    public interface Listener {
        void onRenderUpdate(RenderState state);
    }

    public enum Status { IDLE, RUNNING, DONE, FAILED, CANCELLED }

    private static final RenderState INSTANCE = new RenderState();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final CopyOnWriteArrayList<Listener> listeners = new CopyOnWriteArrayList<>();

    public volatile Status status = Status.IDLE;
    public volatile String projectId;
    public volatile String stage = "";
    public volatile float progress;
    public volatile String error;
    public volatile boolean cancelRequested;

    public static RenderState get() {
        return INSTANCE;
    }

    public void addListener(Listener l) {
        listeners.add(l);
        l.onRenderUpdate(this);
    }

    public void removeListener(Listener l) {
        listeners.remove(l);
    }

    void update(Status s, String stage, float progress) {
        this.status = s;
        this.stage = stage;
        this.progress = progress;
        main.post(() -> {
            for (Listener l : listeners) l.onRenderUpdate(this);
        });
    }

    public boolean isRunning() {
        return status == Status.RUNNING;
    }
}
