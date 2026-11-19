package io.github.saycm.huyaplus;

import android.graphics.Insets;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;

final class SystemBarInsets {
    static void apply(View content) {
        int left = content.getPaddingLeft();
        int top = content.getPaddingTop();
        int right = content.getPaddingRight();
        int bottom = content.getPaddingBottom();
        // Keep the safe area outside the ScrollView so scrolling cannot erase it.
        content.setOnApplyWindowInsetsListener((view, windowInsets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets safe = windowInsets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                view.setPadding(left + safe.left, top + safe.top,
                        right + safe.right, bottom + safe.bottom);
            } else {
                view.setPadding(left + windowInsets.getSystemWindowInsetLeft(),
                        top + windowInsets.getSystemWindowInsetTop(),
                        right + windowInsets.getSystemWindowInsetRight(),
                        bottom + windowInsets.getSystemWindowInsetBottom());
            }
            return windowInsets;
        });
        content.requestApplyInsets();
    }
}
