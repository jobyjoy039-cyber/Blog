# UGC Ad Studio

A small web app that turns a product brief into a ready-to-produce **UGC ad batch**:

1. **Brief**: product, audience, problem, a true proof point, demo action, platforms, length, creator role, CTA.
2. **Scripts**: Hook → Problem/Pitch → Proof/Demo → CTA, with beat timings scaled to the ad length. You can edit any line, and checks cover read-aloud time, hook length, a concrete number, a single CTA and risky claims.
3. **Batch matrix**: up to 8 variants that **change only the hook** (surprise, problem-first, POV, price, proof-first, question, founder, visual). Proof and CTA stay locked, so a winning ad tells you which hook won.
4. **AI video prompts**: one per variant per platform (TikTok, Reels, Facebook, Shorts, YouTube in-stream). Each has the right aspect ratio, a style line, a product-preservation line, a disclosure line and restrictions for the category.
5. **Claim check**: flags phrases like "guaranteed", "clinically proven", "lost 20 pounds" or "doctor recommended", in generated scripts or any copy you paste in.
6. **QA checklist**: 14 checks to run before delivering, saved per product.
7. **Export**: Markdown (copy or download) or JSON. Projects are saved in your browser.

Everything runs in the browser. There are no dependencies, no API keys and no build step.

## Run it

```bash
cd ugc-ad-app
npm start          # http://localhost:3000  (PORT=xxxx to change)
npm test           # generator unit tests (Node 18+)
```

You can also open `index.html` through any static host (GitHub Pages, Netlify, Render static site). It uses ES modules, so it has to be served over http rather than opened as `file://`.

## Files

| File | Purpose |
|---|---|
| `src/generator.js` | Pure logic: scripts, batch, video prompts, claim checker, Markdown export |
| `src/presets.js` | Example briefs (GripMount, PantryPal, Glowdrop) |
| `src/app.js` | UI wiring, localStorage, copy/download |
| `index.html`, `styles.css` | Layout with light/dark themes, works on mobile |
| `server.js` | Zero-dependency static server |
| `test/` | `node --test` suite |

## Credits

The method is adapted from:

- [Anil-matcha/ai-creator-academy](https://github.com/Anil-matcha/ai-creator-academy), Track 1 *AI Video Ads & UGC* (MIT): the 4-beat script template, ad brief checklist, batch matrix, and the GripMount worked example.
- [cliprise/awesome-ai-ugc-video-prompts](https://github.com/cliprise/awesome-ai-ugc-video-prompts): the UGC video prompt formula, platform-first planning, restriction library and QA checklist. Prompt wording in this app is original.

**UGC style is not permission to fake real experience.** The prompts tell the model not to present the creator as a real customer, and the claim checker flags unsupported results. Only claim what you can prove, and disclose paid ads.
