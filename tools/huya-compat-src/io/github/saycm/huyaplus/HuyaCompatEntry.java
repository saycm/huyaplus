package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.Pair;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.webkit.ValueCallback;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Toast;

import org.json.JSONObject;

import java.lang.ref.WeakReference;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.URI;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Predicate;

import io.github.libxposed.api.XposedModule;

public final class HuyaCompatEntry extends XposedModule {
    private static final String TAG = "FuckAD";
    private static final String TARGET_PACKAGE = HuyaVersion.PACKAGE_NAME;
    private static final String TARGET_CLASS =
            "com.huya.kiwi.hyext.impl.modules.internal.HyExtAd";
    private static final String AMS_HELPER_CLASS =
            "com.duowan.kiwi.ad.helper.AmsAdHelper";
    private static final String AMS_LISTENER_CLASS =
            "com.huya.adbusiness.ams.IAmsAdRewardADListener";
    private static final String REWARD_RESULT_CLASS =
            "com.qq.e.tg.rewardAD.RewardResult";
    private static final String AD_SPLASH_FRAGMENT_CLASS =
            "com.duowan.kiwi.adsplash.view.AdSplashFragment";
    private static final String AWARD_MANAGER_CLASS =
            "com.duowan.biz.videoad.impl.HyLotteryAdAwardManager";
    private static final String TASK_CENTER_URL =
            "https://hd.huya.com/h5/welfare_center/index.html";
    private static final String TASK_CENTER_AD_SCRIPT =
            "(function(){"
            + "if(location.origin+location.pathname!=='" + TASK_CENTER_URL + "'||!document.head)return;"
            + "var existing=document.getElementById('huyaplus-task-center-ad-style');"
            + "if(existing)return existing.hasAttribute('data-popup-filter');"
            + "var style=document.createElement('style');"
            + "style.id='huyaplus-task-center-ad-style';"
            + "style.textContent='.sign-popup .sign-popup-wrap-srcoll > .suggest,"
            + ".sign-popup .sign-popup-wrap-srcoll > .suggest-static,"
            + ".app-intermodal-task.huyaplus-hide-download-zone{display:none!important}';"
            + "document.head.appendChild(style);"
            + "function hideDownloadZone(){"
            + "document.querySelectorAll('section.app-intermodal-task').forEach(function(section){"
            + "var matches=Array.prototype.some.call(section.querySelectorAll('.intermodal-tab'),function(tab){"
            + "var icon=tab.querySelector('img');"
            + "return (tab.textContent.trim()||(icon&&icon.alt))==='下载专区';"
            + "});"
            + "section.classList.toggle('huyaplus-hide-download-zone',matches);"
            + "});"
            + "}"
            + "new MutationObserver(hideDownloadZone).observe(document.documentElement,"
            + "{childList:true,subtree:true,characterData:true});"
            + "hideDownloadZone();"
            // Wait for the popup queue and the last deferred task-center bundle to register.
            + "var chunks=window.rspackChunkwelfare_center=window.rspackChunkwelfare_center||[];"
            + "chunks.push([['huyaplus-task-center-ads'],{},function(require){"
            + "require.O(undefined,['6097','4418'],function(){"
            + "if(!require.m[75015])return;"
            + "var queue=require(75015).A;"
            + "if(!queue||typeof queue.enqueue!=='function')return;"
            + "var enqueue=queue.enqueue;"
            + "queue.enqueue=function(task){"
            + "if(task&&task.source==='gold-coin'&&task.latestKey==='gold-coin:index'"
            + "&&task.payload&&task.payload.iWindowType===4)return;"
            + "return enqueue.apply(this,arguments);"
            + "};"
            + "style.setAttribute('data-popup-filter','ready');"
            + "});"
            + "}]);"
            + "return style.hasAttribute('data-popup-filter');"
            + "})()";

    private static final AtomicInteger AMS_REQUESTS = new AtomicInteger();
    private static final AtomicInteger AMS_SESSIONS = new AtomicInteger();
    private static final AtomicInteger AWARD_CALLS = new AtomicInteger();

    private static Handler mainHandler;
    private final QualitySession qualitySession = new QualitySession();
    private Toast qualityNotice;
    private final Map<Object, GlassSettings.NavigationEntry> navigationItems = new WeakHashMap<>();
    private final Map<View, Integer> hiddenNavigationViews = new WeakHashMap<>();
    private boolean hooksInitialized;
    private boolean activityLoaderHookInstalled;
    private boolean activationChecked;
    private SharedPreferences prefs;
    private DailyAutomation dailyAutomation;

    @Override
    public void onModuleLoaded(ModuleLoadedParam param) {
        logInfo("loaded process=" + param.getProcessName() + " api=" + getApiVersion());
    }

    @Override
    public void onPackageReady(PackageReadyParam param) {
        if (param == null
                || !TARGET_PACKAGE.equals(param.getPackageName())
                || !param.isFirstPackage()) {
            return;
        }

        if (!isSupportedFramework()) {
            logInfo("unsupported framework; hooks disabled");
            return;
        }

        logInfo("package ready " + param.getPackageName());
        prefs = getRemotePreferences(GlassSettings.PREFS);
        installActivityLoaderHook(param.getClassLoader());
    }

    private boolean isSupportedFramework() {
        try {
            return "LSPosed".equals(getFrameworkName())
                    && (getFrameworkProperties() & PROP_CAP_SYSTEM) != 0;
        } catch (RuntimeException | LinkageError failure) {
            return false;
        }
    }

    @Override
    public boolean onHotReloading(HotReloadingParam param) {
        logInfo("hot reload rejected");
        return false;
    }

    private synchronized void installActivityLoaderHook(ClassLoader classLoader) {
        if (activityLoaderHookInstalled) {
            return;
        }
        try {
            Class<?> type = classLoader.loadClass("android.app.Activity");
            Method onCreate = type.getDeclaredMethod("onCreate", android.os.Bundle.class);
            hook(onCreate).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object activity = chain.getThisObject();
                if (!activationChecked && activity instanceof Activity) {
                    activationChecked = true;
                    String version = HuyaVersion.installed((Activity) activity);
                    if (!HuyaVersion.supports(version)) {
                        logInfo("unsupported Huya version; requires " + HuyaVersion.SUPPORTED);
                    } else if (isRootAuthorized()) {
                        logInfo("module Root verified");
                        initializeHooks(activity.getClass().getClassLoader());
                    } else {
                        logInfo("module Root unavailable; features disabled");
                    }
                }
                return chain.proceed();
            });
            Method onResume = type.getDeclaredMethod("onResume");
            hook(onResume).intercept(chain -> {
                Object result = chain.proceed();
                if (hooksInitialized && TARGET_PACKAGE.equals(android.app.Application.getProcessName())
                        && chain.getThisObject() instanceof android.content.Context) {
                    android.content.Context context = (android.content.Context) chain.getThisObject();
                    if (dailyAutomation == null) {
                        dailyAutomation = new DailyAutomation(this, prefs,
                                chain.getThisObject().getClass().getClassLoader());
                    }
                    dailyAutomation.onOpen(context);
                }
                return result;
            });
            activityLoaderHookInstalled = true;
            logInfo("hooked activity ClassLoader initialization");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private boolean isRootAuthorized() {
        try {
            SharedPreferences root = getRemotePreferences(GlassSettings.ROOT_PREFS);
            return root != null && root.getBoolean(GlassSettings.ROOT_GRANTED, false);
        } catch (RuntimeException | LinkageError failure) {
            logInfo("LSPosed Root authorization preferences unavailable");
            return false;
        }
    }

    private synchronized void initializeHooks(ClassLoader classLoader) {
        if (hooksInitialized || classLoader == null) {
            return;
        }
        hooksInitialized = true;
        logInfo("initializing with activity loader " + classLoader);
        hookDefaultQuality(classLoader);
        hookMinePage(classLoader);
        hookNavigationVisibility(classLoader);
        hookMallAiFloat(classLoader);
        boolean ads = isEnabled(GlassSettings.KEY_ADS);
        boolean liveCards = isEnabled(GlassSettings.KEY_LIVE_CARDS);
        boolean rewards = isEnabled(GlassSettings.KEY_REWARDS);
        boolean vipAds = isEnabled(GlassSettings.KEY_VIP_ADS);
        boolean vip4k = isEnabled(GlassSettings.KEY_VIP_4K);
        if (rewards) {
            hookMiniappReward(classLoader);
            hookAmsReward(classLoader);
        }
        hookAwardRequests(classLoader);
        hookAdRequestDiagnostics(classLoader);
        if (ads) {
            hookStartupGuide(classLoader);
            hookDisplayAds(classLoader);
            hookImmerseFeedAds(classLoader);
            hookOfflineRoomAd(classLoader);
            hookListAds(classLoader);
            hookSplash(classLoader);
        }
        hookTaskCenterPromotions(classLoader);
        if (liveCards) {
            hookLiveRoomCards(classLoader);
        }
        if (isEnabled(GlassSettings.KEY_LIVE_AD_BANNER)) {
            hookNativeLiveAdBanner(classLoader);
        }
        if (isEnabled(GlassSettings.KEY_LIVE_AD_FLOAT)) {
            hookNativeLiveAdFloat(classLoader);
        }
        if (vipAds) {
            hookVipAdFilter(classLoader);
        }
        if (vip4k) {
            hookVip4KPlayback(classLoader);
        }
    }

    private void hookTaskCenterPromotions(ClassLoader loader) {
        try {
            Class<?> webView = loader.loadClass("com.duowan.kiwi.crossplatform.base.webview.KiwiWebView");
            Method onPageFinished = webView.getDeclaredMethod("onPageFinished", String.class);
            Method evaluateJavascript = webView.getMethod(
                    "evaluateJavascript", String.class, ValueCallback.class);
            ValueCallback<String> applied = value -> {
                if ("true".equals(value)) logInfo("task center promotion filter ready");
            };
            Hooker applyFilter = chain -> {
                Object result = chain.proceed();
                String url = (String) chain.getArg(0);
                if (webView.isInstance(chain.getThisObject())
                        && url != null && TASK_CENTER_URL.equals(url.split("[?#]", 2)[0])
                        && isEnabled(GlassSettings.KEY_ADS)) {
                    try {
                        evaluateJavascript.invoke(chain.getThisObject(), TASK_CENTER_AD_SCRIPT, applied);
                    } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
                        logFailure(failure);
                    }
                }
                return result;
            };
            hook(onPageFinished).intercept(applyFilter);
            Method onPageCommitVisible = loader.loadClass("com.huya.hybrid.webview.HYWebView")
                    .getDeclaredMethod("onPageCommitVisible", String.class);
            hook(onPageCommitVisible).intercept(applyFilter);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
    }

    private void hookNavigationVisibility(ClassLoader loader) {
        try {
            Class<?> helper = loader.loadClass("com.duowan.kiwi.list.homepage.HomepageTabHelper");
            Class<?> tab = loader.loadClass("com.duowan.kiwi.homepage.IHomepageFragmentContainer$c");
            Class<?> bar = loader.loadClass("com.duowan.kiwi.homepage.CustomBar");
            Class<?> skin = loader.loadClass("com.duowan.yyprotocol.ResFile");
            Method toBarItem = helper.getDeclaredMethod("k", tab);
            Method init = bar.getDeclaredMethod("init", List.class, skin, ColorStateList.class, boolean.class);
            Method update = bar.getDeclaredMethod("updateBarItem", List.class, int.class);
            hook(toBarItem).intercept(chain -> {
                Object item = chain.proceed();
                // The helper sets h from HomeTab.getValue() before building the visual item.
                GlassSettings.NavigationEntry entry = GlassSettings.NavigationEntry.forTab(
                        field(chain.getArg(0), "h"));
                if (item != null && entry != null) navigationItems.put(item, entry);
                return item;
            });
            for (Method method : new Method[]{init, update}) {
                hook(method).intercept(chain -> {
                    Object result = chain.proceed();
                    updateNavigationBar(chain.getThisObject(), chain.getArg(0));
                    return result;
                });
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
    }

    private void updateNavigationBar(Object bar, Object data) {
        Object container = field(bar, "mTabContainer");
        if (!(container instanceof LinearLayout) || !(data instanceof List)) return;
        LinearLayout layout = (LinearLayout) container;
        List<?> items = (List<?>) data;
        if (layout.getChildCount() != items.size()) return;
        boolean affected = false;
        int visible = 0;
        for (int index = 0; index < items.size(); index++) {
            View child = layout.getChildAt(index);
            GlassSettings.NavigationEntry entry = navigationItems.get(items.get(index));
            affected |= setNavigationHidden(child, shouldHide(entry));
            if (child.getVisibility() != View.GONE) visible++;
        }
        if (affected && visible > 0) layout.setWeightSum(visible);
    }

    private void hookMallAiFloat(ClassLoader loader) {
        try {
            Class<?> manager = loader.loadClass("com.facebook.react.uimanager.BaseViewManager");
            Class<?> reactGroup = loader.loadClass("com.facebook.react.views.view.ReactViewGroup");
            Class<?> reactRoot = loader.loadClass("com.facebook.react.ReactRootView");
            Method moduleName = reactRoot.getMethod("getJSModuleName");
            Method setNativeId = manager.getDeclaredMethod("setNativeId", View.class, String.class);
            Method pointerEvents = reactGroup.getDeclaredMethod("getPointerEvents");
            Object noPointerEvents = pointerEvents.getReturnType().getField("NONE").get(null);
            hook(pointerEvents).intercept(chain -> hiddenNavigationViews.containsKey(chain.getThisObject())
                    ? noPointerEvents : chain.proceed());
            View.OnAttachStateChangeListener attach = new View.OnAttachStateChangeListener() {
                @Override public void onViewAttachedToWindow(View view) {
                    view.removeOnAttachStateChangeListener(this);
                    updateMallAiFloat(view, reactRoot, moduleName);
                }

                @Override public void onViewDetachedFromWindow(View view) {
                }
            };
            hook(setNativeId).intercept(chain -> {
                Object result = chain.proceed();
                if (!reactGroup.isInstance(chain.getArg(0))) return result;
                View view = (View) chain.getArg(0);
                // MallTab's FloatWindow renders its TouchableOpacity with a one-space nativeID.
                if (" ".equals(chain.getArg(1)) && shouldHide(GlassSettings.NavigationEntry.MALL_AI_FLOAT)) {
                    if (view.isAttachedToWindow()) updateMallAiFloat(view, reactRoot, moduleName);
                    else {
                        view.removeOnAttachStateChangeListener(attach);
                        view.addOnAttachStateChangeListener(attach);
                    }
                } else if (hiddenNavigationViews.containsKey(view)) {
                    setNavigationHidden(view, false);
                } else if (!view.isAttachedToWindow()) {
                    view.removeOnAttachStateChangeListener(attach);
                }
                return result;
            });
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
    }

    private void updateMallAiFloat(View view, Class<?> reactRoot, Method moduleName) {
        try {
            for (ViewParent parent = view.getParent(); parent instanceof View; parent = parent.getParent()) {
                if (reactRoot.isInstance(parent)) {
                    setNavigationHidden(view, "MallTab".equals(moduleName.invoke(parent))
                            && shouldHide(GlassSettings.NavigationEntry.MALL_AI_FLOAT));
                    return;
                }
            }
        } catch (ReflectiveOperationException | RuntimeException failure) {
            logFailure(failure);
        }
    }

    private boolean shouldHide(GlassSettings.NavigationEntry entry) {
        return entry != null && prefs != null && prefs.getBoolean(entry.key, false);
    }

    private boolean setNavigationHidden(View view, boolean hidden) {
        if (hidden) {
            hiddenNavigationViews.putIfAbsent(view, view.getVisibility());
            view.setVisibility(View.GONE);
            return true;
        }
        Integer original = hiddenNavigationViews.remove(view);
        if (original == null) return false;
        view.setVisibility(original);
        return true;
    }

    private void hookMinePage(ClassLoader loader) {
        try {
            Class<?> page = loader.loadClass("com.duowan.kiwi.my.MyRecordNew");
            Method create = page.getDeclaredMethod("onViewCreated", View.class, android.os.Bundle.class);
            hook(create).intercept(chain -> {
                Object result = chain.proceed();
                try {
                    addMineSettingsEntry((View) chain.getArg(0));
                } catch (RuntimeException | LinkageError failure) {
                    logFailure(failure);
                }
                return result;
            });
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
        try {
            Class<?> creator = loader.loadClass("com.duowan.kiwi.my.utils.MyTabModuleViewCreator");
            Method render = creator.getDeclaredMethod("createByTemplateType", Context.class,
                    loader.loadClass("com.duowan.HUYA.MyTabModuleInfo"));
            hook(render).intercept(chain -> {
                Object module = chain.getArg(1);
                Object filtered = filterNativeMineModule(module);
                if (filtered == null) return new Pair<>(false, null);
                return filtered == module ? chain.proceed()
                        : chain.proceed(new Object[]{chain.getArg(0), filtered});
            });
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
        try {
            Class<?> page = loader.loadClass("com.duowan.kiwi.my.MyRecordNew");
            Method render = page.getDeclaredMethod("createLizardModuleView", Context.class,
                    loader.loadClass("com.duowan.HUYA.DynamicItem"));
            hook(render).intercept(chain -> {
                Object module = chain.getArg(1);
                if (module == null) return chain.proceed();
                Object filtered = filterLizardMineModule(module);
                if (filtered == null) return null;
                return filtered == module ? chain.proceed()
                        : chain.proceed(new Object[]{chain.getArg(0), filtered});
            });
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
        }
    }

    private void addMineSettingsEntry(View root) {
        Context context = root.getContext();
        int panelId = context.getResources().getIdentifier("user_info_panel", "id", TARGET_PACKAGE);
        View panel = root.findViewById(panelId);
        if (panel == null || !(panel.getParent() instanceof LinearLayout)) return;
        ViewGroup list = (ViewGroup) panel.getParent();
        String label = "虎牙 Plus 设置";
        if (list.findViewWithTag(label) != null) return;
        Button entry = new Button(context);
        entry.setTag(label);
        entry.setText(label);
        entry.setAllCaps(false);
        entry.setOnClickListener(view -> {
            Intent intent = new Intent().setClassName("io.github.saycm.huyaplus",
                    "io.github.saycm.huyaplus.AppDetailActivity");
            try {
                context.startActivity(intent);
            } catch (android.content.ActivityNotFoundException | SecurityException failure) {
                Toast.makeText(context, "无法打开虎牙 Plus 设置", Toast.LENGTH_SHORT).show();
                logFailure(failure);
            }
        });
        list.addView(entry, list.indexOfChild(panel) + 1,
                new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private Object filterNativeMineModule(Object module) {
        int group = GlassSettings.MineEntry.groupOf(text(field(module, "sId")), text(field(module, "sName")));
        if (group < 0 || prefs == null) return module;
        try {
            List<?> primary = mineRows(field(module, "vItems"));
            List<?> bottom = mineRows(field(module, "vBottomItems"));
            List<?> keptPrimary = filterMineRows(primary, group, false);
            List<?> keptBottom = filterMineRows(bottom, group, false);
            if (primary == keptPrimary && bottom == keptBottom) return module;
            if (keptPrimary.isEmpty() && keptBottom.isEmpty()
                    && field(module, "tLeftItem") == null
                    && field(module, "tGamePlayInfoModule") == null) return null;
            Object filtered = copyMineModel(module);
            if (primary != keptPrimary) module.getClass().getField("vItems").set(filtered, keptPrimary);
            if (bottom != keptBottom) module.getClass().getField("vBottomItems").set(filtered, keptBottom);
            return filtered;
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
            return module;
        }
    }

    private Object filterLizardMineModule(Object module) {
        if (prefs == null || text(field(module, "sTemplateUrl")).trim().endsWith("MyTabSevenModule")) {
            return module;
        }
        Object data = field(module, "tData");
        Object payload = field(data, "mpObject");
        if (!(payload instanceof Map)) return module;
        Map<?, ?> values = (Map<?, ?>) payload;
        int group = GlassSettings.MineEntry.groupOf(mineDynamicId(values.get("id")),
                text(field(values.get("name"), "sString")));
        if (group < 0) return module;
        try {
            Object items = values.get("items");
            List<?> primary = mineRows(field(items, "vArray"));
            List<?> kept = filterMineRows(primary, group, true);
            if (primary == kept) return module;
            if (kept.isEmpty()) return null;
            Object copiedItems = copyMineModel(items);
            items.getClass().getField("vArray").set(copiedItems, kept);
            Map<Object, Object> copiedValues = new LinkedHashMap<>(values);
            copiedValues.put("items", copiedItems);
            Object copiedData = copyMineModel(data);
            data.getClass().getField("mpObject").set(copiedData, copiedValues);
            Object filtered = copyMineModel(module);
            module.getClass().getField("tData").set(filtered, copiedData);
            return filtered;
        } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
            logFailure(failure);
            return module;
        }
    }

    private List<?> filterMineRows(List<?> rows, int group, boolean lizard) {
        ArrayList<Object> kept = new ArrayList<>(rows.size());
        GlassSettings.MineEntry[] entries = GlassSettings.MineEntry.values();
        for (Object row : rows) {
            Object payload = lizard ? field(row, "mpObject") : null;
            Map<?, ?> item = payload instanceof Map ? (Map<?, ?>) payload : Collections.emptyMap();
            String id = lizard ? mineDynamicId(item.get("id")) : text(field(row, "sId"));
            String title = text(lizard ? field(item.get("title"), "sString") : field(row, "sTitle")).trim();
            boolean hide = false;
            for (GlassSettings.MineEntry entry : entries) {
                if (entry.matches(group, id, title) && prefs.getBoolean(entry.key, false)) {
                    hide = true;
                    break;
                }
            }
            if (!hide) kept.add(row);
        }
        return kept.size() == rows.size() ? rows : kept;
    }

    private static List<?> mineRows(Object rows) {
        return rows instanceof List ? (List<?>) rows : Collections.emptyList();
    }

    private static String mineDynamicId(Object value) {
        String id = text(field(value, "sString"));
        return id.isEmpty() ? text(field(value, "lIntegar")) : id;
    }

    private static Object copyMineModel(Object model) throws ReflectiveOperationException {
        Object copy = model.getClass().getMethod("clone").invoke(model);
        if (copy == null || copy == model) throw new IllegalStateException("Cannot copy Mine page data");
        return copy;
    }

    private static String text(Object value) {
        return value == null ? "" : value.toString();
    }

    private boolean isEnabled(String key) {
        boolean defaultValue = GlassSettings.defaultEnabled(key);
        return prefs == null ? defaultValue : prefs.getBoolean(key, defaultValue);
    }

    private void hookDefaultQuality(ClassLoader classLoader) {
        try {
            Class<?> infoType = classLoader.loadClass(
                    "com.duowan.kiwi.live.model.MultiBitrateInfo");
            for (String name : new String[]{
                    "com.duowan.kiwi.live.panel.recyclerview.BasePortraitMultiStreamPanel",
                    "com.duowan.kiwi.live.panel.BaseMultiStreamPanel",
                    "com.duowan.kiwi.live.panel.test.NewBaseMultiStreamPanel",
                    "com.duowan.kiwi.live.panel.BeautyMultiStreamPanel",
                    "com.duowan.kiwi.live.panel.ImmerseMultiStreamPanel"}) {
                try {
                    Method click = classLoader.loadClass(name)
                            .getDeclaredMethod("onClickRateItem", infoType);
                    hook(click).intercept(chain -> {
                        qualitySession.manualSelection();
                        logInfo("manual quality selection; automatic selection cancelled");
                        return chain.proceed();
                    });
                } catch (ClassNotFoundException | NoSuchMethodException ignored) {
                    // A panel may be absent in a particular Huya version.
                }
            }

            Class<?> channelType = classLoader.loadClass(
                    "com.duowan.kiwi.liveroom.ChannelPage");
            hook(channelType.getDeclaredMethod("onCreate", android.os.Bundle.class))
                    .intercept(chain -> {
                        onQualityRoomEntered(chain.getThisObject(), classLoader);
                        return chain.proceed();
                    });
            hook(channelType.getDeclaredMethod("onNewIntent", android.content.Intent.class))
                    .intercept(chain -> {
                        onQualityRoomEntered(chain.getThisObject(), classLoader);
                        return chain.proceed();
                    });
            Class<?> lineDataType = classLoader.loadClass(
                    "com.duowan.kiwi.live.multiline.data.MultiLineData");
            Method setLineInfo = findMethod(lineDataType, "setMultiLineInfo", 3);
            if (setLineInfo != null) {
                hook(setLineInfo).intercept(chain -> {
                    int token = qualitySession.current();
                    Object result = chain.proceed();
                    scheduleQualityApply(classLoader, token);
                    return result;
                });
            }
            logInfo("hooked default live quality");
            hookSwipeRoomQuality(classLoader, channelType);
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookSwipeRoomQuality(ClassLoader loader, Class<?> channelType)
            throws ReflectiveOperationException {
        String livePackage = "com.duowan.kiwi.universal.item.live.";
        Class<?> binder = loader.loadClass(livePackage + "UniversalRoomItemViewBinder");
        Class<?> holder = loader.loadClass(livePackage + "UniversalRoomItemViewHolder");
        Class<?> item = loader.loadClass("com.duowan.HUYA.UserRecItem");
        Method enter = binder.getDeclaredMethod("onPageEnter", int.class, holder, item, boolean.class);
        hook(enter).intercept(chain -> {
            try {
                Object reference = field(chain.getThisObject(), "fragment");
                Object fragment = reference instanceof WeakReference
                        ? ((WeakReference<?>) reference).get() : null;
                Object activity = fragment == null ? null
                        : fragment.getClass().getMethod("getActivity").invoke(fragment);
                Object uid = field(chain.getArg(2), "lUid");
                if (channelType.isInstance(activity) && uid instanceof Number) {
                    int token = qualitySession.enterRoom(((Number) uid).longValue());
                    if (token != 0) {
                        scheduleRoomQualityNotice((Activity) activity, loader, token);
                        scheduleQualityApply(loader, token);
                        logInfo("started quality session for selected live room");
                    }
                }
            } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
                logFailure(failure);
            }
            return chain.proceed();
        });
        logInfo("hooked swipe room quality");
    }

    private void scheduleQualityApply(ClassLoader classLoader, int token) {
        if (!qualitySession.queue(token)) return;
        getMainHandler().postDelayed(() -> {
            boolean retry;
            try {
                retry = qualitySession.pending(token) && !applyConfiguredQuality(classLoader, token);
            } finally {
                qualitySession.dequeue(token);
            }
            if (retry) scheduleQualityApply(classLoader, token);
        }, 1800L);
    }

    private void onQualityRoomEntered(Object activity, ClassLoader loader) {
        int token = qualitySession.enter();
        if (activity instanceof Activity) {
            scheduleRoomQualityNotice((Activity) activity, loader, token);
        }
    }

    private void scheduleRoomQualityNotice(Activity activity, ClassLoader loader, int token) {
        if (qualityNotice != null) {
            qualityNotice.cancel();
            qualityNotice = null;
        }
        WeakReference<Activity> room = new WeakReference<>(activity);
        getMainHandler().postDelayed(() -> showRoomQuality(room, loader, token, 20), 2200L);
    }

    private void showRoomQuality(WeakReference<Activity> room, ClassLoader loader,
                                 int token, int attemptsLeft) {
        Activity activity = room.get();
        if (!qualitySession.noticePending(token) || activity == null
                || activity.isFinishing() || activity.isDestroyed()) return;
        if (activity.hasWindowFocus() && qualitySession.noticeReady(token, qualityNoticeTime())) {
            try {
                String label = playingQualityLabel(loader, token);
                if (!label.isEmpty() && qualitySession.claimNotice(token, qualityNoticeTime())) {
                    qualityNotice = Toast.makeText(activity.getApplicationContext(),
                            "当前画质：" + label, Toast.LENGTH_SHORT);
                    qualityNotice.show();
                    return;
                }
            } catch (ReflectiveOperationException | RuntimeException | LinkageError failure) {
                logFailure(failure);
                return;
            }
        }
        if (attemptsLeft > 1) {
            getMainHandler().postDelayed(
                    () -> showRoomQuality(room, loader, token, attemptsLeft - 1), 500L);
        }
    }

    private String playingQualityLabel(ClassLoader loader, int token)
            throws ReflectiveOperationException {
        Class<?> moduleType = loader.loadClass("com.duowan.kiwi.live.api.multiline.IMultiLineModule");
        Object module = findMultiLineModule(loader, moduleType, token);
        if (module == null || !Boolean.TRUE.equals(moduleType.getMethod("isInChannel").invoke(module))) {
            return "";
        }
        long playId = ((Number) moduleType.getMethod("getPlayId").invoke(module)).longValue();
        Class<?> componentType = loader.loadClass("com.duowan.kiwi.player.ILivePlayerComponent");
        Object component = HuyaComponents.get(loader, componentType);
        if (component == null) return "";
        Object players = componentType.getMethod("getLivePlayerModule").invoke(component);
        if (players == null) return "";
        Class<?> playersType = loader.loadClass("com.duowan.kiwi.player.ILivePlayerModule");
        Object player = playersType.getMethod("getMultiVideoPlayer", long.class).invoke(players, playId);
        Class<?> playerType = loader.loadClass("com.duowan.kiwi.player.ILivePlayer");
        if (player == null || !Boolean.TRUE.equals(playerType.getMethod("isVideoPlaying").invoke(player))) {
            return "";
        }
        int bitrate = ((Number) playerType.getMethod("getCurrentBitrate").invoke(player)).intValue();
        int lineIndex = ((Number) moduleType.getMethod("getLineIndex").invoke(module)).intValue();
        Class<?> infoType = loader.loadClass("com.duowan.kiwi.live.model.MultiBitrateInfo");
        Method getBitrate = infoType.getMethod("getBitrate");
        Method getDisplayName = infoType.getMethod("getDisplayName");
        Method getHevcBitrate = infoType.getMethod("getHEVCBitRate");
        String hevcLabel = "";
        String originalLabel = "";
        for (Object item : currentLineBitrates(loader, moduleType, module, lineIndex)) {
            if (!infoType.isInstance(item)) continue;
            String label = text(getDisplayName.invoke(item)).trim();
            if (label.isEmpty()) continue;
            int tierBitrate = ((Number) getBitrate.invoke(item)).intValue();
            if (tierBitrate == bitrate) return label;
            if (tierBitrate == 0) originalLabel = label;
            if (bitrate > 0 && ((Number) getHevcBitrate.invoke(item)).intValue() == bitrate) {
                hevcLabel = label;
            }
        }
        if (!hevcLabel.isEmpty()) return hevcLabel;
        if (bitrate <= 0 || originalLabel.isEmpty()) return "";
        int originalBitrate = ((Number) moduleType.getMethod("getOriginalBitrate", long.class)
                .invoke(module, playId)).intValue();
        return bitrate == originalBitrate ? originalLabel : "";
    }

    private boolean applyConfiguredQuality(ClassLoader classLoader, int token) {
        int preferred = prefs == null ? LiveQuality.FOLLOW
                : prefs.getInt(GlassSettings.KEY_LIVE_QUALITY, LiveQuality.FOLLOW);
        if (preferred == LiveQuality.FOLLOW || !qualitySession.beginAttempt(token)) return true;
        try {
            Class<?> moduleType = classLoader.loadClass(
                    "com.duowan.kiwi.live.api.multiline.IMultiLineModule");
            Object module = findMultiLineModule(classLoader, moduleType, token);
            if (module == null
                    || !Boolean.TRUE.equals(moduleType.getMethod("isInChannel").invoke(module))
                    || !Boolean.TRUE.equals(moduleType.getMethod("hasValidLine").invoke(module))) {
                return false;
            }
            int lineIndex = ((Number) moduleType.getMethod("getLineIndex")
                    .invoke(module)).intValue();
            Class<?> infoType = classLoader.loadClass(
                    "com.duowan.kiwi.live.model.MultiBitrateInfo");
            Method getBitrate = infoType.getMethod("getBitrate");
            Method getDisplayName = infoType.getMethod("getDisplayName");
            Map<Integer, String> rates = new LinkedHashMap<>();
            for (Object item : currentLineBitrates(classLoader, moduleType, module, lineIndex)) {
                if (!infoType.isInstance(item)) continue;
                Object bitrate = getBitrate.invoke(item);
                Object name = getDisplayName.invoke(item);
                if (bitrate instanceof Number) rates.put(((Number) bitrate).intValue(),
                        name == null ? null : String.valueOf(name));
            }
            if (rates.isEmpty()) return false;
            int selected = LiveQuality.select(preferred, -1, rates);
            if (selected < 0) return false;
            Method switchLine = moduleType.getMethod(
                    "switchLineTo", int.class, int.class, boolean.class);
            if (!qualitySession.pending(token)) return true;
            switchLine.invoke(module, lineIndex, selected, true);
            qualitySession.claim(token);
            qualitySession.deferNotice(token, qualityNoticeTime() + 1000L);
            logInfo("requested default quality once line=" + lineIndex
                    + " selected=" + selected + " available=" + rates);
            return true;
        } catch (Throwable throwable) {
            logFailure(throwable);
            return false;
        }
    }

    private Object findMultiLineModule(ClassLoader loader, Class<?> moduleType, int token)
            throws ReflectiveOperationException {
        long roomId = qualitySession.roomId(token);
        if (roomId < 0L) return null;
        Class<?> componentType = loader.loadClass("com.duowan.kiwi.live.api.ILiveComponent");
        Object component = HuyaComponents.get(loader, componentType);
        if (component == null) return null;
        // Creating a room entry here can mask the active line module during Huya's auto-slide check.
        Object module = componentType.getMethod("tryGetMultiLineModule", long.class)
                .invoke(component, roomId);
        if (module == null) return null;
        long playId = ((Number) moduleType.getMethod("getPlayId").invoke(module)).longValue();
        if (qualitySession.matchesRoom(token, playId)) return module;
        if (playId != 0L) return null;
        // Huya promotes the active player to slot 0 and retains its room ID as the previous ID.
        long previousId = ((Number) moduleType.getMethod("getPrePlayerId").invoke(module)).longValue();
        return qualitySession.matchesRoom(token, previousId) ? module : null;
    }

    private static long qualityNoticeTime() {
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime());
    }

    private static List<?> currentLineBitrates(ClassLoader loader, Class<?> moduleType,
                                               Object module, int lineIndex)
            throws ReflectiveOperationException {
        Object raw = moduleType.getMethod("getLines").invoke(module);
        if (!(raw instanceof Pair)) return Collections.emptyList();
        Pair<?, ?> lines = (Pair<?, ?>) raw;
        Class<?> lineType = loader.loadClass("com.duowan.kiwi.live.model.ABSLine");
        Method getLineIndex = lineType.getMethod("getLineIndex");
        for (Object group : new Object[]{lines.first, lines.second}) {
            if (!(group instanceof List)) continue;
            for (Object line : (List<?>) group) {
                if (lineType.isInstance(line) && ((Number) getLineIndex.invoke(line)).intValue() == lineIndex) {
                    Object rates = lineType.getMethod("getBitrateInfoList").invoke(line);
                    return rates instanceof List ? (List<?>) rates : Collections.emptyList();
                }
            }
        }
        return Collections.emptyList();
    }

    private void hookVipAdFilter(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.popup.impl.pubscreen.PopupStrategyConditionHelper");
            Class<?> itemType = classLoader.loadClass("com.duowan.kiwi.popup.api.PopupItem");
            Method summary = itemType.getMethod("getSummary");
            Method filter = type.getDeclaredMethod("checkPlatformVipFilter", itemType);
            hook(filter).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object item = chain.getArg(0);
                Object flag = item == null ? null
                        : field(summary.invoke(item), "iIsNoShowForPlatformVip");
                if (flag instanceof Number && ((Number) flag).intValue() == 1) {
                    logInfo("blocked VIP-exempt live-room ad");
                    return false;
                }
                return chain.proceed();
            });
            logInfo("hooked VIP-exempt live-room ad filter");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookVip4KPlayback(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.live.vip4k.Vip4KPlayHelper");
            Method active = type.getDeclaredMethod("isPlatformVipActive");
            // Use the existing member playback branch only inside the 4K helper.
            // Stream availability and CDN authentication still use Huya's data.
            hook(active).setPriority(PRIORITY_HIGHEST).intercept(chain -> true);
            logInfo("hooked experimental 4K playback branch");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookImmerseFeedAds(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.immersepage.impl.data.ImmerseDataManagerImpl");
            Method filterList = findMethod(type, "filterList", 3);
            if (filterList == null) {
                return;
            }
            hook(filterList).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                return filterImmerseAds(chain.proceed(), "immersive feed");
            });
            logInfo("hooked immersive recommendation feed ads");

            Class<?> callback = classLoader.loadClass(
                    "com.duowan.kiwi.immersepage.impl.data.IImmerseDataManager$InertItemCallback");
            Method insertAd = type.getDeclaredMethod(
                    "insertAdIfNeed", int.class, ArrayList.class, List.class, callback);
            hook(insertAd).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                if (((List<?>) chain.getArg(1)).isEmpty()) return chain.proceed();
                // Huya leaves the list and its callback untouched when there is no ad to insert.
                logInfo("blocked immersive swipe ad insertion");
                return null;
            });
            logInfo("hooked immersive swipe ad insertion");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> adapter = classLoader.loadClass(
                    "com.duowan.kiwi.universalslide.impl.adapter.UniversalSlideAdapter");
            Method filter = adapter.getDeclaredMethod("filterSupportedItems", List.class);
            hook(filter).setPriority(PRIORITY_HIGHEST).intercept(chain ->
                    filterImmerseAds(chain.proceed(), "swipe list"));
            logInfo("hooked swipe list ad filter");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendPresenter");
            Method gridItems = findMethod(type, "getGridGameCardItemList", 3);
            if (gridItems != null) {
                hook(gridItems).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    Object result = chain.proceed();
                    if (!(result instanceof List)) {
                        return result;
                    }
                    List<?> original = (List<?>) result;
                    List<Object> filtered = new ArrayList<>(original.size());
                    for (Object item : original) {
                        if (!isAdLineItem(item)) {
                            filtered.add(item);
                        }
                    }
                    int removed = original.size() - filtered.size();
                    if (removed > 0) {
                        logInfo("filtered " + removed + " recommendation grid ads");
                        return filtered;
                    }
                    return result;
                });
                logInfo("hooked recommendation grid ads");
            }
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private Object filterImmerseAds(Object result, String source) {
        if (!(result instanceof List)) return result;
        List<?> original = (List<?>) result;
        List<Object> filtered = new ArrayList<>(original.size());
        for (Object item : original) {
            if (!isImmerseAdItem(item)) filtered.add(item);
        }
        int removed = original.size() - filtered.size();
        if (removed == 0) return result;
        logInfo("filtered " + removed + " ads from " + source);
        return filtered;
    }

    private static boolean isImmerseAdItem(Object item) {
        if (item == null) {
            return false;
        }
        if ("com.duowan.HUYA.UserRecItem".equals(item.getClass().getName())) {
            Object ads = field(field(item, "tMCard"), "vAdCard");
            return ads instanceof List && !((List<?>) ads).isEmpty();
        }
        try {
            Object itemType = item.getClass().getMethod("getItemType").invoke(item);
            String name = String.valueOf(itemType);
            return "AD_VIDEO".equals(name)
                    || "HOME_NATIVE_AD".equals(name)
                    || "HOT_LIVE_AD_VIDEO".equals(name)
                    || "LIVE_LIST_AD_VIDEO".equals(name);
        } catch (Throwable throwable) {
            return false;
        }
    }

    private void hookDisplayAds(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.adsplash.controller.AdRouter");
            Method route = findMethod(type, "isNeedShowAdSplash", 4);
            if (route != null) {
                hook(route).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    // 6 is Huya's own "splash disabled" result. The caller still
                    // completes its normal NO_AD callbacks and opens the homepage.
                    logInfo("blocked splash before display");
                    return 6;
                });
                logInfo("hooked splash display decision");
            }
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass("com.duowan.kiwi.ad.impl.HyAdModule");
            Method shield = findMethod(type, "isNeedShieldAdOutLivingRoom", 0);
            if (shield != null) {
                hook(shield).setPriority(PRIORITY_HIGHEST).intercept(chain -> true);
                // The in-room shield also guards rewarded-ad requests, so leave it alone.
                logInfo("enabled ordinary ad request shield");
            }
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.list.patface.chain.PatFaceInterceptorChain");
            Method proceed = type.getDeclaredMethod("proceed", int.class);
            hook(proceed).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                // Stop before constructing or enqueuing the promotional dialog.
                logInfo("blocked automatic promotion location=" + chain.getArg(0));
                return false;
            });
            logInfo("hooked automatic promotion decision");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendPresenter");
            Method callback = findMethod(type, "onLiveListAdBack", 4);
            if (callback != null) {
                hook(callback).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    logInfo("blocked recommendation ad injection ad="
                            + field(chain.getArg(0), "iId"));
                    return null;
                });
                logInfo("hooked recommendation ad injection");
            }
            Method insertGrid = findMethod(type, "l0", 3);
            if (insertGrid != null) {
                hook(insertGrid).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    Object result = chain.proceed();
                    Object output = chain.getArg(0);
                    if (!(output instanceof List)) {
                        return result;
                    }
                    List<?> items = (List<?>) output;
                    int removed = 0;
                    for (int index = items.size() - 1; index >= 0; index--) {
                        if (isAdLineItem(items.get(index))) {
                            items.remove(index);
                            removed++;
                        }
                    }
                    if (removed > 0) {
                        logInfo("filtered " + removed
                                + " ads after recommendation grid insertion");
                    }
                    return result;
                });
                logInfo("hooked recommendation grid insertion");
            }
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookOfflineRoomAd(ClassLoader loader) {
        try {
            Class<?> view = loader.loadClass("com.duowan.kiwi.liveend.impl.views.NotLivingView");
            Class<?> event = loader.loadClass(
                    "com.duowan.kiwi.livead.api.adplugin.event.IPresenterAdEvent$ShowNotLiveAdEvent");
            Method show = view.getDeclaredMethod("onShowStopLiveAdEvent", event);
            hook(show).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                logInfo("blocked offline-room autoplay ad");
                return null;
            });
        } catch (Throwable failure) {
            logFailure(failure);
        }
    }

    private void hookNativeLiveAdBanner(ClassLoader loader) {
        try {
            Class<?> type = loader.loadClass("com.duowan.kiwi.livead.api.adbanner.view.AdLiveBannerView");
            Method show = type.getDeclaredMethod("showAd", List.class, Map.class);
            Method hide = type.getMethod("hideAd");
            hook(show).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                hide.invoke(chain.getThisObject());
                logInfo("blocked native live-room banner");
                return false;
            });
            logInfo("hooked native live-room banner");
        } catch (Throwable failure) {
            logFailure(failure);
        }
    }

    private void hookNativeLiveAdFloat(ClassLoader loader) {
        try {
            Class<?> type = loader.loadClass("com.duowan.kiwi.livead.impl.adfloat.module.RevenueModule");
            Class<?> liveAd = loader.loadClass("com.duowan.HUYA.LiveRoomAdvertise");
            Class<?> ad = loader.loadClass("com.duowan.kiwi.livead.api.adfloat.data.Advertisement");
            Method display = type.getDeclaredMethod("displayAdByMethod", liveAd, ad, long.class, Map.class);
            hook(display).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                logInfo("blocked native live-room floating promotion");
                return null;
            });
            logInfo("hooked native live-room floating promotion");
        } catch (Throwable failure) {
            logFailure(failure);
        }
        try {
            Class<?> type = loader.loadClass("com.duowan.kiwi.universal.live.pubscreen.biz.UniversalLiveAdFloat");
            Method visibility = type.getDeclaredMethod("changeFloatAdVisibilityIfNeed", boolean.class);
            hook(visibility).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                if (Boolean.TRUE.equals(chain.getArg(0))) {
                    logInfo("hid live-room floating ad");
                    return chain.proceed(new Object[]{false});
                }
                return chain.proceed();
            });
            logInfo("hooked live-room floating ad visibility");
        } catch (Throwable failure) {
            logFailure(failure);
        }
    }

    private void hookLiveRoomCards(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.universal.live.activitybar.banner.UniversalLiveBannerView");
            Method setData = type.getDeclaredMethod("setData", List.class);
            hook(setData).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object data = chain.getArg(0);
                if (data instanceof List && !((List<?>) data).isEmpty()) {
                    logInfo("cleared live-room promotion banner");
                    return chain.proceed(new Object[]{new ArrayList<>()});
                }
                return chain.proceed();
            });
            logInfo("hooked live-room promotion banner data");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.interaction.impl.view.UniversalComponentNavigationView");
            Class<?> itemType = classLoader.loadClass(
                    "com.duowan.kiwi.interaction.api.data.ComponentPanelItemInfo");
            Method setData = type.getDeclaredMethod("setAllTimeLimitComps", List.class);
            Method componentId = itemType.getMethod("getComponentId");
            Method componentName = itemType.getMethod("getComponentName");
            Method jumpUrl = itemType.getMethod("getJumpUrl", boolean.class);
            hookCampaignShortcuts(setData, item -> {
                if (!itemType.isInstance(item)) {
                    return false;
                }
                try {
                    Object name = componentName.invoke(item);
                    return Integer.valueOf(36305).equals(componentId.invoke(item))
                            || isCampaignShortcutName(name)
                            || isCampaignShortcutRoute(jumpUrl.invoke(item, false))
                            || isCampaignShortcutRoute(jumpUrl.invoke(item, true));
                } catch (ReflectiveOperationException ignored) {
                    return false;
                }
            });
            logInfo("hooked live-room campaign shortcuts");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> bar = classLoader.loadClass(
                    "com.duowan.kiwi.inputbar.api.view.entryview.base.BottomBarEntryListView");
            Class<?> itemType = classLoader.loadClass(
                    "com.duowan.kiwi.inputbar.api.view.InputEntryData");
            Method title = itemType.getMethod("getTitle");
            Method actionUrl = itemType.getMethod("getActionUrl");
            Method portrait = actionUrl.getReturnType().getMethod("getPortrait");
            Method landscape = actionUrl.getReturnType().getMethod("getLandscape");
            hookCampaignShortcuts(bar.getDeclaredMethod("refreshAllEntryView", List.class), item -> {
                if (!itemType.isInstance(item)) {
                    return false;
                }
                try {
                    Object route = actionUrl.invoke(item);
                    return isCampaignShortcutName(title.invoke(item))
                            || (route != null && (isCampaignShortcutRoute(portrait.invoke(route))
                                    || isCampaignShortcutRoute(landscape.invoke(route))));
                } catch (ReflectiveOperationException ignored) {
                    return false;
                }
            });
            logInfo("hooked live-room input bar campaign shortcuts");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass("com.duowan.kiwi.popup.impl.PopupModule");
            Class<?> itemType = classLoader.loadClass("com.duowan.kiwi.popup.api.PopupItem");
            Method businessKey = itemType.getMethod("getBusinessKey");
            for (String name : new String[]{"tryShowPopup", "tryPlaceholderPopup"}) {
                Method show = type.getDeclaredMethod(name, itemType);
                hook(show).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    Object item = chain.getArg(0);
                    Object key = item == null ? null : businessKey.invoke(item);
                    if ("cardcollectionactivity_streamertrigger".equals(key)) {
                        logInfo("blocked card collection promotion before queueing");
                        return false;
                    }
                    if (key instanceof String && ((String) key).endsWith("_autotrigger")) {
                        logInfo("blocked automatic live-room card before queueing");
                        return false;
                    }
                    return chain.proceed();
                });
            }
            logInfo("hooked automatic live-room cards");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.huya.kiwi.hyext.delegate.api.HYExtRightTopWindowModeManager");
            Method create = findMethod(type, "createFloatWindowItemView", 5);
            if (create != null) {
                hook(create).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    Object entry = chain.getArg(2);
                    Object id = field(entry, "iEntId");
                    // Huya's gift offer, game promotion and shopping activity windows.
                    if (Integer.valueOf(317).equals(id) || Integer.valueOf(201).equals(id)
                            || Integer.valueOf(175).equals(id)) {
                        logInfo("blocked promotional live-room window before creation");
                        return null;
                    }
                    if (Integer.valueOf(497).equals(id)) {
                        logInfo("blocked All-Star live-room activity card before creation");
                        return null;
                    }
                    if (Integer.valueOf(425).equals(id)
                            || isCardCollectionRoute(field(entry, "sFullUrl"))) {
                        logInfo("blocked card collection promotion before window creation");
                        return null;
                    }
                    return chain.proceed();
                });
                logInfo("hooked promotional live-room window creation");
            }
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
        try {
            Class<?> type = classLoader.loadClass(
                    "com.duowan.kiwi.livead.impl.adplugin.module.HYRoomPopupPlugin");
            Method enqueue = findMethod(type, "enqueue", 3);
            if (enqueue == null) {
                return;
            }
            hook(enqueue).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object id = chain.getArg(0);
                if (id instanceof String && ((String) id).startsWith("floatball_ad_")) {
                    logInfo("blocked live-room floating ad before queueing");
                    return null;
                }
                return chain.proceed();
            });
            logInfo("hooked live-room floating ad queue");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookCampaignShortcuts(Method refresh, Predicate<Object> isCampaign) {
        hook(refresh).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
            Object data = chain.getArg(0);
            if (!(data instanceof List)) {
                return chain.proceed();
            }
            List<?> items = (List<?>) data;
            List<Object> filtered = new ArrayList<>(items);
            if (!filtered.removeIf(isCampaign)) {
                return chain.proceed();
            }
            logInfo("filtered card collection or phone draw shortcut via " + refresh.getName());
            return chain.proceed(new Object[]{filtered});
        });
    }

    private static boolean isCampaignShortcutName(Object name) {
        return "抽手机".equals(name) || "集卡".equals(name) || "集卡领虎牙币".equals(name)
                || "集五卡·瓜分10万奖金".equals(name);
    }

    private static boolean isCampaignShortcutRoute(Object value) {
        return isCardCollectionRoute(value)
                || isRoute(value, "zt.huya.com", "/688005a6/mobile/index.html");
    }

    private static boolean isCardCollectionRoute(Object value) {
        return isRoute(value, "hd.huya.com", "/hyfe/revenue-business/cards-pot.html")
                || isRoute(value, "zt.huya.com", "/31bf1210/mobile/index.html");
    }

    private static boolean isRoute(Object value, String host, String path) {
        if (!(value instanceof String)) {
            return false;
        }
        try {
            URI route = URI.create((String) value);
            return host.equalsIgnoreCase(route.getHost()) && path.equals(route.getPath());
        } catch (IllegalArgumentException ignored) {
            return false;
        }
    }

    private void hookListAds(ClassLoader classLoader) {
        List<String> mutations = Arrays.asList(
                "replace", "replaceAndNotify", "replaceData", "add", "addAndNotify",
                "insert", "insertAndNotify", "insertList", "insertListAndNotify",
                "insertItemAndNotify", "insertItemDataOnly",
                "insertItemListAndNotify", "insertItemListDataOnly");
        for (String name : new String[]{
                "com.duowan.kiwi.listframe.adapter.ListLineRecyclerViewAdapter",
                "com.duowan.kiwi.listframe.adapter.HeaderFooterListLineAdapter",
                "com.duowan.kiwi.listline.ListLineAdapter"}) {
            try {
                Class<?> type = classLoader.loadClass(name);
                int count = 0;
                for (Method method : type.getDeclaredMethods()) {
                    if (!mutations.contains(method.getName())
                            || method.getReturnType() != void.class
                            || method.getParameterCount() == 0) {
                        continue;
                    }
                    Class<?> first = method.getParameterTypes()[0];
                    if (first != List.class && !"com.duowan.kiwi.listframe.component.LineItem"
                            .equals(first.getName())) {
                        continue;
                    }
                    hook(method).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                        Object input = chain.getArg(0);
                        if (input instanceof List) {
                            List<?> original = (List<?>) input;
                            List<Object> filtered = new ArrayList<>(original.size());
                            for (Object item : original) {
                                if (!isAdLineItem(item)) {
                                    filtered.add(item);
                                }
                            }
                            int removed = original.size() - filtered.size();
                            if (removed > 0) {
                                Object[] args = chain.getArgs().toArray();
                                args[0] = filtered;
                                logInfo("filtered " + removed
                                        + " list ads via " + chain.getExecutable().getName());
                                return chain.proceed(args);
                            }
                        } else if (isAdLineItem(input)) {
                            // Skip the notification as well as the insertion.
                            logInfo("blocked single list ad");
                            return null;
                        }
                        return chain.proceed();
                    });
                    count++;
                }
                logInfo("hooked " + name + " mutations=" + count);
            } catch (Throwable throwable) {
                logFailure(throwable);
            }
        }
    }

    private static boolean isAdLineItem(Object item) {
        if (item == null) {
            return false;
        }
        try {
            Object view = item.getClass().getMethod("getLineItem").invoke(item);
            if (view == null) {
                return false;
            }
            String name = view.getClass().getName();
            if ("com.duowan.kiwi.list.component.RecommendAdComponent$ViewObject".equals(name)
                    || "com.duowan.kiwi.ad.ui.BigPicAdComponentViewObject".equals(name)
                    || "com.duowan.kiwi.ad.ui.SmallPicAdComponentViewObject".equals(name)) {
                return true;
            }
            if (field(view, "liveListAdInfo") != null
                    || field(view, "mLiveListAdInfo") != null) {
                return true;
            }
            Object user = "com.duowan.HUYA.UserRecItem".equals(name)
                    ? view : field(view, "userRecItem");
            if (user == null) {
                user = field(view, "mUserRecItem");
            }
            Object card = field(user, "tMCard");
            Object kind = field(card, "iCardType");
            Object ads = field(card, "vAdCard");
            return kind instanceof Number && ((Number) kind).intValue() == 4
                    && ads instanceof List && !((List<?>) ads).isEmpty();
        } catch (Throwable throwable) {
            // Unknown rows keep their original behavior.
            return false;
        }
    }

    private void hookAdRequestDiagnostics(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass("com.duowan.biz.videoad.impl.HyVideoAdModule");
            for (Method method : type.getDeclaredMethods()) {
                if ("goVideoAdWithCallback".equals(method.getName())
                        || "lambda$onGetAdFail$2".equals(method.getName())) {
                    hook(method).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                        logInfo("request entry " + chain.getExecutable().getName());
                        return chain.proceed();
                    });
                }
            }
            Method failed = findMethod(type, "onGetAdFail", 8);
            if (failed != null) {
                hook(failed).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    logInfo("ad request failed: code=" + chain.getArg(5)
                            + " reason=" + shortString(chain.getArg(6))
                            + " scene=" + shortString(chain.getArg(2))
                            + " " + mapSummary(chain.getArg(7)));
                    return chain.proceed();
                });
            }
            Method parsed = findMethod(type, "parseAdResult", 12);
            if (parsed != null) {
                hook(parsed).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    logInfo("parseAdResult: ad="
                            + field(chain.getArg(3), "id")
                            + " taskResult=" + field(chain.getArg(4), "iRet")
                            + " " + mapSummary(chain.getArg(11)));
                    return chain.proceed();
                });
            }
            logInfo("ad request diagnostics installed");
        } catch (Throwable throwable) {
            logFailure(throwable);
        }
    }

    private void hookMiniappReward(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(TARGET_CLASS);
            for (String name : new String[]{
                    "showRewardedVideoAd", "showCustomAd", "openCustomAd"}) {
                Method show = findMethod(type, name, 2);
                if (show == null) {
                    Log.w(TAG, name + " not found");
                    continue;
                }

                boolean custom = "openCustomAd".equals(name);
                boolean banner = "showCustomAd".equals(name);
                hook(show).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    String adId = readAdId(
                            chain.getArg(0),
                            custom || banner ? "customAdId" : "rewardedVideoAdId");
                    if (adId == null || adId.isEmpty()) {
                        return chain.proceed();
                    }

                    Object callback = chain.getArg(1);
                    if (banner) {
                        callSuccess(callback);
                        logInfo("skipped miniapp banner");
                        return null;
                    }

                    Object module = chain.getThisObject();
                    callSuccess(callback);
                    getMainHandler().postDelayed(
                            () -> emitMiniappReward(module, adId, custom), 100L);
                    logInfo("skipped miniapp " + name);
                    return null;
                });
                logInfo("hooked " + TARGET_CLASS + "." + name + "/2");
            }
        } catch (Throwable throwable) {
            Log.w(TAG, "init failed", throwable);
            logFailure(throwable);
        }
    }

    private void hookStartupGuide(ClassLoader classLoader) {
        try {
            Method setVisibility;
            Method shouldShow;
            try {
                Class<?> type = classLoader.loadClass("ryxq.weg");
                setVisibility = type.getDeclaredMethod("shouldShowGuideDialog", boolean.class);
                shouldShow = type.getDeclaredMethod("shouldShowGuideDialog");
            } catch (ClassNotFoundException | NoSuchMethodException oldGuideAbsent) {
                Class<?> type = classLoader.loadClass("ryxq.izb");
                setVisibility = type.getDeclaredMethod("shouldShowGuideDialog", boolean.class);
                shouldShow = type.getDeclaredMethod("shouldShowGuideDialog");
            }
            hook(setVisibility).intercept(chain -> chain.proceed(new Object[]{false}));
            hook(shouldShow).intercept(chain -> false);
            logInfo("hooked startup guide display");
        } catch (Throwable failure) {
            logFailure(failure);
        }
    }

    private void hookAmsReward(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(AMS_HELPER_CLASS);
            Method request = findMethod(type, "onCallAmsRewardAd", 6);
            if (request == null) {
                Log.w(TAG, "onCallAmsRewardAd not found");
                return;
            }

            hook(request).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object[] args = chain.getArgs().toArray();
                if (args.length < 6 || args[4] == null) {
                    return chain.proceed();
                }

                Object listener = args[4];
                int requestId = AMS_REQUESTS.incrementAndGet();
                logInfo("intercepted AMS reward request #" + requestId);
                Log.i(TAG, "AMS request #" + requestId + " " + summarizeAmsArgs(args));
                finishAmsReward(listener, requestId);
                Log.i(TAG, "skipped AMS rewarded video on user click #" + requestId);
                return null;
            });
            logInfo("hooked " + AMS_HELPER_CLASS + ".onCallAmsRewardAd/6");
        } catch (Throwable throwable) {
            Log.w(TAG, "AMS init failed", throwable);
            logFailure(throwable);
        }
    }

    private void hookAwardRequests(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(AWARD_MANAGER_CLASS);
            Method award = findMethod(type, "awardAdTaskIfNeed", 6);
            if (award != null) {
                hook(award).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                    Log.i(TAG, "awardAdTaskIfNeed #" + AWARD_CALLS.incrementAndGet()
                            + " " + summarizeAwardArgs(chain.getArgs().toArray()));
                    return chain.proceed();
                });
            } else {
                Log.w(TAG, "awardAdTaskIfNeed/6 not found");
            }
            hookAwardMethod(type, "onAwardAdTask", 1);
            hookAwardMethod(type, "onAwardCommonAdTask", 6);
            hookAwardMethod(type, "onAwardCommonRewardAdTask", 6);
            Log.i(TAG, "hooked reward accounting in " + AWARD_MANAGER_CLASS);
        } catch (Throwable throwable) {
            Log.w(TAG, "award diagnostics init failed", throwable);
            logFailure(throwable);
        }
    }

    private void hookAwardMethod(Class<?> type, String name, int parameterCount) {
        Method method = findMethod(type, name, parameterCount);
        if (method == null) {
            Log.w(TAG, "award method not found " + name + "/" + parameterCount);
            return;
        }
        hook(method).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
            Log.i(TAG, name + " #" + AWARD_CALLS.incrementAndGet()
                    + " " + summarizeAwardArgs(chain.getArgs().toArray()));
            return chain.proceed();
        });
    }

    private void hookSplash(ClassLoader classLoader) {
        try {
            Class<?> type = classLoader.loadClass(AD_SPLASH_FRAGMENT_CLASS);
            Method visible = findMethod(type, "onVisibleToUser", 0);
            if (visible == null) {
                Log.w(TAG, "AdSplashFragment.onVisibleToUser not found");
                return;
            }

            hook(visible).setPriority(PRIORITY_HIGHEST).intercept(chain -> {
                Object result = chain.proceed();
                Object fragment = chain.getThisObject();
                if (fragment == null) {
                    return result;
                }
                try {
                    Method dismiss = fragment.getClass().getMethod(
                            "dismissWhenError", String.class);
                    dismiss.invoke(fragment, "module_skip_splash");
                    Log.i(TAG, "skipped splash ad");
                } catch (Throwable throwable) {
                    Log.w(TAG, "splash dismiss failed", throwable);
                }
                return result;
            });
            Log.i(TAG, "hooked " + AD_SPLASH_FRAGMENT_CLASS + ".onVisibleToUser/0");
        } catch (Throwable throwable) {
            Log.w(TAG, "splash init failed", throwable);
            logFailure(throwable);
        }
    }

    private static void finishAmsReward(Object listener, int requestId) {
        int sessionId = AMS_SESSIONS.incrementAndGet();
        Log.i(TAG, "AMS session #" + sessionId + " for request #" + requestId
                + " listener=" + identity(listener));
        invokeListener(listener, "onADShow", new Class<?>[0]);
        invokeListener(listener, "onADExpose", new Class<?>[0]);
        invokeListener(listener, "onADComplete", new Class<?>[0]);

        try {
            Class<?> resultType = listener.getClass().getClassLoader()
                    .loadClass(REWARD_RESULT_CLASS);
            Object rewardResult = resultType.getConstructor().newInstance();
            Method setPassthrough = resultType.getMethod("setPassthrough", String.class);
            setPassthrough.invoke(rewardResult, "");
            invokeListener(listener, "onReward", new Class<?>[]{resultType}, rewardResult);
        } catch (Throwable throwable) {
            Log.w(TAG, "AMS reward callback failed", throwable);
        }

        getMainHandler().postDelayed(() -> {
            Log.i(TAG, "AMS session #" + sessionId + " close");
            invokeListener(listener, "onADClose", new Class<?>[0]);
        }, 100L);
    }

    private static void invokeListener(
            Object listener, String methodName, Class<?>[] parameterTypes, Object... args) {
        Log.i(TAG, "listener " + methodName + " " + identity(listener));
        try {
            Method method = listener.getClass().getMethod(methodName, parameterTypes);
            method.invoke(listener, args);
        } catch (Throwable throwable) {
            Log.w(TAG, "listener " + methodName + " failed", throwable);
        }
    }

    private static Method findMethod(Class<?> type, String name, int parameterCount) {
        for (Method method : type.getDeclaredMethods()) {
            if (name.equals(method.getName())
                    && method.getParameterCount() == parameterCount) {
                return method;
            }
        }
        return null;
    }

    private static String readAdId(Object params, String key) {
        if (params instanceof Map) {
            Object value = ((Map<?, ?>) params).get(key);
            return value instanceof String ? (String) value : null;
        }
        if (params instanceof JSONObject) {
            return ((JSONObject) params).optString(key, "");
        }
        if (params == null) {
            return null;
        }
        for (String name : new String[]{"optString", "getString", "get"}) {
            try {
                Method method = params.getClass().getMethod(name, String.class);
                Object value = method.invoke(params, key);
                return value == null ? null : value.toString();
            } catch (Throwable ignored) {
                // Try the next Map/JSON-compatible accessor.
            }
        }
        return null;
    }

    private static void callSuccess(Object callback) {
        if (callback == null) {
            return;
        }
        try {
            Method success = callback.getClass().getMethod("onSuccess", Object.class);
            success.invoke(callback, new Object[]{null});
            Log.i(TAG, "show callback completed");
        } catch (Throwable throwable) {
            Log.w(TAG, "show callback failed", throwable);
        }
    }

    private static void emitMiniappReward(Object module, String adId, boolean custom) {
        if (module == null) {
            return;
        }
        Map<String, Object> data = new HashMap<>();
        data.put(custom ? "customAdId" : "rewardedVideoAdId", adId);
        data.put(custom ? "isSuccess" : "isEnded", Boolean.TRUE);
        String event = custom ? "customAdReward" : "rewardedVideoAdClose";
        try {
            Method dispatch = module.getClass().getMethod(
                    "dispatchEvent", String.class, Object.class);
            dispatch.invoke(module, event, data);
            Log.i(TAG, "emitted " + event + " success=true");
        } catch (Throwable throwable) {
            Log.w(TAG, "reward event dispatch failed", throwable);
        }
    }

    private static String summarizeAmsArgs(Object[] args) {
        StringBuilder value = new StringBuilder();
        value.append("ad=").append(field(args[1], "id"));
        value.append(" map=").append(mapSummary(args[0]));
        value.append(" listener=").append(identity(args[4]));
        if (args[5] != null) {
            value.append(" arg5=").append(shortString(args[5]));
        }
        return value.toString();
    }

    private static String summarizeAwardArgs(Object[] args) {
        StringBuilder value = new StringBuilder();
        value.append("thread=").append(Thread.currentThread().getName());
        if (args.length > 0) {
            value.append(" arg0=").append(shortString(args[0]));
        }
        if (args.length > 1) {
            value.append(" map=").append(mapSummary(args[1]));
        }
        if (args.length > 2) {
            value.append(" ad=").append(field(args[2], "id"));
        }
        if (args.length > 3) {
            value.append(" listener=").append(identity(args[3]));
        }
        if (args.length > 4) {
            value.append(" arg4=").append(shortString(args[4]));
        }
        if (args.length > 5) {
            value.append(" task=").append(shortString(args[5]));
        }
        return value.toString();
    }

    private static String mapSummary(Object value) {
        if (!(value instanceof Map)) {
            return shortString(value);
        }
        Map<?, ?> map = (Map<?, ?>) value;
        StringBuilder summary = new StringBuilder("{size=").append(map.size());
        for (String key : new String[]{"currentTaskCenterId", "rewardtaskid", "taskId",
                "businessId", "scene", "adId", "consecutiveconfig"}) {
            if (map.containsKey(key)) {
                summary.append(", ").append(key).append("=").append(shortString(map.get(key)));
            }
        }
        return summary.append("}").toString();
    }

    private static Object field(Object target, String name) {
        if (target == null) {
            return null;
        }
        Class<?> type = target.getClass();
        while (type != null) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (Throwable ignored) {
                type = type.getSuperclass();
            }
        }
        return null;
    }

    private static String identity(Object value) {
        return value == null ? "null" : value.getClass().getSimpleName()
                + "@" + Integer.toHexString(System.identityHashCode(value));
    }

    private static String shortString(Object value) {
        if (value == null) {
            return "null";
        }
        String text = String.valueOf(value);
        return text.length() <= 240 ? text : text.substring(0, 240) + "...";
    }

    private void logInfo(String message) {
        log(Log.INFO, TAG, message);
    }

    private void logFailure(Throwable throwable) {
        log(Log.ERROR, TAG, "hook failure", throwable);
    }

    private static synchronized Handler getMainHandler() {
        if (mainHandler == null) {
            mainHandler = new Handler(Looper.getMainLooper());
        }
        return mainHandler;
    }
}
