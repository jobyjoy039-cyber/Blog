package com.productvideostudio.ui;

import android.app.Activity;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** Tiny view toolkit: the app builds its screens in code with one consistent dark style. */
final class Ui {
    private Ui() {}

    static final int BG = 0xFF0E0E11;
    static final int SURFACE = 0xFF19191E;
    static final int SURFACE_2 = 0xFF24242B;
    static final int TEXT = 0xFFF4F2EE;
    static final int MUTED = 0xFF9C9AA3;
    static final int ACCENT = 0xFFFF6A3D;
    static final int ACCENT_TEXT = 0xFF1A0D08;

    static int dp(Context c, float v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    static GradientDrawable round(int color, float radiusPx) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(radiusPx);
        return g;
    }

    static LinearLayout column(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    static TextView title(Context c, String s) {
        TextView t = text(c, s, 28, TEXT);
        t.setTypeface(Typeface.create("sans-serif-black", Typeface.NORMAL));
        return t;
    }

    static TextView heading(Context c, String s) {
        TextView t = text(c, s, 13, MUTED);
        t.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        t.setLetterSpacing(0.08f);
        t.setAllCaps(true);
        t.setPadding(0, dp(c, 22), 0, dp(c, 8));
        return t;
    }

    static TextView text(Context c, String s, float sp, int color) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setLineSpacing(0, 1.15f);
        return t;
    }

    static Button primary(Context c, String s) {
        Button b = new Button(c);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(17);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        b.setTextColor(ACCENT_TEXT);
        b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x33FFFFFF), round(ACCENT, dp(c, 16)), null));
        b.setMinHeight(dp(c, 56));
        b.setStateListAnimator(null);
        return b;
    }

    static Button secondary(Context c, String s) {
        Button b = new Button(c);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(15);
        b.setTextColor(TEXT);
        b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x22FFFFFF), round(SURFACE_2, dp(c, 14)), null));
        b.setMinHeight(dp(c, 48));
        b.setStateListAnimator(null);
        b.setPadding(dp(c, 16), 0, dp(c, 16), 0);
        return b;
    }

    static EditText input(Context c, String hint, boolean multiline) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setHintTextColor(0xFF6E6C75);
        e.setTextColor(TEXT);
        e.setTextSize(16);
        e.setBackground(round(SURFACE, dp(c, 12)));
        int p = dp(c, 14);
        e.setPadding(p, p, p, p);
        if (multiline) {
            e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            e.setMinLines(3);
            e.setGravity(Gravity.TOP | Gravity.START);
        } else {
            e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            e.setSingleLine(true);
        }
        return e;
    }

    static View card(Context c, View child) {
        LinearLayout l = column(c);
        l.setBackground(round(SURFACE, dp(c, 18)));
        int p = dp(c, 16);
        l.setPadding(p, p, p, p);
        l.addView(child);
        return l;
    }

    static LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    static LinearLayout.LayoutParams margins(Context c, int top) {
        LinearLayout.LayoutParams lp = matchWrap();
        lp.topMargin = dp(c, top);
        return lp;
    }

    static void styleWindow(Activity a) {
        a.getWindow().setStatusBarColor(BG);
        a.getWindow().setNavigationBarColor(BG);
        a.getWindow().getDecorView().setBackgroundColor(BG);
    }

    /** A single-choice row of pill chips. */
    static final class Chips {
        final HorizontalScrollView view;
        private final List<TextView> chips = new ArrayList<>();
        private int selected;
        private final Runnable onChange;

        Chips(Context c, String[] labels, int initial, Runnable onChange) {
            this.onChange = onChange;
            view = new HorizontalScrollView(c);
            view.setHorizontalScrollBarEnabled(false);
            LinearLayout r = row(c);
            for (int i = 0; i < labels.length; i++) {
                TextView t = text(c, labels[i], 14, TEXT);
                t.setPadding(dp(c, 14), dp(c, 9), dp(c, 14), dp(c, 9));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.rightMargin = dp(c, 8);
                final int idx = i;
                t.setOnClickListener(v -> select(idx, true));
                r.addView(t, lp);
                chips.add(t);
            }
            view.addView(r);
            select(initial, false);
        }

        void select(int idx, boolean notify) {
            selected = Math.max(0, Math.min(chips.size() - 1, idx));
            for (int i = 0; i < chips.size(); i++) {
                TextView t = chips.get(i);
                boolean on = i == selected;
                Context c = t.getContext();
                t.setBackground(round(on ? ACCENT : SURFACE_2, dp(c, 20)));
                t.setTextColor(on ? ACCENT_TEXT : TEXT);
                t.setTypeface(on ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            }
            if (notify && onChange != null) onChange.run();
        }

        int selected() {
            return selected;
        }
    }

    static int parseColor(String s) {
        try {
            String t = s.trim();
            if (!t.startsWith("#")) t = "#" + t;
            return Color.parseColor(t) | 0xFF000000;
        } catch (IllegalArgumentException e) {
            return 0;
        }
    }
}
