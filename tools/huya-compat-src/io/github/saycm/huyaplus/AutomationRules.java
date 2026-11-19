package io.github.saycm.huyaplus;

import java.util.LinkedHashMap;
import java.util.Map;

public final class AutomationRules {
    private AutomationRules() {}

    public static boolean isResolvedRoom(long requested, long returnedRoom, long presenter) {
        return requested > 0 && presenter > 0 && (returnedRoom == 0 || returnedRoom == requested);
    }

    public static boolean isFreeGrain(int giftId, int count, long freeCount,
                                      int payMode, long paid, long deduction) {
        return giftId == 4 && count > 0 && freeCount >= count
                && payMode == 2 && paid == 0 && deduction == 0;
    }

    public static Map<Long, Integer> parse(String text) {
        Map<Long, Integer> rooms = new LinkedHashMap<>();
        for (String line : text.split("\\n")) {
            if (line.trim().isEmpty()) continue;
            String[] parts = line.trim().split("=", -1);
            if (parts.length != 2 || !parts[0].trim().matches("[0-9]+")
                    || !parts[1].trim().matches("[0-9]+")) {
                throw new IllegalArgumentException("请填写有效的房间号和整数数量");
            }
            long room = Long.parseLong(parts[0].trim());
            int count = Integer.parseInt(parts[1].trim());
            if (room <= 0 || count <= 0 || rooms.containsKey(room)) {
                throw new IllegalArgumentException("房间号和数量必须大于零，房间不能重复");
            }
            rooms.put(room, count);
        }
        return rooms;
    }

    public static String normalize(String text) {
        StringBuilder value = new StringBuilder();
        for (Map.Entry<Long, Integer> room : parse(text).entrySet()) {
            if (value.length() > 0) value.append('\n');
            value.append(room.getKey()).append('=').append(room.getValue());
        }
        return value.toString();
    }
}
