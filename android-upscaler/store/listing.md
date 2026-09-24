# Play Console: text and form answers for PixelBoost

Copy these into Play Console. Everything here matches what the app actually does. If you change the
app (for example by adding ads or analytics), update the Data safety answers too.

## Main store listing

**App name** (max 30 characters)
```
PixelBoost AI Upscaler
```

**Short description** (max 80 characters)
```
Upscale photos to 4K & 8K with AI. Sharper detail, works offline, no uploads.
```

**Full description** (max 4000 characters)
```
PixelBoost makes small or blurry pictures bigger and sharper with AI, right on your phone.

Pick a photo, drawing or screenshot, choose how big you want it, and PixelBoost rebuilds the
detail: cleaner edges, finer texture and less JPEG noise, instead of the blur you get from
ordinary resizing.

WHAT YOU CAN DO
• Upscale 2x or 4x, or straight to 4K (3840 × 2160) or 8K (7680 × 4320)
• Very small images reach 4K/8K automatically in two AI passes
• Three AI models:
  – Photo, fast: great results for most photos in seconds to a few minutes
  – Anime & drawings: tuned for illustrations, cartoons and line art, and the fastest
  – Photo, best quality: the sharpest results for your favourite shots (slower)
• Press and hold to compare with the original, plus a 100% before/after detail view
• Keeps transparency in PNG images
• Save to your gallery (Pictures/PixelBoost) or share to any app
• Share an image to PixelBoost from your gallery to start straight away

PRIVATE BY DESIGN
Everything runs on your device. PixelBoost has no internet access, no account, no ads and no
tracking. Your photos never leave your phone.

GOOD TO KNOW
• Big jobs take time on a phone. Going to 8K can take several minutes, and the best-quality
  model is slower. Keep the app open until it finishes.
• AI upscaling rebuilds plausible detail. It can't recover information that was never in the photo.

Powered by Real-ESRGAN (BSD-3-Clause), the open-source super-resolution research by Xintao Wang
et al., and ONNX Runtime (MIT). PixelBoost is an independent app and isn't affiliated with the
Real-ESRGAN authors or Microsoft.
```

**Graphics** (all in `store/`)
| Play Console field | File |
|---|---|
| App icon (512 × 512) | `icon-512.png` |
| Feature graphic (1024 × 500) | `feature-graphic-1024x500.png` |
| Phone screenshots (2–8, 9:16) | `phone-screenshots/1-choose.png` … `6-about.png` (captioned) |
| Also usable as screenshots | `screenshots/*.png` (plain 1080 × 1920 renders of the app) |

For 7" and 10" tablet screenshots, Play accepts the same files, or you can skip tablets.

**Category:** Photography
**Tags** (pick up to 5): Photo editor, Photography, Image enhancer, AI, Tools
**Contact email:** jobyjoy039@gmail.com
**Privacy policy URL:** `https://jobyjoy039-cyber.github.io/Blog/privacy-policy.html` (after enabling GitHub Pages, see PUBLISHING.md)

## App content (Policy → App content)

**Privacy policy:** the URL above.

**Ads:** No, my app does not contain ads.

**App access:** All functionality is available without special access (no login).

**Content rating** (IARC questionnaire)
- Category: *All other app types* (utility/productivity/tools)
- Violence, fear, sexuality, language, controlled substances, gambling: **No** to all
- Does the app allow users to interact or exchange content with other users? **No**
  (the Share button hands a file to another app on the phone; PixelBoost has no online features)
- Does the app share the user's location with other users? **No**
- Does the app allow purchases of digital goods? **No**
- Expected rating: Everyone / PEGI 3 / USK 0

**Target audience and content:** ages **13 and over** (choose 13–15, 16–17 and 18+).
Don't include under-13 age groups: that puts the app under the Families policy, with extra requirements.
"Could the app unintentionally appeal to children?" **No**.

**News app:** No. **COVID-19 contact tracing:** No. **Government app:** No.
**Financial features:** None. **Health:** None.

**Advertising ID:** No, the app doesn't use an advertising ID (it doesn't declare the AD_ID permission).

**Data safety**
- Does your app collect or share any of the required user data types? **No**
  (Google counts data as "collected" only when it's sent off the device. PixelBoost only reads
  photos locally and has no Internet permission.)
- Is all of the user data collected by your app encrypted in transit? Not applicable (nothing is collected).
- Do you provide a way for users to request that their data be deleted? Not applicable.
- Result shown on the listing: "No data collected · No data shared with third parties".

## Release notes for 1.1.0
```
First release: AI upscaling to 2x, 4x, 4K and 8K with three on-device models.
```
