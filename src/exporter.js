// Records the canvas plus the audio engine output into a video file, and saves or shares it.
import { Capacitor } from '@capacitor/core';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';

function pickMime() {
  const options = ['video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
  return options.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
}

// Plays the scene once in real time while recording. `play(onDone)` must start playback from 0.
export function recordVideo({ canvas, audio, duration, play, onProgress }) {
  return new Promise((resolve, reject) => {
    if (!window.MediaRecorder || !canvas.captureStream) {
      reject(new Error('Video recording is not supported on this device.'));
      return;
    }
    const stream = canvas.captureStream(30);
    for (const track of audio.recordStream().getAudioTracks()) stream.addTrack(track);
    const mimeType = pickMime();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 5_000_000 } : undefined);
    const chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onerror = (e) => reject(e.error || new Error('Recording failed'));
    rec.onstop = () => {
      const type = rec.mimeType || mimeType || 'video/webm';
      resolve(new Blob(chunks, { type }));
    };
    rec.start(250);
    const t0 = performance.now();
    const tick = setInterval(() => onProgress?.(Math.min(1, (performance.now() - t0) / 1000 / duration)), 200);
    play(() => {
      clearInterval(tick);
      setTimeout(() => rec.state !== 'inactive' && rec.stop(), 300);
    });
  });
}

function blobToBase64(blob) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(',')[1]);
    r.onerror = () => rej(r.error);
    r.readAsDataURL(blob);
  });
}

export function safeName(title) {
  return (title || 'animation').replace(/[^\w\- ]+/g, '').trim().replace(/\s+/g, '-').slice(0, 40) || 'animation';
}

// Saves a blob: on Android, writes it to the app's documents folder and opens the share sheet;
// in a browser, downloads it.
export async function saveBlob(blob, filename) {
  if (Capacitor.isNativePlatform()) {
    const data = await blobToBase64(blob);
    const res = await Filesystem.writeFile({ path: filename, data, directory: Directory.Cache });
    await Share.share({ title: filename, url: res.uri, dialogTitle: 'Save or share' });
    return res.uri;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  return filename;
}
