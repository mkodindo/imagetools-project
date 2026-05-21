'use strict';

// ── DOM refs ──────────────────────────────────────────────────────────────────

const dropZone         = document.getElementById('drop-zone');
const fileInput        = document.getElementById('file-input');
const previewSection   = document.getElementById('preview-section');
const imgBefore        = document.getElementById('img-before');
const overlayBefore    = document.getElementById('overlay-before');
const afterPlaceholder = document.getElementById('after-placeholder');
const imgAfter         = document.getElementById('img-after');
const overlayAfter     = document.getElementById('overlay-after');
const errorBanner      = document.getElementById('error-banner');
const progressWrap     = document.getElementById('progress-wrap');
const progressBar      = document.getElementById('progress-bar');

const qualityGroup  = document.getElementById('quality-group');
const qualitySlider = document.getElementById('quality-slider');
const qualityBubble = document.getElementById('quality-bubble');
const resizeSlider  = document.getElementById('resize-slider');
const resizeBubble  = document.getElementById('resize-bubble');
const stripMetadata = document.getElementById('strip-metadata');
const autoOrient    = document.getElementById('auto-orient');

const settingsPanel    = document.getElementById('settings-panel');
const uploadAnotherBtn = document.getElementById('upload-another-btn');
const optimizeBtn      = document.getElementById('optimize-btn');
const downloadBtn      = document.getElementById('download-btn');

// Preset quality maxima (mirrors Python's _PRESET_QUALITY_MAX)
const PRESET_MAX    = { balanced: 90, speed: 80, max: 95 };
const PRESET_LABELS = { balanced: 'Balanced', speed: 'Speed', max: 'Max Quality' };

let currentFile      = null;
let currentBeforeUrl = null;
let currentAfterUrl  = null;

// ── Slider bubble positioning ─────────────────────────────────────────────────

function positionBubble(slider, bubble, suffix) {
  const min = +slider.min, max = +slider.max, val = +slider.value;
  const pct = (val - min) / (max - min);
  // Compensate for thumb width (~16 px) so bubble tracks the thumb center
  bubble.style.left = `calc(${pct * 100}% + ${(0.5 - pct) * 16}px)`;
  bubble.textContent = val + (suffix || '');
}

function updateQualityBubble() { positionBubble(qualitySlider, qualityBubble, ''); }
function updateResizeBubble()  { positionBubble(resizeSlider,  resizeBubble,  '%'); }

// Update quality slider max limit based on selected preset
function updateQualityMax() {
  const preset = document.querySelector('input[name=preset]:checked')?.value ?? 'balanced';
  const newMax = PRESET_MAX[preset] ?? 90;
  qualitySlider.max = newMax;

  // Update the displayed max in the slider-limits
  const limits = qualityGroup.querySelectorAll('.slider-limits span');
  if (limits[1]) limits[1].textContent = newMax;

  if (+qualitySlider.value > newMax) qualitySlider.value = newMax;
  updateQualityBubble();
}

// ── Estimated settings summary ────────────────────────────────────────────────

function updateEstimated() {
  const preset = document.querySelector('input[name=preset]:checked')?.value ?? 'balanced';
  document.getElementById('est-quality').textContent =
    qualityGroup.hidden ? 'N/A' : qualitySlider.value;
  document.getElementById('est-size').textContent   = resizeSlider.value + '%';
  document.getElementById('est-meta').textContent   = stripMetadata.checked ? 'Stripped' : 'Preserved';
  document.getElementById('est-preset').textContent = PRESET_LABELS[preset] ?? preset;
}

// ── Controls wiring ───────────────────────────────────────────────────────────

document.querySelectorAll('input[name=preset]').forEach(radio => {
  radio.addEventListener('change', () => {
    updateQualityMax();
    updateEstimated();
  });
});

qualitySlider.addEventListener('input', () => { updateQualityBubble(); updateEstimated(); });
resizeSlider.addEventListener('input',  () => { updateResizeBubble();  updateEstimated(); });
stripMetadata.addEventListener('change', updateEstimated);
autoOrient.addEventListener('change',   updateEstimated);

// Initialise bubbles and summary on load
updateQualityBubble();
updateResizeBubble();
updateEstimated();

// ── Drag-drop wiring ──────────────────────────────────────────────────────────

['dragenter', 'dragover'].forEach(evt =>
  dropZone.addEventListener(evt, e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  })
);

['dragleave', 'drop'].forEach(evt =>
  dropZone.addEventListener(evt, e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
  })
);

dropZone.addEventListener('drop', e  => handleFile(e.dataTransfer.files[0]));
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});
fileInput.addEventListener('change', () => handleFile(fileInput.files[0]));

// ── Client-side pre-flight ────────────────────────────────────────────────────

const CLIENT_ALLOWED   = ['image/jpeg', 'image/png', 'image/webp'];
const CLIENT_MAX_BYTES = 25 * 1024 * 1024;

function handleFile(file) {
  if (!file) return;

  if (!CLIENT_ALLOWED.includes(file.type)) {
    showError(`Format non supporté "${file.type}". Utilisez JPEG, PNG ou WebP.`);
    return;
  }
  if (file.size > CLIENT_MAX_BYTES) {
    showError(`Fichier de ${(file.size / 1024 / 1024).toFixed(1)} Mo — limite 25 Mo.`);
    return;
  }

  currentFile = file;
  hideError();

  // Show/hide quality slider based on format
  qualityGroup.hidden = !(file.type === 'image/jpeg' || file.type === 'image/webp');
  updateEstimated();

  // Build Before image from blob
  revokeIfExists(currentBeforeUrl);
  currentBeforeUrl = URL.createObjectURL(file);
  imgBefore.src = currentBeforeUrl;

  // Show Before overlay with file dimensions + size (dimensions after load)
  imgBefore.onload = () => {
    overlayBefore.textContent =
      `${imgBefore.naturalWidth} × ${imgBefore.naturalHeight} · ${formatBytes(file.size)}`;
  };

  // Reset After side to skeleton
  revokeIfExists(currentAfterUrl);
  currentAfterUrl = null;
  imgAfter.hidden         = true;
  overlayAfter.hidden     = true;
  afterPlaceholder.hidden = false;

  // Transition: hide drop zone, show preview + settings
  dropZone.hidden       = true;
  previewSection.hidden = false;
  settingsPanel.hidden  = false;

  // Enable buttons
  optimizeBtn.disabled      = false;
  uploadAnotherBtn.disabled = false;
  downloadBtn.hidden        = true;

  fileInput.value = '';
}

// ── "Upload Another" button ───────────────────────────────────────────────────

uploadAnotherBtn.addEventListener('click', () => {
  currentFile = null;
  hideError();
  resetProgress();

  // Reset Before side
  imgBefore.src = '';
  overlayBefore.textContent = '';

  // Reset After side
  revokeIfExists(currentAfterUrl);
  currentAfterUrl = null;
  imgAfter.hidden         = true;
  overlayAfter.hidden     = true;
  afterPlaceholder.hidden = false;

  // Reset buttons
  optimizeBtn.disabled      = true;
  uploadAnotherBtn.disabled = true;
  downloadBtn.hidden        = true;
  optimizeBtn.innerHTML     = 'Optimize Image';

  // Transition: show drop zone, hide preview + settings
  previewSection.hidden = true;
  settingsPanel.hidden  = true;
  dropZone.hidden       = false;
});

// ── "Optimize Image" button ───────────────────────────────────────────────────

optimizeBtn.addEventListener('click', () => {
  if (!currentFile) return;
  uploadFile(currentFile);
});

// ── XHR upload ────────────────────────────────────────────────────────────────

function uploadFile(file) {
  optimizeBtn.disabled  = true;
  optimizeBtn.innerHTML = '<span class="spinner"></span> Optimisation…';

  const fd = new FormData();
  fd.append('image',          file);
  fd.append('quality',        qualitySlider.value);
  fd.append('resize_pct',     resizeSlider.value);
  fd.append('strip_metadata', stripMetadata.checked ? 'true' : 'false');
  fd.append('auto_orient',    autoOrient.checked    ? 'true' : 'false');
  fd.append('preset',         document.querySelector('input[name=preset]:checked').value);

  const xhr = new XMLHttpRequest();

  xhr.upload.onprogress = e => {
    if (e.lengthComputable) setProgress(Math.round(e.loaded / e.total * 100));
  };

  xhr.onload = () => {
    let data;
    try   { data = JSON.parse(xhr.responseText); }
    catch { showError('Réponse serveur inattendue.'); resetOptimizeBtn(); return; }

    if (xhr.status !== 200) {
      showError(data.error || `Échec de l'envoi (HTTP ${xhr.status})`);
      resetOptimizeBtn();
      return;
    }
    setProgress(100);
    renderResult(data);
  };

  xhr.onerror = () => { showError('Erreur réseau — vérifiez votre connexion.'); resetOptimizeBtn(); };

  xhr.open('POST', '/upload');
  progressWrap.hidden = false;
  xhr.send(fd);
}

// ── Render results ────────────────────────────────────────────────────────────

async function renderResult(data) {
  try {
    const resp = await fetch(`/preview/${data.session_id}/optimized`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();

    revokeIfExists(currentAfterUrl);
    currentAfterUrl = URL.createObjectURL(blob);
    imgAfter.src    = currentAfterUrl;

    // Show After image, hide skeleton
    imgAfter.hidden         = false;
    afterPlaceholder.hidden = true;

    // After overlay: dims + size + savings
    const savings = data.savings_pct > 0
      ? `<span class="overlay-savings">Saved ${data.savings_pct}% (${formatBytes(Math.abs(data.original_size - data.optimized_size))})</span>`
      : `<span class="overlay-savings">No reduction</span>`;
    overlayAfter.innerHTML =
      `${data.width} × ${data.height} · ${formatBytes(data.optimized_size)}<br>${savings}`;
    overlayAfter.hidden = false;

    // Download button
    downloadBtn.href     = currentAfterUrl;
    downloadBtn.download = `optimized_${data.session_id.slice(0, 8)}`;
    downloadBtn.hidden   = false;

    // Clean up server temp files — blob is now in memory
    fetch(`/session/${data.session_id}`, { method: 'DELETE' }).catch(() => {});

  } catch (err) {
    showError(`Impossible de charger l'aperçu : ${err.message}`);
  }

  resetOptimizeBtn();
  resetProgress();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setProgress(pct) {
  progressBar.style.width = pct + '%';
  progressBar.setAttribute('aria-valuenow', pct);
}

function resetProgress() {
  progressWrap.hidden     = true;
  progressBar.style.width = '0%';
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.hidden      = false;
  progressWrap.hidden     = true;
}

function hideError() {
  errorBanner.hidden = true;
}

function resetOptimizeBtn() {
  optimizeBtn.disabled  = false;
  optimizeBtn.innerHTML = 'Optimize Image';
}

function revokeIfExists(url) {
  if (url) URL.revokeObjectURL(url);
}

function formatBytes(bytes) {
  if (bytes < 1024)    return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(2) + ' MB';
}
