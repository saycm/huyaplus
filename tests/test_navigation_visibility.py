"""Exercise independent bottom-bar switches and the scoped mall float hook."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import EXE, JDK, ROOT, SDK, SOURCES


FIXTURES = {
    "android/view/ViewParent.java": """
package android.view;
public interface ViewParent { default ViewParent getParent(){return null;} }
""",
    "android/view/View.java": """
package android.view;
public class View {
 public static final int VISIBLE=0,GONE=8;
 private int visibility;
 private ViewParent parent;
 private OnAttachStateChangeListener listener;
 public interface OnAttachStateChangeListener {
  void onViewAttachedToWindow(View view);
  void onViewDetachedFromWindow(View view);
 }
 public void setVisibility(int value){visibility=value;}
 public int getVisibility(){return visibility;}
 public ViewParent getParent(){return parent;}
 public android.content.Context getContext(){return null;}
 public <T extends View> T findViewById(int id){return null;}
 public <T extends View> T findViewWithTag(Object tag){return null;}
 public void setTag(Object tag){}
 public interface OnClickListener { void onClick(View view); }
 public void setOnClickListener(OnClickListener listener){}
 public boolean isAttachedToWindow(){return parent!=null;}
 public void addOnAttachStateChangeListener(OnAttachStateChangeListener value){listener=value;}
 public void removeOnAttachStateChangeListener(OnAttachStateChangeListener value){if(listener==value)listener=null;}
 public void attach(ViewParent value){parent=value;if(listener!=null)listener.onViewAttachedToWindow(this);}
}
""",
    "android/widget/LinearLayout.java": """
package android.widget;
import android.view.View;
public class LinearLayout extends View {
 public View[] children={new View(),new View(),new View(),new View(),new View(),new View()};
 public float weight=6;
 public int getChildCount(){return children.length;}
 public View getChildAt(int position){return children[position];}
 public void setWeightSum(float value){weight=value;}
}
""",
    "com/duowan/yyprotocol/ResFile.java": "package com.duowan.yyprotocol; public class ResFile {}",
    "com/duowan/kiwi/homepage/IHomepageFragmentContainer.java": """
package com.duowan.kiwi.homepage;
public interface IHomepageFragmentContainer {
 class c { public final int h; public c(int type){h=type;} }
}
""",
    "com/duowan/kiwi/list/homepage/HomepageTabHelper.java": """
package com.duowan.kiwi.list.homepage;
import com.duowan.kiwi.homepage.*;
public class HomepageTabHelper {
 public CustomBar.d k(IHomepageFragmentContainer.c item){return new CustomBar.d();}
}
""",
    "com/duowan/kiwi/homepage/CustomBar.java": """
package com.duowan.kiwi.homepage;
import java.util.List;
import android.widget.LinearLayout;
import android.content.res.ColorStateList;
import com.duowan.yyprotocol.ResFile;
public class CustomBar {
 public final LinearLayout mTabContainer=new LinearLayout();
 public void init(List<?> items,ResFile skin,ColorStateList colors,boolean dark){}
 public void updateBarItem(List<?> items,int position){}
 public static class d {}
}
""",
    "com/facebook/react/ReactRootView.java": """
package com.facebook.react;
public class ReactRootView extends android.view.View implements android.view.ViewParent {
 private final String module;
 public ReactRootView(String name){module=name;}
 public String getJSModuleName(){return module;}
}
""",
    "com/facebook/react/views/view/ReactViewGroup.java": """
package com.facebook.react.views.view;
import com.facebook.react.uimanager.PointerEvents;
public class ReactViewGroup extends android.view.View {
 public PointerEvents getPointerEvents(){return PointerEvents.AUTO;}
}
""",
    "com/facebook/react/uimanager/PointerEvents.java": """
package com.facebook.react.uimanager;
public enum PointerEvents { AUTO,NONE }
""",
    "com/facebook/react/uimanager/BaseViewManager.java": """
package com.facebook.react.uimanager;
import android.view.View;
public class BaseViewManager {
 public void setNativeId(View view,String id){}
}
""",
    "NavigationVisibilityTest.java": """
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.view.*;
import com.duowan.kiwi.homepage.CustomBar;
import com.duowan.kiwi.homepage.IHomepageFragmentContainer;
import com.duowan.kiwi.list.homepage.HomepageTabHelper;
import com.duowan.yyprotocol.ResFile;
import com.facebook.react.ReactRootView;
import com.facebook.react.uimanager.BaseViewManager;
import com.facebook.react.uimanager.PointerEvents;
import com.facebook.react.views.view.ReactViewGroup;
import io.github.libxposed.api.XposedModule;
import io.github.saycm.huyaplus.HuyaCompatEntry;
import java.lang.reflect.*;
import java.util.*;

public class NavigationVisibilityTest {
 static void check(boolean condition,String message){
  if(!condition)throw new AssertionError(message);
 }
 public static void main(String[] args) throws Throwable {
  HuyaCompatEntry hook=new HuyaCompatEntry();
  Set<String> hidden=new HashSet<>();
  Field prefs=HuyaCompatEntry.class.getDeclaredField("prefs");
  prefs.setAccessible(true);
  prefs.set(hook,Proxy.newProxyInstance(NavigationVisibilityTest.class.getClassLoader(),
   new Class<?>[]{SharedPreferences.class},
   (proxy,method,a)->hidden.contains(a[0])||Boolean.TRUE.equals(a[1])));
  Method initialize=HuyaCompatEntry.class.getDeclaredMethod("initializeHooks",ClassLoader.class);
  initialize.setAccessible(true);
  initialize.invoke(hook,NavigationVisibilityTest.class.getClassLoader());
  CustomBar bar=new CustomBar();
  HomepageTabHelper helper=new HomepageTabHelper();
  List<Object> items=new ArrayList<>();
  for(int type:new int[]{5,1,7,4,8,9})
   items.add(XposedModule.call(helper,"k",new Class<?>[]{IHomepageFragmentContainer.c.class},
     new IHomepageFragmentContainer.c(type)));
  Class<?>[] init={List.class,ResFile.class,ColorStateList.class,boolean.class};
  XposedModule.call(bar,"init",init,items,null,null,false);
  check(bar.mTabContainer.weight==6,"Default should keep the host layout");
  String[] keys={"navigation_hidden/mall","navigation_hidden/competition","navigation_hidden/video",
    "navigation_hidden/discovery"};
  int[] index={0,2,4,5};
  for(int selected=0;selected<keys.length;selected++){
   hidden.add(keys[selected]);
   XposedModule.call(bar,"updateBarItem",new Class<?>[]{List.class,int.class},items,1);
   for(int i=0;i<bar.mTabContainer.getChildCount();i++)
    check(bar.mTabContainer.getChildAt(i).getVisibility()==(i==index[selected]?View.GONE:View.VISIBLE),
      "Only the selected navigation item should be hidden");
   check(bar.mTabContainer.weight==5,"Visible tabs must fill the bottom bar");
   hidden.clear();
  }
  hidden.addAll(Arrays.asList(keys));
  XposedModule.call(bar,"init",init,items,null,null,false);
  check(bar.mTabContainer.weight==2&&bar.mTabContainer.getChildAt(1).getVisibility()==View.VISIBLE
    &&bar.mTabContainer.getChildAt(3).getVisibility()==View.VISIBLE,
    "Home and Mine must remain when all four switches are enabled");
  hidden.clear();
  XposedModule.call(bar,"init",init,items,null,null,false);
  check(bar.mTabContainer.weight==6,"Turning off the switches must restore the full bar");
  hidden.add("navigation_hidden/mall_ai_float");
  BaseViewManager manager=new BaseViewManager();
  Class<?>[] setId={View.class,String.class};
  ReactViewGroup floatButton=new ReactViewGroup();
  XposedModule.call(manager,"setNativeId",setId,floatButton," ");
  floatButton.attach(new ReactRootView("MallTab"));
  check(floatButton.getVisibility()==View.GONE,"Hide the mall AI floating button on mount");
  check(XposedModule.call(floatButton,"getPointerEvents",new Class<?>[0])==PointerEvents.NONE,
    "React Native must not route touches to the hidden floating button");
  ReactViewGroup otherPage=new ReactViewGroup();
  otherPage.attach(new ReactRootView("Other"));
  XposedModule.call(manager,"setNativeId",setId,otherPage," ");
  ReactViewGroup header=new ReactViewGroup();
  header.attach(new ReactRootView("MallTab"));
  XposedModule.call(manager,"setNativeId",setId,header,"mall-header");
  check(otherPage.getVisibility()==View.VISIBLE&&header.getVisibility()==View.VISIBLE,
    "Keep other pages and mall header controls visible");
  check(XposedModule.call(header,"getPointerEvents",new Class<?>[0])==PointerEvents.AUTO,
    "The mall header must remain interactive");
  hidden.clear();
  XposedModule.call(manager,"setNativeId",setId,floatButton," ");
  check(floatButton.getVisibility()==View.VISIBLE,"Restoring the floating button must work");
  check(XposedModule.call(floatButton,"getPointerEvents",new Class<?>[0])==PointerEvents.AUTO,
    "Restore the host touch behavior with the floating button");
 }
}
""",
}

class NavigationVisibilityTest(unittest.TestCase):
    def test_individual_navigation_and_mall_switches(self):
        with tempfile.TemporaryDirectory(prefix="huya-nav-") as directory:
            work = Path(directory)
            sources = []
            for name, content in {**SOURCES, **FIXTURES}.items():
                file = work / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
                sources.append(file)
            module = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
            android = SDK / "platforms/android-36/android.jar"
            classes = work / "classes"
            result = subprocess.run([
                JDK / "bin" / ("javac" + EXE), "-encoding", "UTF-8", "-cp", android,
                "-d", classes, *sources, module / "HuyaCompatEntry.java", module / "GlassSettings.java",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([
                JDK / "bin" / ("java" + EXE), "-cp", os.pathsep.join(map(str, (classes, android))),
                "NavigationVisibilityTest",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
