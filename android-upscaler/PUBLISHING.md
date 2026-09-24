# Publishing PixelBoost on Google Play

Everything the Play Console asks for is in this folder:

| What | Where |
|---|---|
| App Bundle to upload | `release/PixelBoost-1.1.0.aab` (signed with your upload key) |
| APK to test on your own phone | `release/PixelBoost-1.1.0.apk` |
| Listing text, Data safety, content rating answers | `store/listing.md` |
| Icon, feature graphic, screenshots | `store/` |
| Privacy policy page | `../docs/privacy-policy.html` |
| Upload key | `upload-keystore.jks` + `keystore.properties`. **Not in git.** You were sent them separately. |

## 0. Keep the upload key safe (do this first)
`upload-keystore.jks` and its password (in `keystore.properties`) sign every update you upload.
Store copies in two safe places (for example a password manager and a private cloud drive). Never commit
them to this public repo; `.gitignore` already excludes them. If you lose them, Google can reset the upload
key, but that takes a support request and a few days.

## 1. Host the privacy policy (GitHub Pages, free)
1. On GitHub, open the **Blog** repo → **Settings → Pages**.
2. Under *Build and deployment*, set **Source: Deploy from a branch**, **Branch:** the branch that holds
   `docs/` (`claude/smartphone-apk-build-ppmfhy`, or `main` after you merge), **Folder: /docs** → Save.
3. After a minute the policy is live at
   `https://jobyjoy039-cyber.github.io/Blog/privacy-policy.html`. Open it to check.

## 2. Create the developer account
1. Go to <https://play.google.com/console/signup> and pay the one-time US$25 fee.
2. Complete identity verification (ID, and phone and email checks).
3. **New personal accounts must run a closed test first:** at least 12 testers opted in for 14 days in a
   row before you can apply for production. Friends and family with Android phones work. Organization
   accounts don't have this requirement.

## 3. Create the app
**Home → Create app**: name *PixelBoost AI Upscaler*, default language English, **App**, **Free**,
then accept the declarations.

## 4. Fill in "Set up your app" (Dashboard)
Use the answers in `store/listing.md` for: Privacy policy, App access, Ads, Content rating,
Target audience, Data safety, Government apps, Financial features, Health, Advertising ID,
then **Main store listing** (text + the graphics in `store/`).

## 5. Upload the bundle
1. **Testing → Closed testing** → create a track (or use *Alpha*) → **Create new release**.
2. When asked about app signing, keep **Google-generated key** (Play App Signing).
3. Upload `release/PixelBoost-1.1.0.aab`. Release name `1.1.0 (2)`; notes are in `store/listing.md`.
4. Add your testers (an email list or Google Group), save, and **Send for review**.
5. After 14 days with 12+ testers: **Production → Apply for production**, then create a production
   release with the same bundle.

Play turns the bundle into per-device APKs. A phone downloads only its own CPU's native library, so the
download is about 45 MB rather than the 58 MB bundle.

## Updating later
1. Raise `android:versionCode` (must go up every upload) and `android:versionName` in `AndroidManifest.xml`.
2. Put `upload-keystore.jks` and `keystore.properties` back in this folder, then run `./build.sh`.
3. Upload the new `.aab` from `release/`.

Note: the APK in `release/` is signed with your upload key. Once Play re-signs the app with Google's key,
a Play Store install and this side-loaded APK can't update each other. Uninstall one before installing the other.
