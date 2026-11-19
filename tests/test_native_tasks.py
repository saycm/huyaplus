"""Exercise the real task parser and runner without a device or user data."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, JDK, EXE


HARNESS = r'''
package io.github.saycm.huyaplus;
import java.util.*;
public class NativeTasksTest {
 static TaskWire.Struct s(Object... fields){
  TaskWire.Struct out=new TaskWire.Struct();
  for(int i=0;i<fields.length;i+=2)out.put((Integer)fields[i],fields[i+1]);return out;
 }
 static byte[] bytes(TaskWire.Struct fields){return TaskWire.encode(fields);}
 static String coopAction(String token){
  return "https://m.huya.com?hyaction=launchcooptask&banneraction=https%3A%2F%2Fm.huya.com%2Freturn%3Freport_type%3Dcooptask%26taskid%3D24%26token%3D"+token;
 }
 static TaskWire.Struct old(long id,String title,int progress,int claimed){
  return s(0,id,1,1,2,progress,3,claimed,4,0,5,title,21,"none",32,new LinkedHashMap<>());
 }
 static TaskWire.Struct actionTask(long id,String title,int goldType,String action){
  return actionTask(id,title,goldType,action,1,0);
 }
 static TaskWire.Struct actionTask(long id,String title,int goldType,String action,int target,int progress){
  return s(0,id,1,target,2,progress,3,0,4,0,5,title,13,"0",14,action,21,"none",28,goldType,32,new LinkedHashMap<>());
 }
 static TaskWire.Struct response(TaskWire.Struct... groups){
  return s(1,Arrays.asList(s(0,14,1,bytes(s(0,Arrays.asList(groups))))));
 }
 static TaskWire.Struct group(TaskWire.Struct... tasks){
  return s(0,"日常任务",1,Arrays.asList(tasks),2,1);
 }
 static void require(boolean value,String reason){if(!value)throw new AssertionError(reason);}
 static class Host implements NativeTaskRunner.Host {
  long time,uid=12;boolean enabled=true;int claimsSent,queries;boolean drop,deny,security,duplicate,delayed;
  NativeTaskRunner.Reply pending;
  final Set<String> claims=new HashSet<>();final List<String> states=new ArrayList<>();
  final List<String> actions=new ArrayList<>();boolean actionAccepted=true,actionCompletes;
  boolean meal,mealReady,mealClaimed;
  int mealReadCount,mealClaims;
  final Set<String> disabledTasks=new HashSet<>();
  final List<List<NativeTaskCatalog.Task>> published=new ArrayList<>();
  final List<Long> claimedIds=new ArrayList<>();
  final List<Long> sentAt=new ArrayList<>();
  final PriorityQueue<Scheduled> timers=new PriorityQueue<>(Comparator.comparingLong(t->t.at));
  TaskWire.Struct page=response(group(old(1,"已完成任务",1,0),old(2,"另一个已完成任务",1,0),
    old(3,"下载安装应用",1,0),old(4,"未完成任务",0,0),old(5,"已领取任务",1,1)));
  static class Scheduled {long at;Runnable run;Scheduled(long a,Runnable r){at=a;run=r;}}
  public boolean enabled(){return enabled;}
  public long uid(){return uid;}
  public boolean claim(String key){return claims.add(key);}
  public void log(String title,String state,String detail){states.add(state+":"+detail);}
  public void later(long ms,Runnable run){timers.add(new Scheduled(time+ms,run));}
  public boolean taskEnabled(NativeTaskCatalog.Task task){return !disabledTasks.contains(task.key());}
  public List<NativeTaskCatalog.Task> readTasks(TaskWire.Struct body){
   return meal?NativeTaskRunner.Host.super.readTasks(body):NativeTaskCatalog.read(body);
  }
  public void publish(List<NativeTaskCatalog.Task> tasks){published.add(new ArrayList<>(tasks));}
  public void perform(NativeTaskCatalog.Task task,NativeTaskRunner.ActionReply reply){
   actions.add(task.automationAction()+":"+task.action);
   reply.complete(actionAccepted,actionAccepted?"原生动作已提交":"系统条件未满足");
  }
  public void send(String servant,String function,TaskWire.Struct request,NativeTaskRunner.Reply reply){
   if(function.equals("getUserTaskDetailByTaskId")){
    require(meal&&servant.equals("webActUI")&&request.number(1)==24675,"wrong meal query");
    long id=request.number(2);
    mealReadCount++;
    reply.complete(s(0,200,2,s(0,24675,1,id,12,mealReady&&id==1239247?1:0,13,mealClaimed?1:0,
     25,Arrays.asList(s(4,9,12,mealReady&&id==1239247?1:0)))),0);
    return;
   }
   if(function.equals("receivePrize")){
    require(meal&&mealReady&&!mealClaimed&&request.number(1)==24675&&request.number(2)==1239247,
     "wrong meal reward request");
    require(time>=90000,"meal detail and claim ignored pacing");
    mealClaims++;
    reply.complete(s(0,200),0);
    return;
   }
   if(function.equals("getLiveBoxUserGrowthPage")){
    queries++;
    if(actions.size()>0&&actionCompletes&&queries>1){
     reply.complete(response(group(old(24,"饭点领金币补贴",1,0))),0);
    }else reply.complete(page,0);
    return;
   }
   require(function.equals("receiveUserLevelTaskPrize"),"unexpected network action "+function);
   require(servant.equals("commui"),"wrong reward servant");
   long claimedId=((Number)request.get(1)).longValue();
   require(claimedId<3||(actions.size()>0&&(claimedId==24||claimedId==25)),"download or ineligible task sent");
   claimsSent++;sentAt.add(time);claimedIds.add(claimedId);
   pending=reply;
   if(!drop){Runnable receipt=()->{reply.complete(s(0,deny?0:1,3,security?923:0),0);
    if(duplicate)reply.complete(s(0,1),0);};if(delayed)later(5000,receipt);else receipt.run();}
  }
  void advance(long until){while(!timers.isEmpty()&&timers.peek().at<=until){
   Scheduled t=timers.poll();time=t.at;t.run.run();}time=until;}
 }
 public static void main(String[] args){
  String test=args[0];
  if(test.equals("removed-gold-tasks")){
   Host host=new Host();host.meal=true;
   host.page=response(group(
     actionTask(27,"手慢无！必领468金币",34,"https://hd.huya.com/h5/welfare_center/free_gift_daily.html").field(4,2),
     actionTask(28,"发送1条弹幕",1,"https://www.huya.com/998?hyaction=live",1,1).field(4,2)),
     s(0,"红包",2,6,4,Arrays.asList(s(0,4,1,bytes(s(0,"看广告开金币红包",1,2,2,6))))));
   new NativeTaskRunner(host,30000).start(12,"2099-01-01");host.advance(90000);
   require(host.queries==1&&host.states.stream().noneMatch(line->line.startsWith("等待:")),
     "removed gold tasks were still scheduled for review");
   require(host.claims.isEmpty()&&host.actions.isEmpty()&&host.claimsSent==0,
     "removed gold tasks triggered an action or claim");
   return;
  }
  if(test.startsWith("meal-")){
   Host host=new Host();
   host.meal=true;
   host.mealReady=!test.equals("meal-incomplete");
   host.mealClaimed=test.equals("meal-already-claimed");
   host.page=response(group(actionTask(26,"饭点领金币补贴",34,
      "https://zt.huya.com/b3f393e7/mobile/index.html?fromid=test",1,
      test.equals("meal-zero-entry-progress")?0:1).field(4,2)));
   new NativeTaskRunner(host,30000).start(12,"2099-01-01");
   host.advance(250000);
   require(host.mealReadCount>=2,"meal status was never queried");
   require(host.mealClaims==(test.equals("meal-success")||test.equals("meal-zero-entry-progress")?1:0),
     "incorrect meal claim count");
   return;
  }
  if(test.equals("coop-callback")){
   String raw="https://m.huya.com?hyaction=launchcooptask&h5link=https%3A%2F%2Fvendor.example%2Ftask%3Fsource%3Dhuya%26token%3Dvendor-token";
   List<NativeTaskCatalog.Task> tasks=NativeTaskCatalog.read(response(group(actionTask(24,"厂商浏览任务",7,raw))));
   require(tasks.isEmpty(),"removed vendor task remained in the task switches");
   Host blockedHost=new Host();blockedHost.page=response(group(actionTask(24,"厂商浏览任务",7,raw)));
   new NativeTaskRunner(blockedHost,30000).start(12,"2099-01-01");blockedHost.advance(300000);
   require(blockedHost.actions.isEmpty()&&blockedHost.claimsSent==0&&blockedHost.claims.isEmpty(),
     "unverified cooperation task caused an action, reward, or daily claim");
   String callback="https%3A%2F%2Fm.huya.com%2Freturn%3Freport_type%3Dcooptask%26taskid%3D24%26token%3Dcallback-token";
   for(String action:Arrays.asList(
     raw+"&banneraction="+callback,
     "https://m.huya.com?hyaction=launchcooptask&h5link=https%3A%2F%2Fvendor.example%2Ftask%3Fcallback%3D"+callback.replace("%","%25"))){
    Host removedHost=new Host();removedHost.page=response(group(actionTask(24,"厂商浏览任务",7,action)));
    new NativeTaskRunner(removedHost,30000).start(12,"2099-01-01");removedHost.advance(300000);
    require(removedHost.published.get(0).isEmpty()&&removedHost.actions.isEmpty()
      &&removedHost.claimsSent==0,"vendor callback bypassed removed category");
   }
   return;
  }
  if(test.equals("wire")){
   byte[] expected=new byte[]{0x0c,0x10,0x7f,0x21,0, (byte)0x80,0x31,(byte)0xff,0x7f};
   require(Arrays.equals(expected,bytes(s(0,0,1,127,2,128,3,-129))),"JCE integer wire bytes");
   require(Arrays.equals(new byte[]{0,2,0x20,1},bytes(s(2,1,0,2))),"JCE field ordering");
   TaskWire.Struct payload=s(0,0,1,"虎牙",2,new byte[]{1,2,3},3,Arrays.asList(s(17,7L)),
     4,Collections.singletonMap("key","value"));
   byte[] packet=TaskWire.packet("wupui","query",payload,8);
   require(TaskWire.unpack(packet).get(5).equals("wupui"),"WUP servant");
   require(TaskWire.reply(packet,"tReq").body.get(1).equals("虎牙"),"UTF-8 struct packet");
   for(byte[] bad:new byte[][]{new byte[]{0x16,10,1},new byte[]{0x09,0,(byte)0xff},new byte[]{0,0,0,2}}){
    try{TaskWire.decode(bad);throw new AssertionError("truncated data accepted");}
    catch(IllegalArgumentException expectedError){}
   }
   packet[3]--;try{TaskWire.unpack(packet);throw new AssertionError("bad WUP length");}
   catch(IllegalArgumentException expectedError){}return;
  }
  if(test.equals("catalog")){
   TaskWire.Struct coop=actionTask(9,"去厂商完成浏览任务",7,
     coopAction("vendor-token"));
   TaskWire.Struct normal=s(1,"游戏完成奖励",11,1,12,1,13,0,14,999L,20,1);
   TaskWire.Struct info=s(0,31L,1,1,2,bytes(normal));
   TaskWire.Struct rewardGroup=s(0,"小游戏",2,15,3,bytes(s(0,Arrays.asList(info,
     s(0,32L,1,5,2,bytes(normal))))));
   List<NativeTaskCatalog.Task> tasks=NativeTaskCatalog.read(response(group(coop,old(10,"充值任务",1,0)),rewardGroup,
    s(0,"下载专区",2,12,3,new byte[]{(byte)0xff})));
   require(tasks.isEmpty(),"removed cooperation, game, download or paid task survived");
   List<NativeTaskCatalog.Task> actions=NativeTaskCatalog.read(response(group(
     actionTask(21,"打开 APP 系统通知",20,""),
     actionTask(22,"关注主播并看播5分钟",41,"hy://live?liveuid=778899"),
     actionTask(23,"厂商浏览任务",7,coopAction("task-token")),
     actionTask(24,"虎牙代售购买账号",65,"https://trade.example/buy"))));
   require(actions.size()==1,"vendor, follow or transaction task was not removed from the catalog");
   require(actions.get(0).automationAction().name().equals("NOTIFICATION"),"notification action");
   require(actions.get(0).key().equals("user/21"),"unstable task switch key");
   require(NativeTaskCatalog.switchKey(actions.get(0)).equals("task_enabled_v1/user/21"),
     "shared task switch key");
   List<NativeTaskCatalog.Task> deeplinks=NativeTaskCatalog.read(response(group(
     actionTask(35,"浏览合作 App 10 秒",7,
       "https://m.huya.com?hyaction=LaunchDeepLink&deeplink=vendor%3A%2F%2Fbrowse&taskid=77&bizid=18"))));
   require(deeplinks.isEmpty(),"removed App browsing task survived via deeplink");
   TaskWire.Struct progress=actions.get(0).progressRequest();
   require("0".equals(progress.text(1)),"notification biz id was not preserved");
   require(progress.number(2)==21,"notification task id was not preserved");
   require(progress.number(3)==0&&progress.number(4)==1&&progress.number(5)>0,
     "deeplink progress payload is invalid");
   TaskWire.Struct noticeJump=actionTask(31,"打开APP系统通知",20,"");
   TaskWire.Struct followJump=actionTask(32,"关注主播并看播5分钟",41,"hy://live?liveuid=778899");
   TaskWire.Struct clickJump=actionTask(33,"厂商浏览任务",7,
     coopAction("jump-token"));
   TaskWire.Struct unknownJump=actionTask(34,"未知跳转任务",99,"https://click.example/task");
   for(TaskWire.Struct task:Arrays.asList(noticeJump,followJump,clickJump,unknownJump)){
    task.put(4,1);task.put(16,"https://jump.example/task");task.put(18,1);
   }
   List<NativeTaskCatalog.Task> jumps=NativeTaskCatalog.read(response(group(noticeJump,followJump,clickJump,unknownJump)));
   require(jumps.size()==2,"vendor or follow task was not removed");
   require(jumps.get(0).skipReason().isEmpty(),"adapted native action blocked by jump metadata");
   require(!jumps.get(1).skipReason().isEmpty(),"unknown jump action was allowed");
   noticeJump.put(21,"coop_task");
   clickJump.put(20,s(1,"https://download.example/app.apk"));
   List<NativeTaskCatalog.Task> protectedTasks=NativeTaskCatalog.read(response(group(noticeJump,clickJump)));
   require(protectedTasks.size()==1&&!protectedTasks.get(0).skipReason().isEmpty(),
     "invalid duplicated cooperation marker bypassed validation");
   List<NativeTaskCatalog.Task> impossible=NativeTaskCatalog.read(response(group(
     old(41,"每日任充",1,0),old(42,"代售购买账号",1,0),
     old(43,"代售出售账号",1,0),old(44,"代售使用AI估值账号",1,0),
     old(45,"下载并安装合作应用",1,0))));
   require(impossible.isEmpty(),"obviously unsupported tasks were not deleted");
   require(NativeTaskCatalog.intervalSeconds("30")==30,"interval");
   for(String bad:new String[]{"0","4","601","-1","5.5","abc"}){
    try{NativeTaskCatalog.intervalSeconds(bad);throw new AssertionError("invalid interval");}
    catch(IllegalArgumentException expectedError){}
   }return;
  }
  Host host=new Host();
  if(test.equals("disabled-before"))host.enabled=false;
  if(test.equals("delayed"))host.delayed=true;
  if(test.equals("account-pending"))host.drop=true;
  if(test.equals("timeout"))host.drop=true;
  if(test.equals("failure"))host.deny=true;
  if(test.equals("security"))host.security=true;
  if(test.equals("duplicate"))host.duplicate=true;
  if(test.equals("task-disabled")||test.equals("task-toggle"))host.disabledTasks.add("user/1");
  if(test.startsWith("action-")){
   host.page=response(group(actionTask(24,"打开APP系统通知",20,"")));
   host.actionCompletes=test.equals("action-success");
   if(test.equals("action-rejected"))host.actionAccepted=false;
  }
  int[] finished={0};
  NativeTaskRunner runner=new NativeTaskRunner(host,30000,()->finished[0]++);
  runner.start(12,"2099-01-01");host.advance(29999);
  if(test.equals("disabled-before")){
   host.advance(120000);require(host.queries==0&&host.claims.isEmpty(),"disabled tasks accessed network or claims");return;
  }
  require(host.claimsSent==0,"claim fired before interval");
  if(test.equals("task-disabled")){
   host.advance(120000);
   require(host.published.size()==1&&host.published.get(0).size()==4,
     "complete task catalog was not published before filtering");
   require(host.claimedIds.equals(Arrays.asList(2L)),"disabled task was executed or rewarded");
   require(host.states.stream().anyMatch(x->x.startsWith("已关闭:")),"disabled task has no journal entry");
   return;
  }
  if(test.equals("task-toggle")){
   host.advance(120000);
   require(host.claimedIds.equals(Arrays.asList(2L)),"disabled task ran before being enabled");
   host.disabledTasks.clear();
   new NativeTaskRunner(host,30000).start(12,"2099-01-01");
   host.advance(240000);
   require(host.claimsSent==2&&host.claimedIds.equals(Arrays.asList(2L,1L)),
     "enabling a task later in the day remained blocked: claims="+host.claims
       +", sent="+host.claimedIds+", states="+host.states);
   return;
  }
  if(test.startsWith("action-")){
   host.advance(120000);
   require(host.actions.size()==1,"native action was not dispatched exactly once");
   require(host.actions.get(0).startsWith("NOTIFICATION:"),"wrong native action");
   if(test.equals("action-rejected")){
    require(host.queries==1&&host.claimsSent==0,"rejected action continued to reward");
    require(host.states.stream().anyMatch(x->x.startsWith("未执行:")),"rejected action was not logged");
    return;
   }
   require(host.queries==2,"task progress was not refreshed before claim");
   if(test.equals("action-unfinished")){
    require(host.claimsSent==0,"unfinished action was rewarded");
    require(host.states.stream().anyMatch(x->x.startsWith("服务端未确认:")),"unfinished action has no diagnostic");
    return;
   }
   require(host.claimsSent==1,"service-confirmed action was not rewarded");
   require(host.states.stream().anyMatch(x->x.startsWith("成功:")),"reward receipt was not confirmed");
   return;
  }
  if(test.equals("account-pending")){
   host.advance(30000);host.uid=13;host.pending.complete(s(0,1),0);host.advance(120000);
   require(host.claimsSent==1,"account change dispatched another claim");
   require(host.states.stream().anyMatch(x->x.startsWith("结果未确认:")),"inflight task has no final log");
   require(host.states.stream().noneMatch(x->x.startsWith("成功:")),"wrong account received success");return;
  }
  if(test.equals("account"))host.uid=13;
  if(test.equals("disabled"))host.enabled=false;
  host.advance(120000);
  if(test.equals("account")||test.equals("disabled")){
   require(host.claimsSent==0,"session or switch ignored");return;
  }
  if(test.equals("timeout")||test.equals("failure")||test.equals("security")){
   require(host.claimsSent==1,"failed or unconfirmed result retried");
   require(host.states.stream().noneMatch(x->x.startsWith("成功:")),"failed request marked successful");
   return;
  }
  require(host.claimsSent==2,"eligible claim count");
  require(host.sentAt.equals(Arrays.asList(30000L,test.equals("delayed")?65000L:60000L)),"interval did not follow acknowledgement");
  require(host.states.stream().filter(x->x.startsWith("成功:")).count()==2,"duplicate callback credited twice");
  require(finished[0]==1,"completion callback did not run exactly once");
  new NativeTaskRunner(host,30000).start(12,"2099-01-01");host.advance(240000);
  require(host.claimsSent==2,"reopening repeated claims");
 }
}
'''


class NativeTasksTest(unittest.TestCase):
    def test_native_transport_preserves_session_and_never_dispatches_downloads(self):
        stubs = {
            "com/duowan/kiwi/ad/api/IHyLotteryAdHelper.java": '''package com.duowan.kiwi.ad.api;
import java.util.Map;
public interface IHyLotteryAdHelper {
 interface HyRewardAdListener {void onRewarded(boolean success,Map ext,String message);void onReward();void onError();}
 interface HYRewardAdReqType {
  Types Companion=new Types();
  class Types {public int getAwardCommAdTaskType(){return 2;}public int getAwardCommRewardTaskType(){return 3;}}
 }
}''',
            "com/google/gson/Gson.java": '''package com.google.gson;
public class Gson {public String toJson(Object value){return "{}";}}''',
            "com/duowan/biz/videoad/impl/HyLotteryAdAwardManager.java": '''package com.duowan.biz.videoad.impl;
import java.util.Map;import com.duowan.kiwi.ad.api.IHyLotteryAdHelper.HyRewardAdListener;
public class HyLotteryAdAwardManager {
 public static final CompanionType Companion=new CompanionType();public static int calls;
 public static class CompanionType {public HyLotteryAdAwardManager getInstance(){return new HyLotteryAdAwardManager();}}
 public void onAwardCommonAdTask(String id,Map sdk,int watch,String json,String req,HyRewardAdListener listener){
  if(!"ad-task".equals(id)||watch!=0||!"6324".equals(req))throw new AssertionError("native video request fields");
  calls++;listener.onReward();boolean success=!"video-denied".equals(ryxq.ev6.mode);
  listener.onRewarded(success,sdk,"");listener.onRewarded(success,sdk,"");
 }
 public void onAwardCommonRewardAdTask(String id,Map sdk,int watch,String json,String req,HyRewardAdListener listener){
  onAwardCommonAdTask(id,sdk,watch,json,req,listener);
 }
}''',
            "com/duowan/kiwi/base/login/api/ILoginModule.java": '''package com.duowan.kiwi.base.login.api;
public interface ILoginModule {boolean isLogin();long getUid();}''',
            "com/duowan/kiwi/base/login/api/ILoginComponent.java": '''package com.duowan.kiwi.base.login.api;
public interface ILoginComponent {ILoginModule getLoginModule();}''',
            "ryxq/xxe.java": '''package ryxq;
import com.duowan.kiwi.base.login.api.*;
public class xxe {public static long uid=12;
 public static Object i(Class<?> type){
  return (ILoginComponent)()->new ILoginModule(){
   public boolean isLogin(){return uid>0;}public long getUid(){return uid;}};}}''',
            "android/content/Context.java": '''package android.content;public class Context {}''',
            "com/duowan/taf/jce/JceOutputStream.java": '''package com.duowan.taf.jce;
public class JceOutputStream {public byte[] bytes;
 public int setServerEncoding(String value){return 0;}public byte[] toByteArray(){return bytes;}}''',
            "com/duowan/HUYA/UserId.java": '''package com.duowan.HUYA;
public class UserId {public long lUid=12;
 public void writeTo(com.duowan.taf.jce.JceOutputStream out){out.bytes=new byte[]{0,(byte)lUid};}}''',
            "com/duowan/biz/wup/WupHelper.java": '''package com.duowan.biz.wup;
public class WupHelper {public static com.duowan.HUYA.UserId identity=new com.duowan.HUYA.UserId();
 public static com.duowan.HUYA.UserId getUserId(){return identity;}}''',
            "com/duowan/jce/wup/UniPacket.java": '''package com.duowan.jce.wup;
public class UniPacket {public byte[] data;public void decode(byte[] bytes){data=bytes;}}''',
            "ryxq/zu6.java": '''package ryxq;public class zu6 {}''',
            "com/huya/kiwi/crossplatform/common/wup/HybridJceCallback.java": '''package com.huya.kiwi.crossplatform.common.wup;
public interface HybridJceCallback {void onResponse(byte[] bytes);void onTraceId(String id);void a(ryxq.zu6 error);}''',
            "ryxq/ev6.java": '''package ryxq;
import com.duowan.jce.wup.UniPacket;import com.huya.kiwi.crossplatform.common.wup.HybridJceCallback;
import io.github.saycm.huyaplus.NativeTransportTest;
public class ev6 {
 public static int count;public static String mode="success";UniPacket packet;HybridJceCallback callback;
 public static ev6 a(UniPacket p,int retry,int timeout,Number channel,HybridJceCallback c){
  if(retry!=0||timeout!=15000||channel!=null)throw new AssertionError("native retry/timeout");
  ev6 r=new ev6();r.packet=p;r.callback=c;return r;}
 public void execute(){count++;NativeTransportTest.verify(packet.data);callback.onTraceId("ignored");
  if("error".equals(mode)){callback.a(new zu6());return;}
  if("malformed".equals(mode)){callback.onResponse(new byte[]{1});return;}
  byte[] response=NativeTransportTest.response();
  if("video-account".equals(mode))xxe.uid=13;
  callback.onResponse(response);callback.onResponse(response);}
}''',
            "io/github/saycm/huyaplus/NativeTransportTest.java": '''package io.github.saycm.huyaplus;
import java.util.*;import java.nio.ByteBuffer;
public class NativeTransportTest {
 public static String servant="wupui",endpoint="getLiveBoxUserGrowthPage";public static int field=1;
 public static Object value=11;
 public static void verify(byte[] packet){
  TaskWire.Struct p=TaskWire.unpack(packet);
  if(!servant.equals(p.get(5))||!endpoint.equals(p.get(6)))throw new AssertionError("unexpected endpoint");
  TaskWire.Struct body=TaskWire.reply(packet,"tReq").body;
  Object actual=body.get(field);
  boolean payloadMatches=value instanceof Number
    ?((Number)value).longValue()==body.number(field)
    :value.equals(actual);
  if(((TaskWire.Struct)body.get(0)).number(0)!=12||!payloadMatches)throw new AssertionError("native identity or payload not preserved");
  if(endpoint.equals("reportUserTaskClickEvent")
    && !"https://huya.com?hyaction=welfarepage&fromid=goldtask&taskid=15".equals(body.text(2)))
    throw new AssertionError("market action was not preserved");
 }
 public static byte[] response(){
  TaskWire.Struct body=new TaskWire.Struct().field(0,1);
  if(endpoint.equals("getCommAdPannel"))body.field(2,new TaskWire.Struct().field(0,"ad-task").field(5,new LinkedHashMap<>()));
  byte[] bytes=TaskWire.packet(servant,endpoint,body,1);
  TaskWire.Struct packet=TaskWire.unpack(bytes);Map<Object,Object> attributes=new LinkedHashMap<>();
  Map<?,?> old=(Map<?,?>)TaskWire.decode((byte[])packet.get(7)).get(0);
  attributes.put("tRsp",old.get("tReq"));packet.put(7,TaskWire.encode(new TaskWire.Struct().field(0,attributes)));
  byte[] raw=TaskWire.encode(packet);return ByteBuffer.allocate(raw.length+4).putInt(raw.length+4).put(raw).array();
 }
 public static void main(String[] args){
  ryxq.ev6.mode=args[0];
  if("logout".equals(args[0]))ryxq.xxe.uid=0;
  if("changed".equals(args[0]))com.duowan.biz.wup.WupHelper.identity.lUid=13;
  if(args[0].startsWith("video-")){
   servant="wupui";endpoint="getCommAdPannel";field=1;value=19;
   int[] callbacks={0};boolean[] accepted={false};
   String type=args[0].equals("video-unknown")?"99":"2";
   new HuyaTaskClient(NativeTransportTest.class.getClassLoader()).claimDiceVideo(
    12,"https://m.huya.com?hyaction=lotteryad&commonpanelreq=1&rewardappid=19&rewardreqid=6324&rewardreqtype="+type,
    ()->!args[0].equals("video-off"),(ok,detail)->{callbacks[0]++;accepted[0]=ok;});
   if(callbacks[0]!=1)throw new AssertionError("video callback duplicated or missing");
   boolean success=args[0].equals("video-normal");
   if(accepted[0]!=success)throw new AssertionError("video outcome not server-confirmed");
   int expected=args[0].equals("video-normal")||args[0].equals("video-denied")?1:0;
   if(com.duowan.biz.videoad.impl.HyLotteryAdAwardManager.calls!=expected)throw new AssertionError("unsafe/duplicate award");
   if(args[0].equals("video-off")&&ryxq.ev6.count!=0)throw new AssertionError("off video requested network");
   return;
  }
  int[] calls={0},code={999};
  String function="download".equals(args[0])?"downloadFile":"getLiveBoxUserGrowthPage";
  String servant="wupui";Object payload=11;
  if("click".equals(args[0])){function="reportUserTaskClickEvent";payload=15;}
  if("widget-report".equals(args[0])){function="reportUserActionFromAppWelfareWidgt";payload="1";}
  if("coop".equals(args[0])){function="reportCoopUserLevelTask";payload="hyaction=launchcooptask&report_type=cooptask";}
  if("progress".equals(args[0])){servant="commui";function="updateUserLevelTaskProgress";payload=405;}
  endpoint=function;NativeTransportTest.servant=servant;field=1;value=payload;
  TaskWire.Struct request=new TaskWire.Struct().field(1,payload);
  if("click".equals(args[0]))request.field(2,
   "https://huya.com?hyaction=welfarepage&fromid=goldtask&taskid=15");
  new HuyaTaskClient(NativeTransportTest.class.getClassLoader()).send(12,servant,function,
   request,(body,result)->{calls[0]++;code[0]=result;});
  if(calls[0]!=1)throw new AssertionError("callback delivered "+calls[0]+" times");
  boolean rejected=Arrays.asList("logout","changed","download","widget-report").contains(args[0]);
  if(rejected&&ryxq.ev6.count!=0)throw new AssertionError("unsafe request dispatched");
  boolean shouldSucceed=Arrays.asList("success","progress","coop","click").contains(args[0]);
  if((!shouldSucceed)!=(code[0]!=0))throw new AssertionError("response status");
 }
}''',
        }
        with tempfile.TemporaryDirectory(prefix="native-transport-") as folder:
            root = Path(folder)
            sources = []
            for name, text in stubs.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                sources.append(str(path))
            sources += [str(ROOT / f"tools/huya-compat-src/io/github/saycm/huyaplus/{name}.java")
                        for name in ("TaskWire", "GlassSettings", "NativeTaskCatalog",
                                     "NativeTaskRunner", "HuyaTaskClient")]
            result = subprocess.run([str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8", "-d", str(root), *sources],
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ("success", "malformed", "error", "logout", "changed", "download",
                         "click", "widget-report", "coop", "progress", "video-normal", "video-denied",
                         "video-off", "video-unknown", "video-account"):
                with self.subTest(case=case):
                    result = subprocess.run([str(JDK / "bin" / ("java" + EXE)), "-cp", str(root),
                                             "io.github.saycm.huyaplus.NativeTransportTest", case],
                                            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_wire_catalog_and_serial_runner(self):
        with tempfile.TemporaryDirectory(prefix="native-tasks-") as folder:
            root = Path(folder)
            harness = root / "NativeTasksTest.java"
            harness.write_text(HARNESS, encoding="utf-8")
            sources = [ROOT / f"tools/huya-compat-src/io/github/saycm/huyaplus/{name}.java"
                       for name in ("TaskWire", "GlassSettings", "NativeTaskCatalog",
                                    "NativeTaskRunner")]
            self.assertTrue(all(p.is_file() for p in sources), "native task adapter is missing")
            result = subprocess.run(
                [str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8", "-d", str(root),
                 *map(str, sources), str(harness)], capture_output=True, text=True,
                encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ("coop-callback", "wire", "catalog", "success", "delayed", "duplicate", "timeout",
                         "failure", "security", "account", "account-pending", "disabled",
                         "disabled-before", "action-success", "action-unfinished",
                         "meal-success", "meal-incomplete", "meal-already-claimed",
                         "meal-zero-entry-progress", "removed-gold-tasks",
                         "action-rejected", "task-disabled", "task-toggle"):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-cp", str(root),
                         "io.github.saycm.huyaplus.NativeTasksTest", case],
                        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
