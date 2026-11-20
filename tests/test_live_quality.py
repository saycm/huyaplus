"""Verify the configurable default live quality without changing stream metadata."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JDK = Path(os.environ["JAVA_HOME"])
EXE = ".exe" if os.name == "nt" else ""
PACKAGE = "io/github/saycm/huyaplus"


class LiveQualityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="huya-quality-")
        cls.root = Path(cls.folder.name)
        test_source = cls.root / PACKAGE / "LiveQualityTest.java"
        test_source.parent.mkdir(parents=True)
        test_source.write_text(
            """package io.github.saycm.huyaplus;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
public final class LiveQualityTest {
 static void check(int actual,int expected,String message){
  if(actual!=expected)throw new AssertionError(message+": "+actual);
 }
 public static void main(String[] args){
  check(LiveQuality.select(-1,2000,new HashSet<Integer>()),
   2000,"Following Huya must preserve the saved bitrate");
  check(LiveQuality.select(4000,2000,
   new HashSet<Integer>(Arrays.asList(500,2000))),
   2000,"An unavailable quality must fall back to Huya");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,3000,
   new HashSet<Integer>(Arrays.asList(0,8000,4000,2000,500))),
   8000,"Blue-ray must resolve to a playable positive bitrate");
  check(LiveQuality.select(0,3000,
   new HashSet<Integer>(Arrays.asList(0,8000,4000,2000,500))),
   8000,"The previous zero preference must migrate to positive Blue-ray");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,3000,
   new HashSet<Integer>(Arrays.asList(0,2000,500))),
   3000,"Rooms without a playable Blue-ray rate must keep Huya behavior");
  Map<Integer,String> varied = new LinkedHashMap<>();
  varied.put(0,"蓝光30M");
  varied.put(8000,"蓝光20M");
  varied.put(6000,"蓝光10M");
  varied.put(2000,"超清");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,2000,varied),
   0,"Blue-ray 30M must win even though its stream id is zero");
  Map<Integer,String> noSpace = new LinkedHashMap<>();
  noSpace.put(0,"蓝光30M");
  noSpace.put(8000,"蓝光20M");
  noSpace.put(6000,"蓝光10");
  noSpace.put(2000,"超清");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,2000,noSpace),
   0,"Blue-ray tier labels may omit the M suffix");
  Map<Integer,String> tiers = new LinkedHashMap<>();
  tiers.put(5000,"蓝光10M");
  tiers.put(3000,"蓝光6M");
  tiers.put(2000,"超清");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,2000,tiers),
   5000,"Blue-ray must follow each room's actual tier list");
  Map<Integer,String> onlyZeroBlueRay = new LinkedHashMap<>();
  onlyZeroBlueRay.put(0,"蓝光20M");
  onlyZeroBlueRay.put(2000,"超清");
  onlyZeroBlueRay.put(500,"流畅");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,2000,onlyZeroBlueRay),
   0,"A room with only Blue-ray 20M must not fall back to Super HD");
  Map<Integer,String> noBlueRay = new LinkedHashMap<>();
  noBlueRay.put(20000,"4K");
  noBlueRay.put(2000,"超清");
  check(LiveQuality.select(LiveQuality.BLUE_RAY,2000,noBlueRay),
   2000,"A room without Blue-ray must retain Huya's quality");
 }
}
""",
            encoding="utf-8",
        )
        classes = cls.root / "classes"
        classes.mkdir()
        result = subprocess.run(
            [
                str(JDK / "bin" / ("javac" + EXE)),
                "-encoding",
                "UTF-8",
                "-d",
                str(classes),
                str(ROOT / "tools/huya-compat-src" / PACKAGE / "LiveQuality.java"),
                str(test_source),
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            cls.folder.cleanup()
            raise RuntimeError(result.stdout + result.stderr)
        cls.classes = classes

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_quality_selection_preserves_original_behavior_and_supports_zero(self):
        result = subprocess.run(
            [
                str(JDK / "bin" / ("java" + EXE)),
                "-cp",
                str(self.classes),
                "io.github.saycm.huyaplus.LiveQualityTest",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_detail_page_and_runtime_hook_are_wired(self):
        layout = (
            ROOT / "tools/huya-module-src/res/layout/activity_app_detail.xml"
        ).read_text(encoding="utf-8")
        strings = (
            ROOT / "tools/huya-module-src/res/values/strings.xml"
        ).read_text(encoding="utf-8")
        activity = (
            ROOT
            / "tools/huya-compat-src"
            / PACKAGE
            / "AppDetailActivity.java"
        ).read_text(encoding="utf-8")
        entry = (
            ROOT
            / "tools/huya-compat-src"
            / PACKAGE
            / "HuyaCompatEntry.java"
        ).read_text(encoding="utf-8")
        settings = (
            ROOT
            / "tools/huya-compat-src"
            / PACKAGE
            / "GlassSettings.java"
        ).read_text(encoding="utf-8")

        self.assertIn('@+id/quality_card', layout)
        self.assertIn('@+id/action_default_quality', layout)
        self.assertIn('name="quality_follow"', strings)
        self.assertIn('name="quality_smooth"', strings)
        self.assertIn('name="quality_super"', strings)
        self.assertIn('name="quality_bluray"', strings)
        self.assertIn("KEY_LIVE_QUALITY", settings)
        self.assertIn("showQualityDialog", activity)
        self.assertIn("GlassSettings.KEY_LIVE_QUALITY", activity)
        self.assertIn("hookDefaultQuality", entry)
        self.assertIn("GlassSettings.KEY_LIVE_QUALITY", entry)
        self.assertIn("getDisplayName", entry)
        self.assertIn("LinkedHashMap", entry)
        self.assertIn("BasePortraitMultiStreamPanel", entry)
        self.assertIn("ILiveComponent", entry)
        self.assertIn("tryGetMultiLineModule", entry)
        self.assertIn("getLineIndex", entry)
        self.assertIn("switchLineTo", entry)
        self.assertIn("LiveQuality.select", entry)
        self.assertIn("preferred == LiveQuality.FOLLOW", entry)
        self.assertNotIn("preferred < 0", entry)
        self.assertIn("ChannelPage", entry)


if __name__ == "__main__":
    unittest.main()
