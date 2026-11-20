import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "io/github/saycm/huyaplus"


class QualitySessionTest(unittest.TestCase):
    def test_manual_selection_cancels_pending_and_auto_applies_once_per_room(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "QualitySessionTest.java"
            source.write_text("""package io.github.saycm.huyaplus;
public class QualitySessionTest {
 public static void main(String[] args) {
  QualitySession session = new QualitySession();
  int first = session.enter();
  if (!session.queue(first) || session.queue(first))
   throw new AssertionError("duplicate updates must share one pending attempt");
  session.dequeue(first);
  if (!session.queue(first))
   throw new AssertionError("an unready room must allow another attempt");
  if (!session.pending(first) || !session.claim(first) || session.claim(first))
   throw new AssertionError("automatic selection must run once");
  int second = session.enter();
  session.dequeue(first);
  if (!session.queue(second))
   throw new AssertionError("callbacks from an old room must not block the new room");
  if (session.pending(first) || !session.pending(second))
   throw new AssertionError("old room callbacks must be invalidated");
  session.manualSelection();
  if (session.pending(second) || session.claim(second))
   throw new AssertionError("manual selection must cancel automatic switching");
  int third = session.enter();
  if (!session.claim(third))
   throw new AssertionError("next room must enable automatic selection");

  if (session.claimNotice(second, 1000L))
   throw new AssertionError("a previous room must not show a notice");
  if (!session.claimNotice(third, 1000L) || session.claimNotice(third, 2000L))
   throw new AssertionError("a room must show at most one notice");
  int fourth = session.enter();
  session.queue(fourth);
  if (session.claimNotice(fourth, 3000L))
   throw new AssertionError("the notice must wait for the queued quality attempt");
  session.dequeue(fourth);
  session.manualSelection();
  if (!session.claimNotice(fourth, 3000L))
   throw new AssertionError("manual selection must not prevent reading the current quality");
  int fifth = session.enter();
  session.deferNotice(fifth, 4000L);
  if (session.claimNotice(fifth, 3999L) || !session.claimNotice(fifth, 4000L))
   throw new AssertionError("the notice must allow a requested switch to settle");

  int swipe = session.enterRoom(101L);
  if (session.roomId(swipe) != 101L || !session.pending(swipe) || session.matchesRoom(swipe, 100L)
    || !session.matchesRoom(swipe, 101L))
   throw new AssertionError("only the selected room's player may receive the new quality");
  session.manualSelection();
  if (session.enterRoom(101L) != 0 || session.pending(swipe))
   throw new AssertionError("a duplicate selection must preserve the manual setting");
  int next = session.enterRoom(102L);
  if (session.roomId(swipe) != -1L || session.matchesRoom(swipe, 101L) || !session.pending(next)
    || !session.matchesRoom(next, 102L))
   throw new AssertionError("swiping to a new room must cancel stale callbacks and re-enable auto quality");
 }
}""", encoding="utf-8")
            jdk = Path(os.environ["JAVA_HOME"]) / "bin"
            exe = ".exe" if os.name == "nt" else ""
            compiled = subprocess.run(
                [str(jdk / ("javac" + exe)), "-encoding", "UTF-8", "-d", str(root),
                 str(ROOT / "tools/huya-compat-src" / PACKAGE / "QualitySession.java"),
                 str(source)], capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(
                [str(jdk / ("java" + exe)), "-cp", str(root),
                 "io.github.saycm.huyaplus.QualitySessionTest"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
