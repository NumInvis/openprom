/**
 * OpenPROM - 诗词 AI 助手前端
 * 模块化架构：State / API / UI / Animations / History / Tabs / Generation
 */

const API_BASE_URL = window.location.origin;

const ERROR_MESSAGES = {
  'COUPLET_001': { msg: '上下联字数不等，请检查后再试' },
  'COUPLET_002': { msg: '输入包含非中文字符，仅支持中文对联' },
  'LLM_001': { msg: '服务暂时繁忙，请稍后重试' },
  'LLM_002': { msg: '结果解析异常，请重试' },
  'QC_001': { msg: '此联存在严重格律问题，建议修改' },
  'SYS_001': { msg: '系统内部错误，请稍后重试' },
  'METER_001': { msg: '格律未通过，请检查输入' },
};

const EXAMPLES = [
  { upper: '春风化雨润桃李', lower: '秋月凝霜照桂兰' },
  { upper: '书山有路勤为径', lower: '学海无涯苦作舟' },
  { upper: '天增岁月人增寿', lower: '春满乾坤福满门' }
];

/* ========== State ========== */
const State = {
  current: 'idle',
  result: null,
  history: [],
  activeTab: 'score',

  set(newState, data = null) {
    this.current = newState;
    if (data) this.result = data;
    UI.updateVisibility();
  }
};

/* ========== DOM refs ========== */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const DOM = {
  upper: $('#upper'), lower: $('#lower'),
  analyzeBtn: $('#analyzeBtn'), fillExampleBtn: $('#fillExampleBtn'),
  newAnalysisBtn: $('#newAnalysisBtn'), shareBtn: $('#shareBtn'), saveBtn: $('#saveBtn'),
  inputSection: $('#inputSection'), loadingSection: $('#loadingSection'), resultSection: $('#resultSection'),
  totalScore: $('#totalScore'), gradeBadge: $('#gradeBadge'), scoreSummary: $('#scoreSummary'),
  resultUpper: $('#resultUpper'), resultLower: $('#resultLower'),
  formalScore: $('#formalScore'), techniqueScore: $('#techniqueScore'), artisticScore: $('#artisticScore'), impressionScore: $('#impressionScore'),
  formalBar: $('#formalBar'), techniqueBar: $('#techniqueBar'), artisticBar: $('#artisticBar'), impressionBar: $('#impressionBar'),
  pingzeScore: $('#pingzeScore'), semanticScore: $('#semanticScore'),
  impressionReason: $('#impressionReason'), techniqueComment: $('#techniqueComment'), artisticComment: $('#artisticComment'),
  warningsCard: $('#warningsCard'), warningsList: $('#warningsList'),
  wordAnalysisCard: $('#wordAnalysisCard'), wordAnalysisPanel: $('#wordAnalysisPanel'),
  loadingSubtitle: $('#loadingSubtitle'), progressFill: $('#progressFill'),
  toast: $('#toast'), toastIcon: $('#toastIcon'), toastMessage: $('#toastMessage'),
  themeToggle: $('#themeToggle'), upperCount: $('#upperCount'), lowerCount: $('#lowerCount'), matchIndicator: $('#matchIndicator'),
  historyList: $('#historyList'), historyEmpty: $('#historyEmpty'), clearHistoryBtn: $('#clearHistoryBtn'),
  tabNav: $('#tabNav'),
  meterText: $('#meterText'), meterType: $('#meterType'), meterPattern: $('#meterPattern'), meterBtn: $('#meterBtn'),
  meterOutput: $('#meterOutput'), meterOutputContent: $('#meterOutputContent'),
};

/* ========== Session ========== */
const Session = {
  KEY: 'openprom-session-id',
  getId() {
    let id = localStorage.getItem(this.KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(this.KEY, id);
    }
    return id;
  }
};

/* ========== API ========== */
const API = {
  async analyze(upper, lower) {
    const resp = await fetch('/api/v1/couplet/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-ID': Session.getId() },
      body: JSON.stringify({ upper, lower, stream: false })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      const errorCode = err.error_code;
      const mapped = ERROR_MESSAGES[errorCode];
      if (mapped) throw new Error(mapped.msg);
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    return resp.json();
  },

  async *streamGenerate(endpoint, body) {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, stream: true }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        const jsonStr = trimmed.slice(6).trim();
        if (jsonStr === '[DONE]') return;
        try { yield JSON.parse(jsonStr); } catch { /* ignore malformed lines */ }
      }
    }
  },

  async meterCheck(text, meterType, patternName) {
    const resp = await fetch('/api/v1/meter/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, meter_type: meterType, pattern_name: patternName || null }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    return resp.json();
  }
};

/* ========== UI ========== */
const UI = {
  init() {
    this.bindEvents();
    this.loadTheme();
    History.load();
    this.updateVisibility();
    Tabs.init();
  },

  bindEvents() {
    DOM.analyzeBtn.addEventListener('click', () => Actions.handleAnalyze());
    DOM.newAnalysisBtn.addEventListener('click', () => Actions.reset());
    DOM.shareBtn.addEventListener('click', () => Actions.handleShare());
    DOM.saveBtn.addEventListener('click', () => Actions.handleSave());
    DOM.fillExampleBtn.addEventListener('click', () => Actions.fillExample());
    DOM.clearHistoryBtn.addEventListener('click', () => History.clear());
    DOM.themeToggle.addEventListener('click', () => Theme.toggle());
    DOM.meterBtn.addEventListener('click', () => Actions.handleMeterCheck());

    [DOM.upper, DOM.lower].forEach(el => {
      el.addEventListener('input', () => this.updateInputMeta());
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (el === DOM.upper) DOM.lower.focus();
          else Actions.handleAnalyze();
        }
      });
    });

    // Generation buttons
    $$('.gen-container').forEach(container => {
      const btn = container.querySelector('.gen-run');
      if (!btn) return;
      btn.addEventListener('click', () => {
        const type = container.dataset.type;
        const mode = container.dataset.mode;
        Actions.handleGenerate(container, type, mode);
      });
    });
  },

  updateVisibility() {
    DOM.inputSection.classList.toggle('hidden', State.current === 'loading');
    DOM.loadingSection.classList.toggle('hidden', State.current !== 'loading');
    DOM.resultSection.classList.toggle('hidden', State.current !== 'success' && State.current !== 'error');
  },

  updateInputMeta() {
    const uLen = DOM.upper.value.length;
    const lLen = DOM.lower.value.length;
    DOM.upperCount.textContent = `${uLen} 字`;
    DOM.lowerCount.textContent = `${lLen} 字`;

    if (uLen > 0 || lLen > 0) {
      if (uLen === lLen) {
        DOM.matchIndicator.textContent = '✓ 字数匹配';
        DOM.matchIndicator.className = 'match-indicator match';
      } else {
        DOM.matchIndicator.textContent = `✗ 差 ${Math.abs(uLen - lLen)} 字`;
        DOM.matchIndicator.className = 'match-indicator mismatch';
      }
    } else {
      DOM.matchIndicator.textContent = '';
      DOM.matchIndicator.className = 'match-indicator';
    }
  },

  showLoading() {
    State.set('loading');
    this.setLoadingStep(0);
    DOM.loadingSubtitle.textContent = '准备分析...';
    DOM.progressFill.style.width = '0%';
  },

  setLoadingStep(step) {
    const steps = $$('.progress-step');
    const labels = ['形式检测中...', '技法分析中...', '艺术评鉴中...', '总评生成中...'];
    steps.forEach((s, i) => {
      s.classList.remove('active', 'completed');
      if (i < step) s.classList.add('completed');
      else if (i === step) s.classList.add('active');
    });
    if (step < labels.length) DOM.loadingSubtitle.textContent = labels[step];
    DOM.progressFill.style.width = `${(step / 3) * 100}%`;
  },

  hideLoading() {
    DOM.loadingSection.classList.add('hidden');
  },

  showResult(data) {
    State.set('success', data);
    Animations.animateNumber(DOM.totalScore, data.total_score, 1200);
    Animations.animateScoreCircle(data.total_score);

    DOM.gradeBadge.textContent = data.grade;
    DOM.scoreSummary.textContent = this.getGradeSummary(data.grade, data.total_score);

    DOM.resultUpper.textContent = data.upper;
    DOM.resultLower.textContent = data.lower;

    this.updateDimension('formal', data.formal_score);
    this.updateDimension('technique', data.technique_score);
    this.updateDimension('artistic', data.artistic_score);
    this.updateDimension('impression', data.impression_score);

    DOM.pingzeScore.textContent = (data.pingze_score * 100).toFixed(0);

    DOM.impressionReason.textContent = data.comments?.impression_comment || '暂无 AI 印象';
    DOM.techniqueComment.textContent = data.comments?.technique_comment || '暂无技法点评';
    DOM.artisticComment.textContent = data.comments?.artistic_comment || '暂无艺术赏析';

    if (data.warnings && data.warnings.length > 0) {
      DOM.warningsCard.classList.remove('hidden');
      DOM.warningsList.innerHTML = '';
      data.warnings.forEach(w => {
        const li = document.createElement('li');
        li.textContent = w;
        DOM.warningsList.appendChild(li);
      });
    } else {
      DOM.warningsCard.classList.add('hidden');
    }

    if (data.detail && data.detail.word_analysis && data.detail.word_analysis.length > 0) {
      DOM.wordAnalysisCard.classList.remove('hidden');
      DOM.wordAnalysisPanel.innerHTML = '';
      const table = document.createElement('table');
      table.className = 'word-analysis-table';
      const thead = document.createElement('thead');
      thead.innerHTML = '<tr><th>位置</th><th>上联</th><th>下联</th><th>词性</th><th>平仄</th></tr>';
      table.appendChild(thead);
      const tbody = document.createElement('tbody');
      data.detail.word_analysis.forEach(wa => {
        const tr = document.createElement('tr');
        const posMatch = wa.pos_match ? '✓' : '✗';
        const toneMatch = wa.tone_match ? '✓' : '✗';
        tr.innerHTML = `<td>${wa.position + 1}</td><td>${wa.upper_char}</td><td>${wa.lower_char}</td><td>${posMatch}</td><td>${toneMatch}</td>`;
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      DOM.wordAnalysisPanel.appendChild(table);
    } else {
      DOM.wordAnalysisCard.classList.add('hidden');
    }

    setTimeout(() => DOM.resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
  },

  updateDimension(type, score) {
    const scoreEl = DOM[`${type}Score`];
    const barEl = DOM[`${type}Bar`];
    if (scoreEl) Animations.animateNumber(scoreEl, score, 1000);
    if (barEl) setTimeout(() => { barEl.style.width = `${Math.min(score, 100)}%`; }, 300);
  },

  getGradeSummary(grade, score) {
    const map = {
      '优秀': '意境深远，对仗精妙',
      '良好': '整体协调，略有可提升之处',
      '及格': '基本合规，技法有待加强',
      '不合格': '形式或内容需大幅调整'
    };
    return map[grade] || '';
  },

  showError(msg) {
    this.showToast(msg, 'error');
    State.set('error');
    this.updateVisibility();
  },

  showToast(msg, type = 'info') {
    const icons = { info: 'ℹ', success: '✓', error: '✕', warning: '!' };
    DOM.toastIcon.textContent = icons[type] || icons.info;
    DOM.toastMessage.textContent = msg;
    DOM.toast.classList.add('show');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => DOM.toast.classList.remove('show'), 3500);
  },

  loadTheme() {
    const saved = localStorage.getItem('openprom-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  }
};

/* ========== Tabs ========== */
const Tabs = {
  init() {
    $$('.tab-button').forEach(btn => {
      btn.addEventListener('click', () => this.switchTo(btn.dataset.tab));
    });
  },

  switchTo(tab) {
    State.activeTab = tab;
    $$('.tab-button').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
    $$('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === `panel-${tab}`));
    localStorage.setItem('openprom-active-tab', tab);
  }
};

/* ========== Animations ========== */
const Animations = {
  animateNumber(el, target, duration = 1000) {
    const start = performance.now();
    const from = parseFloat(el.textContent) || 0;
    const diff = target - from;
    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 4);
      el.textContent = Math.round(from + diff * ease);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  },

  animateScoreCircle(score) {
    const circumference = 2 * Math.PI * 62;
    const offset = circumference - (score / 100) * circumference;
    const el = $('.score-progress');
    if (el) {
      el.style.strokeDasharray = circumference;
      setTimeout(() => { el.style.strokeDashoffset = offset; }, 300);
    }
  }
};

/* ========== History ========== */
const History = {
  KEY: 'openprom-history',
  MAX: 50,

  load() {
    try {
      const raw = localStorage.getItem(this.KEY);
      State.history = raw ? JSON.parse(raw) : [];
    } catch { State.history = []; }
    this.render();
  },

  save() {
    localStorage.setItem(this.KEY, JSON.stringify(State.history));
    this.render();
  },

  add(item) {
    State.history.unshift(item);
    if (State.history.length > this.MAX) State.history.pop();
    this.save();
  },

  clear() {
    if (!State.history.length) return;
    if (!confirm('确定要清空所有评鉴历史吗？')) return;
    State.history = [];
    this.save();
    UI.showToast('历史记录已清空', 'success');
  },

  render() {
    if (!State.history.length) {
      DOM.historyList.innerHTML = '';
      DOM.historyList.appendChild(DOM.historyEmpty);
      DOM.historyEmpty.classList.remove('hidden');
      return;
    }
    DOM.historyEmpty.classList.add('hidden');
    DOM.historyList.innerHTML = State.history.map((h, i) => `
      <div class="history-item" data-index="${i}">
        <div class="history-item-score">${h.total_score}</div>
        <div class="history-item-content">
          <div class="history-item-couplet">${h.upper} · ${h.lower}</div>
          <div class="history-item-meta">${h.grade} · ${new Date(h.time).toLocaleString()}</div>
        </div>
        <span class="history-item-grade">${h.grade}</span>
      </div>
    `).join('');

    $$('.history-item').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.index);
        const item = State.history[idx];
        if (item && item.raw) {
          UI.showResult(item.raw);
          DOM.resultSection.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });
  }
};

/* ========== Theme ========== */
const Theme = {
  toggle() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('openprom-theme', next);
  }
};

/* ========== Actions ========== */
const Actions = {
  async handleAnalyze() {
    const upper = DOM.upper.value.trim();
    const lower = DOM.lower.value.trim();

    if (!upper || !lower) { UI.showToast('请输入上联和下联', 'warning'); return; }
    if (upper.length !== lower.length) { UI.showToast(`字数不等：上联${upper.length}字，下联${lower.length}字`, 'warning'); return; }

    UI.showLoading();

    try {
      const result = await API.analyze(upper, lower);
      UI.setLoadingStep(3);
      UI.showResult(result);
      History.add({
        upper, lower, total_score: result.total_score, grade: result.grade,
        time: Date.now(), raw: result
      });
    } catch (err) {
      console.error(err);
      UI.showError(`评鉴失败：${err.message}`);
    }
  },

  async handleGenerate(container, type, mode) {
    const prompt = container.querySelector('.gen-prompt').value.trim();
    if (!prompt) { UI.showToast('请输入提示内容', 'warning'); return; }

    const output = container.querySelector('.gen-output');
    const content = container.querySelector('.gen-output-content');
    const log = container.querySelector('.gen-output-log');
    output.classList.remove('hidden');
    content.textContent = '思考中...';
    if (log) log.classList.remove('hidden');
    if (log) log.innerHTML = '';

    const body = { prompt };
    if (type === 'couplet') {
      body.length = parseInt(container.querySelector('.gen-length').value, 10);
    } else {
      body.form = container.querySelector('.gen-form').value;
      body.tone_preference = container.querySelector('.gen-tone').value || null;
    }

    const endpoint = `/api/v1/${type}/${mode}`;
    try {
      for await (const event of API.streamGenerate(endpoint, body)) {
        if (event.event === 'final') {
          content.textContent = event.content || '（无输出）';
        } else if (event.event === 'tool_result' && event.result) {
          if (log) {
            const div = document.createElement('div');
            div.className = 'log-entry';
            div.textContent = `工具 ${event.tool}: ${JSON.stringify(event.result, null, 2)}`;
            log.appendChild(div);
          }
        } else if (event.event === 'error') {
          content.textContent = `错误：${event.message || '未知错误'}`;
          break;
        }
      }
    } catch (err) {
      console.error(err);
      content.textContent = `请求失败：${err.message}`;
      UI.showToast(`生成失败：${err.message}`, 'error');
    }
  },

  async handleMeterCheck() {
    const text = DOM.meterText.value.trim();
    if (!text) { UI.showToast('请输入待检测文本', 'warning'); return; }

    DOM.meterOutput.classList.remove('hidden');
    DOM.meterOutputContent.textContent = '检测中...';
    try {
      const result = await API.meterCheck(text, DOM.meterType.value, DOM.meterPattern.value);
      DOM.meterOutputContent.textContent = JSON.stringify(result, null, 2);
    } catch (err) {
      DOM.meterOutputContent.textContent = `请求失败：${err.message}`;
      UI.showToast(`检测失败：${err.message}`, 'error');
    }
  },

  reset() {
    DOM.upper.value = '';
    DOM.lower.value = '';
    UI.updateInputMeta();
    State.set('idle');
    UI.updateVisibility();
    DOM.inputSection.scrollIntoView({ behavior: 'smooth' });
  },

  handleShare() {
    const r = State.result;
    if (!r) return;
    const text = `【PORM对联评鉴】\n上联：${r.upper}\n下联：${r.lower}\n总分：${r.total_score}分（${r.grade}）\n\n来自 OpenPROM 诗词 AI 助手`;
    if (navigator.share) {
      navigator.share({ title: '对联评鉴结果', text }).catch(() => {});
    } else {
      navigator.clipboard.writeText(text).then(() => UI.showToast('结果已复制到剪贴板', 'success'));
    }
  },

  handleSave() {
    const r = State.result;
    if (!r) return;
    History.add({
      upper: r.upper, lower: r.lower, total_score: r.total_score, grade: r.grade,
      time: Date.now(), raw: r
    });
    UI.showToast('已保存到历史记录', 'success');
  },

  fillExample() {
    const ex = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
    DOM.upper.value = ex.upper;
    DOM.lower.value = ex.lower;
    UI.updateInputMeta();
    UI.showToast('已填入示例对联', 'info');
  }
};

/* ========== Boot ========== */
document.addEventListener('DOMContentLoaded', () => {
  UI.init();
  const savedTab = localStorage.getItem('openprom-active-tab');
  if (savedTab) Tabs.switchTo(savedTab);
});
