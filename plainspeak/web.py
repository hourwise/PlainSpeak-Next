"""
Local web application for PlainSpeak.

Provides a browser-based interface for readability analysis. Runs entirely
on localhost — no network access, no accounts, no data collection.

Uses Flask as an optional dependency. Start with:
    plainspeak web
or:
    python -m plainspeak.web
"""

import sys
import webbrowser
from pathlib import Path
from typing import Optional

from . import __version__
from .analyzer import analyze, describe_flesch_score
from .simplifier import (
    analyze_simplification, generate_simplified_text,
    get_barrier_confidence, get_barrier_priority,
    group_barriers_by_sentence, build_top_improvements,
)
from .grammar import post_process_simplified


# ── HTML escaping helper ───────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Escape text for safe HTML inclusion."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ── Template (inline, so no external template files are needed) ────────────

def _build_web_ui() -> str:
    """Return the complete single-page web application HTML."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PlainSpeak — Readability Analyzer</title>
<style>
:root {
  --text: #1a1a1a;
  --bg: #ffffff;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --warning: #92400e;
  --critical: #991b1b;
  --info: #1e40af;
  --success: #166534;
  --border: #d4d4d4;
  --surface: #f8fafc;
  --surface-warning: #fffbeb;
  --surface-critical: #fef2f2;
  --surface-info: #eff6ff;
  --surface-success: #f0fdf4;
  --font: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --mono: 'Courier New', Courier, monospace;
  --line-height: 1.6;
  --radius: 0.5rem;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font);
  font-size: 1rem;
  line-height: var(--line-height);
  color: var(--text);
  background: var(--bg);
  min-height: 100vh;
}

.skip-link {
  position: absolute; top: -100px; left: 0;
  background: var(--accent); color: white;
  padding: 0.5rem 1rem; z-index: 100;
}
.skip-link:focus { top: 0; }

/* ── Layout ── */
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.app-header h1 { font-size: 1.25rem; font-weight: 700; }
.app-header .version { font-size: 0.75rem; color: #888; }
.app-header .badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--surface-success);
  color: var(--success);
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--success);
}

main {
  max-width: 56rem;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}

/* ── Input section ── */
.input-section { margin-bottom: 1.5rem; }

.input-section label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

textarea {
  width: 100%;
  min-height: 12rem;
  font-family: var(--font);
  font-size: 1rem;
  line-height: var(--line-height);
  padding: 1rem;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  resize: vertical;
  background: var(--bg);
  color: var(--text);
  transition: border-color 0.2s;
}
textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.button-row {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
  align-items: center;
}

button, .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  font-family: var(--font);
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
button:active { transform: scale(0.97); }
button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }

.btn-analyze {
  background: var(--accent);
  color: white;
}
.btn-analyze:hover { background: var(--accent-hover); }
.btn-analyze:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
}
.btn-secondary:hover { background: #e5e7eb; }

.btn-small {
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
}

.char-count {
  font-size: 0.8rem;
  color: #888;
  margin-left: auto;
}

/* ── Live scores strip ── */
.live-scores {
  display: none;
  grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.live-scores.visible { display: grid; }

.live-score {
  text-align: center;
  padding: 0.25rem;
}
.live-score .value {
  font-size: 1.25rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--accent);
}
.live-score .label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #777;
}

/* ── Results ── */
.results { display: none; }
.results.visible { display: block; }

/* Consensus banner */
.consensus {
  background: var(--surface);
  border: 2px solid var(--accent);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin: 1rem 0;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.consensus .grade {
  font-size: 3rem;
  font-weight: 800;
  color: var(--accent);
  font-family: var(--mono);
  line-height: 1;
}
.consensus .grade-label { font-size: 0.8rem; color: #666; }
.consensus .description { font-size: 1rem; }

/* Score grid */
.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}
.score-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
}
.score-card dt {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #777;
  margin-bottom: 0.15rem;
}
.score-card dd {
  font-size: 1.35rem;
  font-weight: 700;
  font-family: var(--mono);
}
.score-card .sub {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.15rem;
  font-weight: 400;
  font-family: var(--font);
}

/* Section headings */
h2 {
  font-size: 1.2rem;
  margin: 2rem 0 0.75rem;
  font-weight: 600;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.3rem;
}
h3 { font-size: 1rem; margin: 1.25rem 0 0.5rem; font-weight: 600; }

/* Barrier list */
.barrier-list { list-style: none; margin: 1rem 0; }

.barrier-item {
  padding: 0.75rem 1rem;
  margin: 0.5rem 0;
  border-radius: var(--radius);
  border-left: 4px solid var(--border);
}
.barrier-item.critical {
  background: var(--surface-critical);
  border-left-color: var(--critical);
}
.barrier-item.warning {
  background: var(--surface-warning);
  border-left-color: var(--warning);
}
.barrier-item.info {
  background: var(--surface-info);
  border-left-color: var(--info);
}

.barrier-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  margin-right: 0.5rem;
}
.barrier-badge.critical { background: var(--critical); color: white; }
.barrier-badge.warning { background: var(--warning); color: white; }
.barrier-badge.info { background: var(--info); color: white; }

.barrier-type {
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #666;
}
.barrier-quote {
  font-family: var(--mono);
  font-size: 0.85rem;
  background: rgba(0,0,0,0.04);
  padding: 0.4rem 0.65rem;
  border-radius: 0.25rem;
  margin: 0.4rem 0;
  word-break: break-word;
}
.barrier-suggestion { margin: 0.2rem 0; font-size: 0.9rem; }
.barrier-explanation { font-size: 0.8rem; color: #666; margin-top: 0.15rem; }

/* Summary stats */
.summary-stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin: 1rem 0;
}
.stat-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.5rem 1rem;
  text-align: center;
}
.stat-chip .num {
  font-size: 1.5rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--accent);
}
.stat-chip .lbl {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #888;
}

/* Simplified text area */
.simplified-output {
  width: 100%;
  min-height: 8rem;
  font-family: var(--font);
  font-size: 0.95rem;
  line-height: var(--line-height);
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0.75rem 0;
}
.simplified-output mark {
  background: #fef08a;
  padding: 0.1rem 0.15rem;
  border-radius: 0.15rem;
}

/* Warning note */
.warning-note {
  background: var(--surface-warning);
  border: 1px solid var(--warning);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  margin: 1.5rem 0;
  font-size: 0.85rem;
}
.warning-note strong { color: var(--warning); }

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border);
  margin: 1.5rem 0 1rem;
}
.tab-btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  font-weight: 600;
  font-family: var(--font);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  cursor: pointer;
  color: #888;
  transition: color 0.15s, border-color 0.15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #888;
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.empty-state p { font-size: 0.95rem; max-width: 24rem; margin: 0 auto; }

/* Spinner */
.spinner {
  display: none;
  width: 1.2rem;
  height: 1.2rem;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
.spinner.visible { display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Error message */
.error-msg {
  display: none;
  background: var(--surface-critical);
  border: 1px solid var(--critical);
  color: var(--critical);
  padding: 0.75rem 1rem;
  border-radius: var(--radius);
  margin: 1rem 0;
  font-size: 0.9rem;
}
.error-msg.visible { display: block; }

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --text: #e5e5e5;
    --bg: #1a1a2e;
    --accent: #60a5fa;
    --accent-hover: #3b82f6;
    --border: #333;
    --surface: #16213e;
    --surface-warning: #2d1f0c;
    --surface-critical: #2d0f0f;
    --surface-info: #0f1f2d;
    --surface-success: #0f2d1a;
  }
  textarea {
    background: #0f0f23;
    color: var(--text);
  }
  .barrier-quote { background: rgba(255,255,255,0.06); }
  .btn-secondary { color: var(--text); }
  .btn-secondary:hover { background: #333; }
  .simplified-output { background: #0f0f23; }
}

/* Print */
@media print {
  .app-header, .input-section, .tabs, .button-row { display: none; }
  .live-scores { display: none !important; }
  .results { display: block !important; }
  body { font-size: 11pt; }
}

/* Responsive */
@media (max-width: 480px) {
  .consensus { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .consensus .grade { font-size: 2.2rem; }
  .score-grid { grid-template-columns: 1fr 1fr; }
}
</style>
</head>
<body>

<a href="#main-content" class="skip-link">Skip to main content</a>

<header class="app-header">
  <div>
    <h1>PlainSpeak</h1>
    <span class="version">v__VERSION__</span>
  </div>
  <span class="badge" title="All analysis runs locally on your computer. No data is ever sent anywhere.">🔒 Offline &amp; Private</span>
</header>

<main id="main-content">

  <!-- Input section -->
  <section class="input-section" aria-label="Text input">
    <label for="text-input">Paste or type text to analyze:</label>
    <textarea
      id="text-input"
      placeholder="Paste your text here — a paragraph, a page, a document. PlainSpeak will measure how readable it is and identify what makes it hard to understand."
      aria-describedby="char-count"
    ></textarea>
    <div class="button-row">
      <button id="btn-analyze" class="btn-analyze" onclick="runAnalysis()">
        <span class="spinner" id="spinner"></span>
        Analyze Readability
      </button>
      <button class="btn-secondary" onclick="loadSample('legal')">Try legal sample</button>
      <button class="btn-secondary" onclick="loadSample('medical')">Try medical sample</button>
      <button class="btn-secondary" onclick="loadSample('plain')">Try plain sample</button>
      <button class="btn-secondary" onclick="clearAll()">Clear</button>
      <span class="char-count" id="char-count">0 characters</span>
    </div>
  </section>

  <!-- Live scores (debounced, updates as you type) -->
  <div class="live-scores" id="live-scores" aria-live="polite" aria-label="Live readability scores">
    <div class="live-score">
      <div class="value" id="live-grade">—</div>
      <div class="label">Consensus Grade</div>
    </div>
    <div class="live-score">
      <div class="value" id="live-ease">—</div>
      <div class="label">Reading Ease</div>
    </div>
    <div class="live-score">
      <div class="value" id="live-words">—</div>
      <div class="label">Words</div>
    </div>
    <div class="live-score">
      <div class="value" id="live-sentences">—</div>
      <div class="label">Sentences</div>
    </div>
    <div class="live-score">
      <div class="value" id="live-barriers">—</div>
      <div class="label">Barriers</div>
    </div>
  </div>

  <!-- Error message -->
  <div class="error-msg" id="error-msg" role="alert"></div>

  <!-- Results -->
  <div class="results" id="results" aria-label="Analysis results">

    <!-- Consensus -->
    <div class="consensus" aria-live="polite">
      <div>
        <div class="grade" id="consensus-grade">—</div>
        <div class="grade-label">Consensus Grade Level</div>
      </div>
      <div>
        <div class="description" id="consensus-desc"></div>
        <div style="font-size:0.8rem;color:#888;margin-top:0.25rem;">
          Flesch Reading Ease: <strong id="consensus-ease">—</strong>
        </div>
      </div>
    </div>

    <!-- Summary stats -->
    <div class="summary-stats">
      <div class="stat-chip"><div class="num" id="stat-words">—</div><div class="lbl">Words</div></div>
      <div class="stat-chip"><div class="num" id="stat-sentences">—</div><div class="lbl">Sentences</div></div>
      <div class="stat-chip"><div class="num" id="stat-syllables">—</div><div class="lbl">Syllables</div></div>
      <div class="stat-chip"><div class="num" id="stat-complex">—</div><div class="lbl">Complex Words</div></div>
      <div class="stat-chip"><div class="num" id="stat-barriers">—</div><div class="lbl">Barriers Found</div></div>
    </div>

    <!-- Tabs -->
    <div class="tabs" role="tablist">
      <button class="tab-btn active" role="tab" aria-selected="true" onclick="switchTab('scores')" id="tab-scores">Scores</button>
      <button class="tab-btn" role="tab" aria-selected="false" onclick="switchTab('barriers')" id="tab-barriers">Barriers</button>
      <button class="tab-btn" role="tab" aria-selected="false" onclick="switchTab('simplified')" id="tab-simplified">Simplified Text</button>
    </div>

    <!-- Scores panel -->
    <div class="tab-panel active" id="panel-scores" role="tabpanel">
      <dl class="score-grid" id="score-grid"></dl>
    </div>

    <!-- Barriers panel -->
    <div class="tab-panel" id="panel-barriers" role="tabpanel">
      <div id="barriers-container"></div>
    </div>

    <!-- Simplified panel -->
    <div class="tab-panel" id="panel-simplified" role="tabpanel">
      <div class="warning-note">
        <strong>⚠ Review required.</strong> Simplified text is mechanically generated by word substitution.
        Changed words are <mark>highlighted</mark>. Always review before using — substitutions may not fit the context.
      </div>
      <div class="simplified-output" id="simplified-text"></div>
      <div class="button-row">
        <button class="btn-secondary btn-small" onclick="copySimplified()">📋 Copy simplified text</button>
        <span id="copy-confirm" style="font-size:0.8rem;color:var(--success);display:none;">Copied!</span>
      </div>
    </div>

    <!-- All metrics -->
    <h2>All Readability Scores</h2>
    <dl class="score-grid" id="all-scores-grid"></dl>
  </div>

  <!-- Empty state -->
  <div class="empty-state" id="empty-state">
    <div class="icon">📝</div>
    <p>Paste some text above and click <strong>Analyze Readability</strong> to see how readable it is.</p>
  </div>

</main>

<script>
// ── State ──
let currentData = null;
let debounceTimer = null;
const DEBOUNCE_MS = 600;

// ── Character count ──
const textInput = document.getElementById('text-input');
const charCount = document.getElementById('char-count');
textInput.addEventListener('input', () => {
  const len = textInput.value.length;
  charCount.textContent = len + ' character' + (len !== 1 ? 's' : '');
  // Live analysis on typing
  clearTimeout(debounceTimer);
  if (textInput.value.trim().length > 50) {
    debounceTimer = setTimeout(runLiveAnalysis, DEBOUNCE_MS);
  }
});

// ── Live analysis (lightweight, debounced) ──
async function runLiveAnalysis() {
  const text = textInput.value;
  if (!text.trim() || text.trim().length < 30) {
    document.getElementById('live-scores').classList.remove('visible');
    return;
  }
  try {
    const resp = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, no_simplify: false })
    });
    if (!resp.ok) throw new Error('Analysis failed');
    const data = await resp.json();
    updateLiveScores(data);
  } catch (e) {
    // Silently fail for live scores — not critical
    console.warn('Live analysis failed:', e);
  }
}

function updateLiveScores(data) {
  const ls = document.getElementById('live-scores');
  ls.classList.add('visible');
  document.getElementById('live-grade').textContent = data.consensus_grade_level != null ? data.consensus_grade_level.toFixed(1) : '—';
  document.getElementById('live-ease').textContent = data.flesch_reading_ease != null ? data.flesch_reading_ease.toFixed(0) : '—';
  document.getElementById('live-words').textContent = data.total_words || '—';
  document.getElementById('live-sentences').textContent = data.total_sentences || '—';
  document.getElementById('live-barriers').textContent = data.simplification ? data.simplification.total_barriers : '—';
}

// ── Full analysis ──
async function runAnalysis() {
  const text = textInput.value;
  if (!text.trim()) {
    showError('Please enter some text to analyze.');
    return;
  }

  const btn = document.getElementById('btn-analyze');
  const spinner = document.getElementById('spinner');
  btn.disabled = true;
  spinner.classList.add('visible');
  hideError();
  document.getElementById('results').classList.remove('visible');
  document.getElementById('empty-state').style.display = 'none';

  try {
    const resp = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, no_simplify: false })
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'Analysis failed');
    }
    currentData = await resp.json();
    renderResults(currentData);
  } catch (e) {
    showError(e.message || 'Something went wrong. Please try again.');
  } finally {
    btn.disabled = false;
    spinner.classList.remove('visible');
  }
}

// ── Render ──
function renderResults(data) {
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('results').classList.add('visible');
  updateLiveScores(data);

  // Consensus
  document.getElementById('consensus-grade').textContent = data.consensus_grade_level != null ? data.consensus_grade_level.toFixed(1) : '—';
  document.getElementById('consensus-desc').textContent = data.reading_level_description || '';
  document.getElementById('consensus-ease').textContent = data.flesch_reading_ease != null ? data.flesch_reading_ease.toFixed(1) : '—';

  // Stats
  document.getElementById('stat-words').textContent = data.total_words || 0;
  document.getElementById('stat-sentences').textContent = data.total_sentences || 0;
  document.getElementById('stat-syllables').textContent = data.total_syllables || 0;
  document.getElementById('stat-complex').textContent = data.total_complex_words || 0;
  const barrierCount = data.simplification ? data.simplification.total_barriers : 0;
  document.getElementById('stat-barriers').textContent = barrierCount;

  // Score grid
  const scores = [
    ['Flesch Reading Ease', data.flesch_reading_ease, '/100', describeEase(data.flesch_reading_ease)],
    ['Flesch-Kincaid Grade', data.flesch_kincaid_grade, 'grade', ''],
    ['Gunning Fog Index', data.gunning_fog_index, 'grade', ''],
    ['SMOG Index', data.smog_index, 'grade', ''],
    ['Automated Readability', data.automated_readability_index, 'grade', ''],
    ['Coleman-Liau Index', data.coleman_liau_index, 'grade', ''],
  ];
  document.getElementById('score-grid').innerHTML = scores.map(([name, val, unit, sub]) =>
    '<div class="score-card">' +
    '<dt>' + esc(name) + '</dt>' +
    '<dd>' + (val != null ? val.toFixed(1) : '—') + ' <span style="font-size:0.7rem;font-weight:400;">' + esc(unit) + '</span></dd>' +
    (sub ? '<div class="sub">' + esc(sub) + '</div>' : '') +
    '</div>'
  ).join('');

  // All scores grid (bottom)
  document.getElementById('all-scores-grid').innerHTML = scores.map(([name, val, unit, sub]) =>
    '<div class="score-card">' +
    '<dt>' + esc(name) + '</dt>' +
    '<dd>' + (val != null ? val.toFixed(1) : '—') + ' <span style="font-size:0.7rem;font-weight:400;">' + esc(unit) + '</span></dd>' +
    (sub ? '<div class="sub">' + esc(sub) + '</div>' : '') +
    '</div>'
  ).join('');

  // Barriers
  const barriersContainer = document.getElementById('barriers-container');
  const tabBarriers = document.getElementById('tab-barriers');
  if (data.simplification && data.simplification.barriers && data.simplification.barriers.length > 0) {
    tabBarriers.textContent = 'Barriers (' + data.simplification.barriers.length + ')';
    barriersContainer.innerHTML = '<ul class="barrier-list">' +
      data.simplification.barriers.map(b =>
        '<li class="barrier-item ' + esc(b.severity || 'info') + '">' +
        '<span class="barrier-badge ' + esc(b.severity || 'info') + '">' + esc(b.severity || 'info') + '</span>' +
        '<span class="barrier-type">' + esc(formatBarrierType(b.barrier_type)) + '</span>' +
        '<div class="barrier-quote">' + esc(b.sentence_text || '') + '</div>' +
        (b.suggestion ? '<div class="barrier-suggestion">💡 Suggestion: <strong>' + esc(b.suggestion) + '</strong></div>' : '') +
        (b.explanation ? '<div class="barrier-explanation">' + esc(b.explanation) + '</div>' : '') +
        '</li>'
      ).join('') +
      '</ul>';
  } else {
    tabBarriers.textContent = 'Barriers';
    barriersContainer.innerHTML = '<p style="color:#888;margin:1rem 0;">No readability barriers detected. The text appears to be clearly written.</p>';
  }

  // Simplified text
  const simplifiedContainer = document.getElementById('simplified-text');
  if (data.simplified_text) {
    simplifiedContainer.innerHTML = esc(data.simplified_text).replace(/\\*\\*(.+?)\\*\\*/g, '<mark>$1</mark>');
  } else {
    simplifiedContainer.textContent = 'No simplified version available. Run analysis with simplification enabled.';
  }

  // Reset tabs
  switchTab('scores');

  // Scroll to results
  document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Helpers ──
function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function describeEase(score) {
  if (score == null) return '';
  if (score >= 90) return 'Very Easy';
  if (score >= 80) return 'Easy';
  if (score >= 70) return 'Fairly Easy';
  if (score >= 60) return 'Standard';
  if (score >= 50) return 'Fairly Difficult';
  if (score >= 30) return 'Difficult';
  return 'Very Difficult';
}

function formatBarrierType(type) {
  const labels = {
    'passive_voice': 'Passive Voice',
    'long_sentence': 'Long Sentence',
    'complex_word': 'Complex Word',
    'nominalization': 'Nominalization',
    'jargon': 'Jargon',
    'redundant_pair': 'Redundant Pair',
    'hidden_verb': 'Hidden Verb'
  };
  return labels[type] || type;
}

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.remove('active');
    b.setAttribute('aria-selected', 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('tab-' + name).setAttribute('aria-selected', 'true');
  document.getElementById('panel-' + name).classList.add('active');
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.add('visible');
}

function hideError() {
  document.getElementById('error-msg').classList.remove('visible');
}

function clearAll() {
  textInput.value = '';
  charCount.textContent = '0 characters';
  document.getElementById('results').classList.remove('visible');
  document.getElementById('live-scores').classList.remove('visible');
  document.getElementById('empty-state').style.display = '';
  hideError();
  currentData = null;
  textInput.focus();
}

function copySimplified() {
  const el = document.getElementById('simplified-text');
  const text = el.textContent || '';
  navigator.clipboard.writeText(text).then(() => {
    const confirm = document.getElementById('copy-confirm');
    confirm.style.display = 'inline';
    setTimeout(() => { confirm.style.display = 'none'; }, 2000);
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    const confirm = document.getElementById('copy-confirm');
    confirm.style.display = 'inline';
    setTimeout(() => { confirm.style.display = 'none'; }, 2000);
  });
}

// ── Sample loading ──
const SAMPLES = {
  legal: null,
  medical: null,
  plain: null
};

async function loadSample(name) {
  if (SAMPLES[name]) {
    textInput.value = SAMPLES[name];
    textInput.dispatchEvent(new Event('input'));
    return;
  }
  try {
    const resp = await fetch('/api/sample/' + name);
    if (resp.ok) {
      const data = await resp.json();
      SAMPLES[name] = data.text;
      textInput.value = data.text;
      textInput.dispatchEvent(new Event('input'));
    }
  } catch (e) {
    console.warn('Failed to load sample:', e);
  }
}

// ── Keyboard shortcut ──
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    runAnalysis();
  }
});
</script>
</body>
</html>""".replace("__VERSION__", __version__)


# ── Flask application factory ──────────────────────────────────────────────

def create_app():
    """Create and configure the Flask application."""
    try:
        from flask import Flask, request, jsonify, send_from_directory
    except ImportError:
        print(
            "Error: Flask is required for the web interface.\n"
            "Install it with: pip install plainspeak[web]\n"
            "Or: pip install flask",
            file=sys.stderr,
        )
        sys.exit(1)

    app = Flask(__name__, static_folder=None)

    # ── Routes ──

    @app.route("/")
    def index():
        """Serve the main web UI."""
        return _build_web_ui()

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        """
        Analyze text and return JSON results.

        Expects JSON body: {"text": "...", "no_simplify": false}
        Returns full readability scores + simplification results.
        """
        try:
            body = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON body."}), 400

        text = body.get("text", "") if body else ""
        if not text or not text.strip():
            return jsonify({"error": "No text provided."}), 400

        no_simplify = body.get("no_simplify", False) if body else False

        try:
            readability = analyze(text)
        except ValueError as e:
            return jsonify({"error": str(e)}), 422

        # Build flat response dict directly (frontend expects flat keys,
        # not the nested structure from reporter.generate_json)
        result_dict: dict = {
            "tool": "PlainSpeak",
            "version": __version__,
            # Difficulty band — PRIMARY user-facing output
            "difficulty_band": readability.difficulty_band,
            "difficulty_band_label": readability.difficulty_band_label,
            "difficulty_band_explanation": readability.difficulty_band_explanation,
            "short_text_warning": readability.short_text_warning,
            "metric_spread": round(readability.metric_spread, 1),
            "metric_count": readability.metric_count,
            # Statistics
            "total_words": readability.total_words,
            "total_sentences": readability.total_sentences,
            "total_syllables": readability.total_syllables,
            "total_complex_words": readability.total_complex_words,
            "total_long_words": readability.total_long_words,
            "avg_sentence_length": round(readability.avg_sentence_length, 2),
            "avg_word_length": round(readability.avg_word_length, 2),
            "avg_syllables_per_word": round(readability.avg_syllables_per_word, 2),
            # Scores — secondary evidence
            "flesch_reading_ease": (
                round(readability.flesch_reading_ease, 1)
                if readability.flesch_reading_ease is not None else None
            ),
            "flesch_kincaid_grade": (
                round(readability.flesch_kincaid_grade, 1)
                if readability.flesch_kincaid_grade is not None else None
            ),
            "gunning_fog_index": (
                round(readability.gunning_fog_index, 1)
                if readability.gunning_fog_index is not None else None
            ),
            "smog_index": (
                round(readability.smog_index, 1)
                if readability.smog_index is not None else None
            ),
            "automated_readability_index": (
                round(readability.automated_readability_index, 1)
                if readability.automated_readability_index is not None else None
            ),
            "coleman_liau_index": (
                round(readability.coleman_liau_index, 1)
                if readability.coleman_liau_index is not None else None
            ),
            # Legacy compatibility
            "consensus_grade_level": (
                round(readability.consensus_grade_level, 1)
                if readability.consensus_grade_level is not None else None
            ),
            "reading_level_description": readability.reading_level_description,
        }

        if not no_simplify:
            simplification = analyze_simplification(text)
            simplified_text, _substitution_count = generate_simplified_text(text)
            simplified_text = post_process_simplified(simplified_text)
            
            # Build grouped barriers by sentence
            grouped = group_barriers_by_sentence(simplification.barriers)
            top_improvements = build_top_improvements(grouped)
            
            result_dict["simplification"] = {
                "total_barriers": simplification.total_barriers,
                "critical_count": simplification.critical_count,
                "warning_count": simplification.warning_count,
                "info_count": simplification.info_count,
                "summary": simplification.summary,
                "top_improvements": top_improvements,
                "grouped_barriers": grouped,
                "barriers": [
                    {
                        "barrier_type": b.barrier_type,
                        "sentence_index": b.sentence_index,
                        "sentence_text": b.sentence_text,
                        "start_char": b.start_char,
                        "end_char": b.end_char,
                        "matched_text": b.matched_text,
                        "suggestion": b.suggestion,
                        "explanation": b.explanation,
                        "severity": b.severity,
                        "confidence": get_barrier_confidence(b.barrier_type),
                        "priority": get_barrier_priority(b.barrier_type),
                    }
                    for b in simplification.barriers
                ],
            }
            result_dict["simplified_text"] = simplified_text

        return jsonify(result_dict)

    @app.route("/api/sample/<name>")
    def api_sample(name: str):
        """Return a sample text by name."""
        samples_dir = Path(__file__).resolve().parent.parent / "examples"
        sample_files = {
            "legal": "legal_sample.txt",
            "medical": "medical_sample.txt",
            "plain": "plain_sample.txt",
        }
        if name not in sample_files:
            return jsonify({"error": "Unknown sample. Try: legal, medical, plain."}), 404

        sample_path = samples_dir / sample_files[name]
        if not sample_path.exists():
            return jsonify({"error": "Sample file not found."}), 404

        try:
            text = sample_path.read_text(encoding="utf-8")
            return jsonify({"name": name, "text": text})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


# ── Main entry point ───────────────────────────────────────────────────────

def main():
    """Start the PlainSpeak web server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PlainSpeak Web — Local readability analysis in your browser."
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=5100,
        help="Port to listen on (default: 5100).",
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Don't automatically open the browser.",
    )
    args = parser.parse_args()

    app = create_app()

    print(f"\n  PlainSpeak Web v{__version__}")
    print(f"  ─────────────────────────────")
    print(f"  Starting local server at: http://{args.host}:{args.port}")
    print(f"  All analysis runs offline on your computer.")
    print(f"  No data is ever sent anywhere.")
    print(f"  Press Ctrl+C to stop.\n")

    if not args.no_open:
        webbrowser.open(f"http://{args.host}:{args.port}")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
