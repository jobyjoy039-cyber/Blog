// JNI bridge between WhisperLib.kt and whisper.cpp.

#include <jni.h>
#include <android/log.h>

#include <atomic>
#include <cstring>
#include <string>

#include "whisper.h"

#define TAG "WhisperJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

namespace {

// Only one transcription runs at a time, so a single flag is enough.
std::atomic<bool> g_abort{false};

// Passed to whisper callbacks. They run on the thread that called whisper_full(),
// which is the JNI thread, so the JNIEnv stays valid.
struct CallbackData {
    JNIEnv *env;
    jobject listener;
    jmethodID onProgress;
    jmethodID onSegment;
};

// If a Kotlin callback throws, stop transcribing and let the exception surface
// when transcribe() returns. No further JNI calls are allowed until then.
bool check_exception(JNIEnv *env) {
    if (!env->ExceptionCheck()) return false;
    g_abort.store(true);
    return true;
}

void progress_cb(whisper_context *, whisper_state *, int progress, void *user_data) {
    auto *cb = static_cast<CallbackData *>(user_data);
    if (cb->env->ExceptionCheck()) return;
    cb->env->CallVoidMethod(cb->listener, cb->onProgress, (jint) progress);
    check_exception(cb->env);
}

void new_segment_cb(whisper_context *ctx, whisper_state *, int n_new, void *user_data) {
    auto *cb = static_cast<CallbackData *>(user_data);
    JNIEnv *env = cb->env;
    if (env->ExceptionCheck()) return;
    const int n = whisper_full_n_segments(ctx);
    for (int i = n - n_new; i < n; i++) {
        const char *text = whisper_full_get_segment_text(ctx, i);
        // whisper timestamps are in centiseconds.
        const jlong t0 = whisper_full_get_segment_t0(ctx, i) * 10;
        const jlong t1 = whisper_full_get_segment_t1(ctx, i) * 10;
        // Pass raw UTF-8 bytes: NewStringUTF aborts on invalid/4-byte sequences.
        const jsize len = (jsize) strlen(text);
        jbyteArray bytes = env->NewByteArray(len);
        env->SetByteArrayRegion(bytes, 0, len, reinterpret_cast<const jbyte *>(text));
        env->CallVoidMethod(cb->listener, cb->onSegment, t0, t1, bytes);
        env->DeleteLocalRef(bytes);
        if (check_exception(env)) return;
    }
}

bool abort_cb(void *) {
    return g_abort.load();
}

} // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_videotranscriber_app_WhisperLib_initContext(JNIEnv *env, jobject, jstring modelPath) {
    const char *path = env->GetStringUTFChars(modelPath, nullptr);
    whisper_context_params cparams = whisper_context_default_params();
    cparams.use_gpu = false;
    whisper_context *ctx = whisper_init_from_file_with_params(path, cparams);
    if (!ctx) LOGE("Failed to load model: %s", path);
    env->ReleaseStringUTFChars(modelPath, path);
    return reinterpret_cast<jlong>(ctx);
}

JNIEXPORT void JNICALL
Java_com_videotranscriber_app_WhisperLib_freeContext(JNIEnv *, jobject, jlong ctxPtr) {
    whisper_free(reinterpret_cast<whisper_context *>(ctxPtr));
}

JNIEXPORT jstring JNICALL
Java_com_videotranscriber_app_WhisperLib_systemInfo(JNIEnv *env, jobject) {
    return env->NewStringUTF(whisper_print_system_info());
}

JNIEXPORT void JNICALL
Java_com_videotranscriber_app_WhisperLib_requestAbort(JNIEnv *, jobject) {
    g_abort.store(true);
}

// Returns 0 on success, 1 if aborted, a negative value on error.
JNIEXPORT jint JNICALL
Java_com_videotranscriber_app_WhisperLib_transcribe(
        JNIEnv *env, jobject,
        jlong ctxPtr, jfloatArray samples, jstring language,
        jboolean translate, jint threads, jobject listener) {
    auto *ctx = reinterpret_cast<whisper_context *>(ctxPtr);
    if (!ctx) return -1;

    g_abort.store(false);

    jclass cls = env->GetObjectClass(listener);
    CallbackData cb{
            env,
            listener,
            env->GetMethodID(cls, "onProgress", "(I)V"),
            env->GetMethodID(cls, "onSegment", "(JJ[B)V"),
    };
    env->DeleteLocalRef(cls);
    if (!cb.onProgress || !cb.onSegment) return -2;

    const char *lang = env->GetStringUTFChars(language, nullptr);
    const std::string langStr(lang);
    env->ReleaseStringUTFChars(language, lang);

    whisper_full_params params = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    params.n_threads = threads;
    params.language = langStr.c_str();
    params.translate = translate;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_timestamps = false;
    params.print_special = false;
    params.no_context = true;
    params.progress_callback = progress_cb;
    params.progress_callback_user_data = &cb;
    params.new_segment_callback = new_segment_cb;
    params.new_segment_callback_user_data = &cb;
    params.abort_callback = abort_cb;
    params.abort_callback_user_data = nullptr;

    jsize n = env->GetArrayLength(samples);
    jfloat *data = env->GetFloatArrayElements(samples, nullptr);

    LOGI("Transcribing %d samples with %d threads, language=%s", n, threads, langStr.c_str());
    const int rc = whisper_full(ctx, params, data, n);

    env->ReleaseFloatArrayElements(samples, data, JNI_ABORT);

    if (env->ExceptionCheck()) return -4; // rethrown on the Kotlin side

    if (g_abort.load()) return 1;
    if (rc != 0) {
        LOGE("whisper_full failed: %d", rc);
        return -3;
    }
    return 0;
}

JNIEXPORT jstring JNICALL
Java_com_videotranscriber_app_WhisperLib_detectedLanguage(JNIEnv *env, jobject, jlong ctxPtr) {
    auto *ctx = reinterpret_cast<whisper_context *>(ctxPtr);
    const char *lang = whisper_lang_str(whisper_full_lang_id(ctx));
    return env->NewStringUTF(lang ? lang : "");
}

} // extern "C"
