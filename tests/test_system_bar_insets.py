"""Check system-bar padding at the fixed content container, outside scrolling."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"


class SystemBarInsetsTest(unittest.TestCase):
    def test_all_module_pages_apply_insets_to_the_content_container(self):
        for name in ("GlassDashboardActivity", "AppDetailActivity", "TaskLogActivity", "TaskSettingsActivity"):
            with self.subTest(page=name):
                source = (SOURCE / f"{name}.java").read_text(encoding="utf-8")
                self.assertIn("SystemBarInsets.apply(findViewById(android.R.id.content));", source)

    def test_padding_tracks_insets_without_accumulating_or_changing_base_spacing(self):
        helper = SOURCE / "SystemBarInsets.java"
        self.assertTrue(helper.is_file(), "system-bar inset handling is missing")
        stubs = {
            "android/os/Build.java": """package android.os;
public class Build {public static class VERSION {public static int SDK_INT=36;}}""",
            "android/graphics/Insets.java": """package android.graphics;
public class Insets {public final int left,top,right,bottom;
 public Insets(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}}""",
            "android/view/WindowInsets.java": """package android.view;
import android.graphics.Insets;
public class WindowInsets {
 private final Insets bars,cutout;
 public WindowInsets(Insets b,Insets c){bars=b;cutout=c;}
 public static class Type {public static int systemBars(){return 1;}public static int displayCutout(){return 2;}}
 public Insets getInsets(int mask){
  if(mask!=3)throw new AssertionError("status/navigation bars and cutout must both be included");
  return new Insets(Math.max(bars.left,cutout.left),Math.max(bars.top,cutout.top),
   Math.max(bars.right,cutout.right),Math.max(bars.bottom,cutout.bottom));}
 public int getSystemWindowInsetLeft(){return bars.left;}
 public int getSystemWindowInsetTop(){return bars.top;}
 public int getSystemWindowInsetRight(){return bars.right;}
 public int getSystemWindowInsetBottom(){return bars.bottom;}
}""",
            "android/view/View.java": """package android.view;
public class View {
 public interface OnApplyWindowInsetsListener {WindowInsets onApplyWindowInsets(View v,WindowInsets i);}
 private OnApplyWindowInsetsListener listener;private int left,top,right,bottom;
 public boolean requested;
 public int getPaddingLeft(){return left;}public int getPaddingTop(){return top;}
 public int getPaddingRight(){return right;}public int getPaddingBottom(){return bottom;}
 public void setPadding(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}
 public void setOnApplyWindowInsetsListener(OnApplyWindowInsetsListener l){listener=l;}
 public void requestApplyInsets(){requested=true;}
 public WindowInsets dispatch(WindowInsets i){return listener.onApplyWindowInsets(this,i);}
}""",
            "io/github/saycm/huyaplus/InsetsTest.java": """package io.github.saycm.huyaplus;
import android.view.*;import android.graphics.Insets;import android.os.Build;
public class InsetsTest {
 static void check(View v,int l,int t,int r,int b){
  if(v.getPaddingLeft()!=l||v.getPaddingTop()!=t||v.getPaddingRight()!=r||v.getPaddingBottom()!=b)
   throw new AssertionError("wrong safe-area padding: "+v.getPaddingTop());}
 public static void main(String[] args){
  View content=new View();content.setPadding(3,5,7,9);SystemBarInsets.apply(content);
  if(!content.requested)throw new AssertionError("initial insets not requested");
  WindowInsets portrait=new WindowInsets(new Insets(0,24,0,48),new Insets(0,32,0,0));
  if(content.dispatch(portrait)!=portrait)throw new AssertionError("insets unexpectedly consumed");
  check(content,3,37,7,57);content.dispatch(portrait);check(content,3,37,7,57);
  content.dispatch(new WindowInsets(new Insets(0,24,20,0),new Insets(40,0,0,0)));
  check(content,43,29,27,9);
  content.dispatch(new WindowInsets(new Insets(0,0,0,0),new Insets(0,0,0,0)));
  check(content,3,5,7,9);
  Build.VERSION.SDK_INT=29;content.dispatch(portrait);check(content,3,29,7,57);
 }
}""",
        }
        with tempfile.TemporaryDirectory(prefix="bar-insets-") as folder:
            directory = Path(folder)
            sources = [str(helper)]
            for name, text in stubs.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                sources.append(str(path))
            jdk = Path(os.environ["JAVA_HOME"]) / "bin"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            suffix = ".exe" if os.name == "nt" else ""
            compile_result = subprocess.run(
                [str(jdk / f"javac{suffix}"), "-encoding", "UTF-8", "-d", folder, *sources],
                capture_output=True, creationflags=flags,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr.decode(errors="replace"))
            result = subprocess.run(
                [str(jdk / f"java{suffix}"), "-cp", folder, "io.github.saycm.huyaplus.InsetsTest"],
                capture_output=True, creationflags=flags,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
