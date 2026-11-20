package io.github.saycm.huyaplus;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;

import java.util.ArrayList;
import java.util.Arrays;

public final class TaskLogProvider extends ContentProvider {
    public static final Uri URI = Uri.parse("content://" + GlassSettings.MODULE_PROVIDER);
    private SQLiteOpenHelper helper;

    @Override
    public boolean onCreate() {
        helper = new SQLiteOpenHelper(getContext(), "daily_tasks.db", null, 5) {
            @Override public void onCreate(SQLiteDatabase db) {
                db.execSQL("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        + "time INTEGER NOT NULL, task TEXT NOT NULL, target TEXT NOT NULL, "
                        + "state TEXT NOT NULL, detail TEXT NOT NULL, origin TEXT)");
                db.execSQL("CREATE UNIQUE INDEX events_origin ON events(origin)");
                createTasks(db);
            }
            @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
                if (oldVersion < 2) {
                    db.execSQL("ALTER TABLE events ADD COLUMN origin TEXT");
                    db.execSQL("CREATE UNIQUE INDEX events_origin ON events(origin)");
                }
                if (oldVersion < 3) createTasks(db);
                if (oldVersion < 4) db.delete("tasks", null, null);
                else if (oldVersion < 5) db.delete("tasks", "task_key LIKE ?", new String[]{"dice/%"});
            }
            private void createTasks(SQLiteDatabase db) {
                db.execSQL("CREATE TABLE IF NOT EXISTS tasks (task_key TEXT PRIMARY KEY, "
                        + "title TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, "
                        + "updated INTEGER NOT NULL, sort_order INTEGER NOT NULL)");
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
        if (GlassSettings.VERIFY_ROOT.equals(method)) {
            long identity = Binder.clearCallingIdentity();
            try {
                Bundle result = new Bundle();
                result.putBoolean(GlassSettings.ROOT_GRANTED, RootAccess.verify(getContext()));
                return result;
            } finally {
                Binder.restoreCallingIdentity(identity);
            }
        }
        SQLiteDatabase db = helper.getWritableDatabase();
        Bundle result = new Bundle();
        if ("import".equals(method)) {
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
            try (Cursor rows = db.rawQuery("SELECT task_key, title, status, detail, updated "
                    + "FROM tasks ORDER BY sort_order", null)) {
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

    private static String bounded(String value) {
        return value.substring(0, Math.min(value.length(), 400));
    }

    @Override public Cursor query(Uri uri, String[] p, String s, String[] a, String o) {
        throw new UnsupportedOperationException();
    }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
