// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.runner.lifecycle;
public enum Stage { PRE_ON_CREATE, CREATED, STARTED, RESUMED, PAUSED, STOPPED, RESTARTED, DESTROYED }
