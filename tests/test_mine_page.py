"""Verify that both Mine page renderers receive only the selected removals."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import EXE, JDK, ROOT, SDK, SOURCES


FIXTURES = {
    "android/util/Pair.java": """
package android.util;
public class Pair<F,S> {
 public final F first;
 public final S second;
 public Pair(F first,S second){this.first=first;this.second=second;}
}
""",
    "com/duowan/HUYA/MyTabModuleInfo.java": """
package com.duowan.HUYA;
import java.util.ArrayList;
public class MyTabModuleInfo implements Cloneable {
 public String sId="",sName="";
 public Object tLeftItem,tGamePlayInfoModule;
 public ArrayList<Entry> vItems=new ArrayList<>(),vBottomItems=new ArrayList<>();
 public static class Entry {
  public String sId,sTitle;
  public Entry(String id,String title){sId=id;sTitle=title;}
 }
 public Object clone() throws CloneNotSupportedException {return super.clone();}
}
""",
    "com/duowan/HUYA/DynamicItem.java": """
package com.duowan.HUYA;
import java.util.*;
public class DynamicItem implements Cloneable {
 public String sTemplateUrl="?_name=MyTabNewFourEachLineModule";
 public Value tData=new Value();
 public Object clone() throws CloneNotSupportedException {return super.clone();}
 public static class Value implements Cloneable {
  public long lIntegar;
  public String sString="";
  public Map<String,Value> mpObject=new HashMap<>();
  public ArrayList<Value> vArray=new ArrayList<>();
  public Object clone() throws CloneNotSupportedException {return super.clone();}
 }
}
""",
    "com/duowan/kiwi/my/utils/MyTabModuleViewCreator.java": """
package com.duowan.kiwi.my.utils;
import android.content.Context;
import android.util.Pair;
import com.duowan.HUYA.MyTabModuleInfo;
public class MyTabModuleViewCreator {
 public MyTabModuleInfo rendered;
 private Pair<Boolean,Object> createByTemplateType(Context context,MyTabModuleInfo module) {
  rendered=module;
  return new Pair<>(true,null);
 }
}
""",
    "com/duowan/kiwi/my/MyRecordNew.java": """
package com.duowan.kiwi.my;
import android.content.Context;
import android.view.View;
import com.duowan.HUYA.DynamicItem;
public class MyRecordNew {
 public DynamicItem rendered;
 private View createLizardModuleView(Context context,DynamicItem module) {
  rendered=module;
  return null;
 }
}
""",
    "io/github/saycm/huyaplus/MinePageTest.java": """
package io.github.saycm.huyaplus;
import android.content.Context;
import android.content.SharedPreferences;
import android.util.Pair;
import com.duowan.HUYA.DynamicItem;
import com.duowan.HUYA.DynamicItem.Value;
import com.duowan.HUYA.MyTabModuleInfo;
import com.duowan.HUYA.MyTabModuleInfo.Entry;
import com.duowan.kiwi.my.MyRecordNew;
import com.duowan.kiwi.my.utils.MyTabModuleViewCreator;
import io.github.libxposed.api.XposedModule;
import java.lang.reflect.*;
import java.util.*;

public class MinePageTest {
 static void check(boolean condition,String message) {
  if(!condition) throw new AssertionError(message);
 }
 static Value number(long value) {Value v=new Value();v.lIntegar=value;return v;}
 static Value text(String value) {Value v=new Value();v.sString=value;return v;}
 static Value row(long id,String title) {
  Value v=new Value();
  v.mpObject.put("id",number(id));v.mpObject.put("title",text(title));
  return v;
 }
 static Object nativeRender(MyTabModuleViewCreator creator,MyTabModuleInfo module) throws Throwable {
  return XposedModule.call(creator,"createByTemplateType",
   new Class<?>[]{Context.class,MyTabModuleInfo.class},null,module);
 }
 static void lizardRender(MyRecordNew page,DynamicItem module) throws Throwable {
  XposedModule.call(page,"createLizardModuleView",
   new Class<?>[]{Context.class,DynamicItem.class},null,module);
 }
 public static void main(String[] args) throws Throwable {
  HuyaCompatEntry hook=new HuyaCompatEntry();
  Set<String> hidden=new HashSet<>();
  Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
  prefs.setAccessible(true);
  prefs.set(hook,Proxy.newProxyInstance(MinePageTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},
   (proxy,method,values)->hidden.contains(values[0])||Boolean.TRUE.equals(values[1])));
  Method initialize=HuyaCompatEntry.class.getDeclaredMethod("initializeHooks",ClassLoader.class);
  initialize.setAccessible(true);
  initialize.invoke(hook,MinePageTest.class.getClassLoader());
  MyTabModuleViewCreator creator=new MyTabModuleViewCreator();
  MyRecordNew page=new MyRecordNew();
  List<String> shortcuts=new ArrayList<>();
  for(GlassSettings.MineEntry entry:GlassSettings.MineEntry.values()){
   if(entry.group==0)shortcuts.add(entry.title);
  }
  check(shortcuts.equals(Arrays.asList("我的关注","历史/收藏","我的订单","我的预约",
    "粉丝徽章","我的守护","虎牙贵族","创作中心")),
   "The eight shortcuts need individual switches in display order");
  Set<String> keys=new HashSet<>();
  for(GlassSettings.MineEntry entry:GlassSettings.MineEntry.values()) {
   check(keys.add(entry.key),"Each switch must have its own key");
   MyTabModuleInfo module=new MyTabModuleInfo();
   module.sId=entry.group==0?"31":entry.group==1?"23":"7";
   Entry selected=new Entry("",entry.title);
   Entry untouched=new Entry("9900","未选中的入口");
   module.vItems.addAll(Arrays.asList(untouched,selected,untouched));
   module.vBottomItems.add(selected);
   DynamicItem item=new DynamicItem();
   item.tData.mpObject.put("id",number(entry.group==0?13:Long.parseLong(module.sId)));
   Value rows=new Value(),selectedRow=row(0,entry.title),untouchedRow=row(9900,"未选中的入口");
   rows.vArray.addAll(Arrays.asList(untouchedRow,selectedRow,untouchedRow));
   item.tData.mpObject.put("items",rows);
   nativeRender(creator,module);lizardRender(page,item);
   check(creator.rendered==module&&page.rendered==item,"Default must keep all rows");
   hidden.add(entry.key);
   nativeRender(creator,module);lizardRender(page,item);
   check(creator.rendered.vItems.equals(Arrays.asList(untouched,untouched))
     &&creator.rendered.vBottomItems.isEmpty(),"Native switch did not compact "+entry.title);
   check(page.rendered.tData.mpObject.get("items").vArray.equals(Arrays.asList(untouchedRow,untouchedRow)),
     "Lizard switch did not compact "+entry.title);
   check(module.vItems.size()==3&&module.vBottomItems.size()==1&&rows.vArray.size()==3,
     "Filtering changed the original page data");
   hidden.remove(entry.key);
   nativeRender(creator,module);lizardRender(page,item);
   check(creator.rendered==module&&page.rendered==item,"Disabling the switch must restore the row");
  }
  MyTabModuleInfo shortcutsGrid=new MyTabModuleInfo();
  shortcutsGrid.sId="31";
  shortcutsGrid.vItems.add(new Entry("607",""));
  shortcutsGrid.vItems.add(new Entry("575",""));
  shortcutsGrid.vItems.add(new Entry("581",""));
  hidden.addAll(Arrays.asList("mine_hidden/following","mine_hidden/history","mine_hidden/fan_badge"));
  check(Boolean.FALSE.equals(((Pair<?,?>)nativeRender(creator,shortcutsGrid)).first),
    "The new native shortcut IDs must be recognized and an empty grid must be omitted");
  hidden.clear();
  hidden.add(GlassSettings.MineEntry.GAMES.key);
  MyTabModuleInfo games=new MyTabModuleInfo();
  games.sName="游戏服务";
  games.vItems.add(new Entry("281","备用游戏标题"));
  check(Boolean.FALSE.equals(((Pair<?,?>)nativeRender(creator,games)).first),
    "A grid with all its rows hidden must be omitted");
  DynamicItem lizardGames=new DynamicItem();
  lizardGames.tData.mpObject.put("name",text("游戏服务"));
  Value rows=new Value();
  rows.vArray.add(row(281,"备用游戏标题"));
  lizardGames.tData.mpObject.put("items",rows);
  page.rendered=null;
  lizardRender(page,lizardGames);
  check(page.rendered==null,"A Lizard grid with all its rows hidden must be omitted");
  lizardGames.sTemplateUrl="?_name=MyTabSevenModule";
  lizardRender(page,lizardGames);
  check(page.rendered==lizardGames,"The separate My Games card must keep its original data");
  games.sName="我的游戏";
  nativeRender(creator,games);
  check(creator.rendered==games,"An unrelated native module must keep its original data");
 }
}
""",
}


class MinePageTest(unittest.TestCase):
    def test_individual_switches_filter_both_renderers_without_mutating_host_data(self):
        with tempfile.TemporaryDirectory(prefix="huya-mine-") as folder:
            work = Path(folder)
            sources = []
            for name, content in {**SOURCES, **FIXTURES}.items():
                file = work / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
                sources.append(file)
            module = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
            classes = work / "classes"
            android = SDK / "platforms/android-36/android.jar"
            result = subprocess.run([
                JDK / "bin" / ("javac" + EXE), "-encoding", "UTF-8", "-cp", android,
                "-d", classes, *sources, module / "HuyaCompatEntry.java",
                module / "GlassSettings.java",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([
                JDK / "bin" / ("java" + EXE), "-cp", os.pathsep.join(map(str, (classes, android))),
                "io.github.saycm.huyaplus.MinePageTest",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
