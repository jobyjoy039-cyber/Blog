/* ── State ──────────────────────────────────────────────────────── */
let selectedFiles = [];
let currentJobId = null;
let eventSource = null;

/* ── DOM refs ───────────────────────────────────────────────────── */
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const clearBtn = document.getElementById('clear-btn');
const upscaleBtn = document.getElementById('upscale-btn');
const progressPanel = document.getElementById('progress-panel');
const progressFill = document.getElementById('progress-fill');
const progressLabel = document.getElementById('progress-label');
const progressStatus = document.getElementById('progress-status');
const progressItems = document.getElementById('progress-items');
const resultsPanel = document.getElementById('results-panel');
const resultsGrid = document.getElementById('results-grid');
const downloadAllBtn = document.getElementById('download-all-btn');
const newJobBtn = document.getElementById('new-job-btn');
const modelSelect = document.getElementById('model-select');
const outscaleInput = document.getElementById('outscale');

/* ── File helpers ───────────────────────────────────────────────── */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function addFiles(newFiles) {
  const allowed = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'];
  for (const f of newFiles) {
    const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(ext)) continue;
    if (selectedFiles.some(x => x.name === f.name && x.size === f.size)) continue;
    selectedFiles.push(f);
  }
  renderFileList();
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  renderFileList();
}

function clearFiles() {
  selectedFiles = [];
  renderFileList();
}

function renderFileList() {
  fileList.innerHTML = '';
  if (selectedFiles.length === 0) {
    fileList.hidden = true;
    clearBtn.disabled = true;
    upscaleBtn.disabled = true;
    return;
  }

  fileList.hidden = false;
  clearBtn.disabled = false;
  upscaleBtn.disabled = false;

  selectedFiles.forEach((f, i) => {
    const item = document.createElement('div');
    item.className = 'file-item';

    const thumb = document.createElement('img');
    thumb.className = 'file-thumb';
    thumb.alt = f.name;
    const reader = new FileReader();
    reader.onload = e => { thumb.src = e.target.result; };
    reader.readAsDataURL(f);

    const info = document.createElement('div');
    info.className = 'file-info';
    info.innerHTML = `<div class="file-name">${escHtml(f.name)}</div><div class="file-size">${formatSize(f.size)}</div>`;

    const removeBtn = document.createElement('button');
    removeBtn.className = 'file-remove';
    removeBtn.title = 'Remove';
    removeBtn.textContent = '✕';
    removeBtn.addEventListener('click', () => removeFile(i));

    item.appendChild(thumb);
    item.appendChild(info);
    item.appendChild(removeBtn);
    fileList.appendChild(item);
  });
}

function escHtml(str) {
  return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* ── Drag & Drop ────────────────────────────────────────────────── */
dropZone.addEventListener('click', e => {
  if (e.target.classList.contains('file-label')) return;
  fileInput.click();
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', () => {
  addFiles(fileInput.files);
  fileInput.value = '';
});

clearBtn.addEventListener('click', clearFiles);

/* ── Scale buttons ──────────────────────────────────────────────── */
document.querySelectorAll('.scale-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const delta = parseFloat(btn.dataset.delta);
    let val = parseFloat(outscaleInput.value) + delta;
    val = Math.max(1, Math.min(8, val));
    outscaleInput.value = val;
  });
});

/* ── Model → default scale sync ────────────────────────────────── */
const modelScales = {
  'RealESRGAN_x4plus': 4,
  'RealESRGAN_x4plus_anime_6B': 4,
  'RealESRGAN_x2plus': 2,
  'realesr-animevideov3': 4,
};
modelSelect.addEventListener('change', () => {
  const s = modelScales[modelSelect.value];
  if (s) outscaleInput.value = s;
});

/* ── Upscale job ────────────────────────────────────────────────── */
upscaleBtn.addEventListener('click', startJob);
newJobBtn.addEventListener('click', resetUI);

async function startJob() {
  if (selectedFiles.length === 0) return;

  // Build form data
  const formData = new FormData();
  selectedFiles.forEach(f => formData.append('images', f));
  formData.append('model', modelSelect.value);
  formData.append('outscale', outscaleInput.value);
  formData.append('tile', document.getElementById('tile-size').value);
  formData.append('fp32', document.getElementById('fp32-toggle').checked ? 'true' : 'false');

  // Show progress panel
  showProgressPanel(selectedFiles);

  upscaleBtn.disabled = true;
  clearBtn.disabled = true;

  let jobId;
  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    jobId = data.job_id;
    currentJobId = jobId;
  } catch (err) {
    progressStatus.textContent = 'Error: ' + err.message;
    progressStatus.style.color = 'var(--error)';
    return;
  }

  // SSE stream
  eventSource = new EventSource(`/stream/${jobId}`);
  eventSource.onmessage = e => handleSSE(JSON.parse(e.data));
  eventSource.onerror = () => {
    progressStatus.textContent = 'Connection lost — checking status…';
    eventSource.close();
    setTimeout(() => pollStatus(jobId), 2000);
  };
}

function handleSSE(msg) {
  switch (msg.type) {
    case 'status':
      progressStatus.textContent = msg.message;
      break;
    case 'progress':
      updateProgress(msg);
      break;
    case 'complete':
      eventSource && eventSource.close();
      showResults(msg.results);
      break;
    case 'error':
      eventSource && eventSource.close();
      progressStatus.textContent = 'Error: ' + msg.message;
      progressStatus.style.color = 'var(--error)';
      break;
  }
}

async function pollStatus(jobId) {
  try {
    const res = await fetch(`/status/${jobId}`);
    const data = await res.json();
    if (data.status === 'complete') showResults(data.results);
    else if (data.status === 'error') {
      progressStatus.textContent = 'Error: ' + (data.error || 'Unknown error');
      progressStatus.style.color = 'var(--error)';
    } else setTimeout(() => pollStatus(jobId), 2000);
  } catch {
    setTimeout(() => pollStatus(jobId), 4000);
  }
}

/* ── Progress UI ────────────────────────────────────────────────── */
function showProgressPanel(files) {
  progressPanel.hidden = false;
  resultsPanel.hidden = true;
  progressItems.innerHTML = '';
  progressFill.style.width = '0%';
  progressLabel.textContent = `0 / ${files.length}`;
  progressStatus.textContent = 'Uploading…';
  progressStatus.style.color = '';

  files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'progress-item';
    item.id = `pi-${cssId(f.name)}`;
    item.innerHTML = `
      <div class="pi-dot waiting"></div>
      <div class="pi-name">${escHtml(f.name)}</div>
      <span class="pi-badge waiting">Waiting</span>
    `;
    progressItems.appendChild(item);
  });
}

function cssId(name) {
  return name.replace(/[^a-zA-Z0-9]/g, '_');
}

function updateProgress(msg) {
  progressStatus.textContent = `Processing: ${escHtml(msg.filename)}`;
  const pct = msg.total > 0 ? (msg.current / msg.total) * 100 : 0;
  progressFill.style.width = pct + '%';
  progressLabel.textContent = `${msg.current} / ${msg.total}`;

  const id = `pi-${cssId(msg.filename)}`;
  const item = document.getElementById(id);
  if (!item) return;

  if (msg.done) {
    item.querySelector('.pi-dot').className = 'pi-dot done';
    item.querySelector('.pi-badge').className = 'pi-badge done';
    item.querySelector('.pi-badge').textContent = 'Done';
  } else {
    item.querySelector('.pi-dot').className = 'pi-dot processing';
    item.querySelector('.pi-badge').className = 'pi-badge processing';
    item.querySelector('.pi-badge').textContent = 'Processing';
  }
}

/* ── Results UI ─────────────────────────────────────────────────── */
function showResults(results) {
  progressFill.style.width = '100%';
  const total = results.length;
  const done = results.filter(r => r.status === 'done').length;
  progressLabel.textContent = `${total} / ${total}`;
  progressStatus.textContent = `Complete — ${done} succeeded, ${total - done} failed`;

  resultsPanel.hidden = false;
  resultsGrid.innerHTML = '';

  results.forEach(r => {
    const card = document.createElement('div');
    card.className = 'result-card' + (r.status === 'error' ? ' error-card' : '');

    if (r.status === 'done') {
      const imgUrl = `/download/${currentJobId}/${encodeURIComponent(r.output)}`;
      card.innerHTML = `
        <div class="result-thumb-wrap">
          <img class="result-thumb" src="${imgUrl}" alt="${escHtml(r.output)}" loading="lazy" />
        </div>
        <div class="result-body">
          <div class="result-name" title="${escHtml(r.output)}">${escHtml(r.output)}</div>
          <a class="result-dl-btn" href="${imgUrl}" download="${escHtml(r.output)}">↓ Download</a>
        </div>
      `;
    } else {
      card.innerHTML = `
        <div class="result-body">
          <div class="result-name">${escHtml(r.filename)}</div>
          <div class="result-error">⚠ ${escHtml(r.error || 'Processing failed')}</div>
        </div>
      `;
    }
    resultsGrid.appendChild(card);
  });
}

downloadAllBtn.addEventListener('click', () => {
  if (currentJobId) window.location.href = `/download-zip/${currentJobId}`;
});

/* ── Reset ──────────────────────────────────────────────────────── */
function resetUI() {
  clearFiles();
  progressPanel.hidden = true;
  resultsPanel.hidden = true;
  currentJobId = null;
  if (eventSource) { eventSource.close(); eventSource = null; }
}
