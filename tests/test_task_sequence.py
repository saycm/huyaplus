import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_daily_automation import DAILY_SOURCES
from test_huya_loader_lifecycle import ROOT, JDK, SDK, EXE


class TaskSequenceTest(unittest.TestCase):
    def test_sign_dice_and_badges_wait_for_previous_phase(self):
        sources = dict(DAILY_SOURCES)
        sources["android/os/Handler.java"] = sources["android/os/Handler.java"].replace(
            "static long now;", "public static long now;")
        sources["ryxq/TestServer.java"] = sources["ryxq/TestServer.java"].replace(
            "int lists,signs", "int lists,signs,roomChecks,grainChecks,grainPreparations").replace(
            "class TestServer {", "class TestServer {public static boolean funded;")
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
  public static class Grain {public int iItemType=4;public long iItemCount=1;}
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
        sources["io/github/saycm/huyaplus/HuyaTaskClient.java"] = """
package io.github.saycm.huyaplus;
import android.os.*;
import java.util.*;
final class HuyaTaskClient {
 static final List<String> calls=new ArrayList<>();
 static final List<Long> times=new ArrayList<>();
 static boolean holdDice;
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
   reply.complete(response.field(0,new ArrayList<>()),0);
  }else if(function.equals("getJumpGameModule")){
   if(holdDice)heldDice=reply;
   else reply.complete(emptyDice(),0);
  }else throw new AssertionError("Unexpected task "+function);
 }
 static TaskWire.Struct emptyDice(){return new TaskWire.Struct().field(0,0).field(1,0).field(2,new TaskWire.Struct());}
}"""
        sources["io/github/saycm/huyaplus/SequenceTest.java"] = """
package io.github.saycm.huyaplus;
import android.content.*;import android.os.*;import java.lang.reflect.*;
public class SequenceTest {
 public static void main(String[] args){
  String scenario=args.length>0?args[0]:"";
  boolean[] autoOn={true};
  boolean[] giftOn={args.length>0};
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(SequenceTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},(proxy,method,values)->{
    String key=(String)values[0];
    if(method.getName().equals("getString")){
     if(key.equals(GlassSettings.KEY_TASK_INTERVAL))return "5";
     return key.equals(GlassSettings.KEY_GIFT_ROOMS)?"123=1":"";
    }
    if(method.getName().equals("getBoolean")){
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
  if(alreadySubmitted){
   java.text.SimpleDateFormat day=new java.text.SimpleDateFormat("yyyy-MM-dd",java.util.Locale.ROOT);
   day.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Shanghai"));
   ContentResolver.claims.add("gift-send/"+ryxq.xxe.uid+"/"+day.format(new java.util.Date())+"/789");
  }
  engine.onOpen(new Context());
  if("gift-relogin-during-sign".equals(scenario)){
   ryxq.TestServer.drop=true;
   Handler.advance(5001);
   if(ryxq.TestServer.lists!=1)throw new AssertionError("badge list request did not start");
   long uid=ryxq.xxe.uid;
   ryxq.xxe.uid=0;
   Handler.advance(30000);
   ryxq.xxe.uid=uid;
   ryxq.TestServer.drop=false;
   engine.onOpen(new Context());
   Handler.advance(40000);
   if(ryxq.TestServer.grainChecks!=1||ryxq.TestServer.lists!=1||ryxq.TestServer.signs!=0)
    throw new AssertionError("aborted badge phase prevented gifts from resuming or was repeated");
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
   engine.sendDiceGrain(ryxq.xxe.uid,"2000-01-01",123,"expired-day",()->true,
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
  if(HuyaTaskClient.calls.size()!=1||ryxq.TestServer.lists!=0)
    throw new AssertionError("tasks started before sign receipt");
  Handler.advance(28001);
  if(engine.isIdle())throw new AssertionError("queued legacy continuation considered idle");
  Handler.advance(12000);
  if(!HuyaTaskClient.calls.equals(java.util.Arrays.asList(
     "executeUserSign","getJumpGameTaskList","getJumpGameModule")))
    throw new AssertionError("unexpected phases "+HuyaTaskClient.calls);
  if(HuyaTaskClient.times.get(1)<6000
    ||HuyaTaskClient.times.get(2)-HuyaTaskClient.times.get(1)<5000)
    throw new AssertionError("phase interval ignored "+HuyaTaskClient.times);
  if(ryxq.TestServer.lists!=1||ryxq.TestServer.signs!=2)
    throw new AssertionError("legacy tasks failed after native completion");
  Handler.advance(800000);
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
                         ["gift-stale-account"], ["gift-stale-day"]):
                with self.subTest(case=case):
                    result = subprocess.run([str(JDK / "bin" / ("java" + EXE)), "-cp",
                                             os.pathsep.join((str(folder / "classes"), str(android))),
                                             "io.github.saycm.huyaplus.SequenceTest", *case],
                                            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)
