"""Verify the module package uses the libxposed API 102 descriptor."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "tools/huya-module-src"
META_DIR = MODULE_DIR / "resources/META-INF/xposed"
ENTRY = "io.github.saycm.huyaplus.HuyaCompatEntry"
API_VERSION = "102.0.0"
API_AAR = ROOT / "build/deps" / f"api-{API_VERSION}.aar"
JDK = Path(os.environ["JAVA_HOME"])
SDK = Path(os.environ["ANDROID_HOME"])
EXE = ".exe" if os.name == "nt" else ""


class HuyaApi102MetadataTest(unittest.TestCase):
    def test_module_prop_targets_api_102(self):
        props = {}
        for line in (META_DIR / "module.prop").read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                props[key] = value

        self.assertEqual("102", props["minApiVersion"])
        self.assertEqual("102", props["targetApiVersion"])
        self.assertEqual("true", props["staticScope"])
        self.assertEqual("false", props["autoHotReload"])

    def test_modern_entry_and_scope_lists_are_packaged(self):
        self.assertEqual(
            [ENTRY],
            (META_DIR / "java_init.list").read_text(encoding="utf-8").splitlines(),
        )
        self.assertEqual(
            ["com.duowan.kiwi"],
            (META_DIR / "scope.list").read_text(encoding="utf-8").splitlines(),
        )

    def test_manifest_does_not_use_legacy_xposed_metadata(self):
        manifest = (MODULE_DIR / "AndroidManifest.xml").read_text(encoding="utf-8")
        strings = (MODULE_DIR / "res/values/strings.xml").read_text(encoding="utf-8")
        self.assertNotIn('"xposedmodule"', manifest)
        self.assertNotIn('"xposedminversion"', manifest)
        self.assertNotIn('"xposedscope"', manifest)
        self.assertIn('<string name="app_name">虎牙 plus</string>', strings)
        self.assertIn("<queries>", manifest)
        self.assertIn('<package android:name="com.duowan.kiwi" />', manifest)
        self.assertIn('android:description="@string/app_description"', manifest)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertTrue(
            (MODULE_DIR / "res/mipmap-xxxhdpi/ic_launcher.png").is_file(),
            "launcher icon is missing",
        )
        self.assertIn('android:versionCode="28"', manifest)
        self.assertIn('android:versionName="1.27"', manifest)
        self.assertIn('android:name=".GlassDashboardActivity"', manifest)
        self.assertIn('android:name=".AppDetailActivity"', manifest)
        self.assertIn('android:theme="@style/GlassDashboard"', manifest)
        self.assertIn('io.github.libxposed.service.XposedProvider', manifest)
        self.assertIn('io.github.saycm.huyaplus.XposedService', manifest)

    def test_glass_dashboard_resources_and_activity_exist(self):
        layout = MODULE_DIR / "res/layout/activity_glass_dashboard.xml"
        detail_layout = MODULE_DIR / "res/layout/activity_app_detail.xml"
        hero_pika = MODULE_DIR / "res/drawable-xxxhdpi/ic_hero_pikachu.png"
        app_pika = MODULE_DIR / "res/drawable-xxxhdpi/ic_app_pikachu.png"
        activity = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassDashboardActivity.java"
        )
        detail_activity = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/AppDetailActivity.java"
        )
        mine_settings = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/MineSettingsActivity.java"
        )
        self.assertTrue(layout.is_file(), "glass dashboard layout is missing")
        self.assertTrue(detail_layout.is_file(), "app detail layout is missing")
        self.assertTrue(activity.is_file(), "glass dashboard activity is missing")
        self.assertTrue(detail_activity.is_file(), "app detail activity is missing")
        layout_text = layout.read_text(encoding="utf-8")
        for name in (
            "status_card",
            "hero_avatar",
            "app_card",
            "action_app",
            "status_dot",
            "status_primary",
            "status_secondary",
            "guide_card",
            "community_channel_row",
            "community_discussion_row",
        ):
            self.assertIn(f'@+id/{name}', layout_text)
        for name in (
            "features_card",
            "switch_ads",
            "switch_vip_4k",
            "status_remote",
            "copy_diagnostics",
            "info_card",
            "status_module",
        ):
            self.assertNotIn(f'@+id/{name}', layout_text)
        self.assertIn("Uri.parse", activity.read_text(encoding="utf-8"))
        self.assertIn('name="dashboard_version">v1.27</string>',
                      (MODULE_DIR / "res/values/strings.xml").read_text(encoding="utf-8"))
        detail_text = detail_layout.read_text(encoding="utf-8")
        self.assertTrue(hero_pika.is_file(), "hero pikachu drawable is missing")
        self.assertTrue(app_pika.is_file(), "app pikachu drawable is missing")
        self.assertIn("@drawable/ic_hero_pikachu", layout_text)
        self.assertIn("@drawable/ic_app_pikachu", layout_text)
        self.assertIn("@drawable/ic_app_pikachu", detail_text)
        self.assertEqual(2, layout_text.count("@drawable/tg_avatar"))
        self.assertTrue(
            (MODULE_DIR / "res/drawable-xxxhdpi/tg_avatar.png").is_file(),
            "telegram avatar drawable is missing",
        )
        for name in (
            "detail_back",
            "action_open_app",
            "app_status",
            "features_card",
            "copy_diagnostics_detail",
        ):
            self.assertIn(f'@+id/{name}', detail_text)
        for switch in (
            "ads",
            "rewards",
            "vip_ads",
            "vip_4k",
        ):
            self.assertIn(f'@+id/switch_{switch}_value', detail_text)
            self.assertIn(f'@+id/switch_{switch}', detail_text)
        for key in (
            "live_cards",
            "live_landscape_mark",
            "live_landscape_sidebar",
            "live_cart",
            "live_red_packet",
            "live_week_star",
            "live_ad_banner",
            "live_ad_float",
        ):
            self.assertNotIn(f'@+id/switch_{key}_value', detail_text)
            self.assertIn(
                f'GlassSettings.KEY_{key.upper()}',
                mine_settings.read_text(encoding="utf-8"),
            )
        self.assertIn("AppDetailActivity.class", activity.read_text(encoding="utf-8"))
        activity_text = activity.read_text(encoding="utf-8")
        detail_activity_text = detail_activity.read_text(encoding="utf-8")
        for screen in (activity_text, detail_activity_text):
            self.assertIn("HuyaVersion.installed(this)", screen)
            self.assertIn("HuyaVersion.supports(", screen)
        self.assertTrue(
            (
                ROOT
                / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettingsBridge.java"
            ).is_file()
        )

    def test_glass_dashboard_toggles_control_hook_groups(self):
        detail_activity = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/AppDetailActivity.java"
        )
        entry = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java"
        )
        settings = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettings.java"
        )
        mine_settings = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/MineSettingsActivity.java"
        ).read_text(encoding="utf-8")
        settings_text = settings.read_text(encoding="utf-8")
        detail_text = detail_activity.read_text(encoding="utf-8")
        self.assertIn("GlassSettings.PREFS", detail_text)
        self.assertIn("bindSwitch(R.id.switch_ads_value", detail_text)
        self.assertIn("syncSwitch(R.id.switch_vip_4k_value", detail_text)
        self.assertIn("GlassSettings.PREFS", entry.read_text(encoding="utf-8"))
        entry_text = entry.read_text(encoding="utf-8")
        self.assertIn("getRemotePreferences(", entry_text)
        for key in (
            "ads",
            "live_cards",
            "live_landscape_mark",
            "live_landscape_sidebar",
            "live_cart",
            "live_red_packet",
            "live_week_star",
            "rewards",
            "vip_ads",
            "vip_4k",
        ):
            self.assertIn(f"KEY_{key.upper()}", settings_text)
            self.assertTrue(
                f"GlassSettings.KEY_{key.upper()}" in detail_text
                or f"GlassSettings.KEY_{key.upper()}" in mine_settings
            )

    def test_native_task_catalog_has_per_task_switches_and_cross_process_sync(self):
        panel = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/AutomationPanel.java"
        ).read_text(encoding="utf-8")
        provider = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/TaskLogProvider.java"
        ).read_text(encoding="utf-8")
        store = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/LocalTaskStore.java"
        ).read_text(encoding="utf-8")
        runner = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/NativeTaskRunner.java"
        ).read_text(encoding="utf-8")
        self.assertIn('"read_tasks"', provider)
        self.assertIn('"import_tasks"', provider)
        self.assertIn("replaceTasks", store)
        self.assertIn("taskEnabled", runner)
        self.assertIn("host.publish(catalog)", runner)
        self.assertIn("NativeTaskCatalog.switchKey", panel)
        self.assertIn("TaskLogProvider.URI", panel)
        self.assertIn("任务开关已关闭", runner)
        self.assertNotIn('claim("task-center-native-actions-v1/', runner)

    def test_log_page_waits_for_sync_revision_instead_of_one_fixed_delay(self):
        activity = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/TaskLogActivity.java"
        ).read_text(encoding="utf-8")
        self.assertIn("lastSync() > syncBaseline", activity)
        self.assertIn("SYNC_POLL_MS", activity)
        self.assertIn("SYNC_TIMEOUT_MS", activity)
        self.assertNotIn("postDelayed(afterSync, 900L)", activity)

    def test_log_page_uses_compact_rows_instead_of_individual_glass_cards(self):
        activity = (
            ROOT
            / "tools/huya-compat-src/io/github/saycm/huyaplus/TaskLogActivity.java"
        ).read_text(encoding="utf-8")
        self.assertIn("private LinearLayout logRow", activity)
        self.assertIn("private View divider", activity)
        self.assertNotIn("LinearLayout item = card(logs);", activity)

    def test_glass_dashboard_build_resolves_generated_resources(self):
        build_script = (ROOT / "tools/build.py").read_text(encoding="utf-8")
        self.assertIn('aapt2, "link"', build_script)
        self.assertIn('(build / "gen").rglob("*.java")', build_script)
        self.assertIn('libxposed_service_jar', build_script)
        self.assertIn('libxposed_interface_jar', build_script)
        self.assertIn('archive.extractall(build / "classes")', build_script)
        self.assertLess(
            build_script.index('aapt2, "link"'),
            build_script.index('javac'),
            "resources must be linked before Java sources compile",
        )
        self.assertNotIn("BuildConfig.VERSION_NAME", build_script)

    def test_entry_compiles_against_api_102_only(self):
        self.assertTrue(API_AAR.is_file(), f"missing API fixture: {API_AAR}")
        with tempfile.TemporaryDirectory(prefix="huya-api102-") as folder:
            root = Path(folder)
            api_jar = root / "api-102.0.0.jar"
            with zipfile.ZipFile(API_AAR) as aar:
                api_jar.write_bytes(aar.read("classes.jar"))

            android = SDK / "platforms/android-36/android.jar"
            classes = root / "classes"
            classes.mkdir()
            source = (
                ROOT
                / "tools/huya-compat-src/io/github/saycm/huyaplus/HuyaCompatEntry.java"
            )
            settings = (
                ROOT
                / "tools/huya-compat-src/io/github/saycm/huyaplus/GlassSettings.java"
            )
            result = subprocess.run(
                [
                    str(JDK / "bin" / ("javac" + EXE)),
                    "-encoding",
                    "UTF-8",
                    "-cp",
                    os.pathsep.join((str(android), str(api_jar))),
                    "-d",
                    str(classes),
                    "-sourcepath",
                    str(ROOT / "tools/huya-compat-src"),
                    str(source),
                    str(settings),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            signature = subprocess.run(
                [
                    str(JDK / "bin" / ("javap" + EXE)),
                    "-classpath",
                    os.pathsep.join((str(classes), str(api_jar), str(android))),
                    ENTRY,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertIn("extends io.github.libxposed.api.XposedModule", signature)
            self.assertIn("void onPackageReady(", signature)


if __name__ == "__main__":
    unittest.main()
