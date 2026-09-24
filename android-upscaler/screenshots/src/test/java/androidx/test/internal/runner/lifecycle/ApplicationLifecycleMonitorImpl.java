// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.internal.runner.lifecycle;
import androidx.test.runner.lifecycle.*;
public class ApplicationLifecycleMonitorImpl implements ApplicationLifecycleMonitor {
  public ApplicationLifecycleMonitorImpl() {}
  public void signalLifecycleChange(android.app.Application app, ApplicationStage s) {}
}
