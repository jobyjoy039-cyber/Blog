# Real-ESRGAN Upscaler (Android)

An Android app that upscales images 4x (or 2x) with [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN).
Everything runs on the phone (ONNX Runtime, CPU). No internet connection or account is needed.

**Install:** copy `RealESRGAN-Upscaler.apk` to your phone, open it, and allow "install unknown apps" when asked.
Needs Android 7.0+ on an ARM phone (almost all phones are ARM).

## Using it
1. Tap **Choose image**. You can also share an image to the app from your gallery.
2. Pick a model:
   * **Photo / general** (`realesr-general-x4v3`): for photos and most images.
   * **Anime / illustration** (`realesr-animevideov3`): for drawings and cartoons. About twice as fast.
3. Pick **4x** or **2x**, then tap **Upscale**. Press and hold the picture to compare with the original.
4. **Save to gallery** writes to `Pictures/Real-ESRGAN/`. PNG is used when the image has transparency, JPEG otherwise.

Speed depends on the phone. A 1-megapixel photo takes roughly 30–90 s with the general model.
Very large inputs are scaled down first so the output stays under 32 MP and fits in memory.

## Building
`./build.sh` builds the APK without Gradle or the Google SDK download. It uses Ubuntu's Android packages:

```
sudo apt-get install aapt apksigner zipalign dalvik-exchange android-sdk-platform-23
pip install onnx numpy   # only needed if assets/*.onnx are missing
./build.sh
```

What the script does:
* `tools/convert_to_onnx.py` turns the official `.pth` weights into ONNX. It reads the PyTorch checkpoint
  without needing PyTorch installed and builds the SRVGGNetCompact graph (conv + PReLU stack, pixel shuffle,
  plus the nearest-upsampled input).
* Downloads `onnxruntime-android` 1.20.0 from Maven Central. That's the newest release with Java 8 bytecode,
  which is what `dx` can read. `tools/TensorInfo.java` swaps out the one lambda that `dx` can't convert.
* Only `arm64-v8a` and `armeabi-v7a` native libraries are included. Set `ABIS="arm64-v8a armeabi-v7a x86_64"`
  to add the emulator ABI.
* The APK is signed with `release.keystore`, created on the first build and git-ignored. Keep that file:
  updates only install over an existing copy of the app if they're signed with the same key.
