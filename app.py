import os
import uuid
import json
import threading
import time
import zipfile
import shutil
from pathlib import Path
from queue import Queue, Empty

import cv2
import numpy as np
from flask import Flask, request, jsonify, send_file, Response, stream_with_context, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

UPLOAD_DIR = Path('uploads')
OUTPUT_DIR = Path('outputs')
WEIGHTS_DIR = Path('weights')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}

MODEL_CONFIGS = {
    'RealESRGAN_x4plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
        'scale': 4,
        'arch': 'RRDBNet',
        'num_block': 23,
        'label': 'RealESRGAN x4+ (Photo)',
    },
    'RealESRGAN_x4plus_anime_6B': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
        'scale': 4,
        'arch': 'RRDBNet',
        'num_block': 6,
        'label': 'RealESRGAN x4+ Anime',
    },
    'RealESRGAN_x2plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth',
        'scale': 2,
        'arch': 'RRDBNet',
        'num_block': 23,
        'label': 'RealESRGAN x2+ (Photo)',
    },
    'realesr-animevideov3': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',
        'scale': 4,
        'arch': 'SRVGGNet',
        'label': 'Anime Video v3 (Fast)',
    },
}

# Job state: job_id -> {status, progress, total, results, error, sse_queue}
jobs = {}
jobs_lock = threading.Lock()


def allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def build_upsampler(model_name, tile=0, fp32=False):
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.utils.download_util import load_file_from_url

    cfg = MODEL_CONFIGS[model_name]
    netscale = cfg['scale']

    if cfg['arch'] == 'RRDBNet':
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=cfg['num_block'], num_grow_ch=32, scale=netscale
        )
    else:
        model = SRVGGNetCompact(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_conv=16, upscale=netscale, act_type='prelu'
        )

    weight_path = WEIGHTS_DIR / f'{model_name}.pth'
    if not weight_path.exists():
        load_file_from_url(
            url=cfg['url'],
            model_dir=str(WEIGHTS_DIR),
            progress=True,
            file_name=f'{model_name}.pth',
        )

    upsampler = RealESRGANer(
        scale=netscale,
        model_path=str(weight_path),
        model=model,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=not fp32,
    )
    return upsampler, netscale


def process_job(job_id, file_paths, model_name, outscale, tile, fp32):
    def emit(event_type, data):
        with jobs_lock:
            q = jobs[job_id].get('sse_queue')
        if q:
            q.put(json.dumps({'type': event_type, **data}))

    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        emit('status', {'message': 'Loading model…'})
        upsampler, netscale = build_upsampler(model_name, tile=tile, fp32=fp32)

        total = len(file_paths)
        results = []

        for idx, src_path in enumerate(file_paths):
            src_path = Path(src_path)
            stem = src_path.stem
            suffix = src_path.suffix.lower()
            emit('progress', {'current': idx, 'total': total, 'filename': src_path.name})

            img = cv2.imread(str(src_path), cv2.IMREAD_UNCHANGED)
            if img is None:
                results.append({'filename': src_path.name, 'status': 'error', 'error': 'Could not read image'})
                continue

            try:
                output, _ = upsampler.enhance(img, outscale=outscale)
            except RuntimeError as e:
                results.append({'filename': src_path.name, 'status': 'error', 'error': str(e)})
                continue

            out_name = f'{stem}_upscaled{suffix if suffix != ".jpg" else ".jpg"}'
            if suffix in ('.png', '.tiff', '.tif', '.bmp', '.webp'):
                out_name = f'{stem}_upscaled{suffix}'
            else:
                out_name = f'{stem}_upscaled.jpg'

            out_path = job_output_dir / out_name
            cv2.imwrite(str(out_path), output)
            results.append({'filename': src_path.name, 'output': out_name, 'status': 'done'})

            emit('progress', {'current': idx + 1, 'total': total, 'filename': src_path.name, 'done': True})

        with jobs_lock:
            jobs[job_id]['status'] = 'complete'
            jobs[job_id]['results'] = results

        emit('complete', {'results': results})

    except Exception as e:
        with jobs_lock:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = str(e)
        emit('error', {'message': str(e)})
    finally:
        # Clean up uploads
        for p in file_paths:
            try:
                os.remove(p)
            except OSError:
                pass


@app.route('/')
def index():
    return render_template('index.html', models=MODEL_CONFIGS)


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    model_name = request.form.get('model', 'RealESRGAN_x4plus')
    if model_name not in MODEL_CONFIGS:
        return jsonify({'error': 'Invalid model'}), 400

    try:
        outscale = float(request.form.get('outscale', MODEL_CONFIGS[model_name]['scale']))
    except ValueError:
        outscale = float(MODEL_CONFIGS[model_name]['scale'])

    try:
        tile = int(request.form.get('tile', 0))
    except ValueError:
        tile = 0

    fp32 = request.form.get('fp32', 'false').lower() == 'true'

    job_id = str(uuid.uuid4())
    job_upload_dir = UPLOAD_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in files:
        if f.filename and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            dest = job_upload_dir / fname
            # Handle name collisions
            if dest.exists():
                stem = Path(fname).stem
                ext = Path(fname).suffix
                dest = job_upload_dir / f'{stem}_{uuid.uuid4().hex[:6]}{ext}'
            f.save(str(dest))
            saved_paths.append(str(dest))

    if not saved_paths:
        shutil.rmtree(job_upload_dir, ignore_errors=True)
        return jsonify({'error': 'No valid image files'}), 400

    sse_queue = Queue()
    with jobs_lock:
        jobs[job_id] = {
            'status': 'queued',
            'results': [],
            'error': None,
            'sse_queue': sse_queue,
        }

    t = threading.Thread(
        target=process_job,
        args=(job_id, saved_paths, model_name, outscale, tile, fp32),
        daemon=True,
    )
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/stream/<job_id>')
def stream(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        q = jobs[job_id]['sse_queue']

    def generate():
        while True:
            try:
                msg = q.get(timeout=30)
                yield f'data: {msg}\n\n'
                data = json.loads(msg)
                if data.get('type') in ('complete', 'error'):
                    break
            except Empty:
                yield 'data: {"type":"ping"}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/download/<job_id>/<filename>')
def download_file(job_id, filename):
    safe_name = secure_filename(filename)
    file_path = OUTPUT_DIR / job_id / safe_name
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    return send_file(str(file_path), as_attachment=True, download_name=safe_name)


@app.route('/download-zip/<job_id>')
def download_zip(job_id):
    output_dir = OUTPUT_DIR / job_id
    if not output_dir.exists():
        return jsonify({'error': 'Job not found'}), 404

    zip_path = OUTPUT_DIR / f'{job_id}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in output_dir.iterdir():
            zf.write(f, f.name)

    return send_file(
        str(zip_path),
        as_attachment=True,
        download_name='upscaled_images.zip',
        mimetype='application/zip',
    )


@app.route('/status/<job_id>')
def job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'status': job['status'],
        'results': job['results'],
        'error': job['error'],
    })


if __name__ == '__main__':
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    WEIGHTS_DIR.mkdir(exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
