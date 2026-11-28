package io.github.saycm.huyaplus;

import android.content.Context;
import android.os.Bundle;

import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Locale;
import java.util.UUID;
import java.text.SimpleDateFormat;

final class HookStatus {
    static final String REGISTERED = "registered";
    static final String PARTIAL = "partial";
    static final String DISABLED = "disabled";
    static final String WAITING = "waiting";
    static final String FAILED = "failed";
    private static final String MAIN_PROCESS = "com.duowan.kiwi";
    private static final String SESSION = UUID.randomUUID().toString();
    private static final long STARTED = System.currentTimeMillis();
    private static final Map<String, Bundle> features = new LinkedHashMap<>();
    private static Context context;

    static synchronized void start(Context current, String processName) {
        if (current == null || !MAIN_PROCESS.equals(processName)) return;
        Context application = current.getApplicationContext();
        context = application == null ? current : application;
        publish();
    }

    static synchronized void record(String feature, String state, String reason) {
        if (feature == null || feature.isEmpty() || !validState(state)) return;
        Bundle entry = new Bundle();
        entry.putString("feature", feature);
        entry.putString("state", state);
        entry.putString("reason", reason == null ? "" : reason);
        features.put(feature, entry);
        publish();
    }

    static boolean validState(String state) {
        return REGISTERED.equals(state) || PARTIAL.equals(state) || DISABLED.equals(state)
                || WAITING.equals(state) || FAILED.equals(state);
    }

    static String describe(Bundle status) {
        if (status == null || status.getString("session", "").isEmpty()) {
            return "等待宿主启动并上报\n尚无主进程会话记录；版本匹配不表示功能已加载。";
        }
        SimpleDateFormat time = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.CHINA);
        StringBuilder text = new StringBuilder("最近主进程会话 · ").append(status.getString("process", ""))
                .append("\n开始 ").append(time.format(new Date(status.getLong("started"))))
                .append(" · 上报 ").append(time.format(new Date(status.getLong("updated"))))
                .append("\n会话 ").append(status.getString("session", ""))
                .append("\n当前是否运行未确认；修改开关后重启虎牙更新。\n");
        ArrayList<Bundle> entries = status.getParcelableArrayList("features");
        if (entries == null || entries.isEmpty()) return text.append("\n等待宿主功能 Hook 上报").toString();
        for (Bundle entry : entries) {
            String state = entry.getString("state", "");
            String label = REGISTERED.equals(state) ? "Hook 已注册"
                    : PARTIAL.equals(state) ? "部分加载"
                    : DISABLED.equals(state) ? "已关闭"
                    : WAITING.equals(state) ? "等待宿主启动/功能入口"
                    : FAILED.equals(state) ? "加载失败" : "未知状态";
            text.append('\n').append(featureTitle(entry.getString("feature", ""))).append(" · ").append(label);
            String reason = entry.getString("reason", "");
            if (!reason.isEmpty()) text.append("\n  ").append(reason);
        }
        return text.append("\n\n“Hook 已注册”仅表示注册成功，功能效果以宿主实际行为为准。").toString();
    }

    private static String featureTitle(String feature) {
        switch (feature) {
            case "quality": return "默认清晰度";
            case "mine": return "我的页面";
            case "navigation": return "底栏入口";
            case "mall_ai_float": return "商城 AI 浮标";
            case "live_menu": return "直播间菜单";
            case "miniapp_ads": return "小程序广告与奖励";
            case "rewards": return "奖励直领";
            case "ads": return "开屏与推荐广告";
            case "recommend_video": return "首页推荐视频";
            case "task_center_promotions": return "任务中心推广";
            case "live_room_cards": return "直播间推广卡片";
            case "live_landscape_mark": return "横屏名场面";
            case "live_landscape_sidebar": return "横屏推广侧栏";
            case "live_red_packet": return "红包悬浮窗";
            case "live_week_star": return "周星组件";
            case "live_ad_banner": return "直播原生横幅";
            case "live_ad_float": return "直播原生浮窗";
            case "vip_ads": return "VIP 直播广告";
            case "vip_4k": return "VIP 4K 实验";
            case "daily_automation": return "每日任务调度";
            case "activation": return "模块启用校验";
            default: return feature;
        }
    }

    private static void publish() {
        if (context == null) return;
        Bundle status = new Bundle();
        status.putString("process", MAIN_PROCESS);
        status.putString("session", SESSION);
        status.putLong("started", STARTED);
        status.putLong("updated", System.currentTimeMillis());
        status.putParcelableArrayList("features", new ArrayList<>(features.values()));
        try { context.getContentResolver().call(TaskLogProvider.URI, "hook_status", null, status); }
        catch (RuntimeException unavailable) { /* A status display must not stop host hooks. */ }
    }

    private HookStatus() {}
}
