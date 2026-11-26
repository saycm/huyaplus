"""Exercise the real hooks against the display-ad interfaces found in Huya."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import JDK, ROOT, SDK, SOURCES
from test_navigation_visibility import FIXTURES as NAVIGATION_FIXTURES


DISPLAY_SOURCES = dict(SOURCES)
DISPLAY_SOURCES.update({name: NAVIGATION_FIXTURES[name] for name in (
    "android/content/res/Configuration.java",
    "android/content/res/Resources.java",
    "android/view/View.java",
)})
DISPLAY_SOURCES.update({
    "com/duowan/kiwi/livead/api/adplugin/event/IPresenterAdEvent.java": """
package com.duowan.kiwi.livead.api.adplugin.event;
public interface IPresenterAdEvent {
 class ShowNotLiveAdEvent {}
}
""",
    "com/duowan/kiwi/liveend/impl/views/NotLivingView.java": """
package com.duowan.kiwi.liveend.impl.views;
import com.duowan.kiwi.livead.api.adplugin.event.IPresenterAdEvent.ShowNotLiveAdEvent;
public class NotLivingView {
 public int ads,replays;
 public void onShowStopLiveAdEvent(ShowNotLiveAdEvent event){ads++;}
 public void playLiveRecord(){replays++;}
}
""",
    "com/huya/hybrid/webview/HYWebView.java": """
package com.huya.hybrid.webview;
public class HYWebView {
 public int committed;
 public void onPageCommitVisible(String url){committed++;}
}
""",
    "com/duowan/kiwi/crossplatform/base/webview/KiwiWebView.java": """
package com.duowan.kiwi.crossplatform.base.webview;
import android.webkit.ValueCallback;
import com.huya.hybrid.webview.HYWebView;
public class KiwiWebView extends HYWebView {
 public int finished, injections;
 public void onPageFinished(String url){finished++;}
 public void evaluateJavascript(String script,ValueCallback<String> callback){
  injections++;
  callback.onReceiveValue("true");
 }
}
""",
    "com/duowan/kiwi/livead/api/adbanner/view/AdLiveBannerView.java": """
package com.duowan.kiwi.livead.api.adbanner.view;
import java.util.*;
public class AdLiveBannerView {
 public boolean visible=true;
 public int shows, hides;
 public boolean showAd(List<?> ads,Map<?,?> extras){shows++;visible=true;return true;}
 public void hideAd(){hides++;visible=false;}
}
""",
    "com/duowan/HUYA/LiveRoomAdvertise.java": """
package com.duowan.HUYA;
public class LiveRoomAdvertise {}
""",
    "com/duowan/kiwi/livead/api/adfloat/data/Advertisement.java": """
package com.duowan.kiwi.livead.api.adfloat.data;
public class Advertisement {}
""",
    "com/duowan/kiwi/livead/impl/adfloat/module/RevenueModule.java": """
package com.duowan.kiwi.livead.impl.adfloat.module;
import java.util.Map;
import com.duowan.HUYA.LiveRoomAdvertise;
import com.duowan.kiwi.livead.api.adfloat.data.Advertisement;
public class RevenueModule {
 public int displays;
 private void displayAdByMethod(LiveRoomAdvertise ad,Advertisement data,long time,Map<?,?> extras){
  displays++;
 }
}
""",
    "com/duowan/kiwi/universal/live/pubscreen/biz/UniversalLiveAdFloat.java": """
package com.duowan.kiwi.universal.live.pubscreen.biz;
public class UniversalLiveAdFloat {
 public boolean visible;
 public int updates;
 private void changeFloatAdVisibilityIfNeed(boolean visible){updates++;this.visible=visible;}
}
""",
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
    "com/duowan/kiwi/interaction/api/data/ComponentPanelItemInfo.java": """
package com.duowan.kiwi.interaction.api.data;
import com.duowan.HUYA.interactiveComInfo;
public class ComponentPanelItemInfo {
 private final int id;
 private final String name, route;
 public final interactiveComInfo info=new interactiveComInfo();
 public ComponentPanelItemInfo(int id,String name,String route){
  this.id=id;this.name=name;this.route=route;
 }
 public int getComponentId(){return id;}
 public String getComponentName(){return name;}
 public String getJumpUrl(boolean landscape){return landscape?null:route;}
 public interactiveComInfo getInteractiveComInfo(){return info;}
}
""",
    "com/duowan/HUYA/interactiveComInfo.java": """
package com.duowan.HUYA;
public class interactiveComInfo {
 public interactiveComInfoReminder tReminderInfo;
}
""",
    "com/duowan/HUYA/interactiveComInfoReminder.java": """
package com.duowan.HUYA;
public class interactiveComInfoReminder {
 public int iState;
 public String sButton;
}
""",
    "com/duowan/kiwi/livehighlightmark/impl/view/HighlightMarkView.java": """
package com.duowan.kiwi.livehighlightmark.impl.view;
public class HighlightMarkView extends android.view.View {
 public boolean containerVisible=true;
 public void setVisible(boolean visible){containerVisible=visible;}
}
""",
    "com/duowan/kiwi/interaction/impl/view/UniversalComponentNavigationView.java": """
package com.duowan.kiwi.interaction.impl.view;
import java.util.List;
public class UniversalComponentNavigationView {
 public List<?> items;
 public boolean landscape;
 public boolean isLandscape(){return landscape;}
 public void setAllTimeLimitComps(List<?> items){this.items=items;}
 public void setComponentData(List<?> items){this.items=items;}
}
""",
    "com/duowan/biz/util/OrientationData.java": """
package com.duowan.biz.util;
public class OrientationData {
 private final String portrait, landscape;
 public OrientationData(String portrait,String landscape){this.portrait=portrait;this.landscape=landscape;}
 public String getPortrait(){return portrait;}
 public String getLandscape(){return landscape;}
}
""",
    "com/duowan/kiwi/inputbar/api/view/InputEntryData.java": """
package com.duowan.kiwi.inputbar.api.view;
import com.duowan.biz.util.OrientationData;
public class InputEntryData {
 private final String title;
 private final OrientationData actionUrl;
 private final int type;
 public InputEntryData(String title,OrientationData actionUrl){this(title,actionUrl,0);}
 public InputEntryData(String title,OrientationData actionUrl,int type){
  this.title=title;this.actionUrl=actionUrl;this.type=type;
 }
 public String getTitle(){return title;}
 public OrientationData getActionUrl(){return actionUrl;}
 public int getType(){return type;}
}
""",
    "com/duowan/kiwi/inputbar/api/view/entryview/base/BottomBarEntryListView.java": """
package com.duowan.kiwi.inputbar.api.view.entryview.base;
import java.util.List;
public class BottomBarEntryListView {
 public List<?> items;
 public void refreshAllEntryView(List<?> items){this.items=items;}
}
""",
    "com/duowan/HUYA/ActCommEnt.java": """
package com.duowan.HUYA;
public class ActCommEnt {
 public int iEntId;
 public int iType;
 public String sName;
 public String sFullUrl;
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
    "com/duowan/kiwi/listframe/RefreshListener.java": """
package com.duowan.kiwi.listframe;
public interface RefreshListener { enum RefreshMode { REPLACE_ALL, APPEND } }
""",
    "com/duowan/kiwi/list/homepage/tab/recommend/BaseRecommendFragment.java": """
package com.duowan.kiwi.list.homepage.tab.recommend;
import com.duowan.kiwi.listframe.RefreshListener.RefreshMode;
import java.util.List;
public class BaseRecommendFragment {
 public List<?> items;
 public boolean endRefresh(List<?> rows,RefreshMode mode,int total){items=rows;return true;}
}
""",
    "com/duowan/kiwi/list/homepage/tab/recommend/GameRecommendFragment.java": """
package com.duowan.kiwi.list.homepage.tab.recommend;
import com.duowan.kiwi.listframe.RefreshListener.RefreshMode;
import java.util.List;
public class GameRecommendFragment extends BaseRecommendFragment {
 public boolean endRefresh(List<?> rows,RefreshMode mode,int total){return super.endRefresh(rows,mode,total);}
}
""",
    "com/duowan/kiwi/list/vo/lizard/LZCategoryViewObject.java": """
package com.duowan.kiwi.list.vo.lizard;
public class LZCategoryViewObject {
 private final Object mUserRecItem;
 public LZCategoryViewObject(Object item){mUserRecItem=item;}
 public Object getUserRecItem(){return mUserRecItem;}
}
""",
    "com/duowan/kiwi/list/vo/LiveGridViewObject.java": """
package com.duowan.kiwi.list.vo;
public class LiveGridViewObject {
 public final Object userRecItem;
 public LiveGridViewObject(Object item){userRecItem=item;}
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
public class ImmerseDataManagerImpl implements IImmerseDataManager {
 public final List<ImmerseItem> items=new ArrayList<>();
 private ArrayList filterList(int pageIndex,ArrayList items,boolean fromRefresh){
  return new ArrayList(items);
 }
 public void insertAdIfNeed(int position,ArrayList<ImmerseItem> ads,List<?> localAds,
                            InertItemCallback callback){
  if(ads.isEmpty())return;
  items.addAll(position,ads);
  callback.result(null);
 }
}
""",
    "com/duowan/kiwi/immersepage/impl/data/IImmerseDataManager.java": """
package com.duowan.kiwi.immersepage.impl.data;
import java.util.ArrayList;
public interface IImmerseDataManager {
 interface InertItemCallback { void result(ArrayList<?> items); }
}
""",
    "com/duowan/HUYA/UserRecItem.java": """
package com.duowan.HUYA;
import java.util.ArrayList;
public class UserRecItem {
 public final Card tMCard=new Card();
 public static class Card { public final ArrayList<Object> vAdCard=new ArrayList<>(); }
}
""",
    "com/duowan/kiwi/universalslide/impl/adapter/UniversalSlideAdapter.java": """
package com.duowan.kiwi.universalslide.impl.adapter;
import java.util.ArrayList;
import java.util.List;
public class UniversalSlideAdapter {
 private List<?> filterSupportedItems(List<?> items){ return new ArrayList<>(items); }
}
""",
    "DisplayAdsTest.java": """
import java.util.*;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import android.content.SharedPreferences;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
import com.duowan.kiwi.crossplatform.base.webview.KiwiWebView;
import com.huya.hybrid.webview.HYWebView;
import com.duowan.HUYA.LiveRoomAdvertise;
import com.duowan.kiwi.livead.api.adbanner.view.AdLiveBannerView;
import com.duowan.kiwi.livead.api.adfloat.data.Advertisement;
import com.duowan.kiwi.livead.impl.adfloat.module.RevenueModule;
import com.duowan.kiwi.universal.live.pubscreen.biz.UniversalLiveAdFloat;
import com.duowan.kiwi.adsplash.controller.AdRouter;
import com.duowan.kiwi.ad.impl.HyAdModule;
import com.duowan.kiwi.list.patface.chain.PatFaceInterceptorChain;
import com.duowan.kiwi.listframe.component.LineItem;
import com.duowan.kiwi.list.component.RecommendAdComponent;
import com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendPresenter;
import com.duowan.kiwi.immersepage.api.data.ImmerseItem;
import com.duowan.kiwi.immersepage.api.data.ImmerseItemType;
import com.duowan.kiwi.immersepage.impl.data.IImmerseDataManager.InertItemCallback;
import com.duowan.kiwi.immersepage.impl.data.ImmerseDataManagerImpl;
import com.duowan.kiwi.universalslide.impl.adapter.UniversalSlideAdapter;
import com.duowan.HUYA.UserRecItem;
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
import com.duowan.kiwi.interaction.api.data.ComponentPanelItemInfo;
import com.duowan.kiwi.interaction.impl.view.UniversalComponentNavigationView;
import com.duowan.biz.util.OrientationData;
import com.duowan.kiwi.inputbar.api.view.InputEntryData;
import com.duowan.kiwi.inputbar.api.view.entryview.base.BottomBarEntryListView;
import com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendFragment;
import com.duowan.kiwi.list.homepage.tab.recommend.GameRecommendFragment;
import com.duowan.kiwi.list.vo.LiveGridViewObject;
import com.duowan.kiwi.list.vo.lizard.LZCategoryViewObject;
import com.duowan.kiwi.listframe.RefreshListener.RefreshMode;
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
  public List<Object> vMomentCard=new ArrayList<>();
 }
 public static class User {
  public Card tMCard;
  public int iViewType;
  public String sTitle="normal live";
 }
 public static class Moment {
  public Object tVideoInfo=new Object();
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
 static final class CtorChain implements XposedModule.Chain {
  final Object target;
  CtorChain(Object target){this.target=target;}
  public java.lang.reflect.Executable getExecutable(){return null;}
  public Object getThisObject(){return target;}
  public List<Object> getArgs(){return Collections.emptyList();}
  public Object getArg(int index){throw new IndexOutOfBoundsException();}
  public Object proceed(){return null;}
  public Object proceed(Object[] args){return null;}
 }
 public static void main(String[] args) throws Throwable {
  HuyaCompatEntry entry=new HuyaCompatEntry();
  ClassLoader loader=DisplayAdsTest.class.getClassLoader();
  entry.onPackageReady(new Param(loader));
  if(args[0].equals("native-live-ads")&&args.length==3){
   Map<String,Boolean> settings=Map.of("live_ad_banner",Boolean.valueOf(args[1]),
     "live_ad_float",Boolean.valueOf(args[2]),"ads",false,"live_cards",false);
   Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
   prefs.setAccessible(true);
   prefs.set(entry,Proxy.newProxyInstance(loader,new Class<?>[]{SharedPreferences.class},
    (proxy,method,values)->settings.getOrDefault(values[0],(Boolean)values[1])));
  }
  if(args[0].equals("live-landscape-reward-shortcuts")){
   Map<String,Boolean> settings=Map.of("live_cards",Boolean.valueOf(args[1]),
     "live_landscape_sidebar",Boolean.valueOf(args[2]),"live_cart",false);
   Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
   prefs.setAccessible(true);
   prefs.set(entry,Proxy.newProxyInstance(loader,new Class<?>[]{SharedPreferences.class},
    (proxy,method,values)->settings.getOrDefault(values[0],(Boolean)values[1])));
  }
  if(args[0].equals("recommend-video")){
   Map<String,Boolean> settings=args.length==1?Map.of("ads",false)
     :Map.of("ads",false,"recommend_video",Boolean.valueOf(args[1]));
   Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
   prefs.setAccessible(true);
   prefs.set(entry,Proxy.newProxyInstance(loader,new Class<?>[]{SharedPreferences.class},
    (proxy,method,values)->settings.getOrDefault(values[0],(Boolean)values[1])));
  }
  if(args[0].equals("immerse-insert")||args[0].equals("sign-popup")||args[0].equals("offline-room")){
   Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
   prefs.setAccessible(true);
   prefs.set(entry,Proxy.newProxyInstance(loader,new Class<?>[]{SharedPreferences.class},
    (proxy,method,values)->"ads".equals(values[0])?Boolean.valueOf(args[1]):values[1]));
  }
  XposedModule.invokeHook(
   android.app.Activity.class.getDeclaredMethod("onCreate",android.os.Bundle.class),
   new ActivityChain(new android.app.Activity()));
  if(args[0].equals("recommend-video")){
   User tagged=new User();
   tagged.tMCard=new Card();
   tagged.tMCard.iCardType=1;
   tagged.tMCard.vMomentCard.add(new Moment());
   LineItem badgeVideo=new LineItem(new LZCategoryViewObject(tagged));
   User grid=new User();
   grid.iViewType=7;
   grid.tMCard=tagged.tMCard;
   LineItem gridVideo=new LineItem(new LiveGridViewObject(grid));
   LineItem regularLive=new LineItem(new LiveGridViewObject(tagged));
   LineItem ad=nativeAd();
   User missingVideo=new User();
   missingVideo.tMCard=new Card();
   missingVideo.tMCard.iCardType=1;
   LineItem otherMoment=new LineItem(new LZCategoryViewObject(missingVideo));
   List<?> input=List.of(regularLive,badgeVideo,otherMoment,gridVideo,ad);
   boolean filter=args.length>1&&Boolean.parseBoolean(args[1]);
   Class<?>[] signature={List.class,RefreshMode.class,int.class};
   GameRecommendFragment home=new GameRecommendFragment();
   for(RefreshMode mode:RefreshMode.values()){
    check(Boolean.TRUE.equals(call(home,"endRefresh",signature,input,mode,5)),"Refresh result must be preserved");
    check(home.items.equals(filter?List.of(regularLive,otherMoment,ad):input),"Only homepage VOD cards must be filtered");
   }
   BaseRecommendFragment anotherTab=new BaseRecommendFragment();
   call(anotherTab,"endRefresh",signature,input,RefreshMode.REPLACE_ALL,5);
   check(anotherTab.items.equals(input),"Other tabs must keep their videos");
   return;
  }
  if(args[0].equals("offline-room")){
   var view=new com.duowan.kiwi.liveend.impl.views.NotLivingView();
   var event=new com.duowan.kiwi.livead.api.adplugin.event.IPresenterAdEvent.ShowNotLiveAdEvent();
   call(view,"onShowStopLiveAdEvent",new Class<?>[]{event.getClass()},event);
   call(view,"playLiveRecord",new Class<?>[]{});
   check(view.ads==(Boolean.parseBoolean(args[1])?0:1),"offline-room ad switch ignored");
   check(view.replays==1,"offline-room replay was blocked");
   return;
  }
  if(args[0].equals("sign-popup")){
   KiwiWebView view=new KiwiWebView();
   for(String url:new String[]{
     "https://hd.huya.com/h5/welfare_center/free_gift_daily.html",
     "https://example.com/h5/welfare_center/index.html",
     "https://hd.huya.com/h5/welfare_center/index.html/other"}){
    call(view,"onPageFinished",new Class<?>[]{String.class},url);
   }
   check(view.injections==0,"unrelated page received the sign popup filter");
   String taskCenter="https://hd.huya.com/h5/welfare_center/index.html?source=mine";
   call(view,"onPageFinished",new Class<?>[]{String.class},taskCenter);
   check(view.finished==4,"page lifecycle did not complete");
   call(view,"onPageCommitVisible",new Class<?>[]{String.class},taskCenter);
   HYWebView unrelatedView=new HYWebView();
   call(unrelatedView,"onPageCommitVisible",new Class<?>[]{String.class},taskCenter);
   check(view.committed==1&&unrelatedView.committed==1,"page commit callback did not complete");
   check(view.injections==(Boolean.parseBoolean(args[1])?2:0),
         "task-center promotion filter did not respect the ad switch");
   return;
  }
  if(args[0].equals("native-live-ads")){
   boolean filterBanner=args.length==3&&Boolean.parseBoolean(args[1]);
   boolean filterFloat=args.length==3&&Boolean.parseBoolean(args[2]);
   AdLiveBannerView banner=new AdLiveBannerView();
   Object shown=call(banner,"showAd",new Class<?>[]{List.class,Map.class},List.of("ad"),Map.of());
   check(Boolean.valueOf(!filterBanner).equals(shown),"Banner must respect its own switch");
   check(banner.visible!=filterBanner,"Filtering must collapse the existing banner");
   check(banner.shows==(filterBanner?0:1)&&banner.hides==(filterBanner?1:0),
    "Use exactly one host action to show or hide the banner");

   RevenueModule revenue=new RevenueModule();
   call(revenue,"displayAdByMethod",
    new Class<?>[]{LiveRoomAdvertise.class,Advertisement.class,long.class,Map.class},
    new LiveRoomAdvertise(),new Advertisement(),0L,Map.of());
   check(revenue.displays==(filterFloat?0:1),"Float must respect its own switch");
   UniversalLiveAdFloat overlay=new UniversalLiveAdFloat();
   call(overlay,"changeFloatAdVisibilityIfNeed",new Class<?>[]{boolean.class},true);
   check(overlay.visible!=filterFloat,"Float layout must use the effective visibility");
   call(overlay,"changeFloatAdVisibilityIfNeed",new Class<?>[]{boolean.class},false);
   check(!overlay.visible&&overlay.updates==2,"Float layout must still process visibility changes");
  }else if(args[0].equals("live-cards")){
   PopupModule module=new PopupModule();
   for(String key:new String[]{"magicboxrecentresult_autotrigger",
     "giftblindbox_autotrigger","adrewardtasks_autotrigger","gamepad_autotrigger",
     "gamead_autotrigger","cardcollectionactivity_streamertrigger"}){
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
     "shopplaymate_autotrigger","cardcollectionactivity_streamertrigger"}){
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
   for(boolean landscape:new boolean[]{false,true}){
    for(int id:new int[]{317,201,175,425,8675311}){
     for(int type:new int[]{0,1,2,3}){
      ActCommEnt entryData=new ActCommEnt(id);
      entryData.iType=type;
      int before=manager.attachedCards;
      call(manager,"createFloatWindowItemView",types,null,null,entryData,0,landscape);
      check(manager.attachedCards==before,"All server-pushed activity types must be filtered");
      call(manager,"createFloatWindowItemView",types,null,new MiniAppPopupFragment(),entryData,0,landscape);
      check(manager.attachedCards==before+1,"An open mini app can still be minimized");
     }
    }
   }
  }else if(args[0].equals("live-campaign-shortcuts")){
   UniversalComponentNavigationView nav=new UniversalComponentNavigationView();
   Class<?>[] types={List.class};
   ComponentPanelItemInfo phone=new ComponentPanelItemInfo(36305,"魔奖时刻",null);
   ComponentPanelItemInfo phoneByRoute=new ComponentPanelItemInfo(50001,"活动",
    "https://zt.huya.com/688005a6/mobile/index.html?source=live");
   ComponentPanelItemInfo cards=new ComponentPanelItemInfo(50002,"集卡领虎牙币",null);
   ComponentPanelItemInfo cardsByRoute=new ComponentPanelItemInfo(50003,"活动",
    "https://zt.huya.com/31bf1210/mobile/index.html?source=live");
   ComponentPanelItemInfo box=new ComponentPanelItemInfo(34211,"百宝箱",null);
   ComponentPanelItemInfo unknown=new ComponentPanelItemInfo(50004,"其他活动",
    "https://example.com/31bf1210/mobile/index.html");
   ComponentPanelItemInfo cart=new ComponentPanelItemInfo(50005,"小黄车",null);
   List<?> input=Collections.unmodifiableList(Arrays.asList(
    phone,box,phoneByRoute,cards,cart,unknown,cardsByRoute));
   call(nav,"setAllTimeLimitComps",types,input);
   check(nav.items.equals(Arrays.asList(box,unknown)),"Only the two campaigns should be removed");
   check(input.size()==7,"Campaign filtering must preserve the caller's list");
   call(nav,"setAllTimeLimitComps",types,Collections.singletonList(phone));
   check(nav.items.isEmpty(),"A promotion-only refresh must clear old entries");
   call(nav,"setAllTimeLimitComps",types,new Object[]{null});
   check(nav.items==null,"Null must use Huya's normal reset");
  }else if(args[0].equals("live-input-campaign-shortcuts")){
   BottomBarEntryListView bar=new BottomBarEntryListView();
   InputEntryData gift=new InputEntryData("礼物",null,1);
   InputEntryData fans=new InputEntryData("粉丝团",null,7);
   InputEntryData cards=new InputEntryData("集卡领虎牙币",null);
   InputEntryData cardsByRoute=new InputEntryData("活动",new OrientationData(
    null,"https://hd.huya.com/hyfe/revenue-business/cards-pot.html"));
   InputEntryData other=new InputEntryData("AI工坊",new OrientationData(
    "https://hd.huya.com/hyfe/AI-gift-202605/index.html",null));
   InputEntryData commercial=new InputEntryData("新活动",null,3);
   InputEntryData game=new InputEntryData("",null,4);
   InputEntryData hotPlay=new InputEntryData("守护幸运抽",null,10);
   InputEntryData newHotPlay=new InputEntryData("",null,10);
   InputEntryData cart=new InputEntryData("小黄车入口",null,6);
   InputEntryData cartByName=new InputEntryData("小黄车",null,0);
   List<?> input=Collections.unmodifiableList(Arrays.asList(
    gift,cards,other,cardsByRoute,game,hotPlay,fans,commercial,newHotPlay,cart,cartByName));
   call(bar,"refreshAllEntryView",new Class<?>[]{List.class},input);
   check(bar.items.equals(Arrays.asList(gift,other,fans)),"Remove promotion types and preserve unrelated entries");
   check(input.size()==11,"Input bar filtering must preserve the caller's list");
   call(bar,"refreshAllEntryView",new Class<?>[]{List.class},Arrays.asList(game,commercial,newHotPlay));
   check(bar.items.isEmpty(),"A promotion-only refresh must clear old input entries");
  }else if(args[0].equals("live-landscape-highlight-mark")){
   for(int initial:new int[]{android.view.View.INVISIBLE,android.view.View.VISIBLE,android.view.View.GONE}){
    var mark=new com.duowan.kiwi.livehighlightmark.impl.view.HighlightMarkView();
    mark.setVisibility(initial);
    var orientation=mark.getResources().getConfiguration();
    orientation.orientation=2;
    XposedModule.invokeHook(mark.getClass().getDeclaredConstructor(),new CtorChain(mark));
    check(mark.getVisibility()==android.view.View.GONE,"Landscape creation must hide the highlight mark");
    call(mark,"setVisible",new Class<?>[]{boolean.class},true);
    check(mark.getVisibility()==android.view.View.GONE,"Landscape setVisible(true) must stay hidden");
    orientation.orientation=1;
    mark.dispatchLayout();
    check(mark.getVisibility()==initial,"Portrait must restore the original highlight visibility");
    check(mark.containerVisible,"Hiding the mark must preserve the host's child view state");

    android.view.View root=new android.view.View();
    root.child=new android.view.View();
    root.child.setVisibility(initial);
    var update=HuyaCompatEntry.class.getDeclaredMethod("updateRightSidebarVisibility",android.view.View.class);
    update.setAccessible(true);
    root.getResources().getConfiguration().orientation=2;
    update.invoke(entry,root);
    check(root.child.getVisibility()==android.view.View.GONE,"Landscape must hide the right sidebar");
    root.getResources().getConfiguration().orientation=1;
    update.invoke(entry,root);
    check(root.child.getVisibility()==initial,"Portrait must restore the original sidebar visibility");
   }
  }else if(args[0].equals("live-landscape-reward-shortcuts")){
   UniversalComponentNavigationView nav=new UniversalComponentNavigationView();
   ComponentPanelItemInfo claimable=new ComponentPanelItemInfo(51001,"福利",null);
   claimable.info.tReminderInfo=new com.duowan.HUYA.interactiveComInfoReminder();
   claimable.info.tReminderInfo.sButton="可领取";
   ComponentPanelItemInfo normal=new ComponentPanelItemInfo(51002,"竞猜",null);
   ComponentPanelItemInfo reminder=new ComponentPanelItemInfo(51003,"预约",null);
   reminder.info.tReminderInfo=new com.duowan.HUYA.interactiveComInfoReminder();
   reminder.info.tReminderInfo.sButton="提醒我";
   List<?> input=Collections.unmodifiableList(Arrays.asList(claimable,normal,reminder));
   boolean sidebar=Boolean.parseBoolean(args[2]);
   List<?> expected=sidebar?Arrays.asList(normal,reminder):input;
   nav.landscape=true;
   call(nav,"setAllTimeLimitComps",new Class<?>[]{List.class},input);
   check(nav.items.equals(expected),"Landscape time-limited rewards must follow the sidebar switch");
   call(nav,"setComponentData",new Class<?>[]{List.class},input);
   check(nav.items.equals(expected),"Landscape component data must follow the sidebar switch");
   check(input.size()==3,"Reward filtering must preserve the caller's list");
   nav.landscape=false;
   call(nav,"setAllTimeLimitComps",new Class<?>[]{List.class},input);
   check(nav.items.equals(input),"Portrait must keep claimable rewards");
   HYExtRightTopWindowModeManager manager=new HYExtRightTopWindowModeManager();
   Class<?>[] types={IFloatWindowContainer.class,MiniAppPopupFragment.class,
     ActCommEnt.class,int.class,boolean.class};
   call(manager,"createFloatWindowItemView",types,null,null,new ActCommEnt(8675311),0,true);
   boolean hidePushed=sidebar||Boolean.parseBoolean(args[1]);
   check(manager.attachedCards==(hidePushed?0:1),"Pushed landscape cards must follow promotion or sidebar settings");
   call(manager,"createFloatWindowItemView",types,null,new MiniAppPopupFragment(),new ActCommEnt(8675311),0,true);
   check(manager.attachedCards==(hidePushed?1:2),"An open mini app must keep its floating window");
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
  }else if(args[0].equals("immerse-insert")){
   boolean blockAds=Boolean.parseBoolean(args[1]);
   ImmerseItem first=new ImmerseItem(ImmerseItemType.RECOMMEND_SINGLE_IMMERSION_LIVE);
   ImmerseItem next=new ImmerseItem(ImmerseItemType.RECOMMEND_SINGLE_IMMERSION_LIVE);
   ImmerseItem ad=new ImmerseItem(ImmerseItemType.HOT_LIVE_AD_VIDEO);
   ImmerseDataManagerImpl manager=new ImmerseDataManagerImpl();
   manager.items.addAll(List.of(first,next));
   int[] callbacks={0};
   call(manager,"insertAdIfNeed",
    new Class<?>[]{int.class,ArrayList.class,List.class,InertItemCallback.class},
    1,new ArrayList<>(List.of(ad)),List.of(),
    (InertItemCallback) ignored->callbacks[0]++);
   check(manager.items.equals(blockAds?List.of(first,next):List.of(first,ad,next)),
    "Ad insertion must follow the switch and preserve the live room order");
   check(callbacks[0]==(blockAds?0:1),"Only actual insertion should notify the adapter");
  }else if(args[0].equals("immerse-adapter")){
   UserRecItem first=new UserRecItem(), commercial=new UserRecItem();
   commercial.tMCard.vAdCard.add(new Object());
   ImmerseItem ordinary=new ImmerseItem(ImmerseItemType.VIDEO);
   ImmerseItem ad=new ImmerseItem(ImmerseItemType.LIVE_LIST_AD_VIDEO);
   UniversalSlideAdapter adapter=new UniversalSlideAdapter();
   List<?> input=List.of(first,commercial,ad,ordinary);
   List<?> result=(List<?>)call(adapter,"filterSupportedItems",new Class<?>[]{List.class},input);
   check(result.equals(List.of(first,ordinary)),
    "Neither live list ads nor immersive video ads should become swipe pages");
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

    @unittest.skipUnless(shutil.which("node"), "Node.js is required to execute the task-center script")
    def test_task_center_popup_filter_retries_after_its_module_appears(self):
        source = (ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java").read_text(encoding="utf-8")
        url = re.search(r'TASK_CENTER_URL\s*=\s*("[^"]+")', source)[1]
        constant = source.split("String TASK_CENTER_AD_SCRIPT =", 1)[1].split("\n\n", 1)[0]
        script = "".join(json.loads(part) for part in re.findall(r'"(?:[^"\\]|\\.)*"', constant.replace("TASK_CENTER_URL", url)))
        harness = "const script = " + json.dumps(script) + ";\nconst url = " + url + ";\n" + """
const assert = require('node:assert/strict');
const vm = require('node:vm');
const style = {
    ready: false,
    hasAttribute() { return this.ready; },
    setAttribute() { this.ready = true; },
};
let element;
let observers = 0;
let queued = 0;
let moduleReady = false;
let refreshTabs;
const completed = [];
const shown = [];
const hidden = [];
const queue = {
    state: { currentTask: null },
    enqueue() { queued++; },
    runPresent(task) { shown.push(task.meta.id); },
    complete(id) { completed.push(id); },
};
const layer = {};
const regularLayer = {};
const modal = { show(component) { shown.push(component); }, hide(component) { hidden.push(component); } };
const load = () => {
    if (!moduleReady) throw new Error('Popup dependency is still loading');
    return { A: queue };
};
const modules = { 90486: { Ay: modal }, 16205: { default: layer } };
const resolve = id => modules[id] || load(id);
resolve.m = { 90486: true, 16205: true };
resolve.O = (unused, chunks, ready) => ready();
const ad = { source: 'gold-coin', latestKey: 'gold-coin:index', payload: { iWindowType: 4 } };
const ordinary = { ...ad, payload: { iWindowType: 2 } };
const preloaded = { id: 'already-open', ...ad };
let mounted = false;
function classes() {
    const names = new Set();
    return {
        contains(name) { return names.has(name); },
        toggle(name, enabled) { if (enabled) names.add(name); else names.delete(name); },
    };
}
function section(titles, iconLabel = false) {
    const group = { active: 0, classList: classes() };
    group.tabs = titles.map((text, index) => ({
        textContent: iconLabel && index === 0 ? '' : text,
        classList: classes(),
        querySelector: () => iconLabel && index === 0 ? { alt: text } : null,
        getAttribute: name => name === 'aria-selected' && group.active === index ? 'true' : 'false',
        click: () => { group.active = index; },
    }));
    group.querySelectorAll = () => group.tabs;
    return group;
}
const mixed = section(['下载专区', '游戏活动', '联运活动'], true);
const downloadsOnly = section(['下载试玩']);
const manual = section(['游戏活动']);
const context = {
    location: new URL(url),
    document: {
        getElementById: () => element,
        createElement: () => style,
        head: { appendChild(node) { element = node; } },
        querySelectorAll: () => [mixed, downloadsOnly, manual],
        querySelector: selector => mounted && selector === '.layer-general-wrap' ? {} : null,
    },
    window: { rspackChunkwelfare_center: { push(chunk) { chunk[2](resolve); } } },
    MutationObserver: class {
        constructor(run) { refreshTabs = run; }
        observe() { observers++; }
    },
};
assert.equal(vm.runInNewContext(script, context), false);
assert.equal(mixed.classList.contains('huyaplus-hide-download-zone'), false);
assert.equal(mixed.tabs[0].classList.contains('huyaplus-hide-download-tab'), true);
assert.equal(mixed.tabs[1].classList.contains('huyaplus-hide-download-tab'), false);
assert.equal(mixed.active, 1);
assert.equal(downloadsOnly.classList.contains('huyaplus-hide-download-zone'), true);
assert.equal(manual.active, 0);
mixed.active = 0;
refreshTabs();
assert.equal(mixed.active, 1);
resolve.m[75015] = true;
assert.equal(vm.runInNewContext(script, context), false);
moduleReady = true;
queue.state.currentTask = preloaded;
assert.equal(vm.runInNewContext(script, context), true);
assert.deepEqual(hidden, []);
mounted = true;
refreshTabs();
refreshTabs();
assert.deepEqual(hidden, [layer]);
mounted = false;
const wrapped = queue.enqueue;
assert.equal(vm.runInNewContext(script, context), true);
assert.equal(queue.enqueue, wrapped);
assert.equal(observers, 1);
queue.enqueue(ad);
queue.enqueue({ source: 'ordinary' });
assert.equal(queued, 1);
queue.runPresent({ meta: { id: 'queued-ad', ...ad }, payload: ad.payload });
queue.runPresent({ meta: { id: 'sign-in', ...ordinary }, payload: ordinary.payload });
assert.deepEqual(completed, ['queued-ad']);
assert.deepEqual(shown, ['sign-in']);
modal.show(layer, { dataSource: ad.payload, onAfterClose: () => completed.push('already-active') });
const preserve = () => { throw new Error('normal modal closed'); };
modal.show(layer, { dataSource: ordinary.payload, onAfterClose: preserve });
modal.show(regularLayer, { dataSource: ad.payload, onAfterClose: preserve });
assert.deepEqual(completed, ['queued-ad', 'already-active']);
assert.deepEqual(shown, ['sign-in', layer, regularLayer]);
"""
        result = subprocess.run(["node", "-"], input=harness, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cold_and_hot_splash_use_the_no_display_route(self):
        self.run_case("splash")

    def test_automatic_promotion_stops_before_queuing_a_dialog(self):
        self.run_case("promotion")

    def test_automatic_live_cards_stop_before_queueing_and_keep_manual_entries(self):
        self.run_case("live-cards")

    def test_live_floating_ads_stop_before_native_queue_without_removing_reward_entries(self):
        self.run_case("live-floating-ads")

    def test_native_banner_and_float_filters_are_independent_and_opt_in(self):
        for switches in ((), ("false", "false"), ("true", "false"),
                         ("false", "true"), ("true", "true")):
            with self.subTest(switches=switches):
                self.run_case("native-live-ads", *switches)

    def test_automatic_placeholder_cards_cannot_bypass_the_popup_filter(self):
        self.run_case("live-placeholder-cards")

    def test_promotional_h5_and_miniapp_cards_do_not_attach_floating_windows(self):
        self.run_case("live-promotion-windows")

    def test_live_campaign_shortcuts_keep_non_promotional_buttons(self):
        self.run_case("live-campaign-shortcuts")

    def test_recommend_video_filter_is_opt_in_and_keeps_other_cards(self):
        for switches in ((), ("false",), ("true",)):
            with self.subTest(switches=switches):
                self.run_case("recommend-video", *switches)

    def test_live_input_campaign_shortcuts_keep_gift_and_other_entries(self):
        self.run_case("live-input-campaign-shortcuts")

    def test_landscape_live_room_hides_the_highlight_mark(self):
        self.run_case("live-landscape-highlight-mark")

    def test_landscape_live_room_hides_claimable_reward_shortcuts(self):
        for campaigns in ("false", "true"):
            for sidebar in ("false", "true"):
                with self.subTest(campaigns=campaigns, sidebar=sidebar):
                    self.run_case("live-landscape-reward-shortcuts", campaigns, sidebar)

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

    def test_swipe_ad_insertion_respects_the_ad_filter_switch(self):
        for enabled in ("false", "true"):
            with self.subTest(enabled=enabled):
                self.run_case("immerse-insert", enabled)

    def test_sign_popup_promotion_filter_is_scoped_to_task_center(self):
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                self.run_case("sign-popup", enabled)

    def test_offline_room_ad_is_blocked_before_playback_and_replay_stays_available(self):
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                self.run_case("offline-room", enabled)

    def test_swipe_feed_keeps_only_normal_items_from_both_data_formats(self):
        self.run_case("immerse-adapter")

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
