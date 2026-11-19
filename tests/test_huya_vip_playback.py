"""Exercise VIP ad filtering and the local 4K playback branch."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_display_ads import DISPLAY_SOURCES
from test_huya_loader_lifecycle import JDK, ROOT, SDK


VIP_SOURCES = dict(DISPLAY_SOURCES)
VIP_SOURCES.update({
    "com/duowan/HUYA/LiveRoomPopupWindowSummary.java": """
package com.duowan.HUYA;
public class LiveRoomPopupWindowSummary {
 public int iIsNoShowForPlatformVip;
}
""",
    "com/duowan/kiwi/popup/api/PopupItem.java": """
package com.duowan.kiwi.popup.api;
import com.duowan.HUYA.LiveRoomPopupWindowSummary;
public class PopupItem {
 public LiveRoomPopupWindowSummary summary=new LiveRoomPopupWindowSummary();
 public String getBusinessKey(){return "manual";}
 public LiveRoomPopupWindowSummary getSummary(){return summary;}
}
""",
    "com/duowan/kiwi/popup/impl/pubscreen/PopupStrategyConditionHelper.java": """
package com.duowan.kiwi.popup.impl.pubscreen;
import com.duowan.kiwi.popup.api.PopupItem;
public class PopupStrategyConditionHelper {
 public int checks;
 public boolean checkPlatformVipFilter(PopupItem item){
  checks++;
  if(item==null)throw new IllegalArgumentException("popupItem");
  return true;
 }
}
""",
    "com/duowan/kiwi/platformvip/impl/PlatformVIPModule.java": """
package com.duowan.kiwi.platformvip.impl;
public class PlatformVIPModule {
 public boolean isActive(){return false;}
 public boolean isActiveInLiveRoom(){return false;}
}
""",
    "com/duowan/kiwi/live/model/MultiBitrateInfo.java": """
package com.duowan.kiwi.live.model;
public class MultiBitrateInfo {
 public int bitrate;
 public int iEnable=0;
 public int iEnableMethod=5;
 public long lTrialViewTime;
 public MultiBitrateInfo(int bitrate){this.bitrate=bitrate;}
}
""",
    "com/duowan/kiwi/live/vip4k/Vip4KPlayHelper.java": """
package com.duowan.kiwi.live.vip4k;
import com.duowan.kiwi.live.model.MultiBitrateInfo;
import io.github.libxposed.api.XposedModule;
public class Vip4KPlayHelper {
 public boolean loggedIn=true;
 public int loginPanels,trialTimers,vipWaits;
 public boolean vipEnterPending;
 public boolean isPlatformVipActive(){return false;}
 public boolean handleVip4KClick(MultiBitrateInfo rateItem)throws Throwable {
  if(rateItem==null)throw new IllegalArgumentException("rateItem");
  if(!loggedIn){loginPanels++;return true;}
  boolean vip=(Boolean)XposedModule.call(this,"isPlatformVipActive",new Class<?>[0]);
  if(vip){vipWaits++;vipEnterPending=true;return false;}
  if(rateItem.lTrialViewTime<=0)return true;
  trialTimers++;return false;
 }
}
""",
    "VipPlaybackTest.java": """
import java.lang.reflect.*;
import com.duowan.kiwi.live.model.MultiBitrateInfo;
import com.duowan.kiwi.live.vip4k.Vip4KPlayHelper;
import com.duowan.kiwi.platformvip.impl.PlatformVIPModule;
import com.duowan.kiwi.popup.api.PopupItem;
import com.duowan.kiwi.popup.impl.pubscreen.PopupStrategyConditionHelper;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
public class VipPlaybackTest {
 static void check(boolean value,String message){
  if(!value)throw new AssertionError(message);
 }
 static Object call(Object target,String name,Class<?>[] types,Object... args)throws Throwable {
  return XposedModule.call(target,name,types,args);
 }
 public static void main(String[] args)throws Throwable {
  ClassLoader loader=VipPlaybackTest.class.getClassLoader();
  if(args[0].equals("missing-4k")){
   loader=new ClassLoader(loader){
    public Class<?> loadClass(String name)throws ClassNotFoundException {
     if(name.equals("com.duowan.kiwi.live.vip4k.Vip4KPlayHelper"))
      throw new ClassNotFoundException(name);
     return super.loadClass(name);
    }
   };
  }
  Method init=HuyaCompatEntry.class.getDeclaredMethod("initializeHooks",ClassLoader.class);
  init.setAccessible(true);init.invoke(new HuyaCompatEntry(),loader);
  if(args[0].equals("vip-ads")||args[0].equals("missing-4k")){
   PopupStrategyConditionHelper helper=new PopupStrategyConditionHelper();
   PopupItem item=new PopupItem();item.summary.iIsNoShowForPlatformVip=1;
   check(Boolean.FALSE.equals(call(helper,"checkPlatformVipFilter",
    new Class<?>[]{PopupItem.class},item)),
    "VIP-exempt advertisements must be rejected for a non-member");
   check(helper.checks==0,"Reject the advertisement before the original display filter");
   check(item.summary.iIsNoShowForPlatformVip==1,"Do not alter the server's popup data");
  }else if(args[0].equals("ordinary-popups")){
   PopupStrategyConditionHelper helper=new PopupStrategyConditionHelper();
   for(int flag:new int[]{0,2,-1}){
    PopupItem item=new PopupItem();item.summary.iIsNoShowForPlatformVip=flag;
    check(Boolean.TRUE.equals(call(helper,"checkPlatformVipFilter",
     new Class<?>[]{PopupItem.class},item)),"Unknown flags must use the original filter");
   }
   PopupItem item=new PopupItem();item.summary=null;
   check(Boolean.TRUE.equals(call(helper,"checkPlatformVipFilter",
    new Class<?>[]{PopupItem.class},item)),"Missing summary must retain original handling");
   boolean threw=false;
   try{call(helper,"checkPlatformVipFilter",new Class<?>[]{PopupItem.class},new Object[]{null});}
   catch(Throwable expected){threw=true;}
   check(threw&&helper.checks==5,"Null input must reach the original validation");
  }else if(args[0].equals("4k")){
   Vip4KPlayHelper helper=new Vip4KPlayHelper();
   for(long seconds:new long[]{0,30}){
    MultiBitrateInfo item=new MultiBitrateInfo(20000);item.lTrialViewTime=seconds;
    check(Boolean.FALSE.equals(call(helper,"handleVip4KClick",
     new Class<?>[]{MultiBitrateInfo.class},item)),
     "An existing 4K stream must remain selectable with no trial allowance");
    check(helper.vipEnterPending,"The member branch must wait for the actual stream switch");
    check(item.iEnable==0&&item.iEnableMethod==5&&item.lTrialViewTime==seconds,
     "Do not rewrite stream metadata or trial allowance");
   }
   check(helper.vipWaits==2&&helper.trialTimers==0,
    "4K selection must enter the member branch without scheduling a trial timer");
  }else if(args[0].equals("login")){
   Vip4KPlayHelper helper=new Vip4KPlayHelper();helper.loggedIn=false;
   check(Boolean.TRUE.equals(call(helper,"handleVip4KClick",
    new Class<?>[]{MultiBitrateInfo.class},new MultiBitrateInfo(20000))),
    "Logged-out selection must retain the login prompt");
   check(helper.loginPanels==1&&helper.vipWaits==0&&helper.trialTimers==0,
    "Do not bypass login or start playback while logged out");
  }else if(args[0].equals("account")){
   PlatformVIPModule account=new PlatformVIPModule();
   check(Boolean.FALSE.equals(call(account,"isActive",new Class<?>[0])),
    "The account's global membership must remain unchanged");
   check(Boolean.FALSE.equals(call(account,"isActiveInLiveRoom",new Class<?>[0])),
    "The shared membership service must remain unchanged");
  }
  System.out.println("PASS: "+args[0]);
 }
}
""",
})


class HuyaVipPlaybackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="huya-vip-")
        cls.root = Path(cls.folder.name)
        sources = []
        for name, content in VIP_SOURCES.items():
            if name in ("LoaderLifecycleTest.java", "DisplayAdsTest.java"):
                continue
            path = cls.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            sources.append(str(path))
        sources.append(str(
            ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java"
        ))
        sources.append(str(
            ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettings.java"
        ))
        cls.classpath = os.pathsep.join([
            str(cls.root / "classes"), str(SDK / "platforms/android-36/android.jar")
        ])
        result = subprocess.run([
            str(JDK / "bin/javac.exe"), "-encoding", "UTF-8", "-cp", cls.classpath,
            "-d", str(cls.root / "classes"), *sources,
        ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            cls.folder.cleanup()
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_case(self, name):
        result = subprocess.run([
            str(JDK / "bin/java.exe"), "-cp", self.classpath, "VipPlaybackTest", name,
        ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_vip_exempt_ad_is_filtered_for_a_non_member(self):
        self.run_case("vip-ads")

    def test_ordinary_popup_and_null_validation_retain_original_behavior(self):
        self.run_case("ordinary-popups")

    def test_4k_selection_uses_member_branch_without_a_trial_timer(self):
        self.run_case("4k")

    def test_4k_selection_preserves_login_validation(self):
        self.run_case("login")

    def test_shared_membership_state_is_not_changed(self):
        self.run_case("account")

    def test_missing_4k_class_does_not_disable_ad_filtering(self):
        self.run_case("missing-4k")


if __name__ == "__main__":
    unittest.main()
