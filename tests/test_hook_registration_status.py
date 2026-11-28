"""Check that feature status comes from successful framework registrations."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, SDK, JDK, SOURCES


class HookRegistrationStatusTests(unittest.TestCase):
    def test_registered_partial_disabled_and_failed_are_based_on_actual_hooks(self):
        sources = dict(SOURCES)
        sources.pop("LoaderLifecycleTest.java")
        sources.pop("LoaderActivity.java")
        for package, name in (("com.duowan.kiwi.listframe.adapter", "ListLineRecyclerViewAdapter"),
                              ("com.duowan.kiwi.listframe.adapter", "HeaderFooterListLineAdapter"),
                              ("com.duowan.kiwi.listline", "ListLineAdapter")):
            sources[package.replace(".", "/") + "/" + name + ".java"] = (
                "package " + package + "; public class " + name + " {}")
        sources["io/github/saycm/huyaplus/HookStatus.java"] = """
package io.github.saycm.huyaplus;
import java.util.*;
public final class HookStatus {
 public static final String REGISTERED="registered",PARTIAL="partial",DISABLED="disabled",WAITING="waiting",FAILED="failed";
 public static final Map<String,String> states=new HashMap<>(),reasons=new HashMap<>();
 public static void start(android.content.Context context,String process){}
 public static boolean validState(String state){return true;}
 public static void record(String feature,String state,String reason){states.put(feature,state);reasons.put(feature,reason);}
}
"""
        sources["HookRegistrationTest.java"] = """
import java.lang.reflect.*;
import io.github.saycm.huyaplus.*;
public final class HookRegistrationTest {
 public static void sample(){}
 public static void main(String[] args)throws Exception{
  HuyaCompatEntry entry=new HuyaCompatEntry();
  Method tracked=HuyaCompatEntry.class.getDeclaredMethod("trackedHook",Executable.class);
  tracked.setAccessible(true);
  Method find=HuyaCompatEntry.class.getDeclaredMethod("findMethod",Class.class,String.class,int.class);
  find.setAccessible(true);
  Method lists=HuyaCompatEntry.class.getDeclaredMethod("hookListAds",ClassLoader.class);
  lists.setAccessible(true);
  Method register=HuyaCompatEntry.class.getDeclaredMethod("registerFeature",String.class,boolean.class,Runnable.class);
  register.setAccessible(true);
  int[] calls={0};
  Runnable install=()->{
   calls[0]++;
   if(args[0].equals("failed"))throw new IllegalStateException("installation failed");
   if(args[0].equals("missing"))return;
   try{
    if(args[0].equals("missing-interface"))find.invoke(entry,HookRegistrationTest.class,"sampleMissing",0);
    if(args[0].equals("missing-mutations"))lists.invoke(entry,entry.getClass().getClassLoader());
    var builder=(io.github.libxposed.api.XposedModule.HookBuilder)tracked.invoke(
     entry,HookRegistrationTest.class.getMethod("sample"));
    builder.intercept(chain->chain.proceed());
   }catch(ReflectiveOperationException failure){throw new RuntimeException(failure);}
   if(args[0].equals("partial"))throw new IllegalStateException("another interface unavailable");
  };
  register.invoke(entry,"example",!args[0].equals("disabled"),install);
  String expected=args[0].equals("missing")?"failed":args[0].startsWith("missing-")?"partial":args[0];
  if(!expected.equals(HookStatus.states.get("example")))throw new AssertionError(
   "Expected "+expected+" from actual hook registrations, got "+HookStatus.states);
  if(args[0].equals("disabled")&&calls[0]!=0)throw new AssertionError("Disabled group was installed");
  if(HookStatus.reasons.getOrDefault("example","").isEmpty())
   throw new AssertionError("Missing registration diagnostic");
  if(args[0].equals("registered")&&!HookStatus.reasons.get("example").contains("1"))
   throw new AssertionError("Missing successful registration count");
  if(args[0].equals("missing-interface")&&!HookStatus.reasons.get("example").contains("sampleMissing"))
   throw new AssertionError("Missing unmatched interface diagnostic");
  if(args[0].equals("missing-mutations")&&!HookStatus.reasons.get("example").contains("ListLineAdapter"))
   throw new AssertionError("Missing unmatched adapter diagnostic");
 }
}
"""
        with tempfile.TemporaryDirectory(dir=ROOT / "build/test-tmp") as directory:
            folder = Path(directory)
            paths = []
            for name, content in sources.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                paths.append(str(path))
            paths.extend(str(ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus" / (name + ".java"))
                         for name in ("HuyaCompatEntry", "GlassSettings"))
            classpath = os.pathsep.join((str(folder), str(SDK / "platforms/android-36/android.jar")))
            compile_result = subprocess.run([str(JDK / "bin/javac.exe"), "-encoding", "UTF-8",
                "-cp", classpath, "-d", str(folder), *paths], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            for case in ("registered", "partial", "disabled", "failed", "missing", "missing-interface", "missing-mutations"):
                with self.subTest(case=case):
                    result = subprocess.run([str(JDK / "bin/java.exe"),
                        "-cp", classpath,
                        "HookRegistrationTest", case], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
