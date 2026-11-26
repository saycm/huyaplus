package io.github.saycm.huyaplus;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.IntUnaryOperator;

public final class AutomationRules {
    static final int ALL_FREE_GRAIN = -1;

    private AutomationRules() {}

    public static boolean isResolvedRoom(long requested, long returnedRoom, long presenter) {
        return requested > 0 && presenter > 0 && (returnedRoom == 0 || returnedRoom == requested);
    }

    public static boolean isFreeGrain(int giftId, int count, long freeCount,
                                      int payMode, long paid, long deduction) {
        return giftId == 4 && count > 0 && freeCount >= count
                && payMode == 2 && paid == 0 && deduction == 0;
    }

    public static final class GrainPart {
        public final long room;
        public final int count, number, remaining;

        GrainPart(long room, int count, int number, int remaining) {
            this.room = room;
            this.count = count;
            this.number = number;
            this.remaining = remaining;
        }
    }

    public static List<GrainPart> planDiceGrain(Map<Long, Integer> rooms, IntUnaryOperator choose) {
        List<GrainPart> plan = new ArrayList<>(3);
        if (rooms.isEmpty() || rooms.size() > 3) return plan;
        int split = 4 - rooms.size();
        Long remainderRoom = null;
        for (Map.Entry<Long, Integer> room : rooms.entrySet()) {
            if (room.getValue() == ALL_FREE_GRAIN) remainderRoom = room.getKey();
        }
        if (remainderRoom != null) {
            for (Map.Entry<Long, Integer> room : rooms.entrySet()) {
                int count = room.getValue();
                if (count != ALL_FREE_GRAIN) plan.add(new GrainPart(room.getKey(), count, 1, count));
            }
            for (int index = 1; index <= split; index++) {
                plan.add(new GrainPart(remainderRoom, index == split ? ALL_FREE_GRAIN : 1,
                        index, split - index + 1));
            }
            return plan;
        }
        List<Long> eligible = new ArrayList<>();
        for (Map.Entry<Long, Integer> room : rooms.entrySet()) {
            if (room.getValue() >= split) eligible.add(room.getKey());
        }
        if (eligible.isEmpty()) return plan;
        long splitRoom = eligible.size() == 1 ? eligible.get(0) : eligible.get(choose.applyAsInt(eligible.size()));
        for (Map.Entry<Long, Integer> room : rooms.entrySet()) {
            int parts = room.getKey() == splitRoom ? split : 1;
            int remaining = room.getValue();
            for (int index = 1; index <= parts; index++) {
                int count = remaining / (parts - index + 1);
                plan.add(new GrainPart(room.getKey(), count, index, remaining));
                remaining -= count;
            }
        }
        return plan;
    }

    static String confirmedGrainPart(String day, long room, int number) {
        return "dice-grain-confirmed/" + day + "/" + room + "/" + number;
    }

    static boolean matchesGrainPlan(List<GrainPart> plan, Map<Long, Integer> rooms) {
        Map<Long, Integer> planned = new LinkedHashMap<>();
        for (GrainPart part : plan) {
            int amount = part.count == ALL_FREE_GRAIN ? ALL_FREE_GRAIN
                    : planned.getOrDefault(part.room, 0) + part.count;
            planned.put(part.room, amount);
        }
        return planned.equals(rooms);
    }

    public static Map<Long, Integer> parse(String text) {
        Map<Long, Integer> rooms = new LinkedHashMap<>();
        Long remainderRoom = null;
        for (String line : text.split("\\n")) {
            if (line.trim().isEmpty()) continue;
            String[] parts = line.trim().split("=", -1);
            if (parts.length != 2 || !parts[0].trim().matches("[0-9]+")
                    || !parts[1].trim().matches("[0-9]+|all")) {
                throw new IllegalArgumentException("请填写有效的房间号和整数数量");
            }
            long room = Long.parseLong(parts[0].trim());
            boolean all = "all".equals(parts[1].trim());
            int count = all ? ALL_FREE_GRAIN : Integer.parseInt(parts[1].trim());
            if (room <= 0 || count == 0 || rooms.containsKey(room)
                    || Long.valueOf(room).equals(remainderRoom)) {
                throw new IllegalArgumentException("房间号和数量必须大于零，房间不能重复");
            }
            if (all) {
                if (remainderRoom != null) throw new IllegalArgumentException("只能为一个直播间赠送剩余免费虎粮");
                remainderRoom = room;
            } else rooms.put(room, count);
        }
        if (remainderRoom != null) rooms.put(remainderRoom, ALL_FREE_GRAIN);
        return rooms;
    }

    public static int giftCount(int count, int required, long free) {
        if (free < required) return 0;
        if (count != ALL_FREE_GRAIN) return count;
        return free <= Integer.MAX_VALUE ? (int) free : 0;
    }

    public static String normalize(String text) {
        StringBuilder value = new StringBuilder();
        for (Map.Entry<Long, Integer> room : parse(text).entrySet()) {
            if (value.length() > 0) value.append('\n');
            value.append(room.getKey()).append('=').append(savedCount(room.getValue()));
        }
        return value.toString();
    }

    static String savedCount(int count) {
        return count == ALL_FREE_GRAIN ? "all" : Integer.toString(count);
    }
}
