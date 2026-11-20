package io.github.saycm.huyaplus;

import java.lang.reflect.Method;

final class HuyaComponents {
    private HuyaComponents() {}

    static Object get(ClassLoader loader, Class<?> type) throws ReflectiveOperationException {
        Method lookup;
        try {
            lookup = loader.loadClass("ryxq.xxe").getDeclaredMethod("i", Class.class);
        } catch (ClassNotFoundException | NoSuchMethodException oldRegistryAbsent) {
            lookup = loader.loadClass("ryxq.fwa").getDeclaredMethod("i", Class.class);
        }
        return lookup.invoke(null, type);
    }
}
