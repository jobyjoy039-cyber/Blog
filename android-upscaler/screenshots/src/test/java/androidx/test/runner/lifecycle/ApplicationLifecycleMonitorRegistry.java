// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.runner.lifecycle;
public final class ApplicationLifecycleMonitorRegistry {
  public static void registerInstance(ApplicationLifecycleMonitor m) {}
}
