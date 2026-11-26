package io.github.saycm.huyaplus;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.Bundle;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

final class LocalTaskStore extends SQLiteOpenHelper {
    private final Runnable onAppend;

    LocalTaskStore(Context context) { this(context, null); }

    LocalTaskStore(Context context, Runnable onAppend) {
        super(context, "fuckad_daily_tasks.db", null, 6);
        this.onAppend = onAppend;
    }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE runs (run_key TEXT PRIMARY KEY, started INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE NOT NULL, "
                + "time INTEGER NOT NULL, task TEXT NOT NULL, target TEXT NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL)");
        createTasks(db);
        createGiftPlans(db);
        createTaskScope(db);
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) createTasks(db);
        if (oldVersion < 3) db.delete("tasks", null, null);
        else if (oldVersion < 4) db.delete("tasks", "task_key LIKE ?", new String[]{"dice/%"});
        if (oldVersion < 5) createGiftPlans(db);
        if (oldVersion < 6) {
            createTaskScope(db);
            db.delete("tasks", null, null);
        }
    }

    private void createTasks(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS tasks (task_key TEXT PRIMARY KEY, title TEXT NOT NULL, "
                + "status TEXT NOT NULL, detail TEXT NOT NULL, updated INTEGER NOT NULL, "
                + "sort_order INTEGER NOT NULL)");
    }

    private void createGiftPlans(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS gift_plans (day_key TEXT PRIMARY KEY, plan TEXT NOT NULL, "
                + "created INTEGER NOT NULL)");
    }

    private void createTaskScope(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS task_scope (slot INTEGER PRIMARY KEY, scope TEXT NOT NULL)");
    }

    synchronized void selectTaskScope(String scope) {
        SQLiteDatabase db = getWritableDatabase();
        if (matchesTaskScope(db, scope)) return;
        db.beginTransaction();
        try {
            db.delete("tasks", null, null);
            ContentValues row = new ContentValues();
            row.put("slot", 1);
            row.put("scope", scope);
            db.replaceOrThrow("task_scope", null, row);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private boolean matchesTaskScope(SQLiteDatabase db, String scope) {
        if (scope == null || scope.isEmpty()) return false;
        try (Cursor row = db.rawQuery("SELECT 1 FROM task_scope WHERE slot = 1 AND scope = ?",
                new String[]{scope})) {
            return row.moveToFirst();
        }
    }

    synchronized boolean claim(String key) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues row = new ContentValues();
        row.put("run_key", key);
        row.put("started", System.currentTimeMillis());
        boolean claimed = db.insertWithOnConflict("runs", null, row, SQLiteDatabase.CONFLICT_IGNORE) != -1;
        db.delete("runs", "started < ?", new String[]{Long.toString(System.currentTimeMillis() - 35L * 86400000L)});
        return claimed;
    }

    synchronized boolean hasClaim(String key) {
        try (Cursor row = getReadableDatabase().rawQuery(
                "SELECT 1 FROM runs WHERE run_key = ?", new String[]{key})) {
            return row.moveToFirst();
        }
    }

    synchronized boolean claimFirstGrainPart(String giftKey, String day, long room) {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            if (!claim(giftKey) || !claim("dice-grain-room/" + day + "/" + room)) return false;
            claim("dice-grain-started/" + day);
            db.setTransactionSuccessful();
            return true;
        } finally {
            db.endTransaction();
        }
    }

    synchronized void release(String key) {
        getWritableDatabase().delete("runs", "run_key = ?", new String[]{key});
    }

    synchronized List<AutomationRules.GrainPart> diceGrainPlan(String day) {
        try (Cursor row = getReadableDatabase().rawQuery(
                "SELECT plan FROM gift_plans WHERE day_key = ?", new String[]{day})) {
            if (!row.moveToFirst()) return null;
            List<AutomationRules.GrainPart> plan = new ArrayList<>(3);
            for (String line : row.getString(0).split("\n")) {
                String[] part = line.split(",");
                plan.add(new AutomationRules.GrainPart(Long.parseLong(part[0]), Integer.parseInt(part[1]),
                        Integer.parseInt(part[2]), Integer.parseInt(part[3])));
            }
            return plan;
        }
    }

    synchronized List<AutomationRules.GrainPart> saveDiceGrainPlan(String day,
                                                                List<AutomationRules.GrainPart> plan) {
        if (plan.isEmpty()) return plan;
        StringBuilder encoded = new StringBuilder();
        for (AutomationRules.GrainPart part : plan) {
            encoded.append(part.room).append(',').append(part.count).append(',')
                    .append(part.number).append(',').append(part.remaining).append('\n');
        }
        long now = System.currentTimeMillis();
        ContentValues row = new ContentValues();
        row.put("day_key", day);
        row.put("plan", encoded.toString());
        row.put("created", now);
        SQLiteDatabase db = getWritableDatabase();
        db.insertWithOnConflict("gift_plans", null, row, SQLiteDatabase.CONFLICT_IGNORE);
        db.delete("gift_plans", "created < ?", new String[]{Long.toString(now - 35L * 86400000L)});
        List<AutomationRules.GrainPart> saved = diceGrainPlan(day);
        if (saved == null) throw new IllegalStateException("Gift plan was not saved");
        return saved;
    }

    synchronized void append(String task, String target, String state, String detail) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues row = new ContentValues();
        row.put("event_key", UUID.randomUUID().toString());
        row.put("time", System.currentTimeMillis());
        row.put("task", trim(task)); row.put("target", trim(target));
        row.put("state", trim(state)); row.put("detail", trim(detail));
        db.insertOrThrow("events", null, row);
        db.execSQL("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 500)");
        if (onAppend != null) onAppend.run();
    }

    synchronized ArrayList<Bundle> events() {
        ArrayList<Bundle> entries = new ArrayList<>();
        try (Cursor rows = getReadableDatabase().rawQuery(
                "SELECT event_key,time,task,target,state,detail FROM events ORDER BY id", null)) {
            while (rows.moveToNext()) {
                Bundle entry = new Bundle();
                entry.putString("key", rows.getString(0));
                entry.putLong("time", rows.getLong(1));
                entry.putString("task", rows.getString(2));
                entry.putString("target", rows.getString(3));
                entry.putString("state", rows.getString(4));
                entry.putString("detail", rows.getString(5));
                entries.add(entry);
            }
        }
        return entries;
    }

    synchronized void replaceTasks(String scope, List<NativeTaskCatalog.Task> tasks) {
        SQLiteDatabase db = getWritableDatabase();
        if (!matchesTaskScope(db, scope)) return;
        long updated = System.currentTimeMillis();
        db.beginTransaction();
        try {
            db.delete("tasks", "task_key NOT LIKE ?", new String[]{"dice/%"});
            for (int index = 0; index < tasks.size(); index++) {
                NativeTaskCatalog.Task task = tasks.get(index);
                ContentValues row = new ContentValues();
                row.put("task_key", trim(task.key()));
                row.put("title", trim(task.title));
                row.put("status", trim(task.statusLabel()));
                row.put("detail", trim(task.statusDetail()));
                row.put("updated", updated);
                row.put("sort_order", index);
                db.insertOrThrow("tasks", null, row);
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
        if (onAppend != null) onAppend.run();
    }

    synchronized void replaceDiceTasks(String scope, List<DiceTaskCatalog.Task> tasks) {
        SQLiteDatabase db = getWritableDatabase();
        if (!matchesTaskScope(db, scope)) return;
        long updated = System.currentTimeMillis();
        db.beginTransaction();
        try {
            db.delete("tasks", "task_key LIKE ?", new String[]{"dice/%"});
            for (int index = 0; index < tasks.size(); index++) {
                DiceTaskCatalog.Task task = tasks.get(index);
                ContentValues row = new ContentValues();
                row.put("task_key", trim(task.key()));
                row.put("title", trim(task.title));
                row.put("status", trim(task.statusLabel()));
                row.put("detail", trim(task.statusDetail()));
                row.put("updated", updated);
                row.put("sort_order", index);
                db.insertOrThrow("tasks", null, row);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        if (onAppend != null) onAppend.run();
    }

    synchronized ArrayList<Bundle> tasks(String scope) {
        ArrayList<Bundle> entries = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        if (!matchesTaskScope(db, scope)) return entries;
        try (Cursor rows = db.rawQuery(
                "SELECT task_key,title,status,detail,updated FROM tasks ORDER BY sort_order", null)) {
            while (rows.moveToNext()) {
                Bundle entry = new Bundle();
                entry.putString("key", rows.getString(0));
                entry.putString("title", rows.getString(1));
                entry.putString("status", rows.getString(2));
                entry.putString("detail", rows.getString(3));
                entry.putLong("updated", rows.getLong(4));
                entry.putInt("catalog_version", NativeTaskCatalog.VERSION);
                entries.add(entry);
            }
        }
        return entries;
    }

    private String trim(String value) {
        return value.substring(0, Math.min(value.length(), 400));
    }
}
