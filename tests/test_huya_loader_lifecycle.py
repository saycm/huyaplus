"""Exercise the API 102 dynamic ClassLoader lifecycle against the real module entry."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SDK = Path(os.environ["ANDROID_HOME"])
JDK = Path(os.environ["JAVA_HOME"])
EXE = ".exe" if os.name == "nt" else ""

SOURCES = {
    "android/app/Activity.java": """
package android.app;
public class Activity {
 public void onCreate(android.os.Bundle state){}
 public void onResume(){}
 public boolean isFinishing(){return false;}
 public boolean isDestroyed(){return false;}
 public boolean hasWindowFocus(){return true;}
 public android.content.pm.PackageManager getPackageManager(){return new android.content.pm.PackageManager();}
 public android.content.Context getApplicationContext(){return null;}
 public android.content.ContentResolver getContentResolver(){
  return new android.content.ContentResolver();
 }
}
""",
    "android/content/pm/PackageManager.java": """
package android.content.pm;
public class PackageManager {
 public static String huyaVersion="13.5.62";
 public static class NameNotFoundException extends Exception {}
 public PackageInfo getPackageInfo(String name,int flags)throws NameNotFoundException{
  if(!"com.duowan.kiwi".equals(name)||huyaVersion==null)throw new NameNotFoundException();
  PackageInfo info=new PackageInfo();info.versionName=huyaVersion;return info;
 }
 public String[] getPackagesForUid(int uid){return new String[]{"com.duowan.kiwi"};}
}
""",
    "android/content/pm/PackageInfo.java": """
package android.content.pm;
public class PackageInfo {public String versionName;}
""",
    "android/content/ContentResolver.java": """
package android.content;
import android.os.Bundle;
public class ContentResolver {
 public static String rootStatus="granted";
 public static int rootChecks;
 public Bundle call(String authority,String method,String arg,Bundle extras){
  if(!"io.github.saycm.huyaplus.tasks".equals(authority)||!"verify_root".equals(method))
   throw new AssertionError("Unexpected provider call: "+method);
  rootChecks++;
  if("missing".equals(rootStatus))return null;
  if("unavailable".equals(rootStatus))throw new IllegalArgumentException("provider unavailable");
  Bundle reply=new Bundle();
  reply.putBoolean("root_granted","granted".equals(rootStatus));
  return reply;
 }
 public Bundle call(android.net.Uri uri,String method,String arg,Bundle extras){return null;}
}
""",
    "android/os/Bundle.java": """
package android.os;
public class Bundle {
 private final java.util.Map<String,Object> values=new java.util.HashMap<>();
 public void putBoolean(String key,boolean value){values.put(key,value);}
 public boolean getBoolean(String key){return Boolean.TRUE.equals(values.get(key));}
 public boolean getBoolean(String key,boolean fallback){return (Boolean)values.getOrDefault(key,fallback);}
 public void putString(String key,String value){values.put(key,value);}
 public String getString(String key,String fallback){return (String)values.getOrDefault(key,fallback);}
 public void putLong(String key,long value){values.put(key,value);}
 public long getLong(String key){return (Long)values.getOrDefault(key,0L);}
 public void putInt(String key,int value){values.put(key,value);}
 public int getInt(String key,int fallback){return (Integer)values.getOrDefault(key,fallback);}
 public <T> void putParcelableArrayList(String key,java.util.ArrayList<T> value){values.put(key,value);}
 @SuppressWarnings("unchecked")
 public <T> java.util.ArrayList<T> getParcelableArrayList(String key){
  return (java.util.ArrayList<T>)values.get(key);
 }
}
""",
    "android/util/Log.java": """
package android.util;
public final class Log {
 public static final int INFO=4;
 public static final int WARN=5;
 public static final int ERROR=6;
 public static int i(String tag,String message){return 0;}
 public static int w(String tag,String message){return 0;}
 public static int w(String tag,String message,Throwable throwable){return 0;}
}
""",
    "io/github/libxposed/api/XposedModule.java": """
package io.github.libxposed.api;
import java.lang.reflect.*;
import java.util.*;
public abstract class XposedModule {
 static final Map<Executable,Hooker> hooks=new LinkedHashMap<>();
 public static final int PRIORITY_HIGHEST=Integer.MAX_VALUE;
 public interface ModuleLoadedParam {
  String getProcessName();
 }
 public interface PackageReadyParam {
  String getPackageName();
  boolean isFirstPackage();
  ClassLoader getClassLoader();
 }
 public interface HotReloadingParam {}
 public interface Hooker {
  Object intercept(Chain chain) throws Throwable;
 }
 public interface HookHandle {
  void unhook();
 }
 public interface HookBuilder {
  HookBuilder setPriority(int priority);
  HookBuilder setExceptionMode(ExceptionMode mode);
  HookBuilder setId(String id);
  HookHandle intercept(Hooker hooker);
 }
 public enum ExceptionMode {DEFAULT,PROTECTIVE,PASSTHROUGH}
 public interface Chain {
  Executable getExecutable();
  Object getThisObject();
  List<Object> getArgs();
  Object getArg(int index);
  Object proceed() throws Throwable;
  Object proceed(Object[] args) throws Throwable;
 }
 public int getApiVersion(){return 102;}
 public static final long PROP_CAP_SYSTEM=1L;
 public static String frameworkName="LSPosed";
 public static long frameworkProperties=1L;
 public static String frameworkFailure="";
 public static int preferenceReads;
 public String getFrameworkName(){
  if("name".equals(frameworkFailure))throw new IllegalStateException("unavailable");
  return frameworkName;
 }
 public long getFrameworkProperties(){
  if("properties".equals(frameworkFailure))throw new IllegalStateException("unavailable");
  if("linkage".equals(frameworkFailure))throw new NoSuchMethodError("unavailable");
  return frameworkProperties;
 }
 public android.content.SharedPreferences getRemotePreferences(String name){
  preferenceReads++;return null;
 }
 public void onModuleLoaded(ModuleLoadedParam param){}
 public void onPackageReady(PackageReadyParam param){}
 public boolean onHotReloading(HotReloadingParam param){return false;}
 public void log(int priority,String tag,String message){}
 public void log(int priority,String tag,String message,Throwable throwable){}
 public HookBuilder hook(Executable origin){
  return new HookBuilder(){
   public HookBuilder setPriority(int priority){return this;}
   public HookBuilder setExceptionMode(ExceptionMode mode){return this;}
   public HookBuilder setId(String id){return this;}
   public HookHandle intercept(Hooker hooker){
    hooks.put(origin,hooker);
    return new HookHandle(){
     public void unhook(){hooks.remove(origin);}
    };
   }
  };
 }
 public static Object call(Object target,String name,Class<?>[] types,Object...args)
   throws Throwable {
  Method method;
  try {
   method=target.getClass().getMethod(name,types);
  }catch(NoSuchMethodException exception){
   method=target.getClass().getDeclaredMethod(name,types);
  }
  Hooker hooker=hooks.get(method);
  if(hooker==null)return invoke(method,target,args);
  return hooker.intercept(new TestChain(method,target,args));
 }
 public static Object invokeHook(Executable origin,Chain chain) throws Throwable {
  Hooker hooker=hooks.get(origin);
  if(hooker==null)throw new AssertionError("Hook not installed: "+origin);
  return hooker.intercept(chain);
 }
 static Object invoke(Method method,Object target,Object[] args) throws Throwable {
  method.setAccessible(true);
  try {
   return method.invoke(target,args);
  }catch(InvocationTargetException exception){
   throw exception.getCause();
  }
 }
 static final class TestChain implements Chain {
  final Method method;
  final Object target;
  final Object[] args;
  TestChain(Method method,Object target,Object[] args){
   this.method=method;this.target=target;this.args=args;
  }
  public Executable getExecutable(){return method;}
  public Object getThisObject(){return target;}
  public List<Object> getArgs(){return Collections.unmodifiableList(Arrays.asList(args));}
  public Object getArg(int index){return args[index];}
  public Object proceed() throws Throwable {return invoke(method,target,args);}
  public Object proceed(Object[] values) throws Throwable {
   return invoke(method,target,values);
  }
 }
}
""",
    "io/github/libxposed/api/FrameworkGateTest.java": """
package io.github.libxposed.api;
import io.github.saycm.huyaplus.HuyaCompatEntry;
public final class FrameworkGateTest {
 public static void main(String[] args){
  XposedModule.frameworkName="null".equals(args[0])?null:args[0];
  XposedModule.frameworkProperties=Long.parseLong(args[1]);
  XposedModule.frameworkFailure=args[2];
  boolean allowed=Boolean.parseBoolean(args[3]);
  final int[] loaderReads={0};
  HuyaCompatEntry entry=new HuyaCompatEntry();
  entry.onModuleLoaded(()->"com.duowan.kiwi");
  entry.onPackageReady(new XposedModule.PackageReadyParam(){
   public String getPackageName(){return "com.duowan.kiwi";}
   public boolean isFirstPackage(){return true;}
   public ClassLoader getClassLoader(){loaderReads[0]++;return getClass().getClassLoader();}
  });
  if(XposedModule.hooks.size()!=(allowed?2:0))
   throw new AssertionError("Unexpected hooks for framework: "+args[0]);
  if(XposedModule.preferenceReads!=(allowed?1:0)||loaderReads[0]!=(allowed?1:0))
   throw new AssertionError("Rejected framework accessed preferences or class loader");
 }
}
""",
    "LoaderLifecycleTest.java": """
import java.io.*;
import java.net.*;
import java.util.*;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
public class LoaderLifecycleTest {
 static final class Recorder extends ClassLoader {
  final List<String> requests=new ArrayList<>();
  public Class<?> loadClass(String name) throws ClassNotFoundException {
   if("android.app.Activity".equals(name))return android.app.Activity.class;
   requests.add(name);
   throw new ClassNotFoundException(name);
  }
 }
 static final class ActivityLoader extends ClassLoader {
  final List<String> requests=new ArrayList<>();
  final boolean currentVersion;
  ActivityLoader(){this(false);}
  ActivityLoader(boolean currentVersion){
   super(LoaderLifecycleTest.class.getClassLoader());
   this.currentVersion=currentVersion;
  }
  public Class<?> loadClass(String name) throws ClassNotFoundException {
   if("LoaderActivity".equals(name)){
    Class<?> loaded=findLoadedClass(name);
    if(loaded!=null)return loaded;
    try(InputStream input=LoaderLifecycleTest.class.getResourceAsStream("/LoaderActivity.class")){
     if(input==null)throw new ClassNotFoundException(name);
     ByteArrayOutputStream output=new ByteArrayOutputStream();
     byte[] buffer=new byte[4096];
     for(int count;(count=input.read(buffer))!=-1;)output.write(buffer,0,count);
     byte[] bytes=output.toByteArray();
     return defineClass(name,bytes,0,bytes.length);
    }catch(IOException exception){
     throw new ClassNotFoundException(name,exception);
    }
   }
   if(name.startsWith("android.")||name.startsWith("java.")||name.startsWith("io.github.libxposed.")){
    return super.loadClass(name);
   }
   requests.add(name);
   if("ryxq.weg".equals(name))return currentVersion?Object.class:super.loadClass(name);
   if(currentVersion&&"ryxq.izb".equals(name))return super.loadClass(name);
   throw new ClassNotFoundException(name);
  }
 }
 static final class Param implements XposedModule.PackageReadyParam {
  final String name;
  final ClassLoader loader;
  Param(String name,ClassLoader loader){this.name=name;this.loader=loader;}
  public String getPackageName(){return name;}
  public boolean isFirstPackage(){return true;}
  public ClassLoader getClassLoader(){return loader;}
 }
 public static void main(String[] args) {
  HuyaCompatEntry entry=new HuyaCompatEntry();
  Recorder other=new Recorder();
  entry.onPackageReady(new Param("com.example.unrelated",other));
  if(!other.requests.isEmpty())
   throw new AssertionError("Unrelated package initialized hooks: "+other.requests);

  Recorder target=new Recorder();
  entry.onPackageReady(new Param("com.duowan.kiwi",target));
  if(!target.requests.isEmpty())
   throw new AssertionError("Package-ready loader initialized business hooks: "+target.requests);

  try{
   boolean currentVersion=args.length>0;
   ActivityLoader activityLoader=new ActivityLoader(currentVersion);
   Object activity=activityLoader.loadClass("LoaderActivity").getDeclaredConstructor().newInstance();
   try{
    XposedModule.invokeHook(
      android.app.Activity.class.getDeclaredMethod("onCreate",android.os.Bundle.class),
      new ActivityChain(activity));
   }catch(Throwable ignored){
    throw new AssertionError(ignored);
   }
   try {
    ryxq.weg guide=currentVersion?new ryxq.izb():new ryxq.weg();
    XposedModule.call(guide,"shouldShowGuideDialog",new Class<?>[]{boolean.class},true);
    if(guide.showGuide)throw new AssertionError("startup guide flag remained enabled");
    if(!Boolean.FALSE.equals(XposedModule.call(guide,"shouldShowGuideDialog",new Class<?>[]{})))
     throw new AssertionError("startup guide remained visible");
    XposedModule.call(guide,"lock",new Class<?>[]{int.class},3);
    if(guide.locks!=1)throw new AssertionError("teenager mode lock was changed");
   }catch(Throwable failure){throw new AssertionError(failure);}
   for(String name:new String[]{
    "com.huya.kiwi.hyext.impl.modules.internal.HyExtAd",
    "com.duowan.kiwi.ad.helper.AmsAdHelper",
    "com.duowan.kiwi.adsplash.view.AdSplashFragment"})
    if(!activityLoader.requests.contains(name))
     throw new AssertionError("Activity loader was not used for "+name);

   int activityCount=activityLoader.requests.size();
   entry.onPackageReady(new Param("com.duowan.kiwi",target));
   if(activityLoader.requests.size()!=activityCount)
    throw new AssertionError("Hooks installed twice for the same Activity loader");
  }catch(ReflectiveOperationException exception){
   throw new AssertionError(exception);
  }
  if(entry.getApiVersion()!=102)
   throw new AssertionError("Expected libxposed API 102");
  if(entry.onHotReloading(null))
   throw new AssertionError("Unimplemented hot reload must be rejected");
  System.out.println("PASS: API 102 activity-loader lifecycle and duplicate guard");
 }
 static final class ActivityChain implements XposedModule.Chain {
  final Object activity;
  ActivityChain(Object activity){this.activity=activity;}
  public java.lang.reflect.Executable getExecutable(){return null;}
  public Object getThisObject(){return activity;}
  public List<Object> getArgs(){return Collections.emptyList();}
  public Object getArg(int index){throw new IndexOutOfBoundsException();}
  public Object proceed(){return null;}
  public Object proceed(Object[] args){return null;}
 }
}
""",
    "RootGateTest.java": """
import android.app.Activity;
import android.content.ContentResolver;
import android.os.Bundle;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;

public final class RootGateTest {
 public static void main(String[] args) throws Throwable {
  ContentResolver.rootStatus=args[0];
  if(args.length>1)android.content.pm.PackageManager.huyaVersion="missing".equals(args[1])?null:args[1];
  boolean supported=args.length==1||"13.5.62".equals(args[1]);
  HuyaCompatEntry entry=new HuyaCompatEntry();
  entry.onPackageReady(new LoaderLifecycleTest.Param("com.duowan.kiwi",new LoaderLifecycleTest.Recorder()));
  ClassLoader loader=new LoaderLifecycleTest.ActivityLoader();
  Object activity=loader.loadClass("LoaderActivity").getDeclaredConstructor().newInstance();
  var onCreate=Activity.class.getDeclaredMethod("onCreate",Bundle.class);
  var chain=new LoaderLifecycleTest.ActivityChain(activity);
  XposedModule.invokeHook(onCreate,chain);
  XposedModule.invokeHook(onCreate,chain);
  if(ContentResolver.rootChecks!=(supported?1:0))
   throw new AssertionError("Check Root only for supported Huya");
  boolean initialized=!((LoaderLifecycleTest.ActivityLoader)loader).requests.isEmpty();
  if(initialized!=(supported&&"granted".equals(args[0])))
   throw new AssertionError("Unexpected business hook state: "+args[0]);
 }
}
""",
    "LoaderActivity.java": """
public final class LoaderActivity extends android.app.Activity {
 public LoaderActivity(){}
}
""",
    "ryxq/weg.java": """
package ryxq;
public class weg {
 public boolean showGuide=true;
 public int locks;
 public void shouldShowGuideDialog(boolean value){showGuide=value;}
 public boolean shouldShowGuideDialog(){return showGuide;}
 public void lock(int type){locks++;}
}
""",
    "ryxq/izb.java": """
package ryxq;
public class izb extends weg {
 @Override public void shouldShowGuideDialog(boolean value){super.shouldShowGuideDialog(value);}
 @Override public boolean shouldShowGuideDialog(){return super.shouldShowGuideDialog();}
 @Override public void lock(int type){super.lock(type);}
}
""",
}


QUALITY_SOURCES = {
    "android/widget/Toast.java": """
package android.widget;
public class Toast {
 public static final int LENGTH_SHORT=0;
 public static final java.util.List<String> shown=new java.util.ArrayList<>();
 private String text;
 public static Toast makeText(android.content.Context context,CharSequence text,int duration){
  Toast toast=new Toast();
  toast.text=text.toString();
  return toast;
 }
 public void show(){shown.add(text);}
 public void cancel(){}
}
""",
    "android/os/Looper.java": """
package android.os;
public class Looper {
 public static Looper getMainLooper(){return new Looper();}
}
""",
    "android/os/Handler.java": """
package android.os;
import java.util.ArrayDeque;
import java.util.Queue;
public class Handler {
 public static final Queue<Runnable> callbacks=new ArrayDeque<>();
 public Handler(Looper looper){}
 public boolean postDelayed(Runnable task,long delay){return callbacks.add(task);}
 public boolean post(Runnable task){return callbacks.add(task);}
}
""",
    "android/util/Pair.java": """
package android.util;
public class Pair<F,S> {
 public final F first;
 public final S second;
 public Pair(F first,S second){this.first=first;this.second=second;}
}
""",
    "DefaultQualityHookTest.java": """
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.util.Pair;
import android.widget.Toast;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
import java.lang.reflect.*;
import java.util.*;

public class DefaultQualityHookTest {
 public static class ChannelPage {
  public void onCreate(Bundle state){}
  public void onNewIntent(Intent intent){}
 }
 public static class NoticePage extends android.app.Activity {
  public void onCreate(Bundle state){}
  public void onNewIntent(Intent intent){}
 }
 public static class StreamPanel {
  int picks;
  public void onClickRateItem(Rate rate){picks++;}
 }
 public static class LineData {
  public void setMultiLineInfo(List<Rate> rates,Runnable duringUpdate,int unused){
   line.rates=rates;
   if(duringUpdate!=null)duringUpdate.run();
  }
 }
 public static class Rate {
  final int bitrate;
  Rate(int bitrate){this.bitrate=bitrate;}
  public int getBitrate(){return bitrate;}
    public String getDisplayName(){return bitrate==0?"蓝光":bitrate==8000?"蓝光 8M":"超清";}
  public int getHEVCBitRate(){return bitrate==8000?7200:0;}
 }
 public static class Line {
  List<Rate> rates;
  public int getLineIndex(){return 1;}
  public List<Rate> getBitrateInfoList(){return rates;}
 }
 public static class MultiLineModule {
  int failures,requests,selected;
  boolean inChannel=true,validLine=true;
  long playId=17,prePlayerId;
  public boolean isInChannel(){return inChannel;}
  public boolean hasValidLine(){return validLine;}
  public long getPlayId(){return playId;}
  public long getPrePlayerId(){return prePlayerId;}
    public int getOriginalBitrate(long playId){return playId==17?3000:0;}
  public int getLineIndex(){return 1;}
  public Pair<List<Line>,List<Line>> getLines(){return new Pair<>(List.of(line),List.of());}
  public void switchLineTo(int lineIndex,int bitrate,boolean manual){
   requests++;
   if(failures>0){failures--;throw new IllegalStateException("temporary failure");}
   selected=bitrate;
  }
 }
 public static class LiveComponent {
  static boolean registered=true;
  public MultiLineModule getMultiLineModule(){
   throw new AssertionError("Quality lookup must not create a line module");
  }
  public MultiLineModule tryGetMultiLineModule(long roomId){
   return registered&&(roomId==0||roomId==17)?module:null;
  }
 }
 public static class PlayerComponent {
  public PlayerModule getLivePlayerModule(){return new PlayerModule();}
 }
 public static class PlayerModule {
  public Player getMultiVideoPlayer(long playId){return playId==17?player:null;}
 }
 public static class Player {
  boolean playing;
  int bitrate=7200;
  public boolean isVideoPlaying(){return playing;}
  public int getCurrentBitrate(){return bitrate;}
 }
 public static class ComponentRegistry {
  public static Object i(Class<?> type){
   return type==PlayerComponent.class?new PlayerComponent():new LiveComponent();
  }
 }
 static final ChannelPage page=new ChannelPage();
 static final LineData data=new LineData();
 static final Line line=new Line();
 static final MultiLineModule module=new MultiLineModule();
 static final Player player=new Player();
 static final List<Rate> target=List.of(new Rate(2000));
 static int preference=2000;

 static void check(boolean value,String message){
  if(!value)throw new AssertionError(message);
 }
 static void enter() throws Throwable{
  XposedModule.call(page,"onNewIntent",new Class<?>[]{Intent.class},(Object)null);
 }
 static void update(List<Rate> rates,Runnable duringUpdate) throws Throwable{
  XposedModule.call(data,"setMultiLineInfo",
   new Class<?>[]{List.class,Runnable.class,int.class},rates,duringUpdate,0);
 }
 static void dispatch(){
  Runnable callback=Handler.callbacks.poll();
  check(callback!=null,"Missing scheduled quality attempt");
  callback.run();
 }
 public static void main(String[] args) throws Throwable{
  HuyaCompatEntry entry=new HuyaCompatEntry();
  Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
  prefs.setAccessible(true);
  prefs.set(entry,Proxy.newProxyInstance(getClassLoader(),new Class<?>[]{SharedPreferences.class},
   (proxy,method,values)->preference));
  Method hook=HuyaCompatEntry.class.getDeclaredMethod("hookDefaultQuality",ClassLoader.class);
  hook.setAccessible(true);
  hook.invoke(entry,new ClassLoader(getClassLoader()){
   public Class<?> loadClass(String name) throws ClassNotFoundException{
    return switch(name){
     case "com.duowan.kiwi.liveroom.ChannelPage" ->
      args[0].startsWith("notice")?NoticePage.class:ChannelPage.class;
     case "com.duowan.kiwi.live.panel.BaseMultiStreamPanel" -> StreamPanel.class;
     case "com.duowan.kiwi.live.multiline.data.MultiLineData" -> LineData.class;
     case "com.duowan.kiwi.live.model.MultiBitrateInfo" -> Rate.class;
     case "com.duowan.kiwi.live.model.ABSLine" -> Line.class;
     case "com.duowan.kiwi.live.api.ILiveComponent" -> LiveComponent.class;
     case "com.duowan.kiwi.live.api.multiline.IMultiLineModule" -> MultiLineModule.class;
     case "com.duowan.kiwi.player.ILivePlayerComponent" -> PlayerComponent.class;
     case "com.duowan.kiwi.player.ILivePlayerModule" -> PlayerModule.class;
     case "com.duowan.kiwi.player.ILivePlayer" -> Player.class;
     case "ryxq.xxe" -> {
      if(args.length>1)throw new ClassNotFoundException(name);
      yield ComponentRegistry.class;
     }
     case "ryxq.fwa" -> {
      if(args.length==1)throw new ClassNotFoundException(name);
      yield ComponentRegistry.class;
     }
     default -> super.loadClass(name);
    };
   }
  });
  if("notice".equals(args[0])){
   preference=-1;
   line.rates=List.of(new Rate(8000),new Rate(2000));
   NoticePage room=new NoticePage();
   XposedModule.call(room,"onCreate",new Class<?>[]{Bundle.class},(Object)null);
   dispatch();
   check(Toast.shown.isEmpty(),"Wait for the player to start");
   XposedModule.call(room,"onNewIntent",new Class<?>[]{Intent.class},(Object)null);
   player.playing=true;
   dispatch();
   check(Toast.shown.isEmpty(),"Discard the previous room's callback");
   dispatch();
   check(Toast.shown.equals(List.of("当前画质：蓝光 8M")),
    "Display the player's active HEVC tier when following Huya");
   update(target,null);
   dispatch();
   check(Handler.callbacks.isEmpty()&&Toast.shown.size()==1,
    "Further line metadata must not repeat the notice");
   return;
  }
    if("notice-original".equals(args[0])){
     preference=-1;
     line.rates=List.of(new Rate(0),new Rate(2000));
     NoticePage room=new NoticePage();
     player.playing=true;
     player.bitrate=3100;
     XposedModule.call(room,"onCreate",new Class<?>[]{Bundle.class},(Object)null);
     dispatch();
     check(Toast.shown.isEmpty(),"An unrecognized bitrate must wait for a match");
     player.bitrate=3000;
     dispatch();
     check(Toast.shown.equals(List.of("当前画质：蓝光")),
      "Show the zero tier using the room's original bitrate");
     player.bitrate=2000;
     XposedModule.call(room,"onNewIntent",new Class<?>[]{Intent.class},(Object)null);
     dispatch();
     check(Toast.shown.equals(List.of("当前画质：蓝光","当前画质：超清")),
      "Show the actual transcoded tier after entering another room");
     return;
    }
  XposedModule.call(page,"onCreate",new Class<?>[]{Bundle.class},(Object)null);
  switch(args[0]){
   case "swipe-ready" -> {
    Field sessionField=HuyaCompatEntry.class.getDeclaredField("qualitySession");
    sessionField.setAccessible(true);
    Object session=sessionField.get(entry);
    Method enterRoom=session.getClass().getDeclaredMethod("enterRoom",long.class);
    enterRoom.setAccessible(true);
    enterRoom.invoke(session,17L);
    LiveComponent.registered=false;
    module.inChannel=false;
    module.validLine=false;
    update(target,null);
    dispatch();
    check(module.requests==0,"Do not switch before Huya registers the room");
    LiveComponent.registered=true;
    dispatch();
    check(module.requests==0,"Do not switch before entering the channel");
    module.inChannel=true;
    dispatch();
    check(module.requests==0,"Do not switch when the room has no valid line");
    module.validLine=true;
    module.playId=0;
    module.prePlayerId=18;
    dispatch();
    check(module.requests==0,"Do not switch the previous room's default player");
    module.prePlayerId=17;
    dispatch();
    check(module.requests==1&&module.selected==2000,"Switch once after Huya promotes the current room");
   }
   case "retry" -> {
    update(List.of(),null);
    dispatch();
    update(List.of(new Rate(500)),null);
    dispatch();
    check(module.requests==0,"Do not switch to an unavailable bitrate");
    check(!Handler.callbacks.isEmpty(),"Unavailable target must remain eligible for retry");
    line.rates=target;
    dispatch();
    check(module.requests==1&&module.selected==2000,"Apply the target once it becomes available");
   }
   case "switch-error" -> {
    module.failures=1;
    update(target,null);
    dispatch();
    dispatch();
    check(module.requests==2&&module.selected==2000,"Retry a failed switch and apply the target");
    update(target,null);
    check(Handler.callbacks.isEmpty(),"Do not switch again once successful");
   }
   case "bounded" -> {
    update(List.of(),null);
    for(int attempt=0;attempt<5;attempt++)dispatch();
    check(Handler.callbacks.isEmpty(),"Stop retries after five attempts");
    update(target,null);
    check(Handler.callbacks.isEmpty(),"Metadata updates cannot reset the room's retry budget");
    enter();
    update(target,null);
    dispatch();
    check(module.requests==1,"A new room receives a fresh retry budget");
   }
   case "stale" -> {
    update(target,()->{
     try{enter();}catch(Throwable failure){throw new AssertionError(failure);}
    });
    check(Handler.callbacks.isEmpty(),"An update overtaken by room entry cannot schedule a switch");
    update(target,null);
    enter();
    update(target,null);
    dispatch();
    check(module.requests==0,"A scheduled callback cannot switch a different room");
    dispatch();
    check(module.requests==1,"The current room retains its scheduled attempt");
   }
   case "manual" -> {
    update(target,null);
    StreamPanel panel=new StreamPanel();
    XposedModule.call(panel,"onClickRateItem",new Class<?>[]{Rate.class},new Rate(500));
    dispatch();
    update(target,null);
    check(panel.picks==1&&module.requests==0&&Handler.callbacks.isEmpty(),
     "Manual selection takes precedence over pending and later automatic attempts");
   }
   case "follow" -> {
    preference=-1;
    for(int update=0;update<5;update++){
     update(target,null);
     dispatch();
    }
    check(module.requests==0,"Following Huya leaves the bitrate to Huya");
    preference=2000;
    update(target,null);
    dispatch();
    check(module.requests==1,"Following Huya does not spend the room's retry budget");
   }
   default -> throw new AssertionError(args[0]);
  }
 }
 static ClassLoader getClassLoader(){return DefaultQualityHookTest.class.getClassLoader();}
}
""",
}


QUALITY_SOURCES["RootGateTest.java"] = SOURCES.pop("RootGateTest.java")

for automation_class in ("DailyAutomation", "TaskLogProvider", "RootAccess", "AutomationRules", "LocalTaskStore",
                         "NativeTaskAutomation", "NativeTaskRunner", "NativeTaskCatalog", "TaskWire", "HuyaTaskClient",
                         "DiceTaskRunner", "DiceTaskCatalog", "DiceMissionRunner", "WelfareSignRunner",
                         "HuyaComponents", "HuyaVersion"):
    automation_path = f"io/github/saycm/huyaplus/{automation_class}.java"
    SOURCES[automation_path] = (ROOT / "tools/huya-compat-src" / automation_path).read_text(encoding="utf-8")
SOURCES["io/github/saycm/huyaplus/LiveQuality.java"] = (
    ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/LiveQuality.java"
).read_text(encoding="utf-8")
SOURCES["io/github/saycm/huyaplus/QualitySession.java"] = (
    ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/QualitySession.java"
).read_text(encoding="utf-8")


class HuyaLoaderLifecycleTest(unittest.TestCase):
    def test_first_activity_uses_its_dynamic_loader_once(self):
        with tempfile.TemporaryDirectory(prefix="huya-loader-") as folder:
            root = Path(folder)
            sources = []
            for name, content in {**SOURCES, **QUALITY_SOURCES}.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
                sources.append(str(file))
            sources.append(
                str(
                    ROOT
                    / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java"
                )
            )
            sources.append(
                str(
                    ROOT
                    / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettings.java"
                )
            )
            android = SDK / "platforms/android-36/android.jar"
            compile_result = subprocess.run(
                [
                    str(JDK / "bin" / ("javac" + EXE)),
                    "-encoding",
                    "UTF-8",
                    "-cp",
                    str(android),
                    "-d",
                    str(root / "classes"),
                    *sources,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                compile_result.returncode,
                0,
                compile_result.stdout + compile_result.stderr,
            )
            result = subprocess.run(
                [
                    str(JDK / "bin" / ("java" + EXE)),
                    "-cp",
                    os.pathsep.join([str(root / "classes"), str(android)]),
                    "LoaderLifecycleTest",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())
            result = subprocess.run(
                [
                    str(JDK / "bin" / ("java" + EXE)),
                    "-cp",
                    os.pathsep.join([str(root / "classes"), str(android)]),
                    "LoaderLifecycleTest", "13.5.62",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            root_cases = [(status, "13.5.62") for status in ("granted", "denied", "missing", "unavailable")]
            root_cases += [("granted", version) for version in ("13.5.44", "13.5.61", "13.5.63", "missing")]
            for status, version in root_cases:
                with self.subTest(root=status, version=version):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-cp",
                         os.pathsep.join([str(root / "classes"), str(android)]),
                         "RootGateTest", status, version],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            cases = [
                ("LSPosed", 1, "", True),
                ("LSPosed", 7, "", True),
                ("LSPosed", 0, "", False),
                ("LSPosed", 2, "", False),
                ("FPA", 1, "", False),
                ("LSPatch", 1, "", False),
                ("NPatch", 1, "", False),
                ("LSPosedFake", 1, "", False),
                ("null", 1, "", False),
                ("", 1, "", False),
                ("LSPosed", 1, "name", False),
                ("LSPosed", 1, "properties", False),
                ("LSPosed", 1, "linkage", False),
            ]
            for name, properties, failure, allowed in cases:
                with self.subTest(framework=name, properties=properties, failure=failure):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-cp",
                         os.pathsep.join([str(root / "classes"), str(android)]),
                         "io.github.libxposed.api.FrameworkGateTest", name,
                         str(properties), failure, str(allowed).lower()],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            quality_cases = [(case,) for case in (
                "retry", "switch-error", "bounded", "stale", "manual", "follow",
                "notice", "notice-original", "swipe-ready")]
            quality_cases += [("retry", "13.5.62"), ("notice-original", "13.5.62")]
            for case in quality_cases:
                with self.subTest(quality=case):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-cp",
                         os.pathsep.join([str(root / "classes"), str(android)]),
                         "DefaultQualityHookTest", *case],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
