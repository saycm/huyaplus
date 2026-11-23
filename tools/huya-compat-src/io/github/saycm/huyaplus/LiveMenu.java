package io.github.saycm.huyaplus;

import android.content.SharedPreferences;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Function;
import java.util.function.Predicate;

final class LiveMenu {
    static final String CATALOG = "live_menu_catalog";
    static final String VISIBILITY = "live_menu_visibility";
    static final String REGISTER = "register_live_menu";
    private static final String PREFIX = "live_menu_hidden/";
    private static final String ACTIVITY_PREFIX = PREFIX + "activity/";
    static final int MAX_TITLE_LENGTH = 80;

    private static final String[] KNOWN_ACTIVITIES = {
            "AI工坊", "KNC", "PK段位赛", "PK贡献榜", "万境宝阁", "三角洲微光新赛季活动",
            "三角洲感恩节", "上热门", "一起摸鱼", "互动节目", "主播榜单", "和平精英 · 羊羊狂欢节",
            "大客户周榜", "守护幸运抽", "宝藏计划2.0", "密友", "小黄车", "带盐团",
            "年度全明星", "我是预言家", "我要摸鱼", "战争冲突", "拉轰西游", "新消息",
            "星秀臻享俱乐部", "欧皇时刻", "残局挑战", "浪漫约会", "甩雷大作战", "百宝箱",
            "礼物墙", "礼物宝箱", "神龙显世", "福袋", "粉丝连麦", "荣耀自走棋", "荣耀远征",
            "虎牙全明星", "虎牙王者对决", "虎翼上推荐", "虎运Go开箱", "观赛福利",
            "集五卡瓜分", "领主争霸", "魔奖时刻"
    };

    enum Tool {
        SHARE("分享"),
        BITRATE("清晰度"),
        BARRAGE_SETTING("弹幕设置"),
        TV_SCREEN("TV投屏"),
        LIVE_ROOM_BACKGROUND("直播间背景"),
        CLEAR_SCREEN("清屏"),
        FLOAT_WINDOW("小窗播放"),
        BACKGROUND_PLAY("后台播放"),
        NOT_INTERESTED("不看该主播"),
        NOT_INTERESTED_GAME("减少该分类"),
        TIMED_OFF("定时关闭"),
        ADD_DESKTOP("添加到桌面"),
        TIP_OFF("举报"),
        FEEDBACK("联系客服"),
        CONSUMER_TIP("消费助手"),
        ACCOMPANY("陪伴"),
        COMMENTARY("解说"),
        EFFECT("特效"),
        FM_ADMIN("房间管理"),
        LIVE_BARRAGE("直播字幕"),
        MUTE_AND_REPORT("禁言与举报"),
        TEAM_VOICE("组队语音"),
        VIDEO_SCALE("画面比例");

        final String title;
        final String key = toolKey(name());

        Tool(String title) {
            this.title = title;
        }
    }

    static String toolKey(String name) {
        return PREFIX + "tool/" + name;
    }

    static String activityKey(int componentId, String title) {
        if (componentId > 0) return ACTIVITY_PREFIX + "id/" + componentId;
        return activityTitleKey(title);
    }

    static String activityTitleKey(String title) {
        String label = activityTitle(title);
        return label.isEmpty() ? null : ACTIVITY_PREFIX + "title/" + label;
    }

    private static String legacyTitleKey(String title) {
        String label = title.trim();
        return label.isEmpty() ? null : ACTIVITY_PREFIX + "title/"
                + label.substring(0, Math.min(label.length(), MAX_TITLE_LENGTH));
    }

    static String activityTitle(String title) {
        String label = title.trim();
        if (label.startsWith("大客户周榜-") || label.startsWith("大客户周榜－")
                || label.startsWith("大客户周榜…")) return "大客户周榜";
        return label.substring(0, Math.min(label.length(), MAX_TITLE_LENGTH));
    }

    static Map<String, List<String>> activityGroups(Map<String, ?> observed) {
        Map<String, List<String>> groups = new TreeMap<>();
        for (String title : KNOWN_ACTIVITIES) groups.put(title, new ArrayList<>());
        for (Map.Entry<String, ?> item : observed.entrySet()) {
            if (!(item.getValue() instanceof String) || !isActivityKey(item.getKey())) continue;
            String rawTitle = (String) item.getValue();
            String title = activityTitle(rawTitle);
            if (!title.isEmpty()) {
                List<String> legacy = groups.computeIfAbsent(title, ignored -> new ArrayList<>());
                legacy.add(item.getKey());
                if (!title.equals(rawTitle)) legacy.add(legacyTitleKey(rawTitle));
            }
        }
        return groups;
    }

    static String resolveActivitySetting(String componentKey, String title, Predicate<String> configured) {
        if (title == null) return componentKey;
        String titleKey = activityTitleKey(title);
        if (titleKey != null && configured.test(titleKey)) return titleKey;
        String oldKey = legacyTitleKey(title);
        return oldKey != null && !oldKey.equals(titleKey) && configured.test(oldKey) ? oldKey : componentKey;
    }

    static boolean isActivityKey(String key) {
        return key.startsWith(ACTIVITY_PREFIX) && key.length() <= ACTIVITY_PREFIX.length() + 6 + MAX_TITLE_LENGTH;
    }

    static boolean syncVisibility(SharedPreferences saved, SharedPreferences remote) {
        Map<String, ?> previous = saved.getAll();
        SharedPreferences.Editor importExisting = null;
        for (Map.Entry<String, ?> entry : remote.getAll().entrySet()) {
            String key = entry.getKey();
            if (key.startsWith(PREFIX) && entry.getValue() instanceof Boolean && !previous.containsKey(key)) {
                if (importExisting == null) importExisting = saved.edit();
                importExisting.putBoolean(key, (Boolean) entry.getValue());
            }
        }
        if (importExisting != null && !importExisting.commit()) return false;
        if (previous.isEmpty()) return true;

        // The LSPosed writer updates its local cache before reporting Binder failures.
        SharedPreferences.Editor publish = remote.edit();
        for (Map.Entry<String, ?> entry : previous.entrySet()) {
            publish.putBoolean(entry.getKey(), (Boolean) entry.getValue());
        }
        return publish.commit();
    }

    static <T> List<T> filter(List<T> items, Function<T, String> keyOf, Predicate<String> hidden) {
        List<T> visible = new ArrayList<>(items.size());
        for (T item : items) {
            String key = keyOf.apply(item);
            if (key == null || !hidden.test(key)) visible.add(item);
        }
        return visible.size() == items.size() ? items : visible;
    }

    private LiveMenu() {}
}
