from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOLS = Path(os.environ["ANDROID_HOME"]) / "build-tools" / "36.0.0"
EXE = ".exe" if os.name == "nt" else ""
BAT = ".bat" if os.name == "nt" else ""
APKSIGNER = BUILD_TOOLS / ("apksigner" + BAT)
AAPT2 = BUILD_TOOLS / ("aapt2" + EXE)
APKANALYZER = Path(os.environ["ANDROID_HOME"]) / "cmdline-tools/latest/bin" / ("apkanalyzer" + BAT)
ENTRY = "io.github.saycm.huyaplus.HuyaCompatEntry"
TARGET_CLASS = "com.huya.kiwi.hyext.impl.modules.internal.HyExtAd"
AMS_HELPER = "com.duowan.kiwi.ad.helper.AmsAdHelper"
AMS_LISTENER = "com.huya.adbusiness.ams.IAmsAdRewardADListener"
REWARD_RESULT = "com.qq.e.tg.rewardAD.RewardResult"
AD_SPLASH_FRAGMENT = "com.duowan.kiwi.adsplash.view.AdSplashFragment"


def run(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    assert args.module.is_file(), f"module not found: {args.module}"
    with zipfile.ZipFile(args.module) as apk:
        names = set(apk.namelist())
        assert "classes.dex" in names
        assert "assets/xposed_init" not in names
        assert apk.read("META-INF/xposed/java_init.list").decode("utf-8").splitlines() == [ENTRY]
        assert apk.read("META-INF/xposed/scope.list").decode("utf-8").splitlines() == [
            "com.duowan.kiwi"
        ]
        module_prop = {}
        for line in apk.read("META-INF/xposed/module.prop").decode("utf-8").splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                module_prop[key] = value
        assert module_prop["minApiVersion"] == "102"
        assert module_prop["targetApiVersion"] == "102"
        assert module_prop["staticScope"] == "true"

    manifest = run(str(AAPT2), "dump", "xmltree", "--file", "AndroidManifest.xml", str(args.module))
    assert 'package="io.github.saycm.huyaplus"' in manifest
    assert "io.github.libxposed.service.XposedProvider" in manifest
    assert "io.github.saycm.huyaplus.XposedService" in manifest
    assert run(str(APKANALYZER), "manifest", "version-code", str(args.module)).strip() == "23"
    assert run(str(APKANALYZER), "manifest", "version-name", str(args.module)).strip() == "1.22"
    assert "xposedmodule" not in manifest
    assert "xposedminversion" not in manifest

    defined = run(str(APKANALYZER), "dex", "packages", "--defined-only", str(args.module))
    assert ENTRY.replace(".", "/") in defined or "io.github.saycm.huyaplus" in defined
    assert "io.github.libxposed.service.XposedService" in defined
    assert "io.github.libxposed.service.XposedProvider" in defined
    for name in ("TaskWire", "NativeTaskCatalog", "NativeTaskRunner", "HuyaTaskClient", "NativeTaskAutomation"):
        assert "io.github.saycm.huyaplus." + name in defined, f"missing task class {name}"
    assert not re.search(r"^C\s+d\s+.*\tde\.robv\.android\.xposed", defined, re.MULTILINE), \
        "module contains legacy Xposed classes"
    assert not re.search(r"^C\s+d\s+.*\tio\.github\.libxposed\.api", defined, re.MULTILINE), \
        "module bundles compile-only libxposed API classes"

    entry_code = run(str(APKANALYZER), "dex", "code", "--class", ENTRY, str(args.module))
    assert ".super Lio/github/libxposed/api/XposedModule;" in entry_code
    for expected in (
        '"com.duowan.kiwi"',
        '"com.huya.kiwi.hyext.impl.modules.internal.HyExtAd"',
        '"showRewardedVideoAd"',
        '"showCustomAd"',
        '"openCustomAd"',
        '"customAdId"',
        '"customAdReward"',
        '"isSuccess"',
        '"com.duowan.kiwi.popup.impl.PopupModule"',
        '"tryShowPopup"',
        '"tryPlaceholderPopup"',
        '"getBusinessKey"',
        '"_autotrigger"',
        '"com.duowan.kiwi.livead.impl.adplugin.module.HYRoomPopupPlugin"',
        '"enqueue"',
        '"floatball_ad_"',
        '"com.duowan.kiwi.popup.impl.pubscreen.PopupStrategyConditionHelper"',
        '"checkPlatformVipFilter"',
        '"getSummary"',
        '"iIsNoShowForPlatformVip"',
        '"com.duowan.kiwi.live.vip4k.Vip4KPlayHelper"',
        '"isPlatformVipActive"',
        '"com.huya.kiwi.hyext.delegate.api.HYExtRightTopWindowModeManager"',
        '"createFloatWindowItemView"',
        '"com.duowan.kiwi.universal.live.activitybar.banner.UniversalLiveBannerView"',
        '"rewardedVideoAdId"',
        '"rewardedVideoAdClose"',
        '"isEnded"',
        '"dispatchEvent"',
        '"onSuccess"',
        f'"{AMS_HELPER}"',
        '"onCallAmsRewardAd"',
        f'"{AMS_LISTENER}"',
        f'"{REWARD_RESULT}"',
        f'"{AD_SPLASH_FRAGMENT}"',
        '"onVisibleToUser"',
        '"onADShow"',
        '"onADExpose"',
        '"onADComplete"',
        '"onReward"',
        '"onADClose"',
        '"com.duowan.kiwi.adsplash.controller.AdRouter"',
        '"isNeedShowAdSplash"',
        '"com.duowan.kiwi.ad.impl.HyAdModule"',
        '"isNeedShieldAdOutLivingRoom"',
        '"com.duowan.kiwi.listframe.adapter.ListLineRecyclerViewAdapter"',
        '"com.duowan.kiwi.listline.ListLineAdapter"',
        '"com.duowan.kiwi.list.homepage.tab.recommend.BaseRecommendPresenter"',
        '"com.duowan.kiwi.list.patface.chain.PatFaceInterceptorChain"',
        '"onLiveListAdBack"',
        ".method public onPackageReady(",
    ):
        assert expected in entry_code, f"compat DEX is missing {expected}"

    for expected in ('"dismissWhenError"', '"module_skip_splash"'):
        assert expected in entry_code, f"splash hook DEX is missing {expected}"

    target_code = run(str(APKANALYZER), "dex", "code", "--class", TARGET_CLASS, str(args.target))
    assert (
        ".method public final showRewardedVideoAd(Ljava/lang/Object;"
        "Lcom/huya/hybrid/webview/jssdk/JsCallback;)V"
    ) in target_code
    assert '"rewardedVideoAdClose"' in target_code
    assert '"isEnded"' in target_code
    assert (
        ".method public final openCustomAd(Ljava/lang/Object;"
        "Lcom/huya/hybrid/webview/jssdk/JsCallback;)V"
    ) in target_code
    assert (
        ".method public final showCustomAd(Ljava/lang/Object;"
        "Lcom/huya/hybrid/webview/jssdk/JsCallback;)V"
    ) in target_code
    assert '"customAdReward"' in target_code
    assert '"isSuccess"' in target_code

    ams_helper_code = run(str(APKANALYZER), "dex", "code", "--class", AMS_HELPER, str(args.target))
    assert (
        ".method public onCallAmsRewardAd(Ljava/util/Map;Lcom/duowan/HUYA/AdInfo;"
        "Landroid/app/Activity;Lkotlin/jvm/functions/Function1;"
        "Lcom/huya/adbusiness/ams/IAmsAdRewardADListener;Ljava/util/Map;)V"
    ) in ams_helper_code

    reward_result_code = run(
        str(APKANALYZER), "dex", "code", "--class", REWARD_RESULT, str(args.target)
    )
    assert ".method public constructor <init>()V" in reward_result_code
    assert ".method public setPassthrough(Ljava/lang/String;)V" in reward_result_code

    splash_code = run(
        str(APKANALYZER), "dex", "code", "--class", AD_SPLASH_FRAGMENT, str(args.target)
    )
    assert (
        ".method public onCreateView(Landroid/view/LayoutInflater;"
        "Landroid/view/ViewGroup;Landroid/os/Bundle;)Landroid/view/View;"
    ) in splash_code
    assert ".method public onVisibleToUser()V" in splash_code
    assert ".method public dismissWhenError(Ljava/lang/String;)V" in splash_code

    display_interfaces = {
        "ryxq.ev6": (
            ".method public static a(Lcom/duowan/jce/wup/UniPacket;IILjava/lang/Number;"
            "Lcom/huya/kiwi/crossplatform/common/wup/HybridJceCallback;)Lryxq/ev6;",
        ),
        "com.huya.kiwi.crossplatform.common.wup.HybridJceCallback": (
            ".method public abstract onResponse([B)V",
            ".method public abstract onTraceId(Ljava/lang/String;)V",
            ".method public abstract a(Lryxq/zu6;)V",
        ),
        "com.duowan.jce.wup.UniPacket": (
            ".method public constructor <init>()V",
            ".method public decode([B)V",
        ),
        "com.duowan.kiwi.popup.impl.pubscreen.PopupStrategyConditionHelper": (
            ".method public final checkPlatformVipFilter(Lcom/duowan/kiwi/popup/api/PopupItem;)Z",
        ),
        "com.duowan.kiwi.live.vip4k.Vip4KPlayHelper": (
            ".method public final isPlatformVipActive()Z",
        ),
        "com.duowan.kiwi.universal.live.activitybar.banner.UniversalLiveBannerView": (
            ".method public setData(Ljava/util/List;)V",
        ),
        "com.huya.kiwi.hyext.delegate.api.HYExtRightTopWindowModeManager": (
            ".method public final createFloatWindowItemView("
            "Lcom/duowan/kiwi/passage/api/view/floatwindow/IFloatWindowContainer;"
            "Lcom/huya/oak/miniapp/container/internal/MiniAppPopupFragment;"
            "Lcom/duowan/HUYA/ActCommEnt;IZ)V",
        ),
        "com.duowan.kiwi.popup.impl.PopupModule": (
            ".method public tryShowPopup(Lcom/duowan/kiwi/popup/api/PopupItem;)Z",
            ".method public tryPlaceholderPopup(Lcom/duowan/kiwi/popup/api/PopupItem;)Z",
        ),
        "com.duowan.kiwi.popup.api.PopupItem": (
            ".method public getBusinessKey()Ljava/lang/String;",
            ".method public getSummary()Lcom/duowan/HUYA/LiveRoomPopupWindowSummary;",
        ),
        "com.duowan.kiwi.livead.impl.adplugin.module.HYRoomPopupPlugin": (
            ".method public enqueue(Ljava/lang/String;Ljava/lang/String;"
            "Lcom/duowan/kiwi/livead/api/adplugin/api/IHYRoomPopupPlugin$IHYChannelAvailabilityCheckCallback;)V",
        ),
        "com.duowan.kiwi.adsplash.controller.AdRouter": (
            ".method public final isNeedShowAdSplash(Landroid/content/Context;ZZZ)I",
        ),
        "com.duowan.kiwi.ad.impl.HyAdModule": (
            ".method public isNeedShieldAdOutLivingRoom()Z",
        ),
        "com.duowan.kiwi.list.patface.chain.PatFaceInterceptorChain": (
            ".method public final proceed(I)Z",
        ),
        "com.duowan.kiwi.listframe.component.LineItem": (
            ".method public getLineItem()Landroid/os/Parcelable;",
        ),
        "com.duowan.kiwi.listframe.adapter.ListLineRecyclerViewAdapter": (
            ".method public replaceAndNotify(Ljava/util/List;)V",
            ".method public insertAndNotify(Lcom/duowan/kiwi/listframe/component/LineItem;I)V",
        ),
        "com.duowan.kiwi.listline.ListLineAdapter": (
            ".method public replaceAndNotify(Ljava/util/List;)V",
            ".method public insertItemAndNotify(Lcom/duowan/kiwi/listframe/component/LineItem;I)V",
        ),
    }
    for class_name, methods in display_interfaces.items():
        code = run(str(APKANALYZER), "dex", "code", "--class", class_name, str(args.target))
        for method in methods:
            assert method in code, f"target interface is missing {class_name}: {method}"

    signature = run(str(APKSIGNER), "verify", "--verbose", str(args.module))
    assert "Verifies" in signature
    assert "Verified using v2 scheme (APK Signature Scheme v2): true" in signature or \
        "Verified using v3 scheme (APK Signature Scheme v3): true" in signature

    digest = hashlib.sha256(args.module.read_bytes()).hexdigest().upper()
    print(f"Verified module: {args.module}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
