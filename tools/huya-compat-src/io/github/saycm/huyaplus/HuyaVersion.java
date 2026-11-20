package io.github.saycm.huyaplus;

import android.app.Activity;
import android.content.pm.PackageManager;

final class HuyaVersion {
    static final String PACKAGE_NAME = "com.duowan.kiwi";
    static final String SUPPORTED = "13.5.62";

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
        return SUPPORTED.equals(version);
    }
}
