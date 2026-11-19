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
        sources["io/github/saycm/huyaplus/HuyaTaskClient.java"] = """
package io.github.saycm.huyaplus;
import android.os.*;
import java.util.*;
final class HuyaTaskClient {
 static final List<String> calls=new ArrayList<>();
 static final List<Long> times=new ArrayList<>();
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
   reply.complete(response.field(0,0).field(1,0).field(2,new TaskWire.Struct()),0);
  }else throw new AssertionError("Unexpected task "+function);
 }
}"""
        sources["io/github/saycm/huyaplus/SequenceTest.java"] = """
package io.github.saycm.huyaplus;
import android.content.*;import android.os.*;import java.lang.reflect.*;
public class SequenceTest {
 public static void main(String[] args){
  boolean[] autoOn={true};
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(SequenceTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},(proxy,method,values)->{
    String key=(String)values[0];
    if(method.getName().equals("getString"))return key.equals(GlassSettings.KEY_TASK_INTERVAL)?"5":"";
    if(method.getName().equals("getBoolean"))return key.equals(GlassSettings.KEY_DICE_WELFARE_SIGN)
     ||key.equals(GlassSettings.KEY_AUTO_DICE)&&autoOn[0]||key.equals(GlassSettings.KEY_AUTO_SIGN);
    throw new AssertionError("unused prefs");
   });
  DailyAutomation engine=new DailyAutomation(new io.github.libxposed.api.XposedModule(){},
    prefs,SequenceTest.class.getClassLoader());
  engine.onOpen(new Context());
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
  autoOn[0]=false;
  Handler.advance(60000);
  autoOn[0]=true;
  engine.onOpen(new Context());
  Handler.advance(65000);
  if(java.util.Collections.frequency(HuyaTaskClient.calls,"getJumpGameModule")<2)
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
            result = subprocess.run([str(JDK / "bin" / ("java" + EXE)), "-cp",
                                     os.pathsep.join((str(folder / "classes"), str(android))),
                                     "io.github.saycm.huyaplus.SequenceTest"],
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
