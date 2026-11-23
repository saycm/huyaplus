"""Run the live-room menu filtering rules against ordered menu data."""
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1]
          / "tools/huya-compat-src/io/github/saycm/huyaplus/LiveMenu.java")


class LiveMenuTest(unittest.TestCase):
    def test_hide_one_restore_and_hide_all(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            preferences = root / "SharedPreferences.java"
            preferences.write_text("""
package android.content;
import java.util.Map;
public interface SharedPreferences {
    Map<String, ?> getAll();
    Editor edit();
    interface Editor {
        Editor putBoolean(String key, boolean value);
        boolean commit();
    }
}
""", encoding="utf-8")
            harness = root / "LiveMenuTest.java"
            harness.write_text("""
package io.github.saycm.huyaplus;

import android.content.SharedPreferences;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class LiveMenuTest {
    public static void main(String[] args) {
        check(LiveMenu.Tool.values().length == 23);
        check("live_menu_hidden/tool/TIMED_OFF".equals(LiveMenu.Tool.TIMED_OFF.key));
        String chest = LiveMenu.activityKey(100, "百宝箱");
        String event = LiveMenu.activityKey(101, "新活动");
        String sameTitleEvent = LiveMenu.activityKey(102, "新活动");
        check(event.equals(LiveMenu.activityKey(101, "活动更名")));
        check(!event.equals(sameTitleEvent));
        String activity = LiveMenu.activityTitleKey("新活动");
        check(activity.equals(LiveMenu.activityTitleKey(" 新活动 ")));
        check(!activity.equals(LiveMenu.activityTitleKey("新活动2.0")));
        check(LiveMenu.resolveActivitySetting(event, "新活动", activity::equals).equals(activity));
        check(LiveMenu.resolveActivitySetting(event, "新活动", key -> false).equals(event));
        String local = LiveMenu.activityKey(0, "礼物墙");
        check(local.equals(LiveMenu.activityKey(0, " 礼物墙 ")));
        check(LiveMenu.activityKey(0, " ") == null);
        check(!LiveMenu.activityKey(-1, "互动节目").equals(LiveMenu.activityKey(-1, "新消息")));
        check(LiveMenu.activityTitleKey("大客户周榜-交友").equals(LiveMenu.activityTitleKey("大客户周榜")));
        String oldRankKey = "live_menu_hidden/activity/title/大客户周榜-交友";
        check(oldRankKey.equals(LiveMenu.resolveActivitySetting(event, "大客户周榜-交友", oldRankKey::equals)));
        check(!LiveMenu.isActivityKey(LiveMenu.Tool.SHARE.key));
        check(LiveMenu.isActivityKey(event) && LiveMenu.isActivityKey(local));
        Map<String, List<String>> groups = LiveMenu.activityGroups(Collections.emptyMap());
        check(groups.keySet().containsAll(Arrays.asList("一起摸鱼", "我要摸鱼", "荣耀远征", "甩雷大作战",
                "拉轰西游", "密友", "互动节目", "大客户周榜", "新消息", "粉丝连麦",
                "荣耀自走棋", "星秀臻享俱乐部", "PK贡献榜", "虎牙全明星")));
        Map<String, String> observed = new HashMap<>();
        observed.put(chest, "百宝箱");
        observed.put(event, "大客户周榜-交友");
        observed.put(LiveMenu.activityTitleKey("下发活动"), "下发活动");
        groups = LiveMenu.activityGroups(observed);
        check(groups.get("百宝箱").contains(chest));
        check(groups.get("大客户周榜").containsAll(Arrays.asList(event, oldRankKey)));
        check(!groups.containsKey("大客户周榜-交友") && groups.containsKey("下发活动"));

        List<String> original = Collections.unmodifiableList(Arrays.asList(chest, event, local));
        check(LiveMenu.filter(original, key -> key, event::equals).equals(Arrays.asList(chest, local)));
        check(LiveMenu.filter(original, key -> key, key -> false) == original);
        check(LiveMenu.filter(original, key -> key, key -> true).isEmpty());
        check(original.size() == 3);

        List<String> duplicates = Arrays.asList(event, chest, sameTitleEvent);
        check(LiveMenu.filter(duplicates,
                key -> LiveMenu.resolveActivitySetting(key, chest.equals(key) ? null : "新活动", activity::equals),
                activity::equals).equals(Collections.singletonList(chest)));
        check(LiveMenu.filter(duplicates,
                key -> LiveMenu.resolveActivitySetting(key, chest.equals(key) ? null : "新活动", activity::equals),
                event::equals) == duplicates);
        check(LiveMenu.filter(duplicates,
                key -> LiveMenu.resolveActivitySetting(key, chest.equals(key) ? null : "新活动", configured -> false),
                event::equals).equals(Arrays.asList(chest, sameTitleEvent)));

        String share = LiveMenu.Tool.SHARE.key;
        MemoryPreferences saved = new MemoryPreferences();
        MemoryPreferences framework = new MemoryPreferences();
        framework.edit().putBoolean(share, true).putBoolean("other_setting", true).commit();
        check(LiveMenu.syncVisibility(saved, framework));
        check(Boolean.TRUE.equals(saved.getAll().get(share)));
        check(!saved.getAll().containsKey("other_setting"));

        saved.edit().putBoolean(activity, true).putBoolean(share, false).commit();
        framework.fail = true;
        check(!LiveMenu.syncVisibility(saved, framework));
        check(Boolean.TRUE.equals(saved.getAll().get(activity)));
        check(Boolean.FALSE.equals(saved.getAll().get(share)));
        framework.fail = false;
        check(LiveMenu.syncVisibility(saved, framework));
        check(Boolean.TRUE.equals(framework.getAll().get(activity)));
        check(Boolean.FALSE.equals(framework.getAll().get(share)));
        framework.values.remove(activity);
        check(LiveMenu.syncVisibility(saved, framework));
        check(Boolean.TRUE.equals(framework.getAll().get(activity)));
        check(Boolean.TRUE.equals(framework.getAll().get("other_setting")));
    }

    private static final class MemoryPreferences implements SharedPreferences {
        final Map<String, Boolean> values = new HashMap<>();
        boolean fail;

        public Map<String, ?> getAll() {
            return new HashMap<>(values);
        }

        public Editor edit() {
            return new Editor() {
                final Map<String, Boolean> pending = new HashMap<>();

                public Editor putBoolean(String key, boolean value) {
                    pending.put(key, value);
                    return this;
                }

                public boolean commit() {
                    if (fail) return false;
                    values.putAll(pending);
                    return true;
                }
            };
        }
    }

    private static void check(boolean value) {
        if (!value) throw new AssertionError();
    }
}
""", encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-d", root, preferences, SOURCE, harness], check=True)
            subprocess.run(["java", "-cp", root, "io.github.saycm.huyaplus.LiveMenuTest"], check=True)


if __name__ == "__main__":
    unittest.main()
