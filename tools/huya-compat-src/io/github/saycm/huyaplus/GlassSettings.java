package io.github.saycm.huyaplus;

import java.util.Locale;

public final class GlassSettings {
    public static final String PREFS = "glass_settings";
    static final String MODULE_PROVIDER = "io.github.saycm.huyaplus.tasks";
    static final String VERIFY_ROOT = "verify_root";
    static final String ROOT_GRANTED = "root_granted";
    public static final String KEY_ADS = "ads";
    public static final String KEY_LIVE_CARDS = "live_cards";
    public static final String KEY_LIVE_AD_BANNER = "live_ad_banner";
    public static final String KEY_LIVE_AD_FLOAT = "live_ad_float";
    public static final String KEY_REWARDS = "rewards";
    public static final String KEY_VIP_ADS = "vip_ads";
    public static final String KEY_VIP_4K = "vip_4k";
    public static final String KEY_LIVE_QUALITY = "live_quality_bitrate";
    public static final String KEY_AUTO_SIGN = "auto_sign";
    public static final String KEY_AUTO_GIFT = "auto_gift";
    public static final String KEY_GIFT_ROOMS = "gift_rooms";
    public static final String KEY_NATIVE_TASKS = "native_tasks";
    public static final String KEY_AUTO_DICE = "auto_dice";
    public static final String KEY_DICE_MISSIONS = "dice_missions";
    public static final String KEY_DICE_WELFARE_SIGN = "dice_welfare_sign";
    public static final String KEY_DICE_GIFT_ROOMS = "dice_gift_rooms";
    public static final String KEY_TASK_INTERVAL = "task_interval_seconds";
    public static final String KEY_TASK_ENABLED_PREFIX = "task_enabled_v1/";

    static boolean defaultEnabled(String key) {
        return !KEY_VIP_4K.equals(key)
                && !KEY_LIVE_AD_BANNER.equals(key)
                && !KEY_LIVE_AD_FLOAT.equals(key);
    }

    enum NavigationEntry {
        VIDEO("底栏 · 视频", 8),
        COMPETITION("底栏 · 赛事", 7),
        DISCOVERY("底栏 · 发现", 9),
        MALL("底栏 · 商城", 5),
        MALL_AI_FLOAT("商城 · 小虎 AI 管家浮标", -1);

        final String title;
        final String key;
        private final int tabType;

        NavigationEntry(String title, int tabType) {
            this.title = title;
            this.tabType = tabType;
            key = "navigation_hidden/" + name().toLowerCase(Locale.ROOT);
        }

        static NavigationEntry forTab(Object type) {
            for (NavigationEntry entry : values()) {
                if (entry.tabType >= 0 && Integer.valueOf(entry.tabType).equals(type)) return entry;
            }
            return null;
        }
    }

    enum MineEntry {
        FOLLOWING(0, "我的关注", "607"),
        HISTORY(0, "历史/收藏", "575"),
        ORDERS(0, "我的订单", "365"),
        RESERVATIONS(0, "我的预约", "473"),
        FAN_BADGE(0, "粉丝徽章", "581"),
        GUARD(0, "我的守护", "251"),
        NOBLE(0, "虎牙贵族", "257"),
        CREATOR(0, "创作中心", "405"),
        GAMES(1, "我的游戏", "281"),
        GAME_COACHING(1, "虎牙上分", "309"),
        MINI_GAMES(1, "在线小游戏", "275"),
        GAME_BAG(1, "福利背包", "541"),
        GAME_TOOLS(1, "游戏工具", ""),
        WORLDS_OUTFIT(2, "S赛限定装扮", ""),
        LUCKY_GO(2, "虎运GO", ""),
        HUYA_TV(2, "虎牙TV", "277"),
        STUDENT_AUTH(2, "高校生认证", "565"),
        MOUNTS(2, "我的坐骑", "269"),
        LIVE_DROPS(2, "直播掉宝", "285"),
        GAME_LINK(2, "游戏绑定中心", "291"),
        MINOR_PROTECTION(2, "未成年人保护", "299"),
        MERCHANDISE(2, "虎牙周边", "469"),
        DATA_SERVICE(2, "免流量服务", "279"),
        INVOICES(2, "发票管理", "307"),
        GIFT_CODES(2, "礼品兑换", "395"),
        BETA(2, "有奖内测", "311"),
        TALENT(2, "达人服务", ""),
        CUSTOMER_SERVICE(2, "联系客服", "295");

        final int group;
        final String title;
        final String key;
        private final String itemId;

        MineEntry(int group, String title, String itemId) {
            this.group = group;
            this.title = title;
            this.itemId = itemId;
            key = "mine_hidden/" + name().toLowerCase(Locale.ROOT);
        }

        static int groupOf(String id, String name) {
            if ("23".equals(id) || "游戏服务".equals(name)) return 1;
            if ("7".equals(id) || "17".equals(id) || "更多服务".equals(name)) return 2;
            if ("31".equals(id) || "13".equals(id) || "3".equals(id) || "我的身份".equals(name)) return 0;
            return -1;
        }

        boolean matches(int section, String id, String name) {
            return group == section && (title.equals(name) || (!itemId.isEmpty() && itemId.equals(id)));
        }
    }

    private GlassSettings() {
    }
}
