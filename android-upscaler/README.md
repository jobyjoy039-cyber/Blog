# PixelBoost AI Upscaler (Android)

Upscales images 2x, 4x, or to 4K / 8K with [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) models.
Everything runs on the phone (ONNX Runtime, CPU). There's no internet permission, no account and no ads.

* **Publishing on Google Play:** see [PUBLISHING.md](PUBLISHING.md) and [store/listing.md](store/listing.md).
* **Install on your own phone:** `release/PixelBoost-1.1.0.apk`. Allow "install unknown apps" when asked.
  Needs Android 7.0+.

## Features
* Three models:
  * **Photo, fast** (`realesr-general-x4v3`)
  * **Anime & drawings** (`realesr-animevideov3`), the fastest
  * **Photo, best quality** (`RealESRGAN_x4plus`, RRDBNet), sharpest but 10–20x slower
* Output **2x / 4x**, or **4K / 8K**. The presets fit the image into 3840 × 2160 or 7680 × 4320, turned for
  portrait images. When more than 4x is needed, two passes run automatically. The first pass stops at a
  quarter of the final size, which keeps the slow second pass small.
* Each pass produces the requested size directly: every tile's 4x output is scaled down to the target
  before it's stored. The 4x intermediate never exists in memory, so 8K (33 MP) needs about 130 MB.
* Press and hold to compare, plus a 100% before/after detail view. Transparency is kept (PNG).
  Save to `Pictures/PixelBoost` or share. Images shared from other apps open directly.
* Targets Android 16 (API 36), draws edge-to-edge, and meets Play's 16 KB page-size requirement.

## Layout
| Path | What |
|---|---|
| `src/com/jobyjoy/pixelboost/` | `MainActivity` (UI, planning, saving) and `Upscaler` (tiled ONNX inference) |
| `res/`, `AndroidManifest.xml` | Resources and manifest |
| `assets/*.onnx` | Converted models (x4plus weights stored as fp16, run as fp32) |
| `licenses/licenses.txt` | Notices shown under About → Open-source licenses |
| `tools/convert_to_onnx.py` | `.pth` → ONNX without PyTorch (SRVGGNetCompact and RRDBNet graphs) |
| `tools/make_icons.py`, `tools/make_store_graphics.py` | Launcher/Play icons, feature graphic, captioned screenshots |
| `tools/new_upload_key.sh` | Creates the Play upload key (git-ignored) |
| `screenshots/` | Robolectric test that drives the real app and renders the store screenshots |
| `store/` | Play listing graphics and text |
| `release/` | Signed `.aab` and universal `.apk` |

## Building
`./build.sh` builds without Gradle or Google's SDK download (not reachable where this was built):

```
sudo apt-get install dalvik-exchange android-sdk-platform-23 zipalign   # + a JDK
pip install onnx numpy          # only if assets/*.onnx are missing
tools/new_upload_key.sh         # once; or restore your saved upload-keystore.jks + keystore.properties
./build.sh                      # -> release/PixelBoost-<version>.aab and .apk
```

How the build works:
* aapt2 is taken from the bundletool jar (downloaded from GitHub). Resources are linked in proto format
  and packed into a base module, and bundletool builds the `.aab`.
* The bundle config stores models uncompressed and aligns native libraries to 16 KB. The universal APK is
  generated from the bundle.
* `onnxruntime-android` 1.20.0 is the newest release with Java 8 bytecode, which is what `dx` can read, and its
  native libraries are already 16 KB aligned. `tools/TensorInfo.java` replaces the one lambda `dx` can't
  convert, and the desktop-only CUDA/TensorRT option classes are dropped.

## Testing and screenshots
```
screenshots/run.sh <folder with coffee.jpg, chelsea.jpg, astronaut.jpg, rocket.jpg>
python3 tools/make_store_graphics.py <same folder>
```
The test runs `MainActivity` in Robolectric with native graphics and the desktop build of ONNX Runtime.
It covers loading a shared image, 4x, two-pass 4K, the best-quality model with 2x, saving, and the About and
licenses dialogs. It asserts on sizes and output, and writes the 1080 × 1920 screenshots in `store/screenshots/`.
The sample photos are CC0 / public domain, from scikit-image's `data` module (resized to low resolution).
`screenshots/src/test/java/androidx/` holds small stand-ins for the parts of androidx.test that Robolectric
calls, because that library is only published on Google's Maven.
