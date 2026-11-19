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
  ActivityLoader(){super(LoaderLifecycleTest.class.getClassLoader());}
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
   if("ryxq.weg".equals(name))return super.loadClass(name);
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
   ActivityLoader activityLoader=new ActivityLoader();
   Object activity=activityLoader.loadClass("LoaderActivity").getDeclaredConstructor().newInstance();
   try{
    XposedModule.invokeHook(
      android.app.Activity.class.getDeclaredMethod("onCreate",android.os.Bundle.class),
      new ActivityChain(activity));
   }catch(Throwable ignored){
    throw new AssertionError(ignored);
   }
   try {
    ryxq.weg guide=new ryxq.weg();
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
    "LoaderActivity.java": """
public final class LoaderActivity {
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
}


for automation_class in ("DailyAutomation", "TaskLogProvider", "AutomationRules", "LocalTaskStore",
                         "NativeTaskAutomation", "NativeTaskRunner", "NativeTaskCatalog", "TaskWire", "HuyaTaskClient",
                         "DiceTaskRunner", "DiceTaskCatalog", "DiceMissionRunner", "WelfareSignRunner"):
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
            for name, content in SOURCES.items():
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


if __name__ == "__main__":
    unittest.main()
