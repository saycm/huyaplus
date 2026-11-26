import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_daily_automation import DAILY_SOURCES
from test_huya_loader_lifecycle import ROOT, JDK, SDK, EXE


class TaskSequenceTest(unittest.TestCase):
    def test_badges_run_before_task_center_and_gifts(self):
        sources = dict(DAILY_SOURCES)
        sources["android/os/Handler.java"] = sources["android/os/Handler.java"].replace(
            "static long now;", "public static long now;")
        sources["android/os/SystemClock.java"] = """
package android.os;
public class SystemClock {
 public static long elapsedRealtime(){return Handler.now;}
 public static long uptimeMillis(){return Handler.now;}
}
"""
        sources["ryxq/TestServer.java"] = sources["ryxq/TestServer.java"].replace(
            "int lists,signs", "int lists,signs,roomChecks,grainChecks,grainPreparations").replace(
            "class TestServer {", "class TestServer {public static boolean funded; public static int stock=1;")
        sources["ryxq/xxe.java"] = sources["ryxq/xxe.java"].replace(
            "return (ILoginComponent)", """
  if(type==com.duowan.kiwi.props.api.component.IPropsComponent.class)
   return (com.duowan.kiwi.props.api.component.IPropsComponent)()->id->{
    TestServer.grainPreparations++;
    return new com.duowan.kiwi.props.api.bean.PropItem();
   };
  return (ILoginComponent)""")
        sources["com/duowan/kiwi/props/api/component/IPropsComponent.java"] = """
package com.duowan.kiwi.props.api.component;
public interface IPropsComponent {IPropsModule getPropsModule();}
"""
        sources["com/duowan/kiwi/props/api/component/IPropsModule.java"] = """
package com.duowan.kiwi.props.api.component;
public interface IPropsModule {com.duowan.kiwi.props.api.bean.PropItem getPropAnyWay(int id);}
"""
        sources["com/duowan/kiwi/props/api/bean/PropItem.java"] = """
package com.duowan.kiwi.props.api.bean;
public class PropItem {public boolean isTigerFoodId(){return true;}}
"""
        sources["com/duowan/HUYA/GetUserCardPackageReq.java"] = """
package com.duowan.HUYA;
public class GetUserCardPackageReq {
 public UserId tId;public long lPid,lHomeOwnerUid;public int eTempleteType,eSource;
}"""
        for name, field in (("mfg", "d"), ("nh3", "f")):
            sources[f"ryxq/{name}.java"] = f"""
package ryxq;
public class {name} {{
 public static final {name} {field}=new {name}();
 public int a(){{return 1;}}
}}"""
        path = "com/duowan/biz/wup/gamelive/GameLiveWupFunction.java"
        sources[path] = sources[path].replace("public class GameLiveWupFunction {", """
public class GameLiveWupFunction {
 public static class Stock extends com.duowan.taf.jce.JceStruct {
  public static class Grain {public int iItemType=4;public long iItemCount=TestServer.stock;}
  public final java.util.List<?> vUserCardItemCountLists=TestServer.funded
   ?java.util.Collections.singletonList(new Grain()):java.util.Collections.emptyList();
 }
 public static class z extends jd8 {
  public z(GetUserCardPackageReq req){}
  public void execute(){TestServer.grainChecks++;TestServer.reply(this,new Stock());}
 }""")
        sources["com/duowan/kiwi/liveinfo/wupfunction/WupFunction.java"] = """
package com.duowan.kiwi.liveinfo.wupfunction;
import ryxq.*;
public class WupFunction {
 public static class GameLiveWupFunction {
  public static class Notice {public int iRoomId=123;public long lPresenterUid=789;}
  public static class Room extends com.duowan.taf.jce.JceStruct {
   public Notice tNotice=new Notice();
  }
  public static class getLivingInfo extends jd8 {
   public getLivingInfo(long a,long b,long c,long room,String d,String e){}
   public void execute(){TestServer.roomChecks++;TestServer.reply(this,new Room());}
  }
 }
}"""
        sources["com/duowan/kiwi/props/api/utils/SendGiftPayPloyUtil.java"] = """
package com.duowan.kiwi.props.api.utils;
public class SendGiftPayPloyUtil {
 public static class Pay {
  public int iPayPloy=2;public long lPayCount,lNewCoinDeduction;
 }
 public static Pay createPayPloy(float a,float b,long c,boolean d){return new Pay();}
}"""
        gift_package = "com/duowan/kiwi/props/api/request/"
        sources[gift_package + "SendGiftParam.java"] = """
package com.duowan.kiwi.props.api.request;
import com.duowan.kiwi.props.api.bean.PropItem;
import com.duowan.kiwi.props.api.utils.SendGiftPayPloyUtil.Pay;
public class SendGiftParam {
 public int id,count;public long room,receiver;public Pay pay;
 public static class Builder {
  final SendGiftParam params=new SendGiftParam();
  public Builder(int id,int count){params.id=id;params.count=count;}
  public void giftInfo(PropItem prop){}
  public void roomUid(long room){params.room=room;}
  public void receiveUid(long receiver){params.receiver=receiver;}
  public void payPloy(Pay pay){params.pay=pay;}
  public SendGiftParam build(){return params;}
 }
}"""
        for name, declaration in (
            ("ISendGiftService", "public interface ISendGiftService {void sendGiftCompat(SendGiftParam p,ISendGiftCallback c);}"),
            ("ISendGiftCallback", "public interface ISendGiftCallback {void onResult(SendGiftResult result);}"),
            ("SendGiftResult", "public abstract class SendGiftResult {public static class Success extends SendGiftResult {}}"),
        ):
            sources[gift_package + name + ".java"] = "package com.duowan.kiwi.props.api.request;\n" + declaration
        sources["com/duowan/kiwi/props/impl/request/SendGiftService.java"] = """
package com.duowan.kiwi.props.impl.request;
import com.duowan.kiwi.props.api.request.*;
import io.github.saycm.huyaplus.SequenceTest;
public class SendGiftService implements ISendGiftService {
 public static class Request {
  public long lGiftUid,lRoomUid;public int iItemType,iItemCount;public Object tPayPloy;
 }
 public Request createSendGiftReq(SendGiftParam p,String id,long at){
  Request request=new Request();request.lGiftUid=p.receiver;request.lRoomUid=p.room;
  request.iItemType=p.id;request.iItemCount=p.count;request.tPayPloy=p.pay;return request;
 }
 public void sendGiftCompat(SendGiftParam params,ISendGiftCallback callback){
  try{io.github.libxposed.api.XposedModule.call(this,"createSendGiftReq",
   new Class<?>[]{SendGiftParam.class,String.class,long.class},params,"test",0L);}
  catch(Throwable failure){throw new AssertionError(failure);}
  SequenceTest.sendGrain(params.count,callback);
 }
}"""
        sources["ryxq/xxe.java"] = sources["ryxq/xxe.java"].replace("return (ILoginComponent)", """
  if(type==com.duowan.kiwi.props.api.request.ISendGiftService.class)
   return new com.duowan.kiwi.props.impl.request.SendGiftService();
  return (ILoginComponent)""")
        sources["io/github/saycm/huyaplus/HuyaTaskClient.java"] = """
package io.github.saycm.huyaplus;
import android.os.*;
import java.util.*;
final class HuyaTaskClient {
 static final List<String> calls=new ArrayList<>();
 static final List<Long> times=new ArrayList<>();
 static boolean holdDice;
 static boolean offlineCoins;
 static final Set<Long> rewardedAccounts=new HashSet<>();
 static boolean resumeSplit,offlineGrain;
 static int grainProgress,grainRewards;
 static NativeTaskRunner.Reply heldDice;
 HuyaTaskClient(ClassLoader loader){}
 long loggedInUid() throws ReflectiveOperationException{return ryxq.xxe.uid;}
 boolean notificationEnabled(Object context) throws ReflectiveOperationException{return false;}
 void claimDiceVideo(long uid,String action,java.util.function.BooleanSupplier allowed,NativeTaskRunner.ActionReply reply){
  reply.complete(false,"unused");
 }
 void claimDiceVideo(long uid,String action,java.util.function.BooleanSupplier allowed,
    NativeTaskRunner.ActionReply reply,long interval,java.util.function.Consumer<Runnable> later){
  reply.complete(false,"unused");
 }
 void send(long account,String servant,String function,TaskWire.Struct req,NativeTaskRunner.Reply reply){
  calls.add(function);times.add(Handler.now);
  TaskWire.Struct response=new TaskWire.Struct();
  if(function.equals("executeUserSign")){
   new Handler(Looper.getMainLooper()).postDelayed(()->reply.complete(
     new TaskWire.Struct().field(5,new TaskWire.Struct().field(1,2)),0),1000);
  }else if(function.equals("getJumpGameTaskList")){
   if(offlineGrain){reply.complete(response,-1);return;}
   if(resumeSplit){
    reply.complete(response.field(0,List.of(new TaskWire.Struct().field(0,"grain").field(1,"赠送虎粮")
      .field(5,2).field(6,grainProgress).field(7,3).field(8,grainRewards).field(9,1)
      .field(10,grainRewards==1?2:grainProgress>=3?1:0))),0);
    return;
   }
   reply.complete(response.field(0,new ArrayList<>()),0);
  }else if(function.equals("claimJumpGameTaskReward")){
   if(grainProgress!=3||grainRewards!=0||!req.text(1).equals("grain"))
    throw new AssertionError("unearned or duplicate dice reward");
   grainRewards++;
   reply.complete(response.field(1,List.of(new TaskWire.Struct().field(0,1).field(3,1))),0);
  }else if(function.equals("getJumpGameModule")){
   if(holdDice)heldDice=reply;
   else reply.complete(emptyDice(),0);
  }else if(function.equals("queryFansGroupTaskInfo")){
   reply.complete(response.field(0,0).field(1,account).field(2,req.number(1))
     .field(7,new TaskWire.Struct().field(0,4)),0);
  }else if(function.equals("getLiveBoxUserGrowthPage")){
   if(offlineCoins){reply.complete(response,-1);return;}
   TaskWire.Struct task=new TaskWire.Struct().field(0,1L).field(1,1).field(2,1)
     .field(3,0).field(4,2).field(5,"整点领金币").field(28,1);
   List<TaskWire.Struct> groups=List.of(new TaskWire.Struct().field(0,"每日赚金币").field(1,List.of(task)).field(2,1));
   byte[] data=TaskWire.encode(new TaskWire.Struct().field(0,groups));
   reply.complete(response.field(1,Arrays.asList(new TaskWire.Struct().field(0,14).field(1,data))),0);
  }else if(function.equals("receiveUserLevelTaskPrize")){
   long id=req.number(1);
   if(id!=1||!rewardedAccounts.add(account)) throw new AssertionError("unexpected coin reward: "+id);
   reply.complete(response.field(0,1),0);
  }else throw new AssertionError("Unexpected task "+function);
 }
 static TaskWire.Struct emptyDice(){return new TaskWire.Struct().field(0,0).field(1,0).field(2,new TaskWire.Struct());}
}"""
        sources["io/github/saycm/huyaplus/SequenceTest.java"] = """
package io.github.saycm.huyaplus;
import android.content.*;import android.os.*;import java.lang.reflect.*;
import com.duowan.kiwi.props.api.request.*;
public class SequenceTest {
 static final java.util.List<Integer> grainSends=new java.util.ArrayList<>();
 static boolean dropFirstGift;
 public static void sendGrain(int count,ISendGiftCallback callback){
  grainSends.add(count);ryxq.TestServer.stock-=count;
  if(dropFirstGift&&grainSends.size()==1)return;
  HuyaTaskClient.grainProgress++;
  callback.onResult(new SendGiftResult.Success());
 }
 public static void main(String[] args){
  String scenario=args.length>0?args[0]:"";
  boolean offlineStart="offline-start".equals(scenario);
  boolean badgeSwitch="account-switch-during-badges".equals(scenario);
  boolean snapshotSwitch="task-snapshot-account-switch".equals(scenario);
  boolean resumeSplit=scenario.startsWith("resume-split");
  boolean ordinaryGift="resume-split-ordinary".equals(scenario);
  boolean periodicGift="gift-receipt-periodic".equals(scenario);
  dropFirstGift=periodicGift||"gift-receipt-delayed".equals(scenario);
  boolean split=resumeSplit||dropFirstGift;
  HuyaTaskClient.resumeSplit=split;
  boolean[] autoOn={true};
  boolean[] giftOn={args.length>0&&!offlineStart&&!snapshotSwitch};
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(SequenceTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},(proxy,method,values)->{
    String key=(String)values[0];
    if(method.getName().equals("getString")){
     if(key.equals(GlassSettings.KEY_TASK_INTERVAL))return "5";
     return key.equals(GlassSettings.KEY_GIFT_ROOMS)?(split?"123=6":"123=1"):"";
    }
    if(method.getName().equals("getBoolean")){
     if(offlineStart||snapshotSwitch)
      return key.equals(GlassSettings.KEY_NATIVE_TASKS)||(Boolean)values[1];
     if(badgeSwitch)return key.equals(GlassSettings.KEY_AUTO_SIGN);
     if(split)return key.equals(GlassSettings.KEY_AUTO_GIFT)||key.equals(GlassSettings.KEY_DICE_MISSIONS)
       ||key.equals(DiceTaskCatalog.switchKey("dice/grain"));
     if(key.equals(GlassSettings.KEY_AUTO_GIFT))return giftOn[0];
     if("gift-relogin-during-sign".equals(scenario)&&key.equals(GlassSettings.KEY_AUTO_SIGN))return true;
     if("gift-relogin-during-dice".equals(scenario)&&key.equals(GlassSettings.KEY_AUTO_DICE))return true;
     return args.length==0&&(key.equals(GlassSettings.KEY_DICE_WELFARE_SIGN)
       ||key.equals(GlassSettings.KEY_AUTO_DICE)&&autoOn[0]||key.equals(GlassSettings.KEY_AUTO_SIGN));
    }
    throw new AssertionError("unused prefs");
   });
  DailyAutomation engine=new DailyAutomation(new io.github.libxposed.api.XposedModule(){},
    prefs,SequenceTest.class.getClassLoader());
  boolean alreadySubmitted="gift-already-submitted".equals(scenario);
  if(split){ryxq.TestServer.funded=true;ryxq.TestServer.stock=resumeSplit?4:6;}
  if(alreadySubmitted||resumeSplit){
   java.text.SimpleDateFormat day=new java.text.SimpleDateFormat("yyyy-MM-dd",java.util.Locale.ROOT);
   day.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Shanghai"));
   String run=ryxq.xxe.uid+"/"+day.format(new java.util.Date());
   ContentResolver.claims.add("gift-send/"+run+"/789");
   if(resumeSplit){
    HuyaTaskClient.grainProgress=1;
    LocalTaskStore.giftPlans.put(run,AutomationRules.planDiceGrain(AutomationRules.parse("123=6"),bound->0));
    if(!ordinaryGift)ContentResolver.claims.add("dice-grain-started/"+run);
    if("resume-split-confirmed".equals(scenario))ContentResolver.claims.add("dice-grain-confirmed/"+run+"/123/1");
   }
  }
  if("gift-relogin-during-sign".equals(scenario))ryxq.TestServer.drop=true;
  HuyaTaskClient.offlineCoins=offlineStart;
  if(badgeSwitch)ryxq.TestServer.drop=true;
  engine.onOpen(new Context());
  if(snapshotSwitch){
   for(long uid:new long[]{111,222,111,111,0,111}){
    ryxq.xxe.uid=uid;
    engine.onOpen(new Context());
    Handler.advance(30000);
   }
   if(!HuyaTaskClient.rewardedAccounts.equals(java.util.Set.of(111L,222L)))
    throw new AssertionError("each account should receive only its own reward once");
   if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameTaskList")!=4
      ||java.util.Collections.frequency(HuyaTaskClient.calls,"getLiveBoxUserGrowthPage")!=4)
    throw new AssertionError("both task lists should refresh after switching back or logging in again: "+HuyaTaskClient.calls);
   java.util.List<String> scopes=LocalTaskStore.taskScopes;
   if(scopes.size()!=5||!scopes.get(1).startsWith("222/")||!scopes.get(3).isEmpty()
      ||!scopes.get(2).equals(scopes.get(0))||!scopes.get(4).equals(scopes.get(0)))
    throw new AssertionError("account changes and logout must invalidate task snapshots: "+scopes);
   return;
  }
  if(resumeSplit){
   Handler.advance(90000);
   if(ordinaryGift){
    if(!grainSends.isEmpty()||HuyaTaskClient.grainRewards!=0)
     throw new AssertionError("a previous ordinary gift must not be treated as part of the split: "+grainSends);
    return;
   }
   if(!grainSends.equals(java.util.List.of(2,2))||HuyaTaskClient.grainRewards!=1)
    throw new AssertionError("resume should send only the untouched parts and claim once: "+grainSends);
   return;
  }
  if(dropFirstGift){
   Handler.advance(150000);
   if(!grainSends.equals(java.util.List.of(2,2,2))||HuyaTaskClient.grainRewards!=0)
    throw new AssertionError("missing first receipt must not block remaining parts or trigger an early claim: "+grainSends);
   if(periodicGift){
    HuyaTaskClient.grainProgress++;
    Handler.advance(1100000);
    int reads=java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameTaskList");
    Handler.advance(2200000);
    if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameTaskList")!=reads)
     throw new AssertionError("completed grain task continues polling");
   }else{
    HuyaTaskClient.offlineGrain=true;
    engine.onOpen(new Context());
    Handler.advance(175000);
    HuyaTaskClient.offlineGrain=false;
    HuyaTaskClient.grainProgress++;
    engine.onOpen(new Context());
    Handler.advance(200000);
    engine.onOpen(new Context());
    Handler.advance(230000);
   }
   if(!grainSends.equals(java.util.List.of(2,2,2))||HuyaTaskClient.grainRewards!=1)
    throw new AssertionError("late progress should claim once without sending extra grain: "+grainSends);
   return;
  }
  if(badgeSwitch){
   Handler.advance(5001);
   ryxq.xxe.uid=222;
   ryxq.TestServer.drop=false;
   engine.onOpen(new Context());
   if(LocalTaskStore.taskScopes.size()!=2||!LocalTaskStore.taskScopes.get(1).startsWith("222/"))
    throw new AssertionError("account change must invalidate the old task snapshot before the busy badge run ends");
   Handler.advance(110000);
   if(ryxq.TestServer.lists!=2||ryxq.TestServer.signs!=2||!ryxq.TestServer.signed.contains("222/11"))
    throw new AssertionError("new account did not get its badge run after the old queue stopped");
   return;
  }
  if(offlineStart){
   String query="getLiveBoxUserGrowthPage";
   Handler.advance(20000);
   HuyaTaskClient.offlineCoins=false;
   engine.onOpen(new Context());
   Handler.advance(40000);
   if(java.util.Collections.frequency(HuyaTaskClient.calls,query)!=2
      ||java.util.Collections.frequency(HuyaTaskClient.calls,"receiveUserLevelTaskPrize")!=1
      ||java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameTaskList")!=1)
    throw new AssertionError("failed read was not recovered exactly once: "+HuyaTaskClient.calls);
   return;
  }
  if("gift-relogin-during-sign".equals(scenario)){
   Handler.advance(5001);
   if(ryxq.TestServer.lists!=1)throw new AssertionError("badge list request did not start");
   long uid=ryxq.xxe.uid;
   ryxq.xxe.uid=0;
   Handler.advance(30000);
   ryxq.xxe.uid=uid;
   ryxq.TestServer.drop=false;
   engine.onOpen(new Context());
   Handler.advance(95000);
   if(ryxq.TestServer.grainChecks!=1||ryxq.TestServer.lists!=2||ryxq.TestServer.signs!=2)
    throw new AssertionError("aborted badge phase did not recover on relogin");
   return;
  }
  if("gift-relogin-during-dice".equals(scenario)){
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("missing initial stock check");
   HuyaTaskClient.holdDice=true;
   for(int tick=0;tick<900&&HuyaTaskClient.heldDice==null;tick++)Handler.advance(1000);
   if(HuyaTaskClient.heldDice==null)throw new AssertionError("dice check did not start");
   long uid=ryxq.xxe.uid;
   ryxq.xxe.uid=0;
   engine.onOpen(new Context());
   ryxq.xxe.uid=uid;
   Handler.advance(1000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("gift check interrupted the dice request");
   HuyaTaskClient.holdDice=false;
   HuyaTaskClient.heldDice.complete(HuyaTaskClient.emptyDice(),0);
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=2)throw new AssertionError("gift checks did not recover after the dice request");
   return;
  }
  if("gift-relogin".equals(scenario)){
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("missing initial stock check");
   long uid=ryxq.xxe.uid;
   ryxq.xxe.uid=0;
   Handler.advance(1800000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("stock checked while logged out");
   ryxq.xxe.uid=uid;
   engine.onOpen(new Context());
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=2)throw new AssertionError("gift checks did not resume at login");
   return;
  }
  if("gift-stale-account".equals(scenario)){
   ryxq.TestServer.funded=true;
   Handler.advance(10001);
   if(ryxq.TestServer.grainChecks!=1||ryxq.TestServer.grainPreparations!=0)
    throw new AssertionError("expected gift to be waiting after the stock check");
   ryxq.xxe.uid=222;
   Handler.advance(5000);
   if(ryxq.TestServer.grainPreparations!=0)
    throw new AssertionError("old gift reached item preparation after account switch");
   return;
  }
  if("gift-stale-day".equals(scenario)){
   boolean[] rejected={false};
   engine.sendDiceGrain(ryxq.xxe.uid,"2000-01-01",new AutomationRules.GrainPart(123,1,1,1),()->true,
    (success,detail)->rejected[0]=!success);
   if(!rejected[0]||ryxq.TestServer.roomChecks!=0)
    throw new AssertionError("expired gift started a new request");
   return;
  }
  if(alreadySubmitted){
   Handler.advance(1830000);
   if(ryxq.TestServer.grainChecks!=0)throw new AssertionError("submitted room still checking stock");
   return;
  }
  if(args.length>0){
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("missing initial stock check");
   engine.onOpen(new Context());
   Handler.advance(1760000);
   if(ryxq.TestServer.grainChecks!=1)throw new AssertionError("stock checked before 30 minutes");
   Handler.advance(30000);
   if(ryxq.TestServer.grainChecks!=2)throw new AssertionError("empty stock did not get checked again");
   giftOn[0]=false;
   Handler.advance(1800000);
   if(ryxq.TestServer.grainChecks!=2)throw new AssertionError("disabled gifts still checking stock");
   return;
  }
  Handler.advance(999);
  if(!HuyaTaskClient.calls.isEmpty()||ryxq.TestServer.lists!=1)
    throw new AssertionError("badges did not start before task center requests");
  Handler.advance(28001);
  if(engine.isIdle()||HuyaTaskClient.calls.contains("executeUserSign"))
    throw new AssertionError("task center started before badges completed");
  Handler.advance(51000);
  if(!HuyaTaskClient.calls.equals(java.util.Arrays.asList(
     "queryFansGroupTaskInfo","queryFansGroupTaskInfo","executeUserSign","getJumpGameTaskList","getJumpGameModule")))
    throw new AssertionError("unexpected phases "+HuyaTaskClient.calls);
  if(HuyaTaskClient.times.get(2)-HuyaTaskClient.times.get(1)<5000
    ||HuyaTaskClient.times.get(3)-HuyaTaskClient.times.get(2)<6000
    ||HuyaTaskClient.times.get(4)-HuyaTaskClient.times.get(3)<5000)
    throw new AssertionError("phase interval ignored "+HuyaTaskClient.times);
  if(ryxq.TestServer.lists!=1||ryxq.TestServer.signs!=2)
    throw new AssertionError("missing badge sign requests");
  Handler.advance(820000);
  if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameModule")!=1)
    throw new AssertionError("dice were checked before 15 minutes");
  Handler.advance(100000);
  if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameModule")!=2)
    throw new AssertionError("dice were not checked after 15 minutes");
  autoOn[0]=false;
  Handler.advance(900000);
  autoOn[0]=true;
  engine.onOpen(new Context());
  Handler.advance(900000);
  if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameModule")!=3)
    throw new AssertionError("same-day dice monitor failed to restart");
 }
}"""
        with tempfile.TemporaryDirectory(dir=ROOT / "build/test-tmp") as temp:
            folder = Path(temp)
            files = []
            for name, text in sources.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                files.append(str(path))
            package = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
            files += [str(package / (name + ".java")) for name in ("HuyaCompatEntry", "GlassSettings")]
            android = SDK / "platforms/android-36/android.jar"
            result = subprocess.run([str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8",
                                     "-cp", str(android), "-d", str(folder / "classes"), *files],
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ([], ["free-grain"], ["gift-already-submitted"],
                         ["gift-relogin"], ["gift-relogin-during-sign"], ["gift-relogin-during-dice"],
                         ["gift-stale-account"], ["gift-stale-day"], ["offline-start"],
                         ["account-switch-during-badges"], ["task-snapshot-account-switch"],
                         ["resume-split-confirmed"], ["resume-split-uncertain"],
                         ["gift-receipt-delayed"], ["gift-receipt-periodic"], ["resume-split-ordinary"]):
                with self.subTest(case=case):
                    result = subprocess.run([str(JDK / "bin" / ("java" + EXE)), "-cp",
                                             os.pathsep.join((str(folder / "classes"), str(android))),
                                             "io.github.saycm.huyaplus.SequenceTest", *case],
                                            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
