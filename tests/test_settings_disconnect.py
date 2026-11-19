import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SettingsDisconnectTest(unittest.TestCase):
    def test_death_invalidates_cached_preferences_and_notifies_view(self):
        sources = {
            "android/content/SharedPreferences.java":
                "package android.content; public interface SharedPreferences {}",
            "android/util/Log.java":
                "package android.util; public class Log { public static int w(String a,String b,Throwable t){return 0;} }",
            "io/github/libxposed/service/XposedService.java": """
package io.github.libxposed.service;
public class XposedService {
 public android.content.SharedPreferences getRemotePreferences(String n) {
  return new android.content.SharedPreferences(){};
 }
}""",
            "io/github/libxposed/service/XposedServiceHelper.java": """
package io.github.libxposed.service;
public class XposedServiceHelper {
 public interface OnServiceListener {
  void onServiceBind(XposedService service); void onServiceDied(XposedService service);
 }
 public static OnServiceListener listener;
 public static void registerListener(OnServiceListener l){listener=l;}
}""",
            "io/github/saycm/huyaplus/DisconnectTest.java": """
package io.github.saycm.huyaplus;
import io.github.libxposed.service.*;
public class DisconnectTest {
 public static void main(String[] args){
  int[] bound={0},lost={0};
  GlassSettingsBridge.connect(p->{if(p==null)lost[0]++;else bound[0]++;});
  XposedService first=new XposedService();
  XposedServiceHelper.listener.onServiceBind(first);
  XposedServiceHelper.listener.onServiceDied(first);
  if(GlassSettingsBridge.get()!=null)throw new AssertionError("dead service cached");
  if(lost[0]!=1)throw new AssertionError("view not notified");
  GlassSettingsBridge.connect(p->{if(p!=null)bound[0]++;});
  if(bound[0]!=1)throw new AssertionError("stale connection delivered");
  XposedService second=new XposedService();
  XposedServiceHelper.listener.onServiceBind(second);
  XposedServiceHelper.listener.onServiceDied(first);
  if(GlassSettingsBridge.get()==null)throw new AssertionError("old death cleared new service");
 }
}""",
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "build/test-tmp") as temp:
            folder = Path(temp)
            files = []
            for name, text in sources.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                files.append(str(path))
            package = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
            files += [str(package / (name + ".java")) for name in ("GlassSettings", "GlassSettingsBridge")]
            java = Path(os.environ["JAVA_HOME"]) / "bin"
            compiled = subprocess.run([str(java / "javac.exe"), "-encoding", "UTF-8",
                                       "-d", str(folder), *files], capture_output=True, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(java / "java.exe"), "-cp", str(folder),
                                     "io.github.saycm.huyaplus.DisconnectTest"],
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
