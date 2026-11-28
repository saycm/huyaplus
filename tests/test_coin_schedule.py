"""Exercise hourly coin rechecks against official task and meal snapshots."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_daily_automation import DAILY_SOURCES
from test_huya_loader_lifecycle import ROOT, JDK, EXE


HARNESS = r'''
package io.github.saycm.huyaplus;
import android.content.SharedPreferences;
import android.os.*;
import java.util.*;
public class CoinScheduleTest {
 static final long HOUR=3600000L;
 static long base=java.time.Instant.parse("2030-01-01T00:10:00Z").toEpochMilli();
 static long now(){return base+Handler.now;}
 static long hour(){return now()/HOUR;}
 static long nextHour(){return HOUR-Math.floorMod(now(),HOUR);}
 static void check(boolean value,String detail){if(!value)throw new AssertionError(detail);}
 static SharedPreferences prefs=new SharedPreferences(){
  public String getString(String key,String fallback){return key.equals(GlassSettings.KEY_TASK_INTERVAL)?"5":fallback;}
  public boolean getBoolean(String key,boolean fallback){
   if(key.equals(GlassSettings.KEY_NATIVE_TASKS))return enabled;
   if(key.startsWith(GlassSettings.KEY_TASK_ENABLED_PREFIX))return taskEnabled;
   return false;
  }
 };
 static boolean enabled=true,taskEnabled=true;
 static NativeTaskAutomation engine(LocalTaskStore store,DailyAutomation gifts)throws Exception{
  return new NativeTaskAutomation(new io.github.libxposed.api.XposedModule(),prefs,
   CoinScheduleTest.class.getClassLoader(),store,gifts,CoinScheduleTest::now);
 }
 static class Host implements NativeTaskRunner.Host {
  final LocalTaskStore store=new LocalTaskStore();
  public boolean enabled(){return CoinScheduleTest.enabled;}
  public long uid(){return HuyaTaskClient.uid;}
  public long now(){return CoinScheduleTest.now();}
  public boolean claim(String key){return store.claim(key);}
  public boolean taskEnabled(NativeTaskCatalog.Task task){return CoinScheduleTest.taskEnabled;}
  public void publish(List<NativeTaskCatalog.Task> tasks){}
  public void log(String title,String state,String detail){}
  public void later(long millis,Runnable run){new Handler(Looper.getMainLooper()).postDelayed(run,millis);}
  public void perform(NativeTaskCatalog.Task task,NativeTaskRunner.ActionReply reply){throw new AssertionError("unexpected action");}
  public void send(String servant,String function,TaskWire.Struct request,NativeTaskRunner.Reply reply){
   new HuyaTaskClient(null).send(uid(),servant,function,request,reply);
  }
  void start(){new NativeTaskRunner(this,5000).start(uid(),"2030-01-01");}
 }
 public static void main(String[] args)throws Exception{
  String test=args[0];
  if(test.equals("hourly-reward-slots")||test.equals("ambiguous-hourly-slots")){
   HuyaTaskClient.meal=false;HuyaTaskClient.dropReward=test.startsWith("ambiguous");
   Host host=new Host();host.start();Handler.advance(30000);
   host.start();Handler.advance(30000);
   check(HuyaTaskClient.rewards==1,"same-hour reopening submitted a duplicate reward");
   Handler.advance(nextHour());host.start();Handler.advance(30000);
   check(HuyaTaskClient.rewards==2,"a daily claim key blocked the next official hourly reward");
   return;
  }
  if(test.equals("stale-hourly-snapshot")){
   HuyaTaskClient.meal=false;base=java.time.Instant.parse("2030-01-01T00:59:58Z").toEpochMilli();
   new Host().start();Handler.advance(10000);
   check(HuyaTaskClient.rewards==0,"an old-hour task snapshot triggered a new-hour reward");
   return;
  }
  if(test.equals("meal-slots")){
   HuyaTaskClient.hourly=false;HuyaTaskClient.mealReady=true;
   Host host=new Host();host.start();Handler.advance(60000);
   host.start();Handler.advance(60000);
   check(HuyaTaskClient.mealClaims==1,"same meal was submitted twice");
   HuyaTaskClient.mealId=1239247;host.start();Handler.advance(60000);
   check(HuyaTaskClient.mealClaims==2,"a later official meal slot was blocked");
   return;
  }
  if(test.equals("initial-hour-boundary")){
   base=java.time.Instant.parse("2030-01-01T00:59:52Z").toEpochMilli();
   engine(new LocalTaskStore(),new DailyAutomation()).onReady(HuyaTaskClient.uid);
   Handler.advance(60000);
   check(HuyaTaskClient.reads==2&&HuyaTaskClient.rewards==1,
    "initial queue crossing an hour missed the current-hour refresh");
   return;
  }
  if(test.equals("failed-query")){
   HuyaTaskClient.offline=true;
   engine(new LocalTaskStore(),new DailyAutomation()).onReady(HuyaTaskClient.uid);
   Handler.advance(600000);
   check(HuyaTaskClient.reads==1,"failed query caused repeated short-interval polling");
   HuyaTaskClient.offline=false;Handler.advance(nextHour()+60000);
   check(HuyaTaskClient.reads==2&&HuyaTaskClient.rewards==1,"next hour did not recover a failed list query");
   return;
  }
  if(test.equals("cross-day"))base=java.time.Instant.parse("2030-01-01T15:10:00Z").toEpochMilli();
  if(test.equals("refresh-after-unready")){
   HuyaTaskClient.readyAt=(hour()+1)*HOUR;HuyaTaskClient.mealReady=false;
  }
  DailyAutomation gifts=new DailyAutomation();
  NativeTaskAutomation automation=engine(new LocalTaskStore(),gifts);
  automation.onReady(HuyaTaskClient.uid);Handler.advance(60000);
  check(HuyaTaskClient.reads==1,"initial coin list was not queried once");
  if(test.equals("refresh-after-unready"))check(HuyaTaskClient.rewards==0&&HuyaTaskClient.mealClaims==0,
   "a reward was claimed before official readiness");
  automation.onReady(HuyaTaskClient.uid);Handler.advance(60000);
  check(HuyaTaskClient.reads==1,"same-hour reopen polled the coin list");
  long boundary=nextHour();Handler.advance(boundary-1);
  check(HuyaTaskClient.reads==1,"coin list was polled before the next hour");
  if(test.equals("account-stop"))HuyaTaskClient.uid=13;
  if(test.equals("switch-stop"))enabled=false;
  if(test.equals("task-switch-stop"))taskEnabled=false;
  if(test.equals("busy-recheck"))gifts.idle=false;
  if(test.equals("refresh-after-unready"))HuyaTaskClient.mealReady=true;
  Handler.advance(60001);
  if(test.endsWith("-stop")||test.equals("cross-day")){
   check(HuyaTaskClient.reads==1,"inactive account, date or task switch kept polling");
   Handler.advance(2*HOUR);
   check(HuyaTaskClient.reads==1,"stopped coin timer restarted itself");
   if(test.equals("switch-stop")||test.equals("task-switch-stop")){
    enabled=true;taskEnabled=true;automation.onReady(HuyaTaskClient.uid);Handler.advance(60000);
    check(HuyaTaskClient.reads==2,"reenabling the same-day coin switch did not resume queries");
   }
   return;
  }
  if(test.equals("busy-recheck")){
   check(HuyaTaskClient.reads==1,"coin timer overlapped an active gift queue");
   gifts.idle=true;Handler.advance(120000);
  }
  check(HuyaTaskClient.reads==2,"the daily list cache blocked the next-hour official query");
  if(test.equals("refresh-after-unready"))check(HuyaTaskClient.rewards==1&&HuyaTaskClient.mealClaims==1,
   "newly ready official hourly or meal reward was not claimed");
  Handler.advance(nextHour()+60000);
  check(HuyaTaskClient.reads==3,"coin monitor did not schedule the following hour");
  check(HuyaTaskClient.mealClaims<=1,"hourly rechecks repeated the same meal reward");
 }
}
'''


CLIENT = r'''
package io.github.saycm.huyaplus;
import java.util.*;
final class HuyaTaskClient {
 static long uid=12,readyAt;
 static int reads,rewards,mealReads,mealClaims,mealId=1239241;
 static boolean hourly=true,meal=true,mealReady=true,dropReward,offline;
 static final Set<String> rewarded=new HashSet<>();
 static final Set<Integer> mealRewarded=new HashSet<>();
 HuyaTaskClient(ClassLoader loader){}
 long loggedInUid()throws ReflectiveOperationException{return uid;}
 boolean notificationEnabled(Object context)throws ReflectiveOperationException{return false;}
 void claimDiceVideo(long account,String action,java.util.function.BooleanSupplier allowed,
   NativeTaskRunner.ActionReply reply,long interval,java.util.function.Consumer<Runnable> later){
  throw new AssertionError("unexpected dice video");
 }
 void send(long account,String servant,String function,TaskWire.Struct request,NativeTaskRunner.Reply reply){
  CoinScheduleTest.check(account==uid,"request used an old account");
  TaskWire.Struct response=new TaskWire.Struct();
  if(function.equals("getJumpGameTaskList")){reply.complete(response.field(0,List.of()),0);return;}
  if(function.equals("getLiveBoxUserGrowthPage")){
   reads++;List<TaskWire.Struct> tasks=new ArrayList<>();
   if(offline){reply.complete(response,-1);return;}
   if(hourly)tasks.add(new TaskWire.Struct().field(0,1L).field(1,1)
    .field(2,CoinScheduleTest.now()>=readyAt?1:0).field(3,0).field(4,2).field(5,"整点领金币").field(28,1));
   if(meal)tasks.add(new TaskWire.Struct().field(0,2L).field(1,1).field(2,0).field(3,0)
    .field(4,2).field(5,"饭点领金币补贴").field(28,34)
    .field(14,"https://zt.huya.com/b3f393e7/mobile/index.html"));
   byte[] data=TaskWire.encode(new TaskWire.Struct().field(0,List.of(
    new TaskWire.Struct().field(0,"每日赚金币").field(1,tasks).field(2,1))));
   reply.complete(response.field(1,List.of(new TaskWire.Struct().field(0,14).field(1,data))),0);return;
  }
  if(function.equals("receiveUserLevelTaskPrize")){
   CoinScheduleTest.check(servant.equals("commui")&&request.number(1)==1,"wrong hourly endpoint or payload");
   CoinScheduleTest.check(rewarded.add(account+"/"+CoinScheduleTest.hour()),"duplicate hourly reward request");
   rewards++;if(!dropReward)reply.complete(response.field(0,1),0);return;
  }
  if(function.equals("getUserTaskDetailByTaskId")){
   CoinScheduleTest.check(servant.equals("webActUI")&&request.number(1)==24675,"wrong meal endpoint or payload");
   int id=(int)request.number(2);mealReads++;
   boolean ready=mealReady&&id==mealId;
   reply.complete(response.field(0,200).field(2,new TaskWire.Struct().field(0,24675).field(1,id)
    .field(12,ready?1:0).field(13,mealRewarded.contains(id)?1:0)
    .field(25,List.of(new TaskWire.Struct().field(4,9).field(12,ready?1:0)))),0);return;
  }
  if(function.equals("receivePrize")){
   int id=(int)request.number(2);
   CoinScheduleTest.check(mealReady&&id==mealId&&mealRewarded.add(id),"unearned or duplicate meal reward");
   mealClaims++;reply.complete(response.field(0,200),0);return;
  }
  throw new AssertionError("unexpected request: "+function);
 }
}
'''


class CoinScheduleTests(unittest.TestCase):
    def test_official_hour_and_meal_slots_recheck_without_duplicate_claims(self):
        package = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'
        sources = {
            'android/content/SharedPreferences.java': '''package android.content;
public interface SharedPreferences {String getString(String key,String fallback);boolean getBoolean(String key,boolean fallback);}''',
            'android/os/Handler.java': DAILY_SOURCES['android/os/Handler.java'].replace(
                'static long now;', 'public static long now;'),
            'android/os/Looper.java': DAILY_SOURCES['android/os/Looper.java'],
            'android/util/Log.java': 'package android.util;public class Log {public static final int WARN=5;}',
            'io/github/libxposed/api/XposedModule.java': '''package io.github.libxposed.api;
public class XposedModule {public void log(int level,String tag,String detail){}}''',
            'io/github/saycm/huyaplus/HuyaTaskClient.java': CLIENT,
            'io/github/saycm/huyaplus/DailyAutomation.java': '''package io.github.saycm.huyaplus;
final class DailyAutomation {
 boolean idle=true;
 boolean isIdle(){return idle;}
 void resumePendingLogin(){}
 void sendDiceGrain(long account,String day,AutomationRules.GrainPart part,
   java.util.function.BooleanSupplier allowed,NativeTaskRunner.ActionReply reply){throw new AssertionError("unexpected gift");}
}''',
            'io/github/saycm/huyaplus/LocalTaskStore.java': '''package io.github.saycm.huyaplus;
import java.util.*;
final class LocalTaskStore {
 final Set<String> claims=new HashSet<>();
 boolean claim(String key){return claims.add(key);}
 boolean hasClaim(String key){return claims.contains(key);}
 void append(String type,String title,String state,String detail){}
 void replaceTasks(String day,List<NativeTaskCatalog.Task> tasks){}
 void replaceDiceTasks(String day,List<DiceTaskCatalog.Task> tasks){}
 List<AutomationRules.GrainPart> diceGrainPlan(String day){return null;}
 List<AutomationRules.GrainPart> saveDiceGrainPlan(String day,List<AutomationRules.GrainPart> plan){return plan;}
}''',
            'io/github/saycm/huyaplus/CoinScheduleTest.java': HARNESS,
        }
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/test-tmp') as directory:
            folder = Path(directory)
            files = []
            for name, content in sources.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
                files.append(str(path))
            files += [str(package / (name + '.java')) for name in (
                'TaskWire', 'GlassSettings', 'AutomationRules', 'NativeTaskCatalog',
                'NativeTaskRunner', 'NativeTaskAutomation', 'DiceTaskRunner',
                'DiceTaskCatalog', 'DiceMissionRunner', 'WelfareSignRunner')]
            result = subprocess.run(
                [str(JDK / 'bin' / ('javac' + EXE)), '-encoding', 'UTF-8', '-d', str(folder), *files],
                capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ('refresh-after-unready', 'hourly-reward-slots', 'ambiguous-hourly-slots',
                         'stale-hourly-snapshot', 'meal-slots', 'account-stop', 'cross-day',
                         'switch-stop', 'task-switch-stop', 'busy-recheck',
                         'initial-hour-boundary', 'failed-query'):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(JDK / 'bin' / ('java' + EXE)), '-Dfile.encoding=UTF-8', '-cp', str(folder),
                         'io.github.saycm.huyaplus.CoinScheduleTest', case],
                        capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
