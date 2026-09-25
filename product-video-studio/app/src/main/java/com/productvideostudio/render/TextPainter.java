package com.productvideostudio.render;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;

import com.productvideostudio.model.Storyboard;
import com.productvideostudio.model.Storyboard.TextItem;

/** Draws a caption, badge or button to a bitmap that the compositor animates on the GPU. */
final class TextPainter {
    private TextPainter() {}

    /** Canvas width the text sizes are designed for. */
    static final int DESIGN_WIDTH = 1080;
    private static final int PAD = 28;

    static Bitmap render(TextItem t, Storyboard board, int canvasWidth) {
        float k = canvasWidth / (float) DESIGN_WIDTH;
        TextPaint paint = new TextPaint(Paint.ANTI_ALIAS_FLAG | Paint.SUBPIXEL_TEXT_FLAG);
        boolean bold = t.bold;
        Typeface base = Typeface.create(board.font, Typeface.NORMAL);
        paint.setTypeface(Typeface.create(base, bold ? Typeface.BOLD : Typeface.NORMAL));
        paint.setTextSize(t.size * k);
        paint.setLetterSpacing(board.letterSpacing);
        paint.setColor(t.color);

        boolean pill = t.background != 0;
        int maxWidth = Math.round((pill ? 820 : 940) * k);
        String text = t.text == null ? "" : t.text;
        StaticLayout layout = StaticLayout.Builder.obtain(text, 0, text.length(), paint, maxWidth)
                .setAlignment(Layout.Alignment.ALIGN_CENTER)
                .setLineSpacing(0, 1.02f)
                .setMaxLines(3)
                .setIncludePad(false)
                .build();
        float textW = 0;
        for (int i = 0; i < layout.getLineCount(); i++) textW = Math.max(textW, layout.getLineWidth(i));
        int textH = layout.getHeight();

        float padX = pill ? t.size * 0.9f * k : 0;
        float padY = pill ? t.size * 0.42f * k : 0;
        int w = (int) Math.ceil(textW + 2 * padX) + 2 * PAD;
        int h = (int) Math.ceil(textH + 2 * padY) + 2 * PAD;
        Bitmap bmp = Bitmap.createBitmap(Math.max(2, w), Math.max(2, h), Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);

        if (pill) {
            Paint bg = new Paint(Paint.ANTI_ALIAS_FLAG);
            bg.setColor(t.background);
            bg.setShadowLayer(18 * k, 0, 6 * k, 0x55000000);
            RectF r = new RectF(PAD, PAD, w - PAD, h - PAD);
            float radius = r.height() / 2f;
            c.drawRoundRect(r, radius, radius, bg);
        } else {
            // Legibility over any background: soft shadow for light text, a faint halo for dark text.
            boolean lightText = luminance(t.color) > 0.5f;
            paint.setShadowLayer(14 * k, 0, 3 * k, lightText ? 0x99000000 : 0x40FFFFFF);
        }
        c.save();
        // StaticLayout centers each line within maxWidth; shift so the block is centered in the bitmap.
        c.translate(PAD + padX - (maxWidth - textW) / 2f, PAD + padY);
        layout.draw(c);
        c.restore();
        return bmp;
    }

    static float luminance(int c) {
        return (0.2126f * ((c >> 16) & 0xFF) + 0.7152f * ((c >> 8) & 0xFF) + 0.0722f * (c & 0xFF)) / 255f;
    }
}
