"""Run the real daily engine against a deterministic Android/network boundary."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_huya_loader_lifecycle import ROOT, JDK, SDK, EXE, SOURCES


DAILY_SOURCES = dict(SOURCES)
DAILY_SOURCES.update({
    "android/net/Uri.java": '''package android.net;
public class Uri {
 private final String value;
 private Uri(String value){this.value=value;}
 public static Uri parse(String value){return new Uri(value);}
 public String getScheme(){return java.net.URI.create(value).getScheme();}
 public String toString(){return value;}
}
''',
    "android/os/Bundle.java": '''package android.os;
import java.util.*;
public class Bundle {
 private final Map<String,Object> values=new HashMap<>();
 public boolean isEmpty(){return values.isEmpty();}
 public int size(){return values.size();}
 public Set<String> keySet(){return values.keySet();}
 public void putString(String key,String value){values.put(key,value);}
 public String getString(String key){return getString(key,null);}
 public String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}
 public void putBoolean(String key,boolean value){values.put(key,value);}
 public boolean getBoolean(String key,boolean fallback){return (Boolean)values.getOrDefault(key,fallback);}
 public void putLong(String key,long value){values.put(key,value);}
 public long getLong(String key){return (Long)values.get(key);}
 public void putParcelableArrayList(String key,java.util.ArrayList<?> value){values.put(key,value);}
 public java.util.ArrayList getParcelableArrayList(String key){return (java.util.ArrayList)values.get(key);}
}
''',
    # Provider persistence is outside the daily engine harness.
    "io/github/saycm/huyaplus/TaskLogProvider.java": '''package io.github.saycm.huyaplus;
public class TaskLogProvider {
 public static final android.net.Uri URI=android.net.Uri.parse("tasks");
 public static void saveLiveMenuCatalog(android.content.Context context,android.os.Bundle entries){}
}
''',
    "android/os/Looper.java": '''package android.os;
public class Looper {public static Looper getMainLooper(){return new Looper();}}
''',
    "android/os/Handler.java": '''package android.os;
import java.util.*;
public class Handler {
 static long now;
 static long order;
 static class Task {long due,id;Runnable run;Task(long d,Runnable r){due=d;run=r;id=order++;}}
 static final PriorityQueue<Task> tasks=new PriorityQueue<>((a,b)->a.due==b.due?
   Long.compare(a.id,b.id):Long.compare(a.due,b.due));
 public Handler(Looper looper){}
 public boolean post(Runnable run){return postDelayed(run,0);}
 public boolean postDelayed(Runnable run,long delay){tasks.add(new Task(now+delay,run));return true;}
 public void removeCallbacks(Runnable run){tasks.removeIf(task->task.run==run);}
 public static void advance(long ms){
  long end=now+ms;
  while(!tasks.isEmpty()&&tasks.peek().due<=end){Task task=tasks.poll();now=task.due;task.run.run();}
  now=end;
 }
}
''',
    "android/content/ContentResolver.java": '''package android.content;
import java.util.*;import android.os.Bundle;import android.net.Uri;
public class ContentResolver {
 public static boolean blocked;
 public static boolean delaySync;
 public static final java.util.concurrent.CountDownLatch entered=new java.util.concurrent.CountDownLatch(1);
 public static final java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1);
 public static final Set<String> claims=new HashSet<>();
 public static final List<Bundle> events=new ArrayList<>();
 public static volatile int imports, completed;
 public static volatile boolean nullImport;
 public static int failImportAt;
 public Bundle call(String authority,String method,String arg,Bundle row){return null;}
 public Bundle call(Uri uri,String method,String arg,Bundle row){
  if(delaySync){entered.countDown();try{release.await();}catch(InterruptedException e){throw new RuntimeException(e);}}
  if(blocked)throw new IllegalStateException("Module process must remain stopped");
  Bundle result=new Bundle();
  if("import".equals(method)&&row!=null){
   if(nullImport)return null;
   imports++;
   if(imports==failImportAt)throw new IllegalStateException("batch transport failed");
   events.addAll(row.getParcelableArrayList("events"));
  }
  if("sync_complete".equals(method))completed++;
  return result;
 }
}
''',
    "android/content/Context.java": '''package android.content;
public class Context {
 public static final int MODE_PRIVATE=0;
 public static final int RECEIVER_EXPORTED=2;
 public static BroadcastReceiver receiver;
 public Context getApplicationContext(){return this;}
 public ContentResolver getContentResolver(){return new ContentResolver();}
 public android.content.res.Resources getResources(){return null;}
 public SharedPreferences getSharedPreferences(String name,int mode){return null;}
 public ClassLoader getClassLoader(){return getClass().getClassLoader();}
 public void startActivity(Intent intent){}
 public Intent registerReceiver(BroadcastReceiver value,IntentFilter filter){receiver=value;return null;}
 public Intent registerReceiver(BroadcastReceiver value,IntentFilter filter,int flags){receiver=value;return null;}
}
''',
    "android/content/BroadcastReceiver.java": '''package android.content;
public abstract class BroadcastReceiver {public abstract void onReceive(Context context,Intent intent);}
''',
    "android/content/Intent.java": '''package android.content;
public class Intent {private final String action;public Intent(String action){this.action=action;}
 public Intent(){this(null);}
 public Intent setClassName(String packageName,String className){return this;}
 public Intent putExtra(String key,android.os.Bundle value){return this;}
 public String getAction(){return action;}}
''',
    "android/content/IntentFilter.java": '''package android.content;
public class IntentFilter {public IntentFilter(String action){}}
''',
    "io/github/saycm/huyaplus/LocalTaskStore.java": '''package io.github.saycm.huyaplus;
import android.os.Bundle;import android.content.*;import java.util.*;
final class LocalTaskStore {
 static final List<Bundle> localEvents=new ArrayList<>();
 static final List<String> taskScopes=new ArrayList<>();
 static final Map<String,List<AutomationRules.GrainPart>> giftPlans=new HashMap<>();
 static long lastId,acknowledged;
 final Runnable onAppend;
 LocalTaskStore(Context context){this(context,null);}
 LocalTaskStore(Context context,Runnable onAppend){this.onAppend=onAppend;}
 boolean claim(String key){return ContentResolver.claims.add(key);}
 boolean hasClaim(String key){return ContentResolver.claims.contains(key);}
 boolean claimFirstGrainPart(String key,String day,long room){
  String owner="dice-grain-room/"+day+"/"+room;
  if(hasClaim(key)||hasClaim(owner))return false;
  claim(key);claim(owner);claim("dice-grain-started/"+day);return true;
 }
 void release(String key){ContentResolver.claims.remove(key);}
 void selectTaskScope(String scope){taskScopes.add(scope);}
 List<AutomationRules.GrainPart> diceGrainPlan(String day){return giftPlans.get(day);}
 List<AutomationRules.GrainPart> saveDiceGrainPlan(String day,List<AutomationRules.GrainPart> plan){
  return giftPlans.computeIfAbsent(day,key->plan);
 }
 void append(String task,String target,String state,String detail){
  Bundle row=new Bundle();row.putString("task",task);row.putString("target",target);
  row.putString("state",state);row.putString("detail",detail);row.putLong("id",++lastId);localEvents.add(row);
  if(onAppend!=null)onAppend.run();
 }
 void replaceTasks(String scope,List<NativeTaskCatalog.Task> tasks){if(onAppend!=null)onAppend.run();}
 void replaceDiceTasks(String scope,List<DiceTaskCatalog.Task> tasks){if(onAppend!=null)onAppend.run();}
 ArrayList<Bundle> events(){
  ArrayList<Bundle> pending=new ArrayList<>();
  for(Bundle row:localEvents)if(row.getLong("id")>acknowledged)pending.add(row);
  return pending;
 }
 void acknowledgeEvents(long id){acknowledged=Math.max(acknowledged,id);}
 ArrayList<Bundle> tasks(String scope){return new ArrayList<>();}
}
''',
    "com/duowan/taf/jce/JceStruct.java": '''package com.duowan.taf.jce;public class JceStruct {}
''',
    "com/huya/mtp/data/exception/DataException.java": '''package com.huya.mtp.data.exception;
public class DataException extends RuntimeException {}
''',
    "ryxq/oe6.java": '''package ryxq;
public class oe6 {public static int originals;
 public void onError(com.huya.mtp.data.exception.DataException error,boolean cache){originals++;}
}
''',
    "ryxq/jd8.java": '''package ryxq;
public class jd8 extends oe6 {
 public void onResponse(com.duowan.taf.jce.JceStruct response,boolean cache){originals++;}
}
''',
    "com/duowan/kiwi/base/login/api/ILoginModule.java": '''package com.duowan.kiwi.base.login.api;
public interface ILoginModule {boolean isLogin();long getUid();}
''',
    "com/duowan/kiwi/base/login/api/ILoginComponent.java": '''package com.duowan.kiwi.base.login.api;
public interface ILoginComponent {ILoginModule getLoginModule();}
''',
    "ryxq/xxe.java": '''package ryxq;
import com.duowan.kiwi.base.login.api.*;
public class xxe {
 public static long uid=111;
 public static Object i(Class<?> type){
  return (ILoginComponent)()->new ILoginModule(){
   public boolean isLogin(){return uid>0;}public long getUid(){return uid;}
  };
 }
}
''',
    "com/duowan/HUYA/UserId.java": '''package com.duowan.HUYA;public class UserId {}
''',
    "com/duowan/biz/wup/WupHelper.java": '''package com.duowan.biz.wup;
public class WupHelper {public static com.duowan.HUYA.UserId getUserId(){return new com.duowan.HUYA.UserId();}}
''',
    "com/duowan/HUYA/BadgeInfoListReq.java": '''package com.duowan.HUYA;
public class BadgeInfoListReq extends com.duowan.taf.jce.JceStruct {public long lToUid;}
''',
    "com/duowan/HUYA/BadgeInfoListRsp.java": '''package com.duowan.HUYA;
import java.util.*;
public class BadgeInfoListRsp extends com.duowan.taf.jce.JceStruct {
 public long lUid;public List<Badge> vBadgeInfo=new ArrayList<>();
 public static class Channel {public long lUid;public Channel(long uid){lUid=uid;}}
 public static class Badge {public long lUid;public Channel tChannelInfo;
  public Badge(long uid){lUid=ryxq.xxe.uid;tChannelInfo=new Channel(uid);}}
}
''',
    "com/duowan/HUYA/FansSignReq.java": '''package com.duowan.HUYA;
public class FansSignReq extends com.duowan.taf.jce.JceStruct {public UserId tId;public long lPid;}
''',
    "com/duowan/HUYA/FansSignRsp.java": '''package com.duowan.HUYA;
public class FansSignRsp extends com.duowan.taf.jce.JceStruct {public int iCode;public String sMsg="test";}
''',
    "com/duowan/HUYA/GetFansSignReq.java": '''package com.duowan.HUYA;
public class GetFansSignReq extends FansSignReq {}
''',
    "com/duowan/kiwi/badge/wupfunction/BadgeWupFunction.java": '''package com.duowan.kiwi.badge.wupfunction;
import com.duowan.HUYA.*;import ryxq.*;
public class BadgeWupFunction {
 public static class Status extends FansSignRsp {
  public Sign tSign=new Sign();
  public static class Sign {public long lSignInFlag;public int iPos=1;}
 }
 public static class GetFansSign extends jd8 {
  final GetFansSignReq req;public GetFansSign(GetFansSignReq req){this.req=req;}
  public void execute(){
   Status response=new Status();
   if(TestServer.signed.contains(xxe.uid+"/"+req.lPid))response.tSign.lSignInFlag=1;
   TestServer.reply(this,response);
  }
 }
}
''',
    "ryxq/TestServer.java": '''package ryxq;
import com.duowan.HUYA.*;import io.github.libxposed.api.XposedModule;
public class TestServer {
 public static int lists,signs;public static boolean drop,malformedBadge,staleSignStatus;
 public static int grainClaims;
 public static boolean grainAvailable,dropGrainReceipt,wrongGrainOwner;
 public static boolean rejectSign,dropSignReceipt,malformedSignReceipt;
 public static final java.util.Set<String> signed=new java.util.HashSet<>();
 public static void reply(jd8 request,com.duowan.taf.jce.JceStruct response){
  if(drop)return;
  try{XposedModule.call(request,"onResponse",new Class<?>[]{com.duowan.taf.jce.JceStruct.class,boolean.class},response,false);}
  catch(Throwable failure){throw new AssertionError(failure);}
 }
}
''',
    "com/duowan/biz/wup/gamelive/GameLiveWupFunction.java": '''package com.duowan.biz.wup.gamelive;
import com.duowan.HUYA.*;import ryxq.*;
public class GameLiveWupFunction {
 public static class j0 extends jd8 {
  final BadgeInfoListReq req;public j0(BadgeInfoListReq req){this.req=req;}
  public void execute(){
   TestServer.lists++;BadgeInfoListRsp rsp=new BadgeInfoListRsp();rsp.lUid=req.lToUid;
   if(TestServer.malformedBadge)rsp.vBadgeInfo.add(null);
   rsp.vBadgeInfo.add(new BadgeInfoListRsp.Badge(11));
   rsp.vBadgeInfo.add(new BadgeInfoListRsp.Badge(11));
   rsp.vBadgeInfo.add(new BadgeInfoListRsp.Badge(22));TestServer.reply(this,rsp);
  }
 }
}
''',
    "com/duowan/kiwi/inputbar/impl/wup/InputBarWupFunction.java": '''package com.duowan.kiwi.inputbar.impl.wup;
import com.duowan.HUYA.*;import ryxq.*;
public class InputBarWupFunction {
 public static class SetFansSign extends jd8 {
  final FansSignReq req;public SetFansSign(FansSignReq req){this.req=req;}
  public void execute(){TestServer.signs++;FansSignRsp rsp=new FansSignRsp();
   rsp.iCode=TestServer.rejectSign&&req.lPid==22?7:0;
   if(TestServer.malformedSignReceipt&&req.lPid==11){rsp.iCode=7;rsp.sMsg=null;}
   if(rsp.iCode==0&&(!TestServer.staleSignStatus||req.lPid!=11))TestServer.signed.add(xxe.uid+"/"+req.lPid);
   if(!TestServer.dropSignReceipt||req.lPid!=11)TestServer.reply(this,rsp);}
 }
}
''',
    "io/github/saycm/huyaplus/HuyaTaskClient.java": '''package io.github.saycm.huyaplus;
import ryxq.TestServer;
final class HuyaTaskClient {
 HuyaTaskClient(ClassLoader loader){}
 long loggedInUid() throws ReflectiveOperationException{return ryxq.xxe.uid;}
 boolean notificationEnabled(Object context)throws ReflectiveOperationException{return false;}
 void claimDiceVideo(long account,String action,java.util.function.BooleanSupplier enabled,
    NativeTaskRunner.ActionReply reply,long interval,java.util.function.Consumer<Runnable> afterReply){
  throw new AssertionError("unexpected ad");
 }
 void send(long account,String servant,String function,TaskWire.Struct body,NativeTaskRunner.Reply reply){
  if(!"queryFansGroupTaskInfo".equals(function)&&!"operateFansBox".equals(function)){
   reply.complete(new TaskWire.Struct(),-1);
   return;
  }
  long presenter=body.number(1);
  if(!"wupui".equals(servant)||body.number(2)!=3||account!=ryxq.xxe.uid)
   throw new AssertionError("wrong fans request");
  if("queryFansGroupTaskInfo".equals(function)){
   int state=TestServer.grainAvailable&&presenter==11?3:4;
   reply.complete(new TaskWire.Struct().field(0,0).field(1,TestServer.wrongGrainOwner?account+1:account)
    .field(2,presenter).field(7,new TaskWire.Struct().field(0,state)),0);
  }else if("operateFansBox".equals(function)){
   if(!TestServer.grainAvailable||presenter!=11)throw new AssertionError("unavailable reward claimed");
   TestServer.grainClaims++;TestServer.grainAvailable=false;
   if(!TestServer.dropGrainReceipt)reply.complete(new TaskWire.Struct().field(0,0).field(1,presenter)
    .field(3,4).field(5,10),0);
  }
 }
}
''',
    "io/github/saycm/huyaplus/DailyEngineTest.java": '''package io.github.saycm.huyaplus;
import android.content.*;import android.os.*;import java.lang.reflect.*;
import io.github.libxposed.api.XposedModule;import ryxq.*;
public class DailyEngineTest {
 static boolean has(String state){return LocalTaskStore.localEvents.stream().anyMatch(x->state.equals(x.getString("state","")));}
 static void awaitProvider(String state)throws Exception{
  long end=System.currentTimeMillis()+3000;
  while(System.currentTimeMillis()<end){
   if(ContentResolver.events.stream().anyMatch(x->state.equals(x.getString("state",""))))return;
   Thread.sleep(10);
  }
  throw new AssertionError("Provider never received state: "+state);
 }
 public static void main(String[] args) throws Throwable {
  boolean enabled=!"disabled".equals(args[0])&&!"sync-storm".equals(args[0])
    &&!"auto-sync".equals(args[0])&&!"sync-during".equals(args[0])
    &&!args[0].startsWith("sync-")&&!args[0].startsWith("dice-");
  final boolean[] signOn={enabled};
  if("sync-storm".equals(args[0])||"sync-during".equals(args[0]))ContentResolver.delaySync=true;
  if("module-stopped".equals(args[0])||"sync-resume".equals(args[0]))ContentResolver.blocked=true;
  if("sync-null".equals(args[0]))ContentResolver.nullImport=true;
  if("logout".equals(args[0]))xxe.uid=0;
  if("timeout".equals(args[0]))TestServer.drop=true;
  if("malformed-badge".equals(args[0]))TestServer.malformedBadge=true;
  if("stale-sign-status".equals(args[0])){
   TestServer.dropSignReceipt=true;
   TestServer.staleSignStatus=true;
  }
  if("malformed-sign-receipt".equals(args[0]))TestServer.malformedSignReceipt=true;
  if("reward".equals(args[0])||"reward-timeout".equals(args[0])||"reward-wrong-account".equals(args[0]))
   TestServer.grainAvailable=true;
  if("reward-timeout".equals(args[0]))TestServer.dropGrainReceipt=true;
  if("reward-wrong-account".equals(args[0]))TestServer.wrongGrainOwner=true;
  if("sign-timeout".equals(args[0]))TestServer.dropSignReceipt=true;
  if("sign-rejected".equals(args[0]))TestServer.rejectSign=true;
  if("legacy-claim".equals(args[0])){
   java.text.SimpleDateFormat date=new java.text.SimpleDateFormat("yyyy-MM-dd",java.util.Locale.ROOT);
   date.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Shanghai"));
   ContentResolver.claims.add("sign/"+xxe.uid+"/"+date.format(new java.util.Date()));
  }
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(DailyEngineTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},(proxy,method,values)->{
    if("native-failure".equals(args[0])&&"getBoolean".equals(method.getName())
      &&GlassSettings.KEY_NATIVE_TASKS.equals(values[0]))throw new IllegalStateException("task center preferences unavailable");
    if("getBoolean".equals(method.getName()))return signOn[0]&&GlassSettings.KEY_AUTO_SIGN.equals(values[0]);
    if("getString".equals(method.getName()))return GlassSettings.KEY_TASK_INTERVAL.equals(values[0])?"5":"";
    throw new AssertionError("Unexpected preference access");
   });
  Context context=new Context();XposedModule module=new XposedModule(){};
  ClassLoader loader=DailyEngineTest.class.getClassLoader();
  if("current-version".equals(args[0])){
   loader=new ClassLoader(loader){
    @Override public Class<?> loadClass(String name)throws ClassNotFoundException{
     switch(name){
      case "ryxq.xxe": case "ryxq.jd8": case "ryxq.oe6": return Object.class;
      case "ryxq.fwa": return xxe.class;
      case "ryxq.yy5": return jd8.class;
      case "ryxq.xp4": return oe6.class;
      default: return super.loadClass(name);
     }
    }
   };
  }
  DailyAutomation engine=new DailyAutomation(module,prefs,loader);
  if("sync-batch-failure".equals(args[0])){
   LocalTaskStore journal=new LocalTaskStore(context);
   for(int i=0;i<120;i++)journal.append("bulk",String.valueOf(i),"成功","");
   for(String name:new String[]{"context","store"}){
    Field field=DailyAutomation.class.getDeclaredField(name);field.setAccessible(true);
    field.set(engine,name.equals("context")?context:journal);
   }
   Field dirty=DailyAutomation.class.getDeclaredField("logsDirty");dirty.setAccessible(true);
   Method sync=DailyAutomation.class.getDeclaredMethod("syncLogs");sync.setAccessible(true);
   ContentResolver.failImportAt=2;
   ((java.util.concurrent.atomic.AtomicBoolean)dirty.get(engine)).set(true);sync.invoke(engine);
   if(LocalTaskStore.acknowledged!=50||ContentResolver.completed!=0)
    throw new AssertionError("a failed batch advanced the cursor past confirmed events");
   ContentResolver.failImportAt=0;
   ((java.util.concurrent.atomic.AtomicBoolean)dirty.get(engine)).set(true);sync.invoke(engine);
   java.util.Set<Long> ids=new java.util.HashSet<>();
   for(Bundle row:ContentResolver.events)ids.add(row.getLong("id"));
   if(ContentResolver.events.size()!=121||ids.size()!=121||ContentResolver.completed!=1)
    throw new AssertionError("batch retry lost events or retransmitted confirmed batches");
   return;
  }
  engine.onOpen(context);
  if("disable-running".equals(args[0])){
   signOn[0]=false;
   Handler.advance(40000);
   if(TestServer.signs!=0)throw new AssertionError("disabled queue sent sign requests");
   return;
  }
  Handler.advance(90000);
  int lists=TestServer.lists,signs=TestServer.signs;
  if("sync-incremental".equals(args[0])||"sync-null".equals(args[0])){
   for(Thread thread:Thread.getAllStackTraces().keySet())
    if("FuckAD-log-sync".equals(thread.getName()))thread.join(3000);
   if("sync-null".equals(args[0])){
    if(ContentResolver.completed!=0||LocalTaskStore.acknowledged!=0)
     throw new AssertionError("null provider response was acknowledged as success");
    ContentResolver.nullImport=false;
   }
   int baseline=ContentResolver.completed;
   int imports=ContentResolver.imports;
   Context.receiver.onReceive(context,new Intent(DailyAutomation.SYNC_LOGS));
   long end=System.currentTimeMillis()+3000;
   while(ContentResolver.completed==baseline&&System.currentTimeMillis()<end)Thread.sleep(10);
   if(ContentResolver.completed==baseline)throw new AssertionError("sync did not complete");
   if("sync-incremental".equals(args[0])&&ContentResolver.imports!=imports)
    throw new AssertionError("unchanged history was retransmitted");
   if("sync-null".equals(args[0])&&ContentResolver.events.isEmpty())
    throw new AssertionError("unacknowledged logs were lost");
   return;
  }
  if("malformed-badge".equals(args[0])){
   if(signs!=2||!engine.isIdle())throw new AssertionError("a malformed badge blocked valid badges or left the queue busy");
   return;
  }
  if("stale-sign-status".equals(args[0])||"malformed-sign-receipt".equals(args[0])){
   if(signs!=2)throw new AssertionError("first badge run incomplete");
   engine.onOpen(context);
   Handler.advance(90000);
   if(TestServer.lists!=2||TestServer.signs!=2)throw new AssertionError("an uncertain sign was sent again");
   return;
  }
  if("sync-resume".equals(args[0])){
   for(Thread thread:Thread.getAllStackTraces().keySet()){
    if("FuckAD-log-sync".equals(thread.getName()))thread.join(3000);
   }
   if(ContentResolver.completed!=0)throw new AssertionError("blocked sync was marked complete");
   ContentResolver.blocked=false;
   engine.onOpen(context);
   awaitProvider("跳过");
   return;
  }
  if("sync-empty".equals(args[0])){
   awaitProvider("跳过");
   long end=System.currentTimeMillis()+3000;
   while(ContentResolver.completed==0&&System.currentTimeMillis()<end)Thread.sleep(10);
   if(ContentResolver.completed==0)throw new AssertionError("no completed batch marker");
   LocalTaskStore.localEvents.clear();
   int baseline=ContentResolver.completed;
   Context.receiver.onReceive(context,new Intent(DailyAutomation.SYNC_LOGS));
   end=System.currentTimeMillis()+3000;
   while(ContentResolver.completed==baseline&&System.currentTimeMillis()<end)Thread.sleep(10);
   if(ContentResolver.completed==baseline)throw new AssertionError("empty sync never completed");
   return;
  }
  if(args[0].startsWith("dice-")){
   if(args[0].equals("dice-busy")){
    Field busy=DailyAutomation.class.getDeclaredField("giftActive");busy.setAccessible(true);busy.setBoolean(engine,true);
   }
   int[] calls={0};boolean[] accepted={false};
   engine.sendDiceGrain(xxe.uid,"2099-01-01",new AutomationRules.GrainPart(55,1,1,1),
    ()->!args[0].equals("dice-off"),(ok,detail)->{calls[0]++;accepted[0]=ok;});
   Handler.advance(100000);
   if(calls[0]!=1||accepted[0])throw new AssertionError("disabled/busy/unavailable gift incorrectly completed");
   if(TestServer.lists!=0||TestServer.signs!=0)throw new AssertionError("dice gift ran other daily tasks");
   return;
  }
  if("auto-sync".equals(args[0])){
   awaitProvider("跳过");
   return;
  }
  if("sync-during".equals(args[0])){
   if(!ContentResolver.entered.await(2,java.util.concurrent.TimeUnit.SECONDS))
    throw new AssertionError("automatic sync never started");
   Method write=DailyAutomation.class.getDeclaredMethod("log",String.class,String.class,String.class,String.class);
   write.setAccessible(true);
   write.invoke(engine,"同步测试","","同步后新增","同步进行中追加");
   ContentResolver.release.countDown();
   awaitProvider("同步后新增");
   return;
  }
  if("sync-storm".equals(args[0])){
   Intent sync=new Intent(DailyAutomation.SYNC_LOGS);
   Context.receiver.onReceive(context,sync);
   try{
    if(!ContentResolver.entered.await(2,java.util.concurrent.TimeUnit.SECONDS))throw new AssertionError("sync never started");
    for(int i=0;i<25;i++)Context.receiver.onReceive(context,sync);
    long threads=Thread.getAllStackTraces().keySet().stream()
      .filter(t->"FuckAD-log-sync".equals(t.getName())).count();
    if(threads!=1)throw new AssertionError("Parallel sync threads: "+threads);
    if(lists!=0||signs!=0)throw new AssertionError("sync ran automatic tasks");
   }finally{ContentResolver.release.countDown();}
   return;
  }
  if("current-version".equals(args[0])){
   if(lists!=1||signs!=2||!has("成功"))throw new AssertionError("new WUP callbacks");
   return;
  }
  if("legacy-claim".equals(args[0])){
   if(lists!=1||signs!=2)throw new AssertionError("old daily claim blocked unfinished badges");
   return;
  }
  if("reward".equals(args[0])||"reward-timeout".equals(args[0])||"reward-wrong-account".equals(args[0])
     ||"sign-timeout".equals(args[0])||"sign-rejected".equals(args[0])){
   boolean rewardSucceeded=LocalTaskStore.localEvents.stream().anyMatch(x->
      "粉丝团每日虎粮".equals(x.getString("task",""))&&"成功".equals(x.getString("state","")));
   int claims=args[0].equals("reward")||args[0].equals("reward-timeout")?1:0;
   if(TestServer.grainClaims!=claims||rewardSucceeded!=args[0].equals("reward")||signs!=2)
    throw new AssertionError("incorrect reward or sign outcome");
   if("sign-rejected".equals(args[0])&&!has("未完成"))throw new AssertionError("rejected sign marked successful");
   TestServer.rejectSign=false;
   engine.onOpen(context);Handler.advance(90000);
   if(TestServer.grainClaims!=claims||TestServer.signs!=(args[0].equals("sign-rejected")?3:2))
    throw new AssertionError("recovery repeated a confirmed reward or sign");
   if(args[0].endsWith("timeout")&&TestServer.lists!=2)
    throw new AssertionError("ambiguous receipt did not trigger read-back");
   return;
  }
  if("success".equals(args[0])||"module-stopped".equals(args[0])||"native-failure".equals(args[0])){
   if(lists!=1||signs!=2||!has("成功"))throw new AssertionError("sign results");
   long confirmed=LocalTaskStore.localEvents.stream().filter(x->"粉丝牌打卡".equals(x.getString("task",""))
     &&"成功".equals(x.getString("state",""))).count();
   if(confirmed!=2)throw new AssertionError("missing successful sign results");
   engine.onOpen(context);Handler.advance(40000);
   new DailyAutomation(module,prefs,DailyEngineTest.class.getClassLoader()).onOpen(context);
   Handler.advance(40000);
   if(TestServer.lists!=lists||TestServer.signs!=signs)throw new AssertionError("duplicate daily run");
   XposedModule.call(new jd8(),"onResponse",new Class<?>[]{com.duowan.taf.jce.JceStruct.class,boolean.class},
     new com.duowan.HUYA.FansSignRsp(),false);
   if(oe6.originals!=1)throw new AssertionError("unrelated callback changed");
   xxe.uid=222;engine.onOpen(context);Handler.advance(90000);
   if(TestServer.lists!=2||TestServer.signs!=4)throw new AssertionError("account not isolated");
  }else if("timeout".equals(args[0])){
   if(lists!=1||signs!=0||!has("结果未确认"))throw new AssertionError("timeout marked complete");
   TestServer.drop=false;
   new DailyAutomation(module,prefs,DailyEngineTest.class.getClassLoader()).onOpen(context);
   Handler.advance(90000);
   if(TestServer.lists!=2||TestServer.signs!=2)throw new AssertionError("badge list timeout blocked recovery");
  }else if(lists!=0||signs!=0||!has("跳过"))throw new AssertionError("disabled or logged out ran tasks");
 }
}
''',
})


class DailyAutomationTest(unittest.TestCase):
    def test_daily_claims_callbacks_timeouts_and_account_isolation(self):
        with tempfile.TemporaryDirectory(prefix="daily-engine-") as folder:
            root = Path(folder)
            sources = []
            for name, content in DAILY_SOURCES.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                sources.append(str(path))
            for name in ("HuyaCompatEntry", "GlassSettings"):
                sources.append(str(ROOT / f"tools/huya-compat-src/io/github/saycm/huyaplus/{name}.java"))
            android = SDK / "platforms/android-36/android.jar"
            result = subprocess.run(
                [str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8", "-cp", str(android),
                 "-d", str(root / "classes"), *sources],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ("legacy-claim", "timeout", "success", "current-version", "disabled", "logout", "module-stopped", "auto-sync",
                         "malformed-badge", "stale-sign-status", "malformed-sign-receipt",
                         "reward", "reward-timeout", "reward-wrong-account", "sign-timeout", "sign-rejected",
                         "sync-during", "sync-storm", "sync-resume", "native-failure",
                         "dice-off", "dice-busy", "dice-unavailable", "sync-empty", "disable-running",
                         "sync-incremental", "sync-null", "sync-batch-failure"):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-cp",
                         os.pathsep.join((str(root / "classes"), str(android))),
                         "io.github.saycm.huyaplus.DailyEngineTest", case],
                        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
