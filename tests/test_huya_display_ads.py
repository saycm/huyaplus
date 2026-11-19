"""Exercise the real hooks against the display-ad interfaces found in Huya."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import JDK, ROOT, SDK, SOURCES


DISPLAY_SOURCES = dict(SOURCES)
DISPLAY_SOURCES.update({
    "com/duowan/kiwi/universal/live/activitybar/banner/UniversalLiveBannerView.java": """
package com.duowan.kiwi.universal.live.activitybar.banner;
import java.util.*;
public class UniversalLiveBannerView {
 public List<?> items=new ArrayList<>();
 public boolean visible;
 public int updates;
 public void setData(List<?> data){
  updates++;items=data==null?new ArrayList<>():new ArrayList<>(data);visible=!items.isEmpty();
 }
}
""",
    "com/duowan/kiwi/universal/live/activitybar/banner/UniversalTaskBannerView.java": """
package com.duowan.kiwi.universal.live.activitybar.banner;
import java.util.*;
public class UniversalTaskBannerView {
 public List<?> items=new ArrayList<>();
 public void setData(List<?> data){items=new ArrayList<>(data);}
}
""",
    "com/duowan/HUYA/ActCommEnt.java": """
package com.duowan.HUYA;
public class ActCommEnt {
 public int iEntId;
 public ActCommEnt(int id){iEntId=id;}
}
""",
    "com/duowan/kiwi/passage/api/view/floatwindow/IFloatWindowContainer.java": """
package com.duowan.kiwi.passage.api.view.floatwindow;
public interface IFloatWindowContainer {}
""",
    "com/huya/oak/miniapp/container/internal/MiniAppPopupFragment.java": """
package com.huya.oak.miniapp.container.internal;
public class MiniAppPopupFragment {}
""",
    "com/huya/kiwi/hyext/delegate/api/HYExtRightTopWindowModeManager.java": """
package com.huya.kiwi.hyext.delegate.api;
import com.duowan.HUYA.ActCommEnt;
import com.duowan.kiwi.passage.api.view.floatwindow.IFloatWindowContainer;
import com.huya.oak.miniapp.container.internal.MiniAppPopupFragment;
public class HYExtRightTopWindowModeManager {
 public int attachedCards;
 public void createFloatWindowItemView(IFloatWindowContainer container,
   MiniAppPopupFragment fragment,ActCommEnt item,int index,boolean landscape){
  attachedCards++;
 }
}
""",
    "com/duowan/kiwi/livead/api/adplugin/api/IHYRoomPopupPlugin.java": """
package com.duowan.kiwi.livead.api.adplugin.api;
public interface IHYRoomPopupPlugin {
 interface IHYChannelAvailabilityCheckCallback {}
}
""",
    "com/duowan/kiwi/livead/impl/adplugin/module/HYRoomPopupPlugin.java": """
package com.duowan.kiwi.livead.impl.adplugin.module;
import com.duowan.kiwi.livead.api.adplugin.api.IHYRoomPopupPlugin.IHYChannelAvailabilityCheckCallback;
public class HYRoomPopupPlugin {
 public int queuedCards;
 public void enqueue(String id,String data,IHYChannelAvailabilityCheckCallback callback){
  queuedCards++;
 }
}
""",
    "com/duowan/kiwi/popup/api/PopupItem.java": """
package com.duowan.kiwi.popup.api;
public class PopupItem {
 private final String key;
 public PopupItem(String key){this.key=key;}
 public String getBusinessKey(){return key;}
}
""",
    "com/duowan/kiwi/popup/impl/PopupModule.java": """
package com.duowan.kiwi.popup.impl;
import com.duowan.kiwi.popup.api.PopupItem;
public class PopupModule {
 public int queuedCards;
 public boolean tryShowPopup(PopupItem item){if(item==null)return false;queuedCards++;return true;}
 public boolean tryPlaceholderPopup(PopupItem item){queuedCards++;return true;}
}
""",
    "com/duowan/kiwi/adsplash/controller/AdRouter.java": """
package com.duowan.kiwi.adsplash.controller;
public class AdRouter {
 public int originalCalls;
 public int isNeedShowAdSplash(android.content.Context c,boolean cache,boolean hot,boolean preload){
  originalCalls++;return hot?8:0;
 }
}
""",
    "com/duowan/kiwi/ad/impl/HyAdModule.java": """
package com.duowan.kiwi.ad.impl;
public class HyAdModule {
 public boolean isNeedShieldAdOutLivingRoom(){return false;}
 public boolean isNeedShieldAdInLivingRoom(){return false;}
}
""",
    "com/duowan/kiwi/list/patface/chain/PatFaceInterceptorChain.java": """
package com.duowan.kiwi.list.patface.chain;
public class PatFaceInterceptorChain {
 public int queuedDialogs;
 public boolean proceed(int location){queuedDialogs++;return true;}
}
""",
    "com/duowan/kiwi/listframe/component/LineItem.java": """
package com.duowan.kiwi.listframe.component;
public class LineItem {
 private final Object mViewObject;
 public LineItem(Object value){mViewObject=value;}
 public Object getLineItem(){return mViewObject;}
}
""",
    "com/duowan/kiwi/list/component/RecommendAdComponent.java": """
package com.duowan.kiwi.list.component;
public class RecommendAdComponent {public static class ViewObject {}}
""",
    "com/duowan/kiwi/list/homepage/tab/recommend/BaseRecommendPresenter.java": """
package com.duowan.kiwi.list.homepage.tab.recommend;
import java.util.*;
public class BaseRecommendPresenter {
 public int adCallbacks;
 public void onLiveListAdBack(Object liveAd,Object localAd,Object map,boolean zh){
  adCallbacks++;
 }
 private List<Object> getGridGameCardItemList(List<Object> prefix,List<?> items,Map<?,?> bigCards){
  return new ArrayList<>(items);
 }
 public void l0(List<Object> output,Object cards,Map<?,?> bigCards){
  output.addAll((List<?>)cards);
 }
}
""",
    "com/duowan/kiwi/immersepage/api/data/ImmerseItemType.java": """
package com.duowan.kiwi.immersepage.api.data;
public enum ImmerseItemType {
 AD_VIDEO,COLLECTION_RECOMMEND,FOLLOW_RECOMMEND,HOME_NATIVE_AD,
 HOT_LIVE_AD_VIDEO,IMMERSE_ACTIVE,LIVE_LIST_AD_VIDEO,
 RECOMMEND_SINGLE_IMMERSION_LIVE,USER_FAVOR,VIDEO
}
""",
    "com/duowan/kiwi/immersepage/api/data/ImmerseItem.java": """
package com.duowan.kiwi.immersepage.api.data;
public class ImmerseItem {
 private final ImmerseItemType itemType;
 public ImmerseItem(ImmerseItemType itemType){this.itemType=itemType;}
 public ImmerseItemType getItemType(){return itemType;}
}
""",
    "com/duowan/kiwi/immersepage/impl/data/ImmerseDataManagerImpl.java": """
package com.duowan.kiwi.immersepage.impl.data;
import java.util.*;
import com.duowan.kiwi.immersepage.api.data.ImmerseItem;
public class ImmerseDataManagerImpl {
 private ArrayList filterList(int pageIndex,ArrayList items,boolean fromRefresh){
  return new ArrayList(items);
 }
}
""",
    "DisplayAdsTest.java": """
import java.util.*;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
import com.duowan.kiwi.adsplash.controller.AdRouter;
import com.duowan.kiwi.ad.impl.HyAdModule;
import com.duowan.kiwi.list.patface.chain.PatFaceInterceptorChain;
import com.duowan.kiwi.listframe.component.LineItem;
import com.duowan.kiwi.list.component.RecommendAdComponent;
import com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendPresenter;
import com.duowan.kiwi.immersepage.api.data.ImmerseItem;
import com.duowan.kiwi.immersepage.api.data.ImmerseItemType;
import com.duowan.kiwi.immersepage.impl.data.ImmerseDataManagerImpl;
import com.duowan.kiwi.popup.api.PopupItem;
import com.duowan.kiwi.popup.impl.PopupModule;
import com.duowan.kiwi.livead.impl.adplugin.module.HYRoomPopupPlugin;
import com.duowan.kiwi.livead.api.adplugin.api.IHYRoomPopupPlugin.IHYChannelAvailabilityCheckCallback;
import com.duowan.HUYA.ActCommEnt;
import com.duowan.kiwi.passage.api.view.floatwindow.IFloatWindowContainer;
import com.huya.oak.miniapp.container.internal.MiniAppPopupFragment;
import com.huya.kiwi.hyext.delegate.api.HYExtRightTopWindowModeManager;
import com.duowan.kiwi.universal.live.activitybar.banner.UniversalLiveBannerView;
import com.duowan.kiwi.universal.live.activitybar.banner.UniversalTaskBannerView;
public class DisplayAdsTest {
 static final class Param implements XposedModule.PackageReadyParam {
  final ClassLoader loader;
  Param(ClassLoader loader){this.loader=loader;}
  public String getPackageName(){return "com.duowan.kiwi";}
  public boolean isFirstPackage(){return true;}
  public ClassLoader getClassLoader(){return loader;}
 }
 public static class Card {
  public int iCardType;
  public List<Object> vAdCard=new ArrayList<>();
 }
 public static class User {
  public Card tMCard;
  public String sTitle="normal live";
 }
 public static class Grid {
  public User userRecItem;
 }
 public static class Lizard {
  private Object mLiveListAdInfo;
  public Lizard(Object ad){mLiveListAdInfo=ad;}
 }
 static LineItem nativeAd(){
  Grid grid=new Grid();grid.userRecItem=new User();grid.userRecItem.tMCard=new Card();
  grid.userRecItem.tMCard.iCardType=4;
  grid.userRecItem.tMCard.vAdCard.add(new Object());
  return new LineItem(grid);
 }
 static LineItem normalLine(){
  return new LineItem(new Object());
 }
 static void check(boolean condition,String message){
  if(!condition)throw new AssertionError(message);
 }
 static Object call(Object target,String method,Class<?>[] types,Object... args) throws Throwable{
  return XposedModule.call(target,method,types,args);
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
 public static void main(String[] args) throws Throwable {
  new HuyaCompatEntry().onPackageReady(
   new Param(DisplayAdsTest.class.getClassLoader()));
  XposedModule.invokeHook(
   android.app.Activity.class.getDeclaredMethod("onCreate",android.os.Bundle.class),
   new ActivityChain(new DisplayAdsTest()));
  if(args[0].equals("live-cards")){
   PopupModule module=new PopupModule();
   for(String key:new String[]{"magicboxrecentresult_autotrigger",
     "giftblindbox_autotrigger","adrewardtasks_autotrigger","gamepad_autotrigger",
     "gamead_autotrigger"}){
    Object result=call(module,"tryShowPopup",new Class<?>[]{PopupItem.class},new PopupItem(key));
    check(Boolean.FALSE.equals(result),"Automatic live-room cards must be rejected before queueing");
   }
   check(module.queuedCards==0,"No automatic live-room card may enter the popup queue");
   for(String key:new String[]{"magicboxrecentresult","adrewardtasks","gamead",
     "autotrigger_help","unknown",null}){
    Object result=call(module,"tryShowPopup",new Class<?>[]{PopupItem.class},new PopupItem(key));
    check(Boolean.TRUE.equals(result),"Manual and unknown popup entries must keep working");
   }
   check(module.queuedCards==6,"Manual popup requests must each run exactly once");
   check(Boolean.FALSE.equals(call(module,"tryShowPopup",new Class<?>[]{PopupItem.class},
    new Object[]{null})),"Null input must retain original validation");
   check(module.queuedCards==6,"Null input must not enter the queue");
  }else if(args[0].equals("live-placeholder-cards")){
   PopupModule module=new PopupModule();
   for(String key:new String[]{"gamead_autotrigger","shop_autotrigger",
     "shopplaymate_autotrigger"}){
    Object result=call(module,"tryPlaceholderPopup",new Class<?>[]{PopupItem.class},
     new PopupItem(key));
    check(Boolean.FALSE.equals(result),"Automatic placeholder cards must be rejected before queueing");
   }
   check(module.queuedCards==0,"Placeholder promotion must not bypass the popup filter");
   for(String key:new String[]{"gamead","shop","unknown",null}){
    Object result=call(module,"tryPlaceholderPopup",new Class<?>[]{PopupItem.class},
     new PopupItem(key));
    check(Boolean.TRUE.equals(result),"Manual placeholder entries must retain their original behavior");
   }
   check(module.queuedCards==4,"Manual placeholder requests must each run exactly once");
  }else if(args[0].equals("live-promotion-windows")){
   HYExtRightTopWindowModeManager manager=new HYExtRightTopWindowModeManager();
   Class<?>[] types={IFloatWindowContainer.class,MiniAppPopupFragment.class,
    ActCommEnt.class,int.class,boolean.class};
   for(int id:new int[]{317,201,175}){
    for(boolean landscape:new boolean[]{false,true}){
     for(MiniAppPopupFragment fragment:new MiniAppPopupFragment[]{
       null,new MiniAppPopupFragment()}){
      call(manager,"createFloatWindowItemView",types,null,fragment,
       new ActCommEnt(id),0,landscape);
     }
    }
   }
   check(manager.attachedCards==0,"Gift, game and shopping promotions must not attach floating cards");
   for(ActCommEnt item:new ActCommEnt[]{new ActCommEnt(0),new ActCommEnt(999),null}){
    call(manager,"createFloatWindowItemView",types,null,new MiniAppPopupFragment(),item,0,false);
   }
   check(manager.attachedCards==3,"Other entrance IDs and null must retain original handling");
  }else if(args[0].equals("live-promotion-banners")){
   UniversalLiveBannerView banner=new UniversalLiveBannerView();
   banner.setData(Arrays.asList("old promotion"));
   List<Object> input=new ArrayList<>(Arrays.asList(new Object(),new Object()));
   for(int i=0;i<2;i++){
    call(banner,"setData",new Class<?>[]{List.class},input);
    check(!banner.visible && banner.items.isEmpty(),
     "Live promotion banners must use the original empty-data hide route");
   }
   check(input.size()==2,"Banner filtering must not mutate the caller's list");
   check(banner.updates==3,"Banner cleanup must execute the original lifecycle exactly once per update");
   call(banner,"setData",new Class<?>[]{List.class},new Object[]{null});
   check(!banner.visible,"Null banner reset must keep working");
   UniversalTaskBannerView task=new UniversalTaskBannerView();
   call(task,"setData",new Class<?>[]{List.class},input);
   check(task.items.size()==2,"Task progress banners must retain their data");
  }else if(args[0].equals("live-floating-ads")){
   HYRoomPopupPlugin plugin=new HYRoomPopupPlugin();
   Class<?>[] types={String.class,String.class,IHYChannelAvailabilityCheckCallback.class};
   for(String id:new String[]{"floatball_ad_example_1","floatball_ad_example_2"}){
    call(plugin,"enqueue",types,id,"{}",null);
   }
   check(plugin.queuedCards==0,"Floating ad cards must not enter the native popup queue");
   for(String id:new String[]{"floatball_dailyfreegift_autotrigger_example",
     "floatball_reward_manual_example","unknown",null}){
    call(plugin,"enqueue",types,id,"{}",null);
   }
   check(plugin.queuedCards==4,"Reward entries and unknown native popups must retain their queue");
  }else if(args[0].equals("splash")){
   AdRouter router=new AdRouter();
   for(boolean hot:new boolean[]{false,true})
    for(boolean cached:new boolean[]{false,true}){
     Object result=call(router,"isNeedShowAdSplash",
      new Class<?>[]{android.content.Context.class,boolean.class,boolean.class,boolean.class},
      null,cached,hot,true);
     check(Integer.valueOf(6).equals(result),"Splash must take Huya's no-display route: "+result);
    }
   check(router.originalCalls==0,"Splash must be blocked before requesting or showing it");
  }else if(args[0].equals("promotion")){
   PatFaceInterceptorChain chain=new PatFaceInterceptorChain();
   for(int location:new int[]{0,1,2,3}){
    Object result=call(chain,"proceed",new Class<?>[]{int.class},location);
    check(Boolean.FALSE.equals(result),"Automatic promotion must return the no-display result");
   }
   check(chain.queuedDialogs==0,"Promotion must be stopped before adding a dialog to the queue");
  }else if(args[0].equals("dynamic")){
   BaseRecommendPresenter presenter=new BaseRecommendPresenter();
   call(presenter,"onLiveListAdBack",
    new Class<?>[]{Object.class,Object.class,Object.class,boolean.class},
    new Object(),new Object(),new Object(),true);
   check(presenter.adCallbacks==0,
    "Recommendation ads must be stopped before they are written into existing cards");
  }else if(args[0].equals("grid")){
   BaseRecommendPresenter presenter=new BaseRecommendPresenter();
   LineItem first=normalLine(),last=normalLine();
   ArrayList<LineItem> input=new ArrayList<>(Arrays.asList(first,nativeAd(),last));
   List<?> result=(List<?>)call(presenter,"getGridGameCardItemList",
    new Class<?>[]{List.class,List.class,Map.class},
    new ArrayList<>(),input,new HashMap<>());
   check(result.equals(Arrays.asList(first,last)),
    "Grid recommendation ads must be removed before list insertion: "+result.size());
   check(input.size()==3,"Caller-owned grid rows must stay unchanged");
  }else if(args[0].equals("grid-insert")){
   BaseRecommendPresenter presenter=new BaseRecommendPresenter();
   LineItem first=normalLine(),last=normalLine();
   ArrayList<LineItem> output=new ArrayList<>();
   output.add(first);
   call(presenter,"l0",new Class<?>[]{List.class,Object.class,Map.class},
    output,new ArrayList<>(Arrays.asList(nativeAd(),last)),new HashMap<>());
   check(output.equals(Arrays.asList(first,last)),
    "Grid ads must be removed after either recommendation build path: "+output.size());
  }else if(args[0].equals("immerse")){
   ImmerseItem normal=new ImmerseItem(ImmerseItemType.VIDEO);
   ImmerseItem recommendLive=new ImmerseItem(
    ImmerseItemType.RECOMMEND_SINGLE_IMMERSION_LIVE);
   ArrayList<ImmerseItem> input=new ArrayList<>(Arrays.asList(
    normal,new ImmerseItem(ImmerseItemType.AD_VIDEO),
    recommendLive,new ImmerseItem(ImmerseItemType.HOME_NATIVE_AD),
    new ImmerseItem(ImmerseItemType.HOT_LIVE_AD_VIDEO),
    new ImmerseItem(ImmerseItemType.LIVE_LIST_AD_VIDEO)));
   ImmerseDataManagerImpl manager=new ImmerseDataManagerImpl();
   List<?> result=(List<?>)call(manager,"filterList",
    new Class<?>[]{int.class,ArrayList.class,boolean.class},0,input,false);
   check(result.equals(Arrays.asList(normal,recommendLive)),
    "Immersive feed ads must be removed while normal items keep their order: "+result.size());
   check(input.size()==6,"Caller-owned feed data must stay unchanged");
  }else if(args[0].equals("batch")){
   Object adapter=Class.forName(args[1]).getConstructor().newInstance();
   LineItem first=new LineItem(new Object()),last=new LineItem(new Object());
   Grid ordinary=new Grid();ordinary.userRecItem=new User();ordinary.userRecItem.tMCard=new Card();
   ordinary.userRecItem.tMCard.iCardType=4;
   LineItem placeholder=new LineItem(ordinary);
   List<LineItem> input=Collections.unmodifiableList(Arrays.asList(
    first,new LineItem(new RecommendAdComponent.ViewObject()),nativeAd(),
    new LineItem(new Lizard(new Object())),placeholder,last));
   call(adapter,args[2],new Class<?>[]{List.class},input);
   List<?> items=(List<?>)adapter.getClass().getField("items").get(adapter);
   check(items.equals(Arrays.asList(first,placeholder,last)),
    "Ad cards must be removed while normal cards keep their order: "+items.size());
   check(input.size()==6,"Caller-owned lists must stay unchanged");
  }else if(args[0].equals("single")){
   Object adapter=Class.forName(args[1]).getConstructor().newInstance();
   Class<?>[] types={LineItem.class,int.class};
   call(adapter,args[2],types,nativeAd(),0);
   check(adapter.getClass().getField("calls").getInt(adapter)==0,
    "Single ad insertion must not insert or send an invalid item notification");
   LineItem normal=new LineItem(new Object());
   call(adapter,args[2],types,normal,0);
   check(adapter.getClass().getField("calls").getInt(adapter)==1,
    "Normal insertion must still run");
  }else if(args[0].equals("shield")){
   HyAdModule module=new HyAdModule();
   check(Boolean.TRUE.equals(call(module,"isNeedShieldAdOutLivingRoom",new Class<?>[0])),
    "Ordinary home, subscription, search and profile ad requests must be shielded");
   check(!module.isNeedShieldAdInLivingRoom(),
    "The live-room shield must stay unchanged because it also guards rewarded ads");
  }
  System.out.println("PASS: "+String.join(" ",args));
 }
}
""",
})

for package, name, methods in (
    ("com.duowan.kiwi.listframe.adapter", "ListLineRecyclerViewAdapter",
     ("replace", "replaceAndNotify", "insert", "insertAndNotify")),
    ("com.duowan.kiwi.listframe.adapter", "HeaderFooterListLineAdapter",
     ("replace", "replaceAndNotify", "insert", "insertAndNotify")),
    ("com.duowan.kiwi.listline", "ListLineAdapter",
     ("replaceData", "replaceAndNotify", "insertItemDataOnly", "insertItemAndNotify")),
):
    DISPLAY_SOURCES[package.replace(".", "/") + "/" + name + ".java"] = f"""
package {package};
import java.util.*;
import com.duowan.kiwi.listframe.component.LineItem;
public class {name} {{
 public List<LineItem> items=new ArrayList<>();
 public int calls;
 public void {methods[0]}(List<LineItem> list){{calls++;items=new ArrayList<>(list);}}
 public void {methods[1]}(List<LineItem> list){{calls++;items=new ArrayList<>(list);}}
 public void {methods[2]}(LineItem item,int index){{calls++;items.add(index,item);}}
 public void {methods[3]}(LineItem item,int index){{calls++;items.add(index,item);}}
}}
"""


class HuyaDisplayAdsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="huya-display-")
        cls.root = Path(cls.folder.name)
        sources = []
        for name, content in DISPLAY_SOURCES.items():
            if name == "LoaderLifecycleTest.java":
                continue
            path = cls.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            sources.append(str(path))
        sources.append(str(ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java"))
        sources.append(str(ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettings.java"))
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
            str(JDK / "bin/java.exe"), "-cp", self.classpath, "DisplayAdsTest", *args,
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cold_and_hot_splash_use_the_no_display_route(self):
        self.run_case("splash")

    def test_automatic_promotion_stops_before_queuing_a_dialog(self):
        self.run_case("promotion")

    def test_automatic_live_cards_stop_before_queueing_and_keep_manual_entries(self):
        self.run_case("live-cards")

    def test_live_floating_ads_stop_before_native_queue_without_removing_reward_entries(self):
        self.run_case("live-floating-ads")

    def test_automatic_placeholder_cards_cannot_bypass_the_popup_filter(self):
        self.run_case("live-placeholder-cards")

    def test_promotional_h5_and_miniapp_cards_do_not_attach_floating_windows(self):
        self.run_case("live-promotion-windows")

    def test_live_promotion_banner_refills_are_hidden_without_removing_task_progress(self):
        self.run_case("live-promotion-banners")

    def test_recommendation_ads_stop_before_dynamic_card_injection(self):
        self.run_case("dynamic")

    def test_grid_recommendation_ads_are_removed_before_list_insertion(self):
        self.run_case("grid")

    def test_grid_recommendation_ads_are_removed_after_unified_insertion(self):
        self.run_case("grid-insert")

    def test_recommendation_feed_removes_all_immersive_ad_item_types(self):
        self.run_case("immerse")

    def test_both_list_adapters_filter_ads_without_changing_the_input(self):
        for adapter, methods in (
            ("com.duowan.kiwi.listframe.adapter.ListLineRecyclerViewAdapter",
             ("replace", "replaceAndNotify")),
            ("com.duowan.kiwi.listframe.adapter.HeaderFooterListLineAdapter",
             ("replace", "replaceAndNotify")),
            ("com.duowan.kiwi.listline.ListLineAdapter",
             ("replaceData", "replaceAndNotify")),
        ):
            for method in methods:
                with self.subTest(adapter=adapter, method=method):
                    self.run_case("batch", adapter, method)

    def test_single_ad_insertion_does_not_send_item_notifications(self):
        for adapter, methods in (
            ("com.duowan.kiwi.listframe.adapter.ListLineRecyclerViewAdapter",
             ("insert", "insertAndNotify")),
            ("com.duowan.kiwi.listframe.adapter.HeaderFooterListLineAdapter",
             ("insert", "insertAndNotify")),
            ("com.duowan.kiwi.listline.ListLineAdapter",
             ("insertItemDataOnly", "insertItemAndNotify")),
        ):
            for method in methods:
                with self.subTest(adapter=adapter, method=method):
                    self.run_case("single", adapter, method)

    def test_ordinary_ad_shield_does_not_enable_the_reward_ad_shield(self):
        self.run_case("shield")


if __name__ == "__main__":
    unittest.main()
