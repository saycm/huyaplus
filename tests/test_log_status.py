"""Run journal/provider behavior against SQLite, without a phone or an Android VM."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'

SQLITE_BRIDGE = r'''
import base64, sqlite3, sys
db = sqlite3.connect(sys.argv[1], isolation_level=None, timeout=10)
def decode(value): return base64.b64decode(value).decode('utf-8')
def encode(value): return base64.b64encode(str(value).encode('utf-8')).decode('ascii')
def parameter(value):
    value = decode(value)
    return int(value[2:]) if value.startswith('n:') else value[2:]
for line in sys.stdin:
    try:
        sql, *args = line.rstrip('\n').split('\t')
        rows = db.execute(decode(sql), [parameter(value) for value in args]).fetchall()
        print('OK\t' + ';'.join(','.join(encode(value) for value in row) for row in rows), flush=True)
    except Exception as error:
        print('ERR\t' + str(error), flush=True)
'''

SOURCES = {
    'android/os/Bundle.java': '''package android.os;
public class Bundle {
 final java.util.Map<String,Object> values=new java.util.HashMap<>();
 public void putString(String k,String v){values.put(k,v);}
 public String getString(String k){return getString(k,"");}
 public String getString(String k,String d){return (String)values.getOrDefault(k,d);}
 public void putLong(String k,long v){values.put(k,v);}
 public long getLong(String k){return getLong(k,0);}
 public long getLong(String k,long d){return (Long)values.getOrDefault(k,d);}
 public void putInt(String k,int v){values.put(k,v);}
 public int getInt(String k,int d){return (Integer)values.getOrDefault(k,d);}
 public void putParcelableArrayList(String k,java.util.ArrayList<?> v){values.put(k,v);}
 @SuppressWarnings("unchecked") public <T> java.util.ArrayList<T> getParcelableArrayList(String k){return (java.util.ArrayList<T>)values.get(k);}
 public int size(){return values.size();} public boolean isEmpty(){return values.isEmpty();}
 public java.util.Set<String> keySet(){return values.keySet();}
}''',
    'android/os/Binder.java': '''package android.os; public class Binder {
 public static int uid=20; public static int getCallingUid(){return uid;}
}''',
    'android/os/Process.java': '''package android.os; public class Process {
 public static int myUid(){return 10;}
}''',
    'android/content/ContentValues.java': '''package android.content;
public class ContentValues extends java.util.LinkedHashMap<String,Object> {
 public void put(String k,String v){super.put(k,v);} public void put(String k,long v){super.put(k,v);}
 public void put(String k,int v){super.put(k,v);}
}''',
    'android/content/pm/PackageManager.java': '''package android.content.pm;
public class PackageManager {public String[] getPackagesForUid(int uid){return new String[]{uid==20?"com.duowan.kiwi":"other"};}
 public android.content.Intent getLaunchIntentForPackage(String name){return null;}}
''',
    'android/content/Context.java': '''package android.content;
public class Context {
 public static final int MODE_PRIVATE=0;
 public Context getApplicationContext(){return this;}
 public int getColor(int color){return color;}
 public <T>T getSystemService(Class<T> type){return null;}
 static final java.util.Map<String,java.util.Map<String,Object>> preferences=new java.util.HashMap<>();
 public android.content.pm.PackageManager getPackageManager(){return new android.content.pm.PackageManager();}
 public ContentResolver getContentResolver(){return new ContentResolver();}
 public SharedPreferences getSharedPreferences(String name,int mode){
  java.util.Map<String,Object> values=preferences.computeIfAbsent(name,k->new java.util.HashMap<>());
  return (SharedPreferences)java.lang.reflect.Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.class},(p,m,a)->{
   if(m.getName().equals("edit"))return java.lang.reflect.Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.Editor.class},(e,n,b)->{
    if(n.getName().startsWith("put")){values.put((String)b[0],b[1]);return e;}
    if(n.getName().equals("clear")){values.clear();return e;}
    if(n.getName().equals("commit"))return true;
    if(n.getName().equals("apply"))return null;
    throw new AssertionError(n);
   });
   if(m.getName().startsWith("get"))return values.getOrDefault((String)a[0],a[1]);
   throw new AssertionError(m);
  });
 }
}''',
    'android/content/ContentResolver.java': '''package android.content;
public class ContentResolver {
 public static ContentProvider provider;
 public android.os.Bundle call(android.net.Uri u,String m,String a,android.os.Bundle b){return provider.call(m,a,b);}
 public void notifyChange(android.net.Uri u,android.database.ContentObserver observer){}
}''',
    'android/content/ContentProvider.java': '''package android.content;
public abstract class ContentProvider {
 public Context getContext(){return new Context();}
 public abstract boolean onCreate(); public abstract android.os.Bundle call(String m,String a,android.os.Bundle b);
 public abstract android.database.Cursor query(android.net.Uri u,String[] p,String s,String[] a,String o);
 public abstract String getType(android.net.Uri u); public abstract android.net.Uri insert(android.net.Uri u,ContentValues v);
 public abstract int delete(android.net.Uri u,String s,String[] a); public abstract int update(android.net.Uri u,ContentValues v,String s,String[] a);
}''',
    'android/net/Uri.java': '''package android.net; public class Uri {
 public static Uri parse(String s){return new Uri();} public Uri buildUpon(){return this;}
 public Uri appendPath(String s){return this;} public Uri build(){return this;}
}''',
    'android/database/Cursor.java': '''package android.database;
public class Cursor implements AutoCloseable {
 final String[][] rows; int row=-1;
 public Cursor(String data){rows=data.isEmpty()?new String[0][]:java.util.Arrays.stream(data.split(";",-1)).map(r->java.util.Arrays.stream(r.split(",",-1)).map(v->new String(java.util.Base64.getDecoder().decode(v),java.nio.charset.StandardCharsets.UTF_8)).toArray(String[]::new)).toArray(String[][]::new);}
 public boolean moveToFirst(){row=0;return rows.length>0;} public boolean moveToNext(){return ++row<rows.length;}
 public String getString(int c){return rows[row][c];} public long getLong(int c){return Long.parseLong(getString(c));}
 public void close(){}
}''',
    'android/database/sqlite/SQLiteOpenHelper.java': '''package android.database.sqlite;
public abstract class SQLiteOpenHelper {
 final SQLiteDatabase db;
 public SQLiteOpenHelper(android.content.Context c,String name,Object f,int version){
  db=new SQLiteDatabase(name);
  try(android.database.Cursor row=db.rawQuery("PRAGMA user_version",null)){
   row.moveToFirst();int old=(int)row.getLong(0);
   if(old==0)onCreate(db);else if(old<version)onUpgrade(db,old,version);
   db.execSQL("PRAGMA user_version="+version);
  }
 }
 public abstract void onCreate(SQLiteDatabase db); public abstract void onUpgrade(SQLiteDatabase db,int old,int version);
 public SQLiteDatabase getWritableDatabase(){return db;} public SQLiteDatabase getReadableDatabase(){return db;}
}''',
    'android/database/sqlite/SQLiteDatabase.java': r'''package android.database.sqlite;
import java.io.*;import java.util.*;import android.content.ContentValues;
public class SQLiteDatabase {
 public static final int CONFLICT_IGNORE=4,CONFLICT_REPLACE=5;
 final BufferedWriter writer;final BufferedReader reader;boolean success;
 public SQLiteDatabase(String name){try{
  Process process=new ProcessBuilder(System.getProperty("python"),System.getProperty("bridge"),System.getProperty("dbroot")+"/"+name).start();
  writer=new BufferedWriter(new OutputStreamWriter(process.getOutputStream(),java.nio.charset.StandardCharsets.UTF_8));
  reader=new BufferedReader(new InputStreamReader(process.getInputStream(),java.nio.charset.StandardCharsets.UTF_8));
 }catch(IOException e){throw new RuntimeException(e);}}
 String encode(Object x){return Base64.getEncoder().encodeToString(String.valueOf(x).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
 synchronized String execute(String sql,Object[] args){try{
  writer.write(encode(sql));if(args!=null)for(Object arg:args){writer.write('\t');writer.write(encode((arg instanceof Number?"n:":"s:")+arg));}
  writer.newLine();writer.flush();String value=reader.readLine();
  if(value==null||!value.startsWith("OK\t"))throw new IllegalStateException(sql+": "+value);
  return value.substring(3);
 }catch(IOException e){throw new RuntimeException(e);}}
 public void execSQL(String sql){execute(sql,null);} public void execSQL(String sql,Object[] args){execute(sql,args);}
 public android.database.Cursor rawQuery(String sql,String[] args){return new android.database.Cursor(execute(sql,args));}
 public void beginTransaction(){success=false;execSQL("BEGIN IMMEDIATE");} public void setTransactionSuccessful(){success=true;}
 public void endTransaction(){execSQL(success?"COMMIT":"ROLLBACK");}
 public long insertWithOnConflict(String table,String unused,ContentValues values,int conflict){
  String sql="INSERT OR "+(conflict==4?"IGNORE":"REPLACE")+" INTO "+table+" ("+String.join(",",values.keySet())+") VALUES ("+String.join(",",Collections.nCopies(values.size(),"?"))+")";
  execute(sql,values.values().toArray());try(android.database.Cursor row=rawQuery("SELECT last_insert_rowid()",null)){row.moveToFirst();return row.getLong(0);}
 }
 public long insertOrThrow(String t,String n,ContentValues v){return insertWithOnConflict(t,n,v,CONFLICT_REPLACE);}
 public long replaceOrThrow(String t,String n,ContentValues v){return insertWithOnConflict(t,n,v,CONFLICT_REPLACE);}
 public int delete(String t,String where,String[] args){execute("DELETE FROM "+t+(where==null?"":" WHERE "+where),args);return 0;}
}''',
    'io/github/saycm/huyaplus/NativeTaskCatalog.java': '''package io.github.saycm.huyaplus;
final class NativeTaskCatalog {static final int VERSION=1;static class Task {
 String title;String key(){return "";}String statusLabel(){return "";}String statusDetail(){return "";}
}}''',
    'io/github/saycm/huyaplus/DiceTaskCatalog.java': '''package io.github.saycm.huyaplus;
final class DiceTaskCatalog {static class Task {
 String title;String key(){return "";}String statusLabel(){return "";}String statusDetail(){return "";}
}}''',
    'io/github/saycm/huyaplus/LiveMenu.java': '''package io.github.saycm.huyaplus;
final class LiveMenu {static final String REGISTER="register",CATALOG="catalog";static final int MAX_TITLE_LENGTH=100;
 static boolean isActivityKey(String key){return true;}}
''',
    'io/github/saycm/huyaplus/DailyAutomation.java': '''package io.github.saycm.huyaplus;
final class DailyAutomation {static final String SYNC_LOGS="sync";}''',
    'io/github/saycm/huyaplus/SystemBarInsets.java': '''package io.github.saycm.huyaplus;
final class SystemBarInsets {static void apply(android.view.View view){}}''',
    'io/github/saycm/huyaplus/R.java': '''package io.github.saycm.huyaplus;
final class R {
 static class drawable {static final int dashboard_background=1,accent_button=2,glass_card=3;}
 static class color {static final int huya_accent=1,glass_text=2,glass_secondary=3,hero_text=4;}
}''',
    'io/github/saycm/huyaplus/LogStatusTest.java': '''package io.github.saycm.huyaplus;
import android.content.*;import android.os.*;import java.util.*;import java.lang.reflect.*;
public class LogStatusTest {
 static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
 static void ack(LocalTaskStore store,long id)throws Exception{
  try{LocalTaskStore.class.getDeclaredMethod("acknowledgeEvents",long.class).invoke(store,id);}
  catch(NoSuchMethodException e){throw new AssertionError("journal has no durable acknowledgement cursor");}
 }
 static Bundle status(String session,long started,String state){
  Bundle b=new Bundle();b.putString("process","com.duowan.kiwi");b.putString("session",session);
  b.putLong("started",started);b.putLong("updated",started+10);
  Bundle feature=new Bundle();feature.putString("feature","ads");feature.putString("state",state);feature.putString("reason","test reason");
  b.putParcelableArrayList("features",new ArrayList<>(List.of(feature)));return b;
 }
 public static void main(String[] args)throws Exception{
  Context context=new Context();
  if(args[0].equals("summary")){
   Method summarize;
   try{summarize=TaskLogActivity.class.getDeclaredMethod("summarize",List.class);}
   catch(NoSuchMethodException e){throw new AssertionError("log view has no result summary for the selected range");}
   List<Bundle> entries=new ArrayList<>();
   for(String state:List.of("成功","失败","未确认","服务端未确认","结果未确认","未完成","请求已发出","跳过")){
    Bundle row=new Bundle();row.putString("state",state);entries.add(row);
   }
   String text=(String)summarize.invoke(null,entries);
   check(text.contains("成功 1")&&text.contains("失败 1")&&text.contains("未确认/未完成 4"),"outcomes merged or miscounted: "+text);
   check(text.contains("8 条日志")&&!text.contains("8 个任务"),"event count was presented as task count");
   return;
  }
  if(args[0].equals("status-format")){
   Method describe;
   try{describe=HookStatus.class.getDeclaredMethod("describe",Bundle.class);}
   catch(NoSuchMethodException e){throw new AssertionError("detail cannot distinguish cached sessions from current hook state");}
   String empty=(String)describe.invoke(null,new Bundle());
   check(empty.contains("等待宿主启动"),"missing host was reported as loaded");
   String cached=(String)describe.invoke(null,status("new",200,"partial"));
   check(cached.contains("最近主进程会话")&&cached.contains("当前是否运行未确认"),"cached session impersonates a live host: "+cached);
   check(cached.contains("部分加载")&&cached.contains("test reason"),"partial registration reason missing");
   for(String state:List.of("registered","disabled","waiting","failed")){
    String text=(String)describe.invoke(null,status("new",200,state));
    check(!text.contains("未知状态"),"supported hook state missing: "+state);
   }
   return;
  }
  if(args[0].equals("cursor")){
   LocalTaskStore first=new LocalTaskStore(context);first.append("sign","1","成功","ok");first.append("sign","2","未确认","pending");
   ArrayList<Bundle> rows=first.events();check(rows.size()==2,"new events missing");
   ack(first,rows.get(0).getLong("id"));
   LocalTaskStore second=new LocalTaskStore(context);
   check(second.events().size()==1,"acknowledgement did not survive another connection");
   long newest=second.events().get(0).getLong("id");
   Thread a=new Thread(()->{try{ack(first,newest);}catch(Exception e){throw new RuntimeException(e);}});
   Thread b=new Thread(()->{try{ack(second,rows.get(0).getLong("id"));}catch(Exception e){throw new RuntimeException(e);}});
   a.start();b.start();a.join();b.join();
   check(new LocalTaskStore(context).events().isEmpty(),"stale concurrent ack regressed shared cursor");
   first.append("sign","3","成功","new");check(second.events().size()==1,"new event was skipped after ack");return;
  }
  if(args[0].equals("backlog")){
   LocalTaskStore store=new LocalTaskStore(context);
   for(int i=0;i<510;i++)store.append("offline",String.valueOf(i),"未确认","awaiting sync");
   ArrayList<Bundle> pending=store.events();
   check(pending.size()==510,"retention dropped unacknowledged events during a sync outage");
   ack(store,pending.get(pending.size()-1).getLong("id"));
   try(android.database.Cursor count=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM events",null)){
    count.moveToFirst();check(count.getLong(0)==500,"acknowledged history did not return to retention limit");
   }
   return;
  }
  TaskLogProvider provider=new TaskLogProvider();provider.onCreate();ContentResolver.provider=provider;
  if(args[0].equals("clear")){
   Bundle row=new Bundle();row.putString("key","old");row.putLong("time",System.currentTimeMillis()-10000);
   Bundle batch=new Bundle();batch.putParcelableArrayList("events",new ArrayList<>(List.of(row)));
   provider.call("import",null,batch);provider.call("import",null,batch);
   Binder.uid=10;check(provider.call("read",null,null).getParcelableArrayList("events").size()==1,"origin deduplication failed");
   provider.call("clear",null,null);Binder.uid=20;provider.call("import",null,batch);
   row.putString("key","new");row.putLong("time",System.currentTimeMillis()+1);provider.call("import",null,batch);
   Binder.uid=10;ArrayList<Bundle> rows=provider.call("read",null,null).getParcelableArrayList("events");
   check(rows.size()==1,"clear refilled old history or dropped new event");return;
  }
  if(args[0].equals("status")){
   try{provider.call("hook_status",null,status("new",200,"partial"));}
   catch(IllegalArgumentException e){throw new AssertionError("provider cannot publish actual hook registration status");}
   Binder.uid=10;Bundle read=provider.call("read_hook_status",null,null);
   check("new".equals(read.getString("session")),"session metadata missing");
   ArrayList<Bundle> features=read.getParcelableArrayList("features");
   check(features.size()==1&&"partial".equals(features.get(0).getString("state")),"partial status missing");
   try{provider.call("hook_status",null,status("owner",300,"registered"));throw new AssertionError("owner wrote host hook status");}catch(SecurityException expected){}
   Binder.uid=20;try{provider.call("read_hook_status",null,null);throw new AssertionError("host read owner status");}catch(SecurityException expected){}
   provider.call("hook_status",null,status("old",100,"registered"));
   Bundle wrong=status("other",400,"registered");wrong.putString("process","com.duowan.kiwi:push");
   try{provider.call("hook_status",null,wrong);throw new AssertionError("secondary process overwrote main status");}catch(IllegalArgumentException expected){}
   Binder.uid=10;check("new".equals(provider.call("read_hook_status",null,null).getString("session")),"old process overwrote recent session");
  }
 }
}''',
}


class LogStatusTest(unittest.TestCase):
    def test_journal_cursor_clear_and_host_status_permissions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/test-tmp') as folder:
            root = Path(folder)
            bridge = root / 'sqlite_bridge.py'
            bridge.write_text(SQLITE_BRIDGE, encoding='utf-8')
            sources = []
            for name, text in SOURCES.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text, encoding='utf-8')
                sources.append(str(file))
            sources += [str(PACKAGE / (name + '.java')) for name in
                        ('LocalTaskStore', 'TaskLogProvider', 'GlassSettings', 'AutomationRules', 'TaskLogActivity')]
            if (PACKAGE / 'HookStatus.java').exists():
                sources.append(str(PACKAGE / 'HookStatus.java'))
            java = Path(os.environ['JAVA_HOME']) / 'bin'
            android = Path(os.environ['ANDROID_HOME']) / 'platforms/android-36/android.jar'
            compiled = subprocess.run([str(java / 'javac.exe'), '-encoding', 'UTF-8', '-cp', str(android),
                                       '-d', str(root), *sources], capture_output=True, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for case in ('cursor', 'backlog', 'clear', 'status', 'summary', 'status-format'):
                with self.subTest(case=case):
                    dbroot = root / case
                    dbroot.mkdir()
                    result = subprocess.run([str(java / 'java.exe'), '-cp', os.pathsep.join((str(root), str(android))),
                                             '-Dpython=' + sys.executable, '-Dbridge=' + str(bridge), '-Ddbroot=' + str(dbroot),
                                             'io.github.saycm.huyaplus.LogStatusTest', case],
                                            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
