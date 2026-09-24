// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.internal.runner.intent;
public class IntentMonitorImpl implements androidx.test.runner.intent.IntentMonitor {
  public IntentMonitorImpl() {}
  public void signalIntent(android.content.Intent i) {}
}
