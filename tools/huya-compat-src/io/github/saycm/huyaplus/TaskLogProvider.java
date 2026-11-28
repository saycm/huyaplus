package io.github.saycm.huyaplus;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Arrays;

public final class TaskLogProvider extends ContentProvider {
    public static final Uri URI = Uri.parse("content://" + GlassSettings.MODULE_PROVIDER);
    static final Uri TASKS_URI = URI.buildUpon().appendPath("tasks").build();
    private static final ZoneId TASK_ZONE = ZoneId.of("Asia/Shanghai");
    private SQLiteOpenHelper helper;

    @Override
    public boolean onCreate() {
        helper = new SQLiteOpenHelper(getContext(), "daily_tasks.db", null, 7) {
            @Override public void onCreate(SQLiteDatabase db) {
                db.execSQL("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        + "time INTEGER NOT NULL, task TEXT NOT NULL, target TEXT NOT NULL, "
                        + "state TEXT NOT NULL, detail TEXT NOT NULL, origin TEXT)");
                db.execSQL("CREATE UNIQUE INDEX events_origin ON events(origin)");
                createTasks(db);
                createHookStatus(db);
            }
            @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
                if (oldVersion < 2) {
                    db.execSQL("ALTER TABLE events ADD COLUMN origin TEXT");
                    db.execSQL("CREATE UNIQUE INDEX events_origin ON events(origin)");
                }
                if (oldVersion < 3) createTasks(db);
                if (oldVersion < 6) db.delete("tasks", null, null);
                if (oldVersion < 7) createHookStatus(db);
            }
            private void createTasks(SQLiteDatabase db) {
                db.execSQL("CREATE TABLE IF NOT EXISTS tasks (task_key TEXT PRIMARY KEY, "
                        + "title TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, "
                        + "updated INTEGER NOT NULL, sort_order INTEGER NOT NULL)");
            }
            private void createHookStatus(SQLiteDatabase db) {
                db.execSQL("CREATE TABLE IF NOT EXISTS hook_session (slot INTEGER PRIMARY KEY, "
                        + "process TEXT NOT NULL, session TEXT NOT NULL, started INTEGER NOT NULL, updated INTEGER NOT NULL)");
                db.execSQL("CREATE TABLE IF NOT EXISTS hook_features (feature TEXT PRIMARY KEY, "
                        + "state TEXT NOT NULL, reason TEXT NOT NULL)");
            }
        };
        return true;
    }

    @Override
    public synchronized Bundle call(String method, String arg, Bundle extras) {
        boolean owner = Binder.getCallingUid() == Process.myUid();
        String[] callers = getContext().getPackageManager().getPackagesForUid(Binder.getCallingUid());
        boolean huya = callers != null && Arrays.asList(callers).contains("com.duowan.kiwi");
        if (!owner && !huya) throw new SecurityException("Caller is not allowed");
        if (LiveMenu.REGISTER.equals(method)) {
            if (!huya) throw new SecurityException("Only Huya can register live-room menu entries");
            if (extras == null || extras.size() > 300) throw new IllegalArgumentException("Invalid live menu");
            saveLiveMenuCatalog(getContext(), extras);
            return new Bundle();
        }
        SQLiteDatabase db = helper.getWritableDatabase();
        Bundle result = new Bundle();
        if ("hook_status".equals(method)) {
            if (!huya) throw new SecurityException("Only Huya can report hook registration status");
            saveHookStatus(db, extras);
        } else if ("read_hook_status".equals(method)) {
            if (!owner) throw new SecurityException("Only module can read hook registration status");
            readHookStatus(db, result);
        } else if ("import".equals(method)) {
            ArrayList<Bundle> incoming = extras == null ? null : extras.getParcelableArrayList("events");
            if (incoming == null || incoming.size() > 50) throw new IllegalArgumentException("Invalid batch");
            long cutoff = getContext().getSharedPreferences("task_log_display", 0).getLong("cutoff", 0);
            db.beginTransaction();
            try {
                for (Bundle entry : incoming) {
                    String key = entry.getString("key", "");
                    if (key.isEmpty() || key.length() > 64 || entry.getLong("time") <= cutoff) continue;
                    ContentValues row = new ContentValues();
                    row.put("origin", key);
                    row.put("time", entry.getLong("time"));
                    for (String field : new String[]{"task", "target", "state", "detail"}) {
                        String value = entry.getString(field, "");
                        row.put(field, value.substring(0, Math.min(value.length(), 400)));
                    }
                    db.insertWithOnConflict("events", null, row, SQLiteDatabase.CONFLICT_IGNORE);
                }
                db.execSQL("DELETE FROM events WHERE id NOT IN "
                        + "(SELECT id FROM events ORDER BY time DESC, id DESC LIMIT 500)");
                db.setTransactionSuccessful();
            } finally {
                db.endTransaction();
            }
        } else if ("sync_complete".equals(method)) {
            if (!huya) throw new SecurityException("Only Huya can complete log synchronization");
            android.content.SharedPreferences display =
                    getContext().getSharedPreferences("task_log_display", 0);
            display.edit().putLong("last_sync",
                    Math.max(System.currentTimeMillis(), display.getLong("last_sync", 0) + 1)).commit();
        } else if ("import_tasks".equals(method)) {
            ArrayList<Bundle> incoming = extras == null ? null : extras.getParcelableArrayList("tasks");
            if (incoming == null || incoming.size() > 300) throw new IllegalArgumentException("Invalid task batch");
            db.beginTransaction();
            try {
                db.delete("tasks", null, null);
                for (int index = 0; index < incoming.size(); index++) {
                    Bundle entry = incoming.get(index);
                    if (entry.getInt("catalog_version", 0) != NativeTaskCatalog.VERSION) continue;
                    String key = entry.getString("key", "");
                    if (key.isEmpty() || key.length() > 160) continue;
                    ContentValues row = new ContentValues();
                    row.put("task_key", key);
                    row.put("title", bounded(entry.getString("title", "")));
                    row.put("status", bounded(entry.getString("status", "")));
                    row.put("detail", bounded(entry.getString("detail", "")));
                    row.put("updated", entry.getLong("updated"));
                    row.put("sort_order", index);
                    db.insertWithOnConflict("tasks", null, row, SQLiteDatabase.CONFLICT_REPLACE);
                }
                db.setTransactionSuccessful();
            } finally {
                db.endTransaction();
            }
            getContext().getSharedPreferences("task_log_display", 0).edit()
                    .putLong("last_tasks_sync", System.currentTimeMillis()).apply();
            getContext().getContentResolver().notifyChange(TASKS_URI, null);
        } else if ("sync_status".equals(method)) {
            if (!owner) throw new SecurityException("Only module can read log synchronization status");
            result.putLong("last_sync", getContext().getSharedPreferences("task_log_display", 0)
                    .getLong("last_sync", 0));
        } else if ("read".equals(method)) {
            if (!owner) throw new SecurityException("Only module can read logs");
            ArrayList<Bundle> entries = new ArrayList<>();
            try (Cursor rows = db.rawQuery("SELECT time, task, target, state, detail "
                    + "FROM events ORDER BY time DESC, id DESC LIMIT 300", null)) {
                while (rows.moveToNext()) {
                    Bundle entry = new Bundle();
                    entry.putLong("time", rows.getLong(0));
                    entry.putString("task", rows.getString(1));
                    entry.putString("target", rows.getString(2));
                    entry.putString("state", rows.getString(3));
                    entry.putString("detail", rows.getString(4));
                    entries.add(entry);
                }
            }
            result.putParcelableArrayList("events", entries);
            result.putLong("last_sync", getContext().getSharedPreferences("task_log_display", 0)
                    .getLong("last_sync", 0));
        } else if ("read_tasks".equals(method)) {
            if (!owner) throw new SecurityException("Only module can read task catalog");
            ArrayList<Bundle> entries = new ArrayList<>();
            LocalDate today = LocalDate.now(TASK_ZONE);
            try (Cursor rows = db.rawQuery("SELECT task_key, title, status, detail, updated "
                    + "FROM tasks WHERE updated >= ? AND updated < ? ORDER BY sort_order", new String[]{
                    Long.toString(today.atStartOfDay(TASK_ZONE).toInstant().toEpochMilli()),
                    Long.toString(today.plusDays(1).atStartOfDay(TASK_ZONE).toInstant().toEpochMilli())})) {
                while (rows.moveToNext()) {
                    Bundle entry = new Bundle();
                    entry.putString("key", rows.getString(0));
                    entry.putString("title", rows.getString(1));
                    entry.putString("status", rows.getString(2));
                    entry.putString("detail", rows.getString(3));
                    entry.putLong("updated", rows.getLong(4));
                    entries.add(entry);
                }
            }
            result.putParcelableArrayList("tasks", entries);
            result.putLong("last_sync", getContext().getSharedPreferences("task_log_display", 0)
                    .getLong("last_tasks_sync", 0));
        } else if ("clear".equals(method)) {
            if (!owner) throw new SecurityException("Only module can clear logs");
            getContext().getSharedPreferences("task_log_display", 0).edit()
                    .putLong("cutoff", System.currentTimeMillis()).commit();
            db.delete("events", null, null);
        } else {
            throw new IllegalArgumentException("Unknown action");
        }
        return result;
    }

    private void saveHookStatus(SQLiteDatabase db, Bundle status) {
        ArrayList<Bundle> features = status == null ? null : status.getParcelableArrayList("features");
        if (features == null || features.size() > 100
                || !"com.duowan.kiwi".equals(status.getString("process", ""))
                || status.getString("session", "").isEmpty() || status.getString("session", "").length() > 64
                || status.getLong("started") <= 0 || status.getLong("updated") < status.getLong("started")) {
            throw new IllegalArgumentException("Invalid main-process hook status");
        }
        db.beginTransaction();
        try {
            try (Cursor current = db.rawQuery("SELECT started FROM hook_session WHERE slot = 1", null)) {
                if (current.moveToFirst() && current.getLong(0) > status.getLong("started")) return;
            }
            ContentValues session = new ContentValues();
            session.put("slot", 1);
            session.put("process", "com.duowan.kiwi");
            session.put("session", status.getString("session"));
            session.put("started", status.getLong("started"));
            session.put("updated", status.getLong("updated"));
            db.replaceOrThrow("hook_session", null, session);
            db.delete("hook_features", null, null);
            for (Bundle entry : features) {
                String feature = entry.getString("feature", "");
                String state = entry.getString("state", "");
                if (feature.isEmpty() || feature.length() > 100 || !HookStatus.validState(state)) continue;
                ContentValues row = new ContentValues();
                row.put("feature", feature);
                row.put("state", state);
                row.put("reason", bounded(entry.getString("reason", "")));
                db.replaceOrThrow("hook_features", null, row);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private void readHookStatus(SQLiteDatabase db, Bundle result) {
        try (Cursor session = db.rawQuery("SELECT process, session, started, updated FROM hook_session WHERE slot = 1", null)) {
            if (!session.moveToFirst()) return;
            result.putString("process", session.getString(0));
            result.putString("session", session.getString(1));
            result.putLong("started", session.getLong(2));
            result.putLong("updated", session.getLong(3));
        }
        ArrayList<Bundle> features = new ArrayList<>();
        try (Cursor rows = db.rawQuery("SELECT feature, state, reason FROM hook_features ORDER BY feature", null)) {
            while (rows.moveToNext()) {
                Bundle entry = new Bundle();
                entry.putString("feature", rows.getString(0));
                entry.putString("state", rows.getString(1));
                entry.putString("reason", rows.getString(2));
                features.add(entry);
            }
        }
        result.putParcelableArrayList("features", features);
    }

    private static String bounded(String value) {
        return value.substring(0, Math.min(value.length(), 400));
    }

    static void saveLiveMenuCatalog(Context context, Bundle entries) {
        if (entries == null || entries.isEmpty()) return;
        SharedPreferences.Editor catalog = context.getSharedPreferences(LiveMenu.CATALOG, Context.MODE_PRIVATE).edit();
        for (String key : entries.keySet()) {
            if (!LiveMenu.isActivityKey(key)) continue;
            String title = entries.getString(key, "").trim();
            if (!title.isEmpty() && title.length() <= LiveMenu.MAX_TITLE_LENGTH) {
                catalog.putString(key, title);
            }
        }
        catalog.apply();
    }

    @Override public Cursor query(Uri uri, String[] p, String s, String[] a, String o) {
        throw new UnsupportedOperationException();
    }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
