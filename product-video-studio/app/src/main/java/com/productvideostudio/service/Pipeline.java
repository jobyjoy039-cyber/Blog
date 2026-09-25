package com.productvideostudio.service;

import android.content.Context;
import android.graphics.Bitmap;
import android.util.Log;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.analysis.ImageAnalyzer;
import com.productvideostudio.analysis.ProductInsights;
import com.productvideostudio.analysis.UrlMetadata;
import com.productvideostudio.analysis.VisionLabeler;
import com.productvideostudio.audio.AudioComposer;
import com.productvideostudio.audio.BeatDetector;
import com.productvideostudio.director.CreativeDirector;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Project;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** Everything between "the user tapped Create" and a finished storyboard. Runs off the main thread. */
public final class Pipeline {
    private static final String TAG = "Pipeline";

    public interface Progress {
        void update(String message);
    }

    private Pipeline() {}

    public static void prepare(Context ctx, ProjectStore store, Project p, Progress progress) {
        File dir = store.dir(p);

        // 1. Product page: fill empty fields and borrow its share image if we have no photos.
        if (p.url != null && !p.url.trim().isEmpty()
                && (p.name.trim().isEmpty() || p.description.trim().isEmpty() || p.images.isEmpty())) {
            progress.update("Reading your product page…");
            try {
                UrlMetadata m = UrlMetadata.fetch(p.url);
                if (p.name.trim().isEmpty()) p.name = m.title;
                if (p.description.trim().isEmpty()) p.description = m.description;
                if (p.images.isEmpty() && !m.imageUrl.isEmpty()) {
                    String name = "img_url.jpg";
                    UrlMetadata.downloadTo(m.imageUrl, new File(dir, name));
                    p.images.add(name);
                }
            } catch (Exception e) {
                Log.w(TAG, "page fetch failed", e);
            }
        }

        // 2. Analyze photos (cached per file).
        List<ImageAnalysis> keep = new ArrayList<>();
        try (VisionLabeler vision = new VisionLabeler()) {
            for (int i = 0; i < p.images.size(); i++) {
                String file = p.images.get(i);
                ImageAnalysis a = p.analysisFor(file);
                if (a == null) {
                    progress.update("Studying photo " + (i + 1) + " of " + p.images.size() + "…");
                    String path = new File(dir, file).getAbsolutePath();
                    a = ImageAnalyzer.analyze(path, file);
                    Bitmap forVision = Bitmaps.decode(path, 720);
                    vision.label(forVision, a);
                    if (forVision != null) forVision.recycle();
                }
                keep.add(a);
            }
        }
        p.analyses = keep;

        // 3. Beat grid from the user's own song.
        int bpm = 0;
        float offset = 0;
        if (Project.MUSIC_FILE.equals(p.musicMode) && p.musicFile != null) {
            progress.update("Finding the beat in your track…");
            BeatDetector d = AudioComposer.detectBeats(new File(dir, p.musicFile));
            if (d != null) {
                bpm = d.bpm;
                offset = d.offset % (60f / d.bpm);
            }
        }

        // 4. Direct.
        progress.update("Directing your video…");
        ProductInsights insights = ProductInsights.from(p);
        p.storyboard = CreativeDirector.direct(p, insights, bpm, offset);
        p.caption = p.storyboard.caption;
        store.save(p);
    }
}
