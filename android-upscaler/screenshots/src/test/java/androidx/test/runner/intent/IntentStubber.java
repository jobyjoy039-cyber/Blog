// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.runner.intent;
public interface IntentStubber { android.app.Instrumentation.ActivityResult getActivityResultForIntent(android.content.Intent i); }
