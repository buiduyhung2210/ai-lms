/**
 * AI LMS — Frontend Application
 * Handles file upload, SSE progress streaming, and results rendering.
 */

// ── DOM refs ─────────────────────────────────────────────────
const dropZone         = document.getElementById('drop-zone');
const fileInput        = document.getElementById('file-input');
const fileInfo         = document.getElementById('file-info');
const fileNameDisplay  = document.getElementById('file-name-display');
const fileSizeDisplay  = document.getElementById('file-size-display');
const btnGenerate      = document.getElementById('btn-generate');
const apiKeyInput      = document.getElementById('api-key-input');

const uploadSection    = document.getElementById('upload-section');
const progressSection  = document.getElementById('progress-section');
const resultsSection   = document.getElementById('results-section');

const progressBar      = document.getElementById('progress-bar');
const progressBarWrap  = document.getElementById('progress-bar-wrap');
const progressStepText = document.getElementById('progress-step-text');
const progressSub      = document.getElementById('progress-sub');

const errorCard        = document.getElementById('error-card');
const errorMsg         = document.getElementById('error-msg');

const resultVideo      = document.getElementById('result-video');
const videoDownloadLink       = document.getElementById('video-download-link');
const resultInfographic       = document.getElementById('result-infographic');
const infographicDownloadLink = document.getElementById('infographic-download-link');
const resultsTitle     = document.getElementById('results-title');
const resultsTopic     = document.getElementById('results-topic');
const slidesList       = document.getElementById('slides-list');
const btnReset         = document.getElementById('btn-reset');

// ── State ─────────────────────────────────────────────────────
let selectedFile = null;
let eventSource  = null;

// ── File selection ─────────────────────────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function handleFileSelect(file) {
  const allowed = ['.pdf', '.docx', '.doc', '.txt'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showError(`Unsupported file type "${ext}". Please upload PDF, DOCX, or TXT.`);
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    showError('File is too large. Maximum allowed size is 20 MB.');
    return;
  }
  selectedFile = file;
  fileNameDisplay.textContent = file.name;
  fileSizeDisplay.textContent = formatBytes(file.size);
  fileInfo.classList.add('show');
  btnGenerate.disabled = false;
  hideError();
}

fileInput.addEventListener('change', (e) => {
  if (e.target.files[0]) handleFileSelect(e.target.files[0]);
});

// Drag & drop
dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFileSelect(f);
});

// Keyboard accessibility
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});

// ── Generate ───────────────────────────────────────────────────

btnGenerate.addEventListener('click', startGeneration);

async function startGeneration() {
  if (!selectedFile) return;

  const apiKey = apiKeyInput.value.trim();

  hideError();
  showProgress();

  const formData = new FormData();
  formData.append('file', selectedFile);
  if (apiKey) {
    formData.append('api_key', apiKey);
  }

  let jobId;
  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Server error ${res.status}`);
    }
    jobId = data.job_id;
  } catch (err) {
    showUpload();
    showError(`Failed to start generation: ${err.message}`);
    return;
  }

  // Start SSE polling
  pollJobStatus(jobId);
}

function pollJobStatus(jobId) {
  if (eventSource) eventSource.close();

  eventSource = new EventSource(`/api/status/${jobId}`);

  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateProgress(data);

    if (data.status === 'done') {
      eventSource.close();
      showResults(data.result);
    } else if (data.status === 'error') {
      eventSource.close();
      showUpload();
      showError(data.error || 'An unknown error occurred during generation.');
    }
  };

  eventSource.onerror = () => {
    if (eventSource) eventSource.close();
    showUpload();
    showError('Lost connection to server. Please try again.');
  };
}

// ── Progress updates ──────────────────────────────────────────

const STEP_MAP = [
  { key: 'parse',       triggers: ['Parsing'],               id: 'pstep-parse' },
  { key: 'analyze',     triggers: ['Analyzing'],              id: 'pstep-analyze' },
  { key: 'infographic', triggers: ['infographic', 'Generating infographic', 'Designing'], id: 'pstep-infographic' },
  { key: 'slides',      triggers: ['Rendering slide', 'slide'],     id: 'pstep-slides' },
  { key: 'audio',       triggers: ['narration', 'audio', 'Generating narration'], id: 'pstep-audio' },
  { key: 'video',       triggers: ['Assembling', 'video', 'Complete'], id: 'pstep-video' },
];

function updateProgress(data) {
  const pct = Math.min(data.progress || 0, 100);
  progressBar.style.width = pct + '%';
  progressBarWrap.setAttribute('aria-valuenow', pct);

  progressStepText.textContent = data.step || 'Processing...';

  // Update step indicators
  const stepText = (data.step || '').toLowerCase();
  let activeIdx = -1;
  STEP_MAP.forEach((s, i) => {
    if (s.triggers.some(t => stepText.includes(t.toLowerCase()))) {
      activeIdx = i;
    }
  });

  STEP_MAP.forEach((s, i) => {
    const el = document.getElementById(s.id);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (i < activeIdx) el.classList.add('done');
    else if (i === activeIdx) el.classList.add('active');
  });
}

// ── Results ───────────────────────────────────────────────────

function showResults(result) {
  progressSection.style.display = 'none';
  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  resultsTitle.textContent = result.lesson_title || 'Your Training Materials';
  resultsTopic.textContent = `Topic: ${result.topic || 'General Training'}`;

  // Video
  const videoUrl = result.video_url;
  resultVideo.src = videoUrl;
  videoDownloadLink.href = videoUrl;
  videoDownloadLink.download = `training_${Date.now()}.mp4`;

  // Infographics
  const infographicContainer = document.getElementById('infographic-container') || resultInfographic.parentElement;
  
  // Clear previous infographics if we added many
  const oldExtra = infographicContainer.querySelectorAll('.extra-infographic');
  oldExtra.forEach(el => el.remove());

  const urls = result.infographic_urls || [];
  const b64s = result.infographic_base64s || [];

  if (urls.length > 0) {
    // Update first one (main)
    resultInfographic.src = urls[0];
    infographicDownloadLink.href = urls[0];
    
    // Add others
    for (let i = 1; i < urls.length; i++) {
      const wrapper = document.createElement('div');
      wrapper.className = 'extra-infographic card mt-4';
      wrapper.innerHTML = `
        <img src="${urls[i]}" class="img-fluid rounded mb-2" alt="Infographic ${i+1}">
        <a href="${urls[i]}" download="infographic_${i+1}.png" class="btn btn-outline-primary btn-sm w-100">
          Download Part ${i+1}
        </a>
      `;
      infographicContainer.appendChild(wrapper);
    }
  } else if (result.infographic_url) {
      resultInfographic.src = result.infographic_url;
      infographicDownloadLink.href = result.infographic_url;
  }

  // Slide outline
  slidesList.innerHTML = '';
  (result.slides || []).forEach((slide) => {
    const item = document.createElement('div');
    item.className = 'slide-item';
    item.setAttribute('role', 'listitem');
    
    let bulletsHtml = '';
    if (slide.bullets && slide.bullets.length > 0) {
      bulletsHtml = '<ul class="slide-bullets" style="margin-top: 10px; font-size: 0.9em; color: var(--text-muted);">';
      slide.bullets.forEach(b => {
        if (typeof b === 'object' && b !== null) {
          bulletsHtml += `<li>${escapeHtml(b.text || '')}`;
          if (b.example) {
            bulletsHtml += `<br><code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-size: 0.85em; color: var(--accent); margin-top: 4px; display: inline-block;">${escapeHtml(b.example)}</code>`;
          }
          bulletsHtml += `</li>`;
        } else {
          bulletsHtml += `<li>${escapeHtml(b)}</li>`;
        }
      });
      bulletsHtml += '</ul>';
    }

    item.innerHTML = `
      <div class="slide-item-header">
        <div class="slide-num">${slide.slide_number}</div>
        <span class="slide-heading">${escapeHtml(slide.heading)}</span>
      </div>
      <p class="slide-narration">${escapeHtml(slide.narration || '')}</p>
      ${bulletsHtml}
    `;
    slidesList.appendChild(item);
  });
}

// ── Utility: show/hide sections ───────────────────────────────

function showProgress() {
  uploadSection.style.display = 'none';
  progressSection.style.display = 'block';
  resultsSection.style.display = 'none';
  errorCard.classList.remove('show');
  progressBar.style.width = '0%';
  progressStepText.textContent = 'Initializing...';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showUpload() {
  uploadSection.style.display = 'block';
  progressSection.style.display = 'none';
  resultsSection.style.display = 'none';
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorCard.classList.add('show');
  errorCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideError() {
  errorCard.classList.remove('show');
}

// ── Reset ──────────────────────────────────────────────────────

btnReset.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.remove('show');
  fileNameDisplay.textContent = '';
  fileSizeDisplay.textContent = '';
  btnGenerate.disabled = true;
  resultVideo.src = '';
  resultInfographic.src = '';
  slidesList.innerHTML = '';
  hideError();
  showUpload();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (eventSource) { eventSource.close(); eventSource = null; }
});

// ── Helpers ────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Restore API key from sessionStorage if available
const savedKey = sessionStorage.getItem('gemini_api_key');
if (savedKey) apiKeyInput.value = savedKey;
apiKeyInput.addEventListener('input', () => {
  if (apiKeyInput.value.trim()) {
    sessionStorage.setItem('gemini_api_key', apiKeyInput.value.trim());
  }
});
