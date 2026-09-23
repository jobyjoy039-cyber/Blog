# Ritvayalife carousel renderer

Turns carousel text (JSON) into Instagram-ready 1080 × 1350 PNGs in the Ritvayalife style
(cream background, green headlines, Inter / Inter Tight). Each slide gets soft grain, a leaf
motif, and a rhythm line + rings that flow continuously from one slide into the next.

## Download ready-made slides

Finished slides live in `output/<carousel>/01.png … 07.png`. Upload them to Instagram in
number order.

## Make a new carousel

1. Copy a file in `carousels/` (e.g. `warm-water-after-meals.json`), rename it, and edit
   `slug`, `label` and the slide text.
2. Install once: `npm install` (Chromium must be available to Playwright).
3. Render: `npm run render` (all) or `node render.mjs <slug>` (one).

### Slide fields

| Field | Use |
|---|---|
| `pos` | `upper` · `mid` · `low` — vertical position of the text block |
| `h1` | big hook text (slide 1); `<br>` for line breaks |
| `h2` | slide headline |
| `tag` | small caps label above the headline (e.g. `TRADITIONAL VIEW`) |
| `divider` | `true` adds a thin line under the headline |
| `equation` | large green line (e.g. `<i>Āyus</i> + <i>Veda</i>`) |
| `body` | list of paragraphs |
| `rows` | `[["Name", "description"], …]` aligned rows |
| `flows` | `[["cause", "step", "effect"], …]` arrow chains |
| `list` | numbered steps (01 / 02 / 03) |
| `statement` | large insight text; wrap one phrase in `<span class="accent">` for gold |
| `cta`, `signoff` | final slide |
| `foot` | small footnote (e.g. "Modern lens: …") |

Fonts: Inter and Inter Tight (SIL Open Font License), bundled in `fonts/`.
