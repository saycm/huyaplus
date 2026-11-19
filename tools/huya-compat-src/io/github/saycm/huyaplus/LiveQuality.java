package io.github.saycm.huyaplus;

import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class LiveQuality {
    public static final int FOLLOW = -1;
    public static final int BLUE_RAY = -2;
    private static final int MIN_BLUE_RAY_BITRATE = 4000;
    private static final Pattern BLUE_RAY_MEGABITS = Pattern.compile(
            "(\\d+(?:\\.\\d+)?)\\s*(?:M|MB|MBPS|兆)?",
            Pattern.CASE_INSENSITIVE);

    private LiveQuality() {
    }

    public static int select(int preferred, int original, Set<Integer> available) {
        int resolved = preferred == 0 || preferred == BLUE_RAY
                ? highestBlueRay(available) : preferred;
        return resolved >= 0 && available.contains(resolved) ? resolved : original;
    }

    public static int select(
            int preferred, int original, Map<Integer, String> available) {
        int resolved = preferred == 0 || preferred == BLUE_RAY
                ? highestBlueRay(available) : preferred;
        return resolved >= 0 && available.containsKey(resolved)
                ? resolved : original;
    }

    private static int highestBlueRay(Set<Integer> available) {
        int selected = -1;
        for (int bitrate : available) {
            if (bitrate >= MIN_BLUE_RAY_BITRATE && bitrate > selected) {
                selected = bitrate;
            }
        }
        return selected;
    }

    private static int highestBlueRay(Map<Integer, String> available) {
        int selected = -1;
        double selectedMegabits = -1;
        boolean found = false;
        for (Map.Entry<Integer, String> option : available.entrySet()) {
            int bitrate = option.getKey();
            String name = option.getValue();
            if (bitrate < 0 || !isBlueRay(name)) {
                continue;
            }
            found = true;
            double megabits = advertisedMegabits(name);
            if (megabits > selectedMegabits
                    || (megabits == selectedMegabits && bitrate > selected)) {
                selected = bitrate;
                selectedMegabits = megabits;
            }
        }
        return found ? selected : -1;
    }

    private static boolean isBlueRay(String name) {
        if (name == null) {
            return false;
        }
        return name.contains("蓝光")
                || name.toUpperCase(Locale.ROOT).contains("BLU-RAY")
                || name.toUpperCase(Locale.ROOT).contains("BLURAY");
    }

    private static double advertisedMegabits(String name) {
        if (name == null) {
            return -1;
        }
        Matcher matcher = BLUE_RAY_MEGABITS.matcher(name);
        return matcher.find() ? Double.parseDouble(matcher.group(1)) : -1;
    }
}
