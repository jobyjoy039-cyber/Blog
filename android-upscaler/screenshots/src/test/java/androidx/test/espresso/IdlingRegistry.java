// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.espresso;
public final class IdlingRegistry {
  private static final IdlingRegistry INSTANCE = new IdlingRegistry();
  public static IdlingRegistry getInstance() { return INSTANCE; }
  public java.util.Collection<IdlingResource> getResources() { return java.util.Collections.emptyList(); }
  public java.util.Collection<android.os.Looper> getLoopers() { return java.util.Collections.emptyList(); }
}
