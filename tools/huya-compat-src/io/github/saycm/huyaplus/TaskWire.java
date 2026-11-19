package io.github.saycm.huyaplus;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.BufferUnderflowException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** The bounded subset of TAF/JCE used by the native welfare page. */
final class TaskWire {
    static final int MAX_BYTES = 4 * 1024 * 1024;
    static final class Struct extends LinkedHashMap<Integer, Object> {
        Struct field(int tag, Object value) { put(tag, value); return this; }
        long number(int tag) { Object v = get(tag); return v instanceof Number ? ((Number) v).longValue() : 0; }
        String text(int tag) { Object v = get(tag); return v instanceof String ? (String) v : ""; }
    }
    static final class Reply {
        final Struct body;
        final int code;
        Reply(Struct body, int code) { this.body = body; this.code = code; }
    }

    static byte[] encode(Struct fields) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (Map.Entry<Integer, Object> field : new TreeMap<>(fields).entrySet()) write(out, field.getKey(), field.getValue(), 0);
        if (out.size() > MAX_BYTES) throw new IllegalArgumentException("Task packet too large");
        return out.toByteArray();
    }

    private static void head(ByteArrayOutputStream out, int tag, int type) {
        if (tag < 0 || tag > 255) throw new IllegalArgumentException("Invalid field tag");
        out.write(((tag < 15 ? tag : 15) << 4) | type);
        if (tag >= 15) out.write(tag);
    }

    private static void bits(ByteArrayOutputStream out, long value, int count) {
        for (int i = count - 1; i >= 0; i--) out.write((int) (value >>> (i * 8)) & 255);
    }

    private static void write(ByteArrayOutputStream out, int tag, Object value, int depth) {
        if (depth > 32 || out.size() > MAX_BYTES) throw new IllegalArgumentException("Task packet too large");
        if (value instanceof Number) {
            long n = ((Number) value).longValue();
            if (n == 0) head(out, tag, 12);
            else if (n >= -128 && n <= 127) { head(out, tag, 0); bits(out, n, 1); }
            else if (n >= -32768 && n <= 32767) { head(out, tag, 1); bits(out, n, 2); }
            else if (n >= Integer.MIN_VALUE && n <= Integer.MAX_VALUE) { head(out, tag, 2); bits(out, n, 4); }
            else { head(out, tag, 3); bits(out, n, 8); }
        } else if (value instanceof String) {
            byte[] bytes = ((String) value).getBytes(StandardCharsets.UTF_8);
            if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("Task string too large");
            head(out, tag, bytes.length <= 255 ? 6 : 7);
            bits(out, bytes.length, bytes.length <= 255 ? 1 : 4);
            out.write(bytes, 0, bytes.length);
        } else if (value instanceof byte[]) {
            byte[] bytes = (byte[]) value;
            if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("Task bytes too large");
            head(out, tag, 13); head(out, 0, 0); write(out, 0, bytes.length, depth + 1);
            out.write(bytes, 0, bytes.length);
        } else if (value instanceof Struct) {
            head(out, tag, 10);
            for (Map.Entry<Integer, Object> field : new TreeMap<>((Struct) value).entrySet()) {
                write(out, field.getKey(), field.getValue(), depth + 1);
            }
            head(out, 0, 11);
        } else if (value instanceof Map) {
            Map<?, ?> map = (Map<?, ?>) value;
            if (map.size() > 10000) throw new IllegalArgumentException("Task map too large");
            head(out, tag, 8); write(out, 0, map.size(), depth + 1);
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                write(out, 0, entry.getKey(), depth + 1); write(out, 1, entry.getValue(), depth + 1);
            }
        } else if (value instanceof List) {
            List<?> list = (List<?>) value;
            if (list.size() > 10000) throw new IllegalArgumentException("Task list too large");
            head(out, tag, 9); write(out, 0, list.size(), depth + 1);
            for (Object entry : list) write(out, 0, entry, depth + 1);
        } else throw new IllegalArgumentException("Unsupported task field");
    }

    static Struct decode(byte[] bytes) {
        if (bytes == null || bytes.length > MAX_BYTES) throw new IllegalArgumentException("Invalid task data length");
        try { return new Reader(bytes).fields(false, 0); }
        catch (BufferUnderflowException | ClassCastException failure) {
            throw new IllegalArgumentException("Truncated task data", failure);
        }
    }

    private static final class Reader {
        final ByteBuffer data;
        Reader(byte[] bytes) { data = ByteBuffer.wrap(bytes); }
        int header() {
            int b = data.get() & 255;
            int tag = (b >>> 4) == 15 ? data.get() & 255 : b >>> 4;
            return (tag << 4) | (b & 15);
        }
        Struct fields(boolean ended, int depth) {
            Struct fields = new Struct();
            while (data.hasRemaining()) {
                int h = header();
                if ((h & 15) == 11) {
                    if (!ended) throw new IllegalArgumentException("Unexpected struct end");
                    return fields;
                }
                if (fields.containsKey(h >>> 4)) throw new IllegalArgumentException("Duplicate task field");
                fields.put(h >>> 4, value(h & 15, depth + 1));
            }
            if (ended) throw new IllegalArgumentException("Missing struct end");
            return fields;
        }
        int size(int max) {
            int h = header();
            if ((h >>> 4) != 0 || (h & 15) > 3 && (h & 15) != 12) {
                throw new IllegalArgumentException("Invalid collection size");
            }
            long n = ((Number) value(h & 15, 0)).longValue();
            if (n < 0 || n > max) throw new IllegalArgumentException("Task collection too large");
            return (int) n;
        }
        byte[] bytes(int size) {
            if (size < 0 || size > data.remaining()) throw new IllegalArgumentException("Invalid task byte length");
            byte[] bytes = new byte[size]; data.get(bytes); return bytes;
        }
        Object value(int type, int depth) {
            if (depth > 32) throw new IllegalArgumentException("Task nesting too deep");
            switch (type) {
                case 0: return (long) data.get();
                case 1: return (long) data.getShort();
                case 2: return (long) data.getInt();
                case 3: return data.getLong();
                case 4: return (double) data.getFloat();
                case 5: return data.getDouble();
                case 6: return new String(bytes(data.get() & 255), StandardCharsets.UTF_8);
                case 7: return new String(bytes(data.getInt()), StandardCharsets.UTF_8);
                case 8: {
                    int count = size(10000); Map<Object, Object> map = new LinkedHashMap<>();
                    for (int i = 0; i < count; i++) {
                        int key = header(); Object k = value(key & 15, depth + 1);
                        int val = header(); map.put(k, value(val & 15, depth + 1));
                    }
                    return map;
                }
                case 9: {
                    int count = size(10000); List<Object> list = new ArrayList<>();
                    for (int i = 0; i < count; i++) list.add(value(header() & 15, depth + 1));
                    return list;
                }
                case 10: return fields(true, depth + 1);
                case 12: return 0L;
                case 13:
                    if (header() != 0) throw new IllegalArgumentException("Unsupported byte list");
                    return bytes(size(MAX_BYTES));
                default: throw new IllegalArgumentException("Unknown task wire type");
            }
        }
    }

    static byte[] packet(String servant, String function, Struct body, int id) {
        byte[] request = encode(new Struct().field(0, body));
        Map<String, byte[]> values = new LinkedHashMap<>(); values.put("tReq", request);
        byte[] inner = encode(new Struct().field(0, values));
        Struct packet = new Struct().field(1, 3).field(2, 0).field(3, 0).field(4, id)
                .field(5, servant).field(6, function).field(7, inner).field(8, 15000)
                .field(9, new LinkedHashMap<>()).field(10, new LinkedHashMap<>());
        byte[] encoded = encode(packet);
        if (encoded.length + 4 > MAX_BYTES) throw new IllegalArgumentException("Packet too large");
        return ByteBuffer.allocate(encoded.length + 4).putInt(encoded.length + 4).put(encoded).array();
    }

    static Struct unpack(byte[] bytes) {
        if (bytes == null || bytes.length < 4 || bytes.length > MAX_BYTES
                || ByteBuffer.wrap(bytes).getInt() != bytes.length) throw new IllegalArgumentException("Invalid WUP length");
        byte[] body = new byte[bytes.length - 4]; System.arraycopy(bytes, 4, body, 0, body.length);
        Struct packet = decode(body);
        if (packet.number(1) != 3) throw new IllegalArgumentException("Unsupported WUP version");
        return packet;
    }

    static Reply reply(byte[] bytes, String name) {
        Struct packet = unpack(bytes);
        Object raw = packet.get(7);
        if (!(raw instanceof byte[])) throw new IllegalArgumentException("Missing WUP body");
        Object data = decode((byte[]) raw).get(0);
        if (!(data instanceof Map)) throw new IllegalArgumentException("Missing WUP attributes");
        Map<?, ?> values = (Map<?, ?>) data;
        int code = 0;
        Object codeBytes = values.get("");
        if (codeBytes instanceof byte[]) code = (int) decode((byte[]) codeBytes).number(0);
        Object status = packet.get(10);
        if (status instanceof Map && ((Map<?, ?>) status).containsKey("STATUS_RESULT_CODE")) {
            int outer = Integer.parseInt(String.valueOf(((Map<?, ?>) status).get("STATUS_RESULT_CODE")));
            if (outer != 0) code = outer;
        }
        Object body = values.get(name);
        if (body == null && "tRsp".equals(name)) body = values.get("tResp");
        if (!(body instanceof byte[])) {
            if (code != 0) return new Reply(new Struct(), code);
            throw new IllegalArgumentException("Missing task response");
        }
        Object parsed = decode((byte[]) body).get(0);
        if (!(parsed instanceof Struct)) throw new IllegalArgumentException("Missing task response struct");
        return new Reply((Struct) parsed, code);
    }
}
