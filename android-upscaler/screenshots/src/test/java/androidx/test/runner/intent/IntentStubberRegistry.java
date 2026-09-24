// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.runner.intent;
public final class IntentStubberRegistry {
  public static boolean isLoaded() { return false; }
  public static IntentStubber getInstance() { return null; }
}
