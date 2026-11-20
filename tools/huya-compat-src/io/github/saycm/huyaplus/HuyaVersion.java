package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.pm.PackageManager;

final class HuyaVersion {
    static final String PACKAGE_NAME = "com.duowan.kiwi";
    private static final String VERSION_62 = "13.5.62";
    private static final String VERSION_63 = "13.5.63";
    static final String SUPPORTED = VERSION_62 + " / " + VERSION_63;

    private HuyaVersion() {}

    static String installed(Activity activity) {
        try {
            String version = activity.getPackageManager().getPackageInfo(PACKAGE_NAME, 0).versionName;
            return version == null ? "" : version;
        } catch (PackageManager.NameNotFoundException | RuntimeException unavailable) {
            return null;
        }
    }

    static boolean supports(String version) {
        return VERSION_62.equals(version) || VERSION_63.equals(version);
    }
}
