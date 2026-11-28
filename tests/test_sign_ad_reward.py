"""Exercise the task-center sign popup's native timed-ad reward path."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, SDK, JDK
from test_huya_miniapp_rewards import MINIAPP_SOURCES


SOURCES = dict(MINIAPP_SOURCES)
SOURCES.update({
    "android/os/Handler.java": """
package android.os;
import java.util.*;
public final class Handler {
 public static final List<Runnable> pending=new ArrayList<>();
 public Handler(Looper looper){}
 public boolean post(Runnable callback){pending.add(callback);return true;}
 public boolean postDelayed(Runnable callback,long delay){return true;}
 public void removeCallbacks(Runnable callback){pending.remove(callback);}
 public static void drain(){var callbacks=new ArrayList<>(pending);pending.clear();for(var r:callbacks)r.run();}
}
""",
    "org/json/JSONObject.java": """
package org.json;
import java.util.*;
public final class JSONObject {
 private final Map<String,Object> values=new LinkedHashMap<>();
 public JSONObject put(String key,Object value){values.put(key,value);return this;}
 public Object get(String key){return values.get(key);}
 public String optString(String key,String fallback){
  Object value=get(key);return value==null?fallback:value.toString();
 }
}
""",
    "com/huya/hybrid/react/utils/ReactHelper.java": """
package com.huya.hybrid.react.utils;
import java.util.*;
import org.json.JSONObject;
public final class ReactHelper {
 static Object get(Object data,String key){
  return data instanceof Map?((Map<?,?>)data).get(key)
    :data instanceof JSONObject?((JSONObject)data).get(key):null;
 }
 public static boolean webSafelyParseBoolean(Object data,String key,boolean fallback){
  Object value=get(data,key);return value instanceof Boolean?(Boolean)value:fallback;
 }
 public static int webSafelyParseInt(Object data,String key,int fallback){
  Object value=get(data,key);return value instanceof Number?((Number)value).intValue():fallback;
 }
}
""",
    "com/duowan/HUYA/AdInfo.java": """
package com.duowan.HUYA;
public final class AdInfo {}
""",
    "com/huya/kiwi/hyweb/modules/HYWebAd.java": """
package com.huya.kiwi.hyweb.modules;
import java.util.*;
import com.duowan.HUYA.AdInfo;
import com.huya.hybrid.webview.jssdk.JsCallback;
import io.github.libxposed.api.XposedModule;
public final class HYWebAd {
 public int checks,adOpens;
 public boolean allowed=true;
 public final WebView webView=new WebView();
 public static final class WebView {
  public String url="https://hd.huya.com/h5/welfare_center/index.html?rso=sign#popup";
  public String getUrl(){return url;}
 }
 public WebView getWebView(){return webView;}
 public void clickAd(Object params,Map<String,String> extras,JsCallback callback)throws Throwable {
  checks++;
  if(allowed)XposedModule.call(this,"realClick",
    new Class<?>[]{Object.class,AdInfo.class,int.class,Map.class,String.class,JsCallback.class},
    params,new AdInfo(),5,extras,"server-click-request",callback);
 }
 private void realClick(Object params,AdInfo ad,int heartbeat,Map<String,String> extras,
                        String requestId,JsCallback callback){adOpens++;callback.onSuccess(null);}
}
""",
    "com/duowan/kiwi/ad/api/IHyLotteryAdHelper.java": """
package com.duowan.kiwi.ad.api;
import java.util.Map;
public interface IHyLotteryAdHelper {
 interface HyRewardAdListener {
  void onRewarded(boolean success,Map<String,String> extras,String toast);
  void onError(int code,String message,int type,String detail);
  void onReward();
 }
}
""",
    "com/duowan/biz/videoad/impl/HyLotteryAdAwardManager.java": """
package com.duowan.biz.videoad.impl;
import java.util.*;
import com.duowan.kiwi.ad.api.IHyLotteryAdHelper.HyRewardAdListener;
public final class HyLotteryAdAwardManager {
 public static final CompanionType Companion=new CompanionType();
 public static final HyLotteryAdAwardManager instance=new HyLotteryAdAwardManager();
 public static final class CompanionType {
  public HyLotteryAdAwardManager getInstance(){return instance;}
 }
 public int calls,duration;
 public String task,extras,request;
 public boolean fail;
 public HyRewardAdListener callback;
 public void onAwardCommonRewardAdTask(String task,Map<?,?> map,int duration,String extras,
                                       String request,HyRewardAdListener callback){
  calls++;this.task=task;this.duration=duration;this.extras=extras;this.request=request;
  this.callback=callback;
  if(fail)throw new IllegalStateException("transport unavailable");
 }
}
""",
    "com/google/gson/Gson.java": r"""
package com.google.gson;
import java.util.*;
public final class Gson {
 public String toJson(Object value){
  List<String> fields=new ArrayList<>();
  for(var item:((Map<?,?>)value).entrySet())fields.add(quote(item.getKey())+":"+quote(item.getValue()));
  return "{"+String.join(",",fields)+"}";
 }
 static String quote(Object value){return "\""+value.toString().replace("\\","\\\\").replace("\"","\\\"")+"\"";}
}
""",
    "com/duowan/kiwi/crossplatform/base/webview/event/WebNativeEventEntity.java": """
package com.duowan.kiwi.crossplatform.base.webview.event;
public final class WebNativeEventEntity {
 public final String name;
 public final Object data;
 public WebNativeEventEntity(String name,Object data){this.name=name;this.data=data;}
}
""",
    "com/duowan/ark/ArkUtils.java": """
package com.duowan.ark;
import java.util.*;
import com.duowan.kiwi.crossplatform.base.webview.event.WebNativeEventEntity;
public final class ArkUtils {
 public static final List<WebNativeEventEntity> events=new ArrayList<>();
 public static void send(Object event){events.add((WebNativeEventEntity)event);}
}
""",
    "SignAdRewardTest.java": """
import java.util.*;
import java.lang.reflect.*;
import android.os.Handler;
import com.duowan.ark.ArkUtils;
import com.duowan.biz.videoad.impl.HyLotteryAdAwardManager;
import com.huya.kiwi.hyweb.modules.HYWebAd;
import com.huya.hybrid.webview.jssdk.JsCallback;
import io.github.saycm.huyaplus.HuyaCompatEntry;
public final class SignAdRewardTest {
 public static final class Callback implements JsCallback {
  public int calls;
  public void onSuccess(Object value){calls++;}
 }
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 public static void main(String[] args)throws Throwable {
  String test=args[0];
  boolean[] enabled={!test.equals("off")};
  HuyaCompatEntry entry=new HuyaCompatEntry();
  Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");prefs.setAccessible(true);
  prefs.set(entry,Proxy.newProxyInstance(SignAdRewardTest.class.getClassLoader(),
    new Class<?>[]{android.content.SharedPreferences.class},
    (proxy,method,values)->"rewards".equals(values[0])?enabled[0]:values[1]));
  Method init=HuyaCompatEntry.class.getDeclaredMethod("initializeHooks",ClassLoader.class);
  init.setAccessible(true);init.invoke(entry,SignAdRewardTest.class.getClassLoader());
  HYWebAd web=new HYWebAd();
  Map<String,Object> values=new LinkedHashMap<>();
  values.put("adTaskCalcUseNative",true);
  values.put("adTaskRewardClickCheck",1);
  values.put("adTaskRewardReqType",2);
  values.put("adTaskRewardedNotify",2);
  values.put("adTaskDuration",15);
  values.put("adTaskId","sign-task");
  values.put("adTaskUniqId","sign-task");
  Map<String,String> extras=new LinkedHashMap<>();extras.put("signToken","original-token");
  if(test.equals("other-page"))web.webView.url="https://hd.huya.com/h5/other/index.html";
  if(test.equals("spoof-page"))web.webView.url="https://hd.huya.com.evil/h5/welfare_center/index.html";
  if(test.equals("not-native"))values.put("adTaskCalcUseNative",false);
  if(test.equals("no-click-check"))values.put("adTaskRewardClickCheck",0);
  if(test.equals("wrong-type"))values.put("adTaskRewardReqType",1);
  if(test.equals("not-reward"))values.put("adTaskRewardedNotify",0);
  if(test.equals("no-id"))values.remove("adTaskId");
  if(test.equals("no-uniq-id"))values.remove("adTaskUniqId");
  if(test.equals("distinct-ids"))values.put("adTaskUniqId","sign-uniq");
  if(test.equals("wrong-id"))values.put("adTaskId",42);
  if(test.equals("no-duration"))values.put("adTaskDuration",0);
  if(test.equals("rejected-click"))web.allowed=false;
  Object params=values;
  if(test.equals("json")){
   org.json.JSONObject json=new org.json.JSONObject();values.forEach(json::put);params=json;
  }
  HyLotteryAdAwardManager manager=HyLotteryAdAwardManager.instance;
  manager.fail=test.equals("throw");
  Callback callback=new Callback();
  web.clickAd(params,extras,callback);
  check(web.checks==1,"Preserve Huya's original server click validation");
  if(test.equals("rejected-click")){
   check(manager.calls==0&&web.adOpens==0,"Rejected clicks must not submit rewards");return;
  }
  boolean fallback=Set.of("off","other-page","spoof-page","not-native","wrong-type",
    "not-reward","no-click-check","no-id","no-uniq-id","wrong-id","no-duration").contains(test);
  if(fallback){
   check(manager.calls==0&&web.adOpens==1,"Keep the original path outside timed task-center rewards");
   check(ArkUtils.events.isEmpty(),"Fallback must not emit reward events");return;
  }
  check(web.adOpens==0,"The sign bonus must not open the timed ad landing page");
  check(callback.calls==1,"Acknowledge the click once");
  check(manager.calls==1,"Submit one native reward request");
  check(manager.task.equals("sign-task")&&manager.duration==15,"Preserve task ID and required duration");
  check(manager.request.equals("server-click-request"),"Preserve the validated click request ID");
  check(manager.extras.equals("{\\\"signToken\\\":\\\"original-token\\\"}"),"Preserve original reward metadata");
  check(extras.equals(Map.of("signToken","original-token")),"Do not mutate caller metadata");
  check(ArkUtils.events.isEmpty(),"No completion before the server receipt");
  if(test.equals("throw"))return;
  if(test.equals("pending")){
   web.clickAd(params,extras,new Callback());
   check(manager.calls==1&&web.adOpens==0,"Repeated pending clicks must not resubmit");
  }
  manager.callback.onReward();
  check(ArkUtils.events.isEmpty(),"A playback-only callback does not confirm a reward");
  if(test.equals("error")){
   manager.callback.onError(1,"failed",0,"");Handler.drain();
   manager.callback.onRewarded(true,Map.of("sTaskUniqueKey","sign-task"),"late success");Handler.drain();
   check(ArkUtils.events.isEmpty(),"Transport errors must not complete sign bonuses");return;
  }
  Map<String,String> receipt=new LinkedHashMap<>();
  receipt.put("sTaskUniqueKey","sign-task");receipt.put("ticket","server-ticket");
  boolean success=!test.equals("denied");
  manager.callback.onRewarded(success,receipt,"this is a toast, not rewardExt");
  manager.callback.onRewarded(success,receipt,"duplicate");
  check(ArkUtils.events.isEmpty(),"Deliver web events on the main thread");
  Handler.drain();
  if(!success){check(ArkUtils.events.isEmpty(),"Server refusal must not complete the bonus");return;}
  check(ArkUtils.events.size()==2,"Emit one duration event and one end event");
  check(ArkUtils.events.get(0).name.equals("HYAdTaskDurationExceed"),"Duration must precede end");
  check(ArkUtils.events.get(1).name.equals("HYAdTaskEnd"),"Finish the sign popup's two-event handshake");
  Map<?,?> body=(Map<?,?>)ArkUtils.events.get(0).data;
  check(body.get("uniqId").equals(values.get("adTaskUniqId"))&&body.get("duration").equals(15),"Match the clicked task");
  check(body.get("ext").equals("{\\\"sTaskUniqueKey\\\":\\\"sign-task\\\",\\\"ticket\\\":\\\"server-ticket\\\"}"),
    "Use the server receipt map as rewardExt, never the toast");
 }
}
""",
})


class SignAdRewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="huya-sign-reward-")
        folder = Path(cls.folder.name)
        sources = []
        for name, content in SOURCES.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            sources.append(str(path))
        source = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
        sources.extend(str(source / (name + ".java")) for name in ("HuyaCompatEntry", "GlassSettings"))
        cls.classpath = os.pathsep.join((str(folder / "classes"), str(SDK / "platforms/android-36/android.jar")))
        result = subprocess.run([
            str(JDK / "bin/javac.exe"), "-encoding", "UTF-8", "-cp", cls.classpath,
            "-d", str(folder / "classes"), *sources,
        ], capture_output=True, text=True)
        if result.returncode:
            cls.folder.cleanup()
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_case(self, case):
        result = subprocess.run([
            str(JDK / "bin/java.exe"), "-cp", self.classpath, "SignAdRewardTest", case,
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sign_bonus_uses_native_receipt_and_both_completion_events(self):
        for case in ("success", "json", "pending", "distinct-ids"):
            with self.subTest(case=case):
                self.run_case(case)

    def test_rejected_or_failed_rewards_never_report_success(self):
        for case in ("rejected-click", "denied", "error", "throw"):
            with self.subTest(case=case):
                self.run_case(case)

    def test_disabled_unrelated_and_invalid_clicks_keep_the_original_path(self):
        for case in ("off", "other-page", "spoof-page", "not-native", "wrong-type",
                     "not-reward", "no-click-check", "no-id", "no-uniq-id", "wrong-id", "no-duration"):
            with self.subTest(case=case):
                self.run_case(case)


if __name__ == "__main__":
    unittest.main()
