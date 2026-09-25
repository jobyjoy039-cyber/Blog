package com.productvideostudio.analysis;

import android.graphics.Bitmap;
import android.util.Log;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.label.ImageLabel;
import com.google.mlkit.vision.label.ImageLabeler;
import com.google.mlkit.vision.label.ImageLabeling;
import com.google.mlkit.vision.label.defaults.ImageLabelerOptions;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import com.productvideostudio.model.ImageAnalysis;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * On-device recognition with ML Kit's bundled models: what the product is (labels) and what is
 * printed on it (text). Must be called off the main thread. Failures leave the analysis
 * untouched so the director still works from pixels alone.
 */
public final class VisionLabeler implements AutoCloseable {
    private static final String TAG = "VisionLabeler";
    private final ImageLabeler labeler;
    private final TextRecognizer recognizer;

    public VisionLabeler() {
        ImageLabeler l = null;
        TextRecognizer r = null;
        try {
            l = ImageLabeling.getClient(ImageLabelerOptions.DEFAULT_OPTIONS);
            r = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        } catch (Throwable t) {
            Log.w(TAG, "ML Kit unavailable", t);
        }
        labeler = l;
        recognizer = r;
    }

    public void label(Bitmap bmp, ImageAnalysis out) {
        if (bmp == null) return;
        InputImage image = InputImage.fromBitmap(bmp, 0);
        if (labeler != null) {
            try {
                List<ImageLabel> labels = Tasks.await(labeler.process(image), 20, TimeUnit.SECONDS);
                out.labels.clear();
                for (ImageLabel l : labels) {
                    if (l.getConfidence() >= 0.55f) out.labels.add(l.getText());
                }
            } catch (Exception e) {
                Log.w(TAG, "labeling failed", e);
            }
        }
        if (recognizer != null) {
            try {
                Text text = Tasks.await(recognizer.process(image), 20, TimeUnit.SECONDS);
                List<Text.Line> lines = new ArrayList<>();
                for (Text.TextBlock b : text.getTextBlocks()) lines.addAll(b.getLines());
                lines.sort((a, b) -> Integer.compare(height(b), height(a)));
                out.texts.clear();
                for (Text.Line line : lines) {
                    String s = line.getText().trim();
                    if (s.length() >= 2 && s.length() <= 40 && out.texts.size() < 8) out.texts.add(s);
                }
            } catch (Exception e) {
                Log.w(TAG, "text recognition failed", e);
            }
        }
    }

    private static int height(Text.Line l) {
        return l.getBoundingBox() == null ? 0 : l.getBoundingBox().height();
    }

    @Override
    public void close() {
        try {
            if (labeler != null) labeler.close();
            if (recognizer != null) recognizer.close();
        } catch (Exception ignored) {
        }
    }
}
