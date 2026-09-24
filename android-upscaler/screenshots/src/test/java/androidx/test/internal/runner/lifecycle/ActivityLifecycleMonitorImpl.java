// Minimal stand-in for androidx.test (only on Google Maven, unreachable here); just what Robolectric calls.
package androidx.test.internal.runner.lifecycle;
import android.app.Activity;
import androidx.test.runner.lifecycle.*;
import java.util.*;
public class ActivityLifecycleMonitorImpl implements ActivityLifecycleMonitor {
  private final Map<Activity, Stage> stages = new LinkedHashMap<>();
  private final List<ActivityLifecycleCallback> callbacks = new ArrayList<>();
  public ActivityLifecycleMonitorImpl() {}
  public void addLifecycleCallback(ActivityLifecycleCallback cb) { callbacks.add(cb); }
  public void removeLifecycleCallback(ActivityLifecycleCallback cb) { callbacks.remove(cb); }
  public Stage getLifecycleStageOf(Activity a) { return stages.get(a); }
  public Collection<Activity> getActivitiesInStage(Stage s) {
    List<Activity> r = new ArrayList<>();
    for (Map.Entry<Activity, Stage> e : stages.entrySet()) if (e.getValue() == s) r.add(e.getKey());
    return r;
  }
  public void signalLifecycleChange(Stage s, Activity a) {
    stages.put(a, s);
    for (ActivityLifecycleCallback cb : new ArrayList<>(callbacks)) cb.onActivityLifecycleChanged(a, s);
  }
}
