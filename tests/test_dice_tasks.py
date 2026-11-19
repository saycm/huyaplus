"""Exercise receipt-driven dice execution against the real Java runner."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, JDK, EXE

HARNESS = r'''
package io.github.saycm.huyaplus;
import java.util.*;
public class DiceTasksTest {
 static TaskWire.Struct s(Object... fields) {
  TaskWire.Struct result=new TaskWire.Struct();
  for(int i=0;i<fields.length;i+=2)result.put((Integer)fields[i],fields[i+1]);
  return result;
 }
 static void check(boolean ok,String reason){if(!ok)throw new AssertionError(reason);}
 static class Host implements DiceTaskRunner.Host {
  long time,uid=12;boolean enabled=true,drop,deny,duplicate,malformed,refresh;
  int dice=2,pos=4,rolls,done;String map="map-a";
  final Set<String> claims=new HashSet<>();
  final List<String> logs=new ArrayList<>();final List<Long> sentAt=new ArrayList<>();
  final List<Long> allRequests=new ArrayList<>();
  final PriorityQueue<Timer> timers=new PriorityQueue<>(Comparator.comparingLong(t->t.at));
  static class Timer {long at;Runnable run;Timer(long a,Runnable r){at=a;run=r;}}
  public boolean enabled(){return enabled;}
  public long uid(){return uid;}
  public boolean claim(String key){return claims.add(key);}
  public void log(String state,String detail){logs.add(state+":"+detail);}
  public void later(long millis,Runnable run){timers.add(new Timer(time+millis,run));}
  public void send(String function,TaskWire.Struct request,NativeTaskRunner.Reply reply){
   allRequests.add(time);
   if(function.equals("getJumpGameModule")){
    reply.complete(malformed?s(0,2):s(0,dice,1,pos,2,s(0,map,4,Arrays.asList(s(0,4),s(0,17)))),0);return;
   }
   if(function.equals("getJumpGameDiceCount")){reply.complete(s(0,dice),0);return;}
   check(function.equals("rollJumpGameDice"),"unexpected endpoint "+function);
   check(map.equals(request.text(1))&&request.number(2)==pos&&request.number(3)==17,
      "roll did not use server map and position");
   rolls++;sentAt.add(time);
   if(drop)return;
   if(deny){reply.complete(s(3,"任务不可用"),9);return;}
   dice--;pos+=3;if(refresh){map="map-b";pos=4;}
   TaskWire.Struct result=s(0,3,1,pos,2,100,3,"",6,refresh?1:0,7,1);
   reply.complete(result,0);if(duplicate)reply.complete(result,0);
  }
  void advance(long until){while(!timers.isEmpty()&&timers.peek().at<=until){
   Timer t=timers.poll();time=t.at;t.run.run();}time=until;}
 }
 public static void main(String[] args){
  Host h=new Host();String test=args[0];
  if(test.equals("empty"))h.dice=0;
  if(test.equals("timeout"))h.drop=true;
  if(test.equals("denied"))h.deny=true;
  if(test.equals("duplicate"))h.duplicate=true;
  if(test.equals("map-refresh"))h.refresh=true;
  if(test.equals("malformed"))h.malformed=true;
  if(test.equals("disabled"))h.enabled=false;
  DiceTaskRunner runner=new DiceTaskRunner(h,30000,()->h.done++);
  if(test.equals("new-inventory")){
   h.dice=0;runner.start(12,"2099-01-01");h.advance(300000);
   h.dice=2;
   new DiceTaskRunner(h,30000,()->h.done++).start(12,"2099-01-01");
   h.advance(600000);
   check(h.rolls==2,"newly acquired dice were blocked by daily deduplication");
   return;
  }
  runner.start(12,"2099-01-01");runner.start(12,"2099-01-01");
  if(test.equals("account-change"))h.uid=99;
  h.advance(300000);
  if(Arrays.asList("normal","duplicate","map-refresh").contains(test)){
   check(h.rolls==2,"free dice were not consumed exactly once");
   check(h.sentAt.equals(Arrays.asList(30000L,90000L)),"roll interval not honored");
   for(int i=1;i<h.allRequests.size();i++)check(h.allRequests.get(i)-h.allRequests.get(i-1)>=30000,
      "query or roll request was sent before the configured interval");
   check(h.logs.stream().filter(x->x.startsWith("成功:")).count()==2,"unconfirmed or duplicate success");
   new DiceTaskRunner(h,30000,()->{}).start(12,"2099-01-01");h.advance(600000);
   check(h.rolls==2,"same-day restart repeated rolls");
  }else if(Arrays.asList("timeout","denied").contains(test)){
   check(h.rolls==1,"failed request was retried");
   check(h.logs.stream().noneMatch(x->x.startsWith("成功:")),"failure reported success");
  }else check(h.rolls==0,"disabled, invalid or empty task sent a roll");
  check(h.done==1,"completion callback did not run exactly once");
 }
}
'''


class DiceTasksTests(unittest.TestCase):
    def test_dice_receipts_intervals_and_duplicate_protection(self):
        source = ROOT / 'tools/huya-compat-src/io/github/saycm/huyaplus'
        self.assertTrue((source / 'DiceTaskRunner.java').exists(),
                        'The receipt-driven free dice task has not been implemented')
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/test-tmp') as directory:
            folder = Path(directory)
            harness = folder / 'DiceTasksTest.java'
            harness.write_text(HARNESS, encoding='utf-8')
            # NativeTaskRunner.Reply is the existing transport callback type.
            subprocess.run([str(JDK / 'bin' / ('javac' + EXE)), '-encoding', 'UTF-8', '-d', str(folder),
                            str(source / 'TaskWire.java'), str(source / 'GlassSettings.java'),
                            str(source / 'NativeTaskCatalog.java'), str(source / 'NativeTaskRunner.java'),
                            str(source / 'DiceTaskRunner.java'), str(harness)], check=True,
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for case in ['normal', 'empty', 'timeout', 'denied', 'duplicate', 'map-refresh',
                         'malformed', 'disabled', 'account-change', 'new-inventory']:
                with self.subTest(case=case):
                    result = subprocess.run([str(JDK / 'bin' / ('java' + EXE)), '-cp', str(folder),
                                             'io.github.saycm.huyaplus.DiceTasksTest', case],
                                            capture_output=True, text=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
