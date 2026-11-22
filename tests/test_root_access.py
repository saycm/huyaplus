"""Verify startup reads saved Root authorization without launching su."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_huya_loader_lifecycle import EXE, JDK, ROOT


class RootAccessTest(unittest.TestCase):
    def test_startup_uses_saved_authorization_after_reopening(self):
        package = "io/github/saycm/huyaplus"
        sources = {
            "android/content/Context.java": """
package android.content;
public class Context {
 public static final int MODE_PRIVATE=0;
 private final SharedPreferences settings;
 public Context(SharedPreferences settings){this.settings=settings;}
 public SharedPreferences getSharedPreferences(String name,int mode){return settings;}
}
""",
            "android/content/SharedPreferences.java": """
package android.content;
public interface SharedPreferences {
 boolean getBoolean(String key,boolean fallback);
 Editor edit();
 interface Editor {
  Editor putBoolean(String key,boolean value);
  Editor remove(String key);
  boolean commit();
  void apply();
 }
}
""",
            f"{package}/RootAccessTest.java": """
package io.github.saycm.huyaplus;
import android.content.Context;
import android.content.SharedPreferences;
public class RootAccessTest {
 static Context reopen(boolean granted){
  return new Context(new SharedPreferences(){
   public boolean getBoolean(String key,boolean fallback){
    return "root_granted".equals(key)?granted:fallback;
   }
   public Editor edit(){throw new AssertionError("Startup must not modify saved authorization");}
  });
 }
 public static void main(String[] args){
  if(RootAccess.verify(reopen(false)))throw new AssertionError("First startup requires authorization");
  for(int i=0;i<2;i++)
   if(!RootAccess.verify(reopen(true)))throw new AssertionError("Saved grant lost on cold startup");
  final boolean[] saved = {false};
  SharedPreferences remote = new SharedPreferences(){
   public boolean getBoolean(String key,boolean fallback){return saved[0];}
   public Editor edit(){return new Editor(){
    private boolean pending;
    public Editor putBoolean(String key,boolean value){
     if(!"root_granted".equals(key))throw new AssertionError(key);
     pending=value;
     return this;
    }
    public Editor remove(String key){throw new AssertionError(key);}
    public boolean commit(){saved[0]=pending;return true;}
    public void apply(){throw new AssertionError("Authorization must be persisted before startup");}
   };}
  };
  if(!RootAccess.syncTo(reopen(true),remote)||!saved[0])
   throw new AssertionError("Existing authorization must migrate to LSPosed");
  if(!RootAccess.syncTo(reopen(false),remote)||saved[0])
   throw new AssertionError("No saved grant must disable LSPosed authorization");
 }
}
""",
        }
        with tempfile.TemporaryDirectory(prefix="huya-root-") as folder:
            root = Path(folder)
            for name, content in sources.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
            app = ROOT / "tools/huya-compat-src" / package
            compiled = subprocess.run(
                [str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8", "-d", str(root),
                 *(str(root / name) for name in sources),
                 str(app / "RootAccess.java"), str(app / "GlassSettings.java")],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(JDK / "bin" / ("java" + EXE)), "-cp", str(root),
                 "io.github.saycm.huyaplus.RootAccessTest"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
