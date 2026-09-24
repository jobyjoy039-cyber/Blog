// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.espresso;
public interface IdlingResource {
  String getName();
  boolean isIdleNow();
  void registerIdleTransitionCallback(ResourceCallback cb);
  interface ResourceCallback { void onTransitionToIdle(); }
}
