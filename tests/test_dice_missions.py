from pathlib import Path
import subprocess
import tempfile
import unittest

from test_huya_loader_lifecycle import ROOT, JDK, EXE

HARNESS = r'''
package io.github.saycm.huyaplus;
import java.util.*;
public class DiceMissionsTest {
 static TaskWire.Struct fields(Object... values){
  TaskWire.Struct result=new TaskWire.Struct();
  for(int index=0;index<values.length;index+=2)result.put((Integer)values[index],values[index+1]);
  return result;
 }
 static void check(boolean value,String detail){if(!value)throw new AssertionError(detail);}
 static class Host implements DiceMissionRunner.Host {
  long time,account=10;boolean enabled=true,drop,deny,duplicate;
  int claims,actions,finished,received,queries,total=1;int type=9;
  boolean taskOn=true,ready=true,badReward,marketConfirmed=true,marketRewardConfirmed=true;
  final Set<String> keys=new HashSet<>();final List<String> logs=new ArrayList<>();
  final PriorityQueue<Timer> timers=new PriorityQueue<>(Comparator.comparingLong(timer->timer.at));
  static class Timer{long at;Runnable run;Timer(long at,Runnable run){this.at=at;this.run=run;}}
  public long uid(){return account;}
  public boolean taskEnabled(DiceTaskCatalog.Task task){return enabled&&taskOn;}
  public boolean claim(String key){return keys.add(key);}
  public void log(String task,String state,String detail){logs.add(state+":"+detail);}
  public void later(long delay,Runnable run){timers.add(new Timer(time+delay,run));}
  public void publish(List<DiceTaskCatalog.Task> tasks){}
  public void perform(DiceTaskCatalog.Task task,NativeTaskRunner.ActionReply reply){
   actions++;
   if(type==5){
    check(task.marketVisit(),"unverified browsing task dispatched");
    if(marketConfirmed){received++;ready=total==1;}
   }else ready=true;
   reply.complete(true,"动作完成");
  }
  public void send(String endpoint,TaskWire.Struct request,NativeTaskRunner.Reply reply){
   if(endpoint.equals("getJumpGameTaskList")){
    if(type==9&&time>=60000)ready=true;
    queries++;
    String title=type==2?"去任意直播间送虎粮":type==6?"看视频领骰子":type==3?"金币商城兑换":
      type==5?"浏览游戏商城15s":"倒计时获得骰子";
    String taskId=type==5?"15":"server-task";
    String action=type==5?"https://huya.com?hyaction=welfarepage&fromid=goldtask&taskid=15":"";
    int status=type==5?(received>=total?2:ready?1:0):(received>0?2:ready?1:0);
    reply.complete(fields(0,Arrays.asList(fields(0,taskId,1,title,4,action,5,type,6,ready?60:0,
      7,60,8,received,9,total,10,status))),0);
    return;
   }
   check(endpoint.equals("claimJumpGameTaskReward"),"unexpected endpoint");
   check((type==5?"15":"server-task").equals(request.text(1)),"server task id lost");
   claims++;
   if(drop)return;
   if(deny){reply.complete(fields(),8);return;}
   if(type!=5||marketRewardConfirmed)received++;
   TaskWire.Struct response=fields(0,"ok",1,Arrays.asList(fields(0,1,3,badReward?0:1)));
   reply.complete(response,0);if(duplicate)reply.complete(response,0);
  }
  void advance(long until){
   while(!timers.isEmpty()&&timers.peek().at<=until){Timer timer=timers.poll();time=timer.at;timer.run.run();}
   time=until;
  }
 }
 public static void main(String[] args){
  Host host=new Host();String test=args[0];
  if(test.equals("countdown-fairness")){
   Host fair=new Host(){
    @Override public void send(String endpoint,TaskWire.Struct request,NativeTaskRunner.Reply reply){
     if(!endpoint.equals("getJumpGameTaskList")){
      super.send(endpoint,request,reply);return;
     }
     reply.complete(fields(0,Arrays.asList(
      fields(0,"timer",1,"倒计时15分钟",5,9,6,0,7,900,8,0,9,3,10,0),
      fields(0,"server-task",1,"看视频领骰子",5,6,6,ready?1:0,7,1,8,received,9,1,10,received>0?2:ready?1:0)
     )),0);
    }
   };
   fair.ready=false;
   new DiceMissionRunner(fair,5000,()->fair.finished++).start(10,"2099-01-01");
   fair.advance(30000);
   check(fair.actions==1&&fair.claims==1,"long countdown blocked other tasks");
   return;
  }
  if(test.equals("off"))host.taskOn=false;
  if(test.equals("countdown"))host.ready=false;
  if(test.equals("timeout"))host.drop=true;
  if(test.equals("deny"))host.deny=true;
  if(test.equals("duplicate"))host.duplicate=true;
  if(test.equals("bad-reward"))host.badReward=true;
  if(test.equals("gift")){host.type=2;host.ready=false;}
  if(test.equals("video")){host.type=6;host.ready=false;}
  if(test.equals("widget")){host.type=1;host.ready=false;}
  if(test.equals("browse")||test.equals("browse-unconfirmed")){host.type=5;host.ready=false;
   host.marketConfirmed=!test.equals("browse-unconfirmed");}
  if(test.equals("browse-multi")){host.type=5;host.ready=false;host.total=2;}
  if(test.equals("browse-claim-unconfirmed")){host.type=5;host.ready=false;
   host.marketConfirmed=false;host.marketRewardConfirmed=false;host.ready=true;}
  if(test.equals("home")||test.equals("home-ready")){host.type=8;host.ready=test.equals("home-ready");}
  if(test.equals("trial-ready"))host.type=4;
  if(test.equals("paid")){host.type=3;host.ready=false;}
  if(test.equals("widget")){
   List<DiceTaskCatalog.Task> visible=DiceTaskCatalog.read(fields(0,Arrays.asList(
     fields(0,"1",1,"添加桌面小组件",4,"https://m.huya.com?hyaction=newrn",5,1,
       6,0,7,1,8,0,9,1,10,0))));
   check(visible.isEmpty(),"removed widget task remains visible");
  }
  if(test.equals("home")){
   List<DiceTaskCatalog.Task> visible=DiceTaskCatalog.read(fields(0,Arrays.asList(
     fields(0,"home",1,"从首页进入任务中心",5,8,6,0,7,1,8,0,9,1,10,0),
     fields(0,"trial",1,"试玩小游戏",5,4,6,1,7,1,8,0,9,1,10,1),
     fields(0,"other",1,"浏览其他页面",5,5,6,1,7,1,8,1,9,1,10,2),
     fields(0,"timer",1,"倒计时获得骰子",5,9,6,0,7,60,8,0,9,1,10,0))));
   check(visible.size()==1&&visible.get(0).id.equals("timer"),
     "task list included unsupported tasks or removed a supported countdown");
  }
  DiceMissionRunner runner=new DiceMissionRunner(host,5000,()->host.finished++);
  runner.start(10,"2099-01-01");
  if(test.equals("changed"))host.account=11;
  host.advance(180000);
  if(Arrays.asList("off","paid","changed").contains(test))
   check(host.claims==0&&host.actions==0,"closed/paid/changed task ran");
  else if(Arrays.asList("widget","home","home-ready","trial-ready").contains(test)){
   check(host.claims==0&&host.actions==0,"unverified task dispatched an action or reward");
   check(host.queries==1&&host.logs.stream().noneMatch(value->value.startsWith("等待:")),
     "an unsupported task was scheduled");
  }else if(test.startsWith("browse")){
   check(host.actions==(test.equals("browse-claim-unconfirmed")?0:1),"market task submitted more than once");
   check(host.claims==(test.equals("browse-claim-unconfirmed")?1:0),
     "market reward request count changed");
   long success=host.logs.stream().filter(value->value.startsWith("成功:")).count();
   check(success==(test.equals("browse")||test.equals("browse-multi")?1:0),
     "market success must follow server claimed count");
   if(test.equals("browse-unconfirmed")||test.equals("browse-claim-unconfirmed"))
    check(host.logs.stream().anyMatch(value->value.startsWith("服务端未确认:")),
      "unconfirmed server progress must be reported");
  }else{
   check(host.claims==1,"reward not attempted exactly once");
   if(Arrays.asList("gift","video").contains(test))
    check(host.actions==1,"task action was not run");
   if(test.equals("countdown"))check(host.actions==0,"countdown incorrectly dispatched an action");
   if(test.equals("timeout")||test.equals("deny")||test.equals("bad-reward"))
    check(host.logs.stream().noneMatch(value->value.startsWith("成功:")),"failed claim marked successful");
   else check(host.logs.stream().filter(value->value.startsWith("成功:")).count()==1,"receipt credited twice");
  }
  check(host.finished==1,"completion callback did not finish");
 }
}
'''


class DiceMissionTests(unittest.TestCase):
    def test_real_tasks_use_switches_receipts_and_daily_deduplication(self):
        source = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus"
        self.assertTrue((source / "DiceMissionRunner.java").is_file(),
                        "Dice task switches do not have an execution runner")
        with tempfile.TemporaryDirectory(dir=ROOT / "build/test-tmp") as directory:
            folder = Path(directory)
            harness = folder / "DiceMissionsTest.java"
            harness.write_text(HARNESS, encoding="utf-8")
            subprocess.run(
                [str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8", "-d", str(folder),
                 *[str(source / (name + ".java")) for name in
                   ("TaskWire", "GlassSettings", "NativeTaskCatalog", "NativeTaskRunner",
                    "DiceTaskCatalog", "DiceMissionRunner")], str(harness)],
                check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for case in ("normal", "off", "timeout", "deny", "duplicate", "bad-reward",
                         "gift", "video", "widget", "browse", "browse-unconfirmed",
                         "browse-multi", "browse-claim-unconfirmed", "home", "home-ready",
                         "trial-ready", "paid", "changed",
                         "countdown-fairness", "countdown"):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(JDK / "bin" / ("java" + EXE)), "-Dfile.encoding=UTF-8", "-cp", str(folder),
                         "io.github.saycm.huyaplus.DiceMissionsTest", case],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
