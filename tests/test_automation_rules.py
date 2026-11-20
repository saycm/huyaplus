"""Exercise saved room/count validation without Android or account access."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_huya_loader_lifecycle import ROOT, JDK, EXE


class AutomationRulesTest(unittest.TestCase):
    def test_room_rules_validate_before_any_gift_is_sent(self):
        with tempfile.TemporaryDirectory(prefix="ad-rules-") as folder:
            root = Path(folder)
            harness = root / "RulesTest.java"
            harness.write_text('''
import io.github.saycm.huyaplus.AutomationRules;
import java.util.*;
public class RulesTest {
 static void plan(String config,int choice,String expected){
  StringJoiner actual=new StringJoiner(",");
  for(AutomationRules.GrainPart part:AutomationRules.planDiceGrain(
      AutomationRules.parse(config),bound->choice)){
   actual.add(part.room+"="+part.count+"@"+part.number+"/"+part.remaining);
  }
  if(!expected.equals(actual.toString()))throw new AssertionError(actual.toString());
 }
 public static void main(String[] args){
  plan("1=2",0,"");
  plan("1=8",0,"1=2@1/8,1=3@2/6,1=3@3/3");
  plan("1=4\\n2=7",0,"1=2@1/4,1=2@2/2,2=7@1/7");
  plan("1=4\\n2=7",1,"1=4@1/4,2=3@1/7,2=4@2/4");
  plan("1=1\\n2=3",0,"1=1@1/1,2=1@1/3,2=2@2/2");
  plan("1=1\\n2=1",0,"");
  plan("1=1\\n2=1\\n3=1",0,"1=1@1/1,2=1@1/1,3=1@1/1");
  plan("1=2\\n2=2\\n3=2\\n4=2",0,"");
  plan("1=all",0,"1=1@1/3,1=1@2/2,1=-1@3/1");
  plan("1=all\\n2=3",0,"2=3@1/3,1=1@1/2,1=-1@2/1");
  plan("1=all\\n2=3\\n3=1",0,"2=3@1/3,3=1@1/1,1=-1@1/1");
  if(!"2=3\\n1=all".equals(AutomationRules.normalize("1=all\\n2=3")))
   throw new AssertionError("remaining inventory room must run last");
  if(AutomationRules.giftCount(-1,1,15)!=15 || AutomationRules.giftCount(-1,1,0)!=0
    || AutomationRules.giftCount(-1,1,2147483648L)!=0
    || AutomationRules.giftCount(1,3,2)!=0 || AutomationRules.giftCount(2,2,5)!=2)
   throw new AssertionError("free inventory amount");
  if(!AutomationRules.parse("").isEmpty())throw new AssertionError("empty");
  if(AutomationRules.parse("123=2\\n456=3").get(456L)!=3)
   throw new AssertionError("counts");
  for(String value:new String[]{"0=1","-1=2","123=0","123=-2","123=1.5",
    "123=2147483648","abc=1","123", "123=1=2", "123=1\\n123=2", "123=all\\n456=all"}){
   try{AutomationRules.parse(value);throw new AssertionError("accepted "+value);}
   catch(IllegalArgumentException expected){}
  }
  if(!"123=2\\n456=3".equals(AutomationRules.normalize(" 123 = 2 \\n 456=3\\n")))
   throw new AssertionError("normalization");
  if(!AutomationRules.isFreeGrain(4,2,2,2,0,0))throw new AssertionError("free gift");
  if(AutomationRules.isFreeGrain(5,2,2,2,0,0)
    ||AutomationRules.isFreeGrain(4,0,2,2,0,0)
    ||AutomationRules.isFreeGrain(4,3,2,2,0,0)
    ||AutomationRules.isFreeGrain(4,2,2,0,0,0)
    ||AutomationRules.isFreeGrain(4,2,2,2,1,0)
    ||AutomationRules.isFreeGrain(4,2,2,2,0,1))throw new AssertionError("unsafe gift");
  if(!AutomationRules.isResolvedRoom(123,0,456)||!AutomationRules.isResolvedRoom(123,123,456)
    ||AutomationRules.isResolvedRoom(123,124,456)||AutomationRules.isResolvedRoom(123,0,0))
   throw new AssertionError("optional room number mapping");
 }
}
''', encoding="utf-8")
            source = ROOT / "tools/huya-compat-src/io/github/saycm/huyaplus/AutomationRules.java"
            compiled = subprocess.run(
                [str(JDK / "bin" / ("javac" + EXE)), "-encoding", "UTF-8",
                 "-d", str(root), str(source), str(harness)],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(JDK / "bin" / ("java" + EXE)), "-cp", str(root), "RulesTest"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
