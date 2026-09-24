// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.runner.lifecycle;
public final class ActivityLifecycleMonitorRegistry {
  private static ActivityLifecycleMonitor instance;
  public static ActivityLifecycleMonitor getInstance() { return instance; }
  public static void registerInstance(ActivityLifecycleMonitor m) { instance = m; }
}
