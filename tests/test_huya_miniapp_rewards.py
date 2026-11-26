"""Exercise Huya's two mini-game reward protocols against the module hooks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, SDK, JDK, SOURCES


MINIAPP_SOURCES = {
    name: content for name, content in SOURCES.items()
    if name not in ("LoaderLifecycleTest.java", "LoaderActivity.java")
}
MINIAPP_SOURCES.update({
    "android/os/Looper.java": """
package android.os;
public final class Looper {
 public static Looper getMainLooper(){return new Looper();}
}
""",
    "android/os/Handler.java": """
package android.os;
import java.util.*;
public final class Handler {
 public static final List<Runnable> pending=new ArrayList<>();
 public Handler(Looper looper){}
 public boolean post(Runnable callback){return postDelayed(callback,0);}
 public boolean postDelayed(Runnable callback,long delay){pending.add(callback);return true;}
 public void removeCallbacks(Runnable callback){pending.remove(callback);}
 public static void drain(){
  List<Runnable> callbacks=new ArrayList<>(pending);pending.clear();
  for(Runnable callback:callbacks)callback.run();
 }
}
""",
    "org/json/JSONObject.java": """
package org.json;
import java.util.*;
public final class JSONObject {
 private final Map<String,Object> values=new HashMap<>();
 public JSONObject put(String key,Object value){values.put(key,value);return this;}
 public String optString(String key,String fallback){
  Object value=values.get(key);return value==null?fallback:value.toString();
 }
}
""",
    "com/huya/hybrid/webview/jssdk/JsCallback.java": """
package com.huya.hybrid.webview.jssdk;
public interface JsCallback {void onSuccess(Object value);}
""",
    "com/huya/kiwi/hyext/impl/modules/internal/HyExtAd.java": """
package com.huya.kiwi.hyext.impl.modules.internal;
import java.util.*;
import com.huya.hybrid.webview.jssdk.JsCallback;
import com.huya.kiwi.hyext.impl.utils.HyExtAdManager;
public final class HyExtAd {
 public int adOpens;
 public final List<String> order=new ArrayList<>();
 public final Map<String,Object> events=new LinkedHashMap<>();
 public void showCustomAd(Object params,JsCallback callback){
  HyExtAdManager.getInstance().showCustomAdView("unit",null);adOpens++;
 }
 public void openCustomAd(Object params,JsCallback callback){adOpens++;}
 public void showRewardedVideoAd(Object params,JsCallback callback){adOpens++;}
 public void dispatchEvent(String event,Object data){order.add(event);events.put(event,data);}
}
""",
    "com/huya/kiwi/hyext/impl/utils/HyExtAdManager.java": """
package com.huya.kiwi.hyext.impl.utils;
public final class HyExtAdManager {
 public static int displays;
 public static HyExtAdManager getInstance(){return new HyExtAdManager();}
 public void showCustomAdView(String unitId,Object style){displays++;}
}
""",
    "MiniappRewardsTest.java": """
import java.lang.reflect.*;
import java.util.*;
import android.os.Handler;
import org.json.JSONObject;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
import com.huya.hybrid.webview.jssdk.JsCallback;
import com.huya.kiwi.hyext.impl.modules.internal.HyExtAd;
public final class MiniappRewardsTest {
 public static final class Callback implements JsCallback {
  final HyExtAd module;
  public int calls;
  Callback(HyExtAd module){this.module=module;}
  public void onSuccess(Object value){calls++;module.order.add("success");}
 }
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 public static void main(String[] args)throws Throwable {
  String protocol=args[0];
  boolean custom=protocol.equals("custom");
  boolean banner=protocol.equals("banner");
  String methodName=custom?"openCustomAd":banner?"showCustomAd":"showRewardedVideoAd";
  String idKey=custom||banner?"customAdId":"rewardedVideoAdId";
  String event=custom?"customAdReward":"rewardedVideoAdClose";
  String successKey=custom?"isSuccess":"isEnded";
  Object id="example-ad";
  if(args[2].equals("missing"))id=null;
  if(args[2].equals("empty"))id="";
  if(args[2].equals("number"))id=42;
  Object params;
  if(args[1].equals("json")){
   params=new JSONObject().put(idKey,id);
  }else if(args[1].equals("null")){
   params=null;
  }else{
   Map<String,Object> map=new LinkedHashMap<>();
   map.put(idKey,id);params=map;
  }
  HuyaCompatEntry entry=new HuyaCompatEntry();
  boolean filterBanner=args.length==3||Boolean.parseBoolean(args[3]);
  if(args.length==5){
   Map<String,Boolean> settings=Map.of("ads",filterBanner,"rewards",Boolean.valueOf(args[4]));
   Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
   prefs.setAccessible(true);
   prefs.set(entry,Proxy.newProxyInstance(MiniappRewardsTest.class.getClassLoader(),
    new Class<?>[]{android.content.SharedPreferences.class},
    (proxy,method,values)->settings.getOrDefault(values[0],(Boolean)values[1])));
  }
  Method initialize=HuyaCompatEntry.class.getDeclaredMethod("initializeHooks",ClassLoader.class);
  initialize.setAccessible(true);initialize.invoke(entry,MiniappRewardsTest.class.getClassLoader());
  HyExtAd module=new HyExtAd();
  Callback callback=new Callback(module);
  XposedModule.call(module,methodName,new Class<?>[]{Object.class,JsCallback.class},params,callback);
  boolean valid=params!=null&&id instanceof String&&!((String)id).isEmpty();
  if(banner){
   int expectedDisplays=filterBanner?0:1;
   check(com.huya.kiwi.hyext.impl.utils.HyExtAdManager.displays==expectedDisplays,
    "The mini-game banner must follow the display ad switch");
   check(module.adOpens==expectedDisplays,"The original display must follow the display ad switch");
   if(filterBanner)check(callback.calls==1,"Hiding the banner must complete the show callback");
   check(Handler.pending.isEmpty(),"Hiding the banner must not grant a reward");
   check(module.events.isEmpty(),"Hiding the banner must not dispatch a reward");
  }else if(valid){
   check(module.adOpens==0,"A mini-game reward click must not open an ad: "+methodName);
   check(callback.calls==1,"The show callback must complete once");
   check(module.events.isEmpty(),"The reward must follow the show callback asynchronously");
   check(Handler.pending.size()==1,"One click must enqueue one reward event");
   Handler.drain();
   check(module.order.equals(Arrays.asList("success",event)),"Wrong callback order: "+module.order);
   check(module.events.size()==1,"The reward must be dispatched exactly once");
   Map<?,?> payload=(Map<?,?>)module.events.get(event);
   check(payload!=null,"Wrong reward event: "+module.events);
   check(payload.size()==2,"The reward event must contain only its ID and outcome");
   check(id.equals(payload.get(idKey)),"The event must identify the clicked ad");
   check(Boolean.TRUE.equals(payload.get(successKey)),"Wrong reward completion flag");
  }else{
   check(module.adOpens==1,"Invalid parameters must retain Huya's original validation");
   check(callback.calls==0&&Handler.pending.isEmpty(),"Invalid parameters must not grant a reward");
  }
  System.out.println("PASS: "+String.join(" ",args));
 }
}
""",
})


class HuyaMiniappRewardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="huya-miniapp-")
        cls.root = Path(cls.folder.name)
        sources = []
        for name, content in MINIAPP_SOURCES.items():
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
        ], capture_output=True, text=True)
        if result.returncode:
            cls.folder.cleanup()
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_case(self, *args):
        result = subprocess.run([
            str(JDK / "bin/java.exe"), "-cp", self.classpath, "MiniappRewardsTest", *args,
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_custom_game_rewards_complete_without_opening_ads(self):
        for params in ("map", "json"):
            with self.subTest(params=params):
                self.run_case("custom", params, "valid")

    def test_custom_game_banner_is_not_mounted(self):
        for ads in ("false", "true"):
            for rewards in ("false", "true"):
                with self.subTest(ads=ads, rewards=rewards):
                    self.run_case("banner", "map", "valid", ads, rewards)

    def test_rewarded_video_accepts_game_map_parameters(self):
        self.run_case("rewarded", "map", "valid")

    def test_rewarded_video_keeps_json_support(self):
        self.run_case("rewarded", "json", "valid")

    def test_invalid_game_parameters_keep_original_validation(self):
        for protocol in ("custom", "rewarded"):
            for params, value in (
                ("map", "missing"), ("map", "empty"), ("map", "number"), ("null", "missing")
            ):
                with self.subTest(protocol=protocol, params=params, value=value):
                    self.run_case(protocol, params, value)


if __name__ == "__main__":
    unittest.main()
