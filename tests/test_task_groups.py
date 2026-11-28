"""Removed categories must not reach the task switches or execution queue."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, JDK, EXE

HARNESS = r'''
package io.github.saycm.huyaplus;
import java.util.*;
public class TaskGroupsTest {
 static TaskWire.Struct s(Object... fields){
  TaskWire.Struct result=new TaskWire.Struct();
  for(int i=0;i<fields.length;i+=2)result.put((Integer)fields[i],fields[i+1]);return result;
 }
 static TaskWire.Struct user(long id,String title,int type){
  return s(0,id,1,1,2,1,3,0,4,0,5,title,28,type);
 }
 static TaskWire.Struct group(String title,int type,TaskWire.Struct... tasks){
  return s(0,title,1,Arrays.asList(tasks),2,type);
 }
 static TaskWire.Struct page(TaskWire.Struct... groups){
  return s(1,Arrays.asList(s(0,14,1,TaskWire.encode(s(0,Arrays.asList(groups))))));
 }
 static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);}
 public static void main(String[] args){
  TaskWire.Struct day=group("每日赚金币",1,user(1,"整点领金币",0),user(2,"饭点领金币补贴",60));
  if("selected".equals(args[0])){
   TaskWire.Struct hourly=user(1,"整点领金币",1);
   hourly.put(4,2);
   TaskWire.Struct meal=user(2,"饭点领金币补贴",34);
   meal.put(4,2);
   TaskWire.Struct surprise=user(3,"手慢无！必领468金币",34);
   surprise.put(4,2);
   surprise.put(14,"https://hd.huya.com/h5/welfare_center/free_gift_daily.html?hideBar=0");
   TaskWire.Struct chat=user(4,"发送1条弹幕",1);
   chat.put(4,2);
   chat.put(14,"https://www.huya.com/998?hyaction=live");
   TaskWire.Struct envelope=s(0,"看广告开金币红包",1,2,2,6);
   TaskWire.Struct mixed=s(0,"红包",2,6,4,Arrays.asList(s(0,4,1,TaskWire.encode(envelope))));
   List<NativeTaskCatalog.Task> tasks=NativeTaskCatalog.readDailyGold(page(
     group("每日赚金币",1,hourly,meal,surprise,chat,user(9,"关注主播并看播5分钟",41)),mixed));
   check(tasks.size()==2,"only hourly and meal rewards should remain");
   check(tasks.get(0).title.equals("整点领金币")&&tasks.get(1).title.equals("饭点领金币补贴"),
     "unexpected daily gold switches");
   for(String removed:Arrays.asList("发送1条弹幕","手慢无！必领468金币","看广告开金币红包")){
    check(!NativeTaskCatalog.isDailyGoldTask(removed),"cached task still visible: "+removed);
   }
   check(tasks.get(0).skipReason().isEmpty(),"claimable hourly task was skipped");
   check(!tasks.get(1).skipReason().isEmpty(),"unverified meal flow must stay blocked");
   hourly.put(2,0);
   check(!NativeTaskCatalog.readDailyGold(page(group("每日赚金币",1,hourly)))
     .get(0).skipReason().isEmpty(),"unearned hourly reward was enabled");
  }else if("groups".equals(args[0])){
   for(String title:Arrays.asList("玩游戏赚金币","玩游戏 赚金币","限时活动","浏览APP赚金币","浏览 APP 赚金币","流量app赚金币")){
    List<NativeTaskCatalog.Task> tasks=NativeTaskCatalog.read(page(day,group(title,1,user(3,"已完成任务",0))));
    check(tasks.size()==2,"removed category entered catalog: "+title);
   }
   for(int type:new int[]{12,15,19}){
    TaskWire.Struct removed=s(0,"已排除分组",2,type,3,new byte[]{(byte)255});
    check(NativeTaskCatalog.read(page(day,removed)).size()==2,"removed payload was decoded");
   }
  }else{
   TaskWire.Struct coop=user(3,"去QQ阅读领福利",7);
   coop.put(14,"https://m.huya.com?hyaction=launchcooptask");
   List<NativeTaskCatalog.Task> tasks=NativeTaskCatalog.read(page(group("每日赚金币",1,user(1,"整点领金币",0),coop)));
   check(tasks.size()==1&&tasks.get(0).id==1,"vendor task leaked into daily task group");
  }
 }
}
'''


class TaskGroupTests(unittest.TestCase):
    def test_removed_categories_never_enter_catalog(self):
        source = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/test-tmp') as directory:
            folder = Path(directory)
            harness = folder / 'TaskGroupsTest.java'
            harness.write_text(HARNESS, encoding='utf-8')
            result = subprocess.run(
                [str(JDK / 'bin' / ('javac' + EXE)), '-encoding', 'UTF-8', '-d', str(folder),
                 *[str(source / (name + '.java')) for name in
                   ('TaskWire', 'GlassSettings', 'NativeTaskCatalog')], str(harness)],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ('groups', 'vendor', 'selected'):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(JDK / 'bin' / ('java' + EXE)), '-Dfile.encoding=UTF-8', '-cp', str(folder),
                         'io.github.saycm.huyaplus.TaskGroupsTest', case],
                        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_detail_opens_two_task_pages_with_existing_theme(self):
        source = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'
        panel = (source / 'AutomationPanel.java').read_text(encoding='utf-8')
        self.assertIn('TaskSettingsActivity.class', panel)
        self.assertIn('"骰子任务"', panel)
        self.assertIn('"每日赚金币"', panel)
        activity = source / 'TaskSettingsActivity.java'
        self.assertTrue(activity.exists())
        text = activity.read_text(encoding='utf-8')
        self.assertIn('SystemBarInsets.apply', text)
        self.assertIn('GlassSettingsBridge.connect', text)
        for name in ('AppDetailActivity', 'TaskSettingsActivity'):
            page = (source / (name + '.java')).read_text(encoding='utf-8')
            resume = page.split('@Override protected void onResume()', 1)[1].split('\n    }', 1)[0]
            self.assertIn('GlassSettingsBridge.connect', resume)
            self.assertIn('!isFinishing() && !isDestroyed()', resume)
        manifest = (ROOT / 'tools/huya-module-src/AndroidManifest.xml').read_text(encoding='utf-8')
        self.assertIn('android:name=".TaskSettingsActivity"', manifest)
        layout = (ROOT / 'tools/huya-module-src/res/layout/activity_task_settings.xml').read_text(encoding='utf-8')
        self.assertIn('@drawable/dashboard_background', layout)
        self.assertIn('@drawable/glass_card', layout)

    def test_stale_catalog_rows_are_discarded_without_touching_claims(self):
        source = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'
        store = (source / 'LocalTaskStore.java').read_text(encoding='utf-8')
        self.assertIn('"fuckad_daily_tasks.db", null, 7', store)
        self.assertIn('if (oldVersion < 3) db.delete("tasks", null, null);', store)
        self.assertNotIn('if (oldVersion < 3) db.delete("runs"', store)
        self.assertIn('if (oldVersion < 5) createGiftPlans(db);', store)
        self.assertIn('if (oldVersion < 6) {\n            createTaskScope(db);\n'
                      '            db.delete("tasks", null, null);', store)
        self.assertIn('WHERE slot = 1 AND scope = ?', store)
        provider = (source / 'TaskLogProvider.java').read_text(encoding='utf-8')
        self.assertIn('"daily_tasks.db", null, 7', provider)
        self.assertIn('if (oldVersion < 6) db.delete("tasks", null, null);', provider)
        self.assertIn('WHERE updated >= ? AND updated < ?', provider)
        self.assertIn('ZoneId.of("Asia/Shanghai")', provider)
        self.assertIn('entry.getInt("catalog_version", 0) != NativeTaskCatalog.VERSION', provider)
