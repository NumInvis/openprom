/**
 * OpenPROM · 前端逻辑
 * 模块：State / DOM / Session / API / UI / Tabs / Animate / History / Theme / Actions
 * SSE 全事件：thinking / tool_call / tool_result / done / final / error / start / result
 */

const ERROR_MESSAGES = {
  'COUPLET_001': '上下联字数不等，请检查后再试',
  'COUPLET_002': '输入包含非中文字符，仅支持中文对联',
  'LLM_001': '服务暂时繁忙，请稍后重试',
  'LLM_002': '结果解析异常，请重试',
  'QC_001': '此联存在严重格律问题，建议修改',
  'SYS_001': '系统内部错误，请稍后重试',
  'METER_001': '格律未通过，请检查输入',
};

const EXAMPLES = [
  { upper: '春风化雨润桃李', lower: '秋月凝霜照桂兰' },
  { upper: '书山有路勤为径', lower: '学海无涯苦作舟' },
  { upper: '天增岁月人增寿', lower: '春满乾坤福满门' },
];

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

/* ========== State ========== */
const State = {
  cur: 'idle',
  result: null,
  history: [],
  activeTab: 'score',
  set(s, data = null) { this.cur = s; if (data) this.result = data; UI.syncVisibility(); },
};

/* ========== DOM ========== */
const DOM = {};
function cacheDOM() {
  [
    'upper','lower','analyzeBtn','fillExampleBtn','newAnalysisBtn','shareBtn','saveBtn',
    'scoreInput','scoreLoading','scoreResult','totalScore','gradeBadge','scoreSummary',
    'resultUpper','resultLower','formalScore','techniqueScore','artisticScore','impressionScore',
    'formalBar','techniqueBar','artisticBar','impressionBar','pingzeScore','semanticScore','saddleTag',
    'techniqueComment','artisticComment','impressionReason','warningsCard','warningsList',
    'wordAnalysisCard','wordAnalysisPanel','loadingSub','scoreRing',
    'toast','toastSeal','toastMessage','themeToggle','upperCount','lowerCount','matchIndicator',
    'historyList','historyEmpty','clearHistoryBtn','tabNav',
    'meterText','meterType','meterPattern','meterPatternList','meterBtn','meterOutput','meterComplianceTag','meterBody',
    'knowledgeQuery','knowledgeTaskType','knowledgeTopK','knowledgeBtn','knowledgeOutput','knowledgeMeta','knowledgeList',
    'traceList','traceEmpty','refreshTracesBtn',
  ].forEach(id => { DOM[id] = document.getElementById(id); });
}

/* ========== Session ========== */
const Session = {
  KEY: 'openprom-session-id',
  get() {
    let id = localStorage.getItem(this.KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(this.KEY, id);
    }
    return id;
  },
};

/* ========== API ========== */
const API = {
  async analyze(upper, lower) {
    const resp = await fetch('/api/v1/couplet/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-ID': Session.get() },
      body: JSON.stringify({ upper, lower, stream: false }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      const mapped = ERROR_MESSAGES[err.error_code];
      throw new Error(mapped || err.detail || `请求失败 (${resp.status})`);
    }
    return resp.json();
  },

  async *stream(endpoint, body) {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-ID': Session.get() },
      body: JSON.stringify({ ...body, stream: true }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      const mapped = ERROR_MESSAGES[err.error_code];
      throw new Error(mapped || err.detail || `请求失败 (${resp.status})`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data: ')) {
          if (line.startsWith(':')) continue;
          continue;
        }
        const jsonStr = line.slice(6).trim();
        if (jsonStr === '[DONE]') return;
        try { yield JSON.parse(jsonStr); } catch { /* ignore */ }
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
  },

  async knowledgeSearch(query, topK, taskType) {
    const body = { query, top_k: topK };
    if (taskType) body.task_type = taskType;
    const resp = await fetch('/api/v1/knowledge/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `请求失败 (${resp.status})`);
    }
    return resp.json();
  },

  async listTraces(limit = 20) {
    const resp = await fetch(`/api/v1/tasks/traces?limit=${limit}`);
    if (!resp.ok) throw new Error(`请求失败 (${resp.status})`);
    return resp.json();
  },
};
/* ========== UI ========== */
const UI = {
  init() {
    cacheDOM();
    this.bind();
    Theme.load();
    History.load();
    this.syncVisibility();
    Tabs.init();
    const savedTab = localStorage.getItem('openprom-active-tab');
    if (savedTab) Tabs.switch(savedTab);
    Actions.loadMeterPatterns();
  },

  bind() {
    DOM.analyzeBtn.addEventListener('click', () => Actions.analyze());
    DOM.newAnalysisBtn.addEventListener('click', () => Actions.reset());
    DOM.shareBtn.addEventListener('click', () => Actions.share());
    DOM.saveBtn.addEventListener('click', () => Actions.save());
    DOM.fillExampleBtn.addEventListener('click', () => Actions.fillExample());
    DOM.clearHistoryBtn.addEventListener('click', () => History.clear());
    DOM.themeToggle.addEventListener('click', () => Theme.toggle());
    DOM.meterBtn.addEventListener('click', () => Actions.meterCheck());
    DOM.meterType.addEventListener('change', () => Actions.loadMeterPatterns());
    DOM.knowledgeBtn.addEventListener('click', () => Actions.knowledgeSearch());
    DOM.refreshTracesBtn.addEventListener('click', () => Actions.loadTraces());

    [DOM.upper, DOM.lower].forEach(el => {
      el.addEventListener('input', () => this.updateInputMeta());
      el.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (el === DOM.upper) DOM.lower.focus();
          else Actions.analyze();
        }
      });
    });

    $$('.gen-stage').forEach(stage => {
      const btn = stage.querySelector('.gen-run');
      if (!btn) return;
      btn.addEventListener('click', () => {
        Actions.generate(stage, stage.dataset.type, stage.dataset.mode);
      });
    });
  },

  syncVisibility() {
    DOM.scoreInput.classList.toggle('hidden', State.cur === 'loading');
    DOM.scoreLoading.classList.toggle('hidden', State.cur !== 'loading');
    DOM.scoreResult.classList.toggle('hidden', State.cur !== 'success' && State.cur !== 'error');
  },

  updateInputMeta() {
    const u = DOM.upper.value.length, l = DOM.lower.value.length;
    DOM.upperCount.textContent = `${u} 字`;
    DOM.lowerCount.textContent = `${l} 字`;
    if (u > 0 || l > 0) {
      if (u === l) {
        DOM.matchIndicator.textContent = '✓ 字数匹配';
        DOM.matchIndicator.className = 'match-ind match';
      } else {
        DOM.matchIndicator.textContent = `✗ 差 ${Math.abs(u - l)} 字`;
        DOM.matchIndicator.className = 'match-ind mismatch';
      }
    } else {
      DOM.matchIndicator.textContent = '';
      DOM.matchIndicator.className = 'match-ind';
    }
  },

  showLoading() {
    State.set('loading');
    this.setLoadStep(0);
    DOM.loadingSub.textContent = '准备分析…';
  },

  setLoadStep(step) {
    const rows = $$('.bar-row');
    const labels = ['形式分析中…', '技法评判中…', '艺术赏析中…', '马鞍校准中…'];
    rows.forEach((r, i) => {
      r.classList.remove('active', 'done');
      if (i < step) r.classList.add('done');
      else if (i === step) r.classList.add('active');
    });
    if (step < labels.length) DOM.loadingSub.textContent = labels[step];
  },

  showResult(data) {
    State.set('success', data);
    Animate.number(DOM.totalScore, data.total_score, 1200);
    Animate.ring(data.total_score);
    DOM.gradeBadge.textContent = data.grade;
    DOM.scoreSummary.textContent = this.gradeSummary(data.grade);
    DOM.resultUpper.textContent = data.upper;
    DOM.resultLower.textContent = data.lower;
    this.updateDim('formal', data.formal_score);
    this.updateDim('technique', data.technique_score);
    this.updateDim('artistic', data.artistic_score);
    this.updateDim('impression', data.impression_score);
    DOM.pingzeScore.textContent = Math.round((data.pingze_score || 0) * 100);
    DOM.semanticScore.textContent = data.detail?.word_analysis?.length ? '已分析' : '—';
    DOM.saddleTag.textContent = data.saddle_applied ? '已校准' : '原值';
    DOM.techniqueComment.textContent = data.comments?.technique_comment || '暂无点评';
    DOM.artisticComment.textContent = data.comments?.artistic_comment || '暂无赏析';
    DOM.impressionReason.textContent = data.comments?.impression_comment || '暂无印象';

    if (data.warnings && data.warnings.length) {
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

    if (data.detail?.word_analysis?.length) {
      DOM.wordAnalysisCard.classList.remove('hidden');
      this.renderWordTable(data.detail.word_analysis);
    } else {
      DOM.wordAnalysisCard.classList.add('hidden');
    }

    setTimeout(() => DOM.scoreResult.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
  },

  renderWordTable(wa) {
    DOM.wordAnalysisPanel.innerHTML = '';
    const tbl = document.createElement('table');
    tbl.className = 'word-table';
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>位</th><th>上联</th><th>下联</th><th>词性</th><th>平仄</th></tr>';
    tbl.appendChild(thead);
    const tbody = document.createElement('tbody');
    wa.forEach(w => {
      const tr = document.createElement('tr');
      const posCls = w.pos_match ? 'pos-ok' : 'pos-bad';
      const posMark = w.pos_match ? '✓' : '✗';
      const toneMark = w.tone_match === null || w.tone_match === undefined ? '—' : (w.tone_match ? '✓' : '✗');
      const toneCls = w.tone_match ? 'pos-ok' : 'pos-bad';
      tr.innerHTML = `<td>${w.position + 1}</td><td>${w.upper_char}</td><td>${w.lower_char}</td><td class="${posCls}">${posMark}</td><td class="${toneCls}">${toneMark}</td>`;
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    DOM.wordAnalysisPanel.appendChild(tbl);
  },

  updateDim(type, score) {
    const sEl = DOM[`${type}Score`], bEl = DOM[`${type}Bar`];
    if (sEl) Animate.number(sEl, score, 1000);
    if (bEl) setTimeout(() => { bEl.style.width = `${Math.min(score, 100)}%`; }, 300);
  },

  gradeSummary(grade) {
    return { '优秀': '意境深远，对仗精妙', '良好': '整体协调，略有可提升', '及格': '基本合规，技法待加强', '不合格': '形式或内容需调整' }[grade] || '——';
  },

  showError(msg) {
    this.toast(msg, 'error');
    State.set('error');
    this.syncVisibility();
  },

  toast(msg, type = 'info') {
    DOM.toast.className = `toast ${type}`;
    const seals = { info: '·', success: '✓', error: '✕', warning: '!' };
    DOM.toastSeal.textContent = seals[type] || '·';
    DOM.toastMessage.textContent = msg;
    DOM.toast.classList.add('show');
    clearTimeout(this._tt);
    this._tt = setTimeout(() => DOM.toast.classList.remove('show'), 3500);
  },
};

/* ========== Tabs ========== */
const Tabs = {
  init() {
    $$('.tab').forEach(b => b.addEventListener('click', () => this.switch(b.dataset.tab)));
  },
  switch(tab) {
    State.activeTab = tab;
    $$('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    $$('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${tab}`));
    localStorage.setItem('openprom-active-tab', tab);
    if (tab === 'tasks') Actions.loadTraces();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },
};

/* ========== Animate ========== */
const Animate = {
  number(el, target, dur = 1000) {
    const start = performance.now();
    const from = parseFloat(el.textContent) || 0;
    const diff = target - from;
    function tick(now) {
      const p = Math.min((now - start) / dur, 1);
      const e = 1 - Math.pow(1 - p, 4);
      el.textContent = Math.round(from + diff * e);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  },
  ring(score) {
    const r = 70;
    const c = 2 * Math.PI * r;
    const off = c - (score / 100) * c;
    const el = $('.ring-fg');
    if (el) {
      el.style.strokeDasharray = c;
      setTimeout(() => { el.style.strokeDashoffset = off; }, 300);
    }
  },
};

/* ========== History ========== */
const History = {
  KEY: 'openprom-history', MAX: 50,
  load() {
    try { State.history = JSON.parse(localStorage.getItem(this.KEY)) || []; } catch { State.history = []; }
    this.render();
  },
  save() { localStorage.setItem(this.KEY, JSON.stringify(State.history)); this.render(); },
  add(item) { State.history.unshift(item); if (State.history.length > this.MAX) State.history.pop(); this.save(); },
  clear() {
    if (!State.history.length) return;
    if (!confirm('确定清空所有评鉴记录？')) return;
    State.history = [];
    this.save();
    UI.toast('历史已清空', 'success');
  },
  render() {
    if (!State.history.length) {
      DOM.historyList.innerHTML = '';
      DOM.historyList.appendChild(DOM.historyEmpty.cloneNode(true));
      return;
    }
    DOM.historyList.innerHTML = State.history.map((h, i) => `
      <div class="history-item" data-i="${i}">
        <div class="history-item-score">${h.total_score}</div>
        <div class="history-item-content">
          <div class="history-item-couplet">${escapeHtml(h.upper)} · ${escapeHtml(h.lower)}</div>
          <div class="history-item-meta">${h.grade} · ${new Date(h.time).toLocaleString()}</div>
        </div>
        <span class="history-item-grade">${h.grade}</span>
      </div>`).join('');
    $$('.history-item').forEach(el => {
      el.addEventListener('click', () => {
        const item = State.history[parseInt(el.dataset.i)];
        if (item?.raw) UI.showResult(item.raw);
      });
    });
  },
};

/* ========== Theme ========== */
const Theme = {
  load() {
    const saved = localStorage.getItem('openprom-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', saved || (prefersDark ? 'dark' : 'light'));
  },
  toggle() {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('openprom-theme', next);
  },
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
/* ========== Actions ========== */
const Actions = {
  async analyze() {
    const upper = DOM.upper.value.trim(), lower = DOM.lower.value.trim();
    if (!upper || !lower) { UI.toast('请输入上联和下联', 'warning'); return; }
    if (upper.length !== lower.length) { UI.toast(`字数不等：上联${upper.length}字，下联${lower.length}字`, 'warning'); return; }
    UI.showLoading();
    // 前端按时间模拟阶段反馈（后端为单次调用，无流式进度）
    [600, 1800, 3000].forEach((d, i) => setTimeout(() => UI.setLoadStep(i + 1), d));
    try {
      const result = await API.analyze(upper, lower);
      UI.setLoadStep(3);
      setTimeout(() => UI.showResult(result), 300);
      History.add({ upper, lower, total_score: result.total_score, grade: result.grade, time: Date.now(), raw: result });
    } catch (err) {
      console.error(err);
      UI.showError(`评鉴失败：${err.message}`);
    }
  },

  async generate(stage, type, mode) {
    const prompt = stage.querySelector('.gen-prompt').value.trim();
    if (!prompt) { UI.toast('请输入提示内容', 'warning'); return; }
    const output = stage.querySelector('.gen-output');
    const content = stage.querySelector('.gen-output-content');
    const status = stage.querySelector('.gen-output-status');
    const logBody = stage.querySelector('.gen-log-body');
    output.classList.remove('hidden');
    content.textContent = '';
    status.textContent = '生成中…';
    status.className = 'gen-output-status active';
    if (logBody) logBody.innerHTML = '';

    const body = { prompt };
    if (type === 'couplet') {
      body.length = parseInt(stage.querySelector('.gen-length').value, 10);
    } else {
      body.form = stage.querySelector('.gen-form').value;
      body.tone_preference = stage.querySelector('.gen-tone').value || null;
    }
    const endpoint = `/api/v1/${type}/${mode}`;
    try {
      for await (const ev of API.stream(endpoint, body)) {
        if (ev.event === 'phase') {
          const label = ev.label || ev.phase;
          this.appendLog(logBody, 'phase', `━━ ${label} ━━`);
        } else if (ev.event === 'thinking') {
          const phase = ev.phase ? `[${ev.phase}] ` : '';
          this.appendLog(logBody, 'thinking', `${phase}思考 · 第 ${ev.round || '?'} 轮`);
        } else if (ev.event === 'tool_call') {
          this.appendLog(logBody, 'tool', `→ ${ev.tool}(${JSON.stringify(ev.arguments || {})})`);
        } else if (ev.event === 'tool_result') {
          const r = typeof ev.result === 'string' ? ev.result : JSON.stringify(ev.result || {});
          this.appendLog(logBody, 'tool', `← ${ev.tool}: ${r.slice(0, 200)}`);
        } else if (ev.event === 'done') {
          if (ev.content) content.textContent = ev.content;
        } else if (ev.event === 'final') {
          content.textContent = ev.content || '（无输出）';
          status.textContent = '完成';
          status.className = 'gen-output-status done';
        } else if (ev.event === 'start') {
        } else if (ev.event === 'result') {
          content.textContent = ev.content || JSON.stringify(ev, null, 2);
          status.textContent = '完成';
          status.className = 'gen-output-status done';
        } else if (ev.event === 'error') {
          content.textContent = `错误：${ev.message || '未知错误'}`;
          status.textContent = '失败';
          status.className = 'gen-output-status';
          this.appendLog(logBody, 'error', ev.message || '未知错误');
          break;
        }
      }
      if (!content.textContent) content.textContent = '（无输出）';
    } catch (err) {
      console.error(err);
      content.textContent = `请求失败：${err.message}`;
      status.textContent = '失败';
      status.className = 'gen-output-status';
      UI.toast(`生成失败：${err.message}`, 'error');
    }
  },

  appendLog(body, type, text) {
    if (!body) return;
    const div = document.createElement('div');
    div.className = `log-entry log-entry--${type}`;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  },

  async loadMeterPatterns() {
    const type = DOM.meterType.value;
    if (type === 'couplet') {
      DOM.meterPatternList.innerHTML = '';
      return;
    }
    try {
      const r = await fetch(`/api/v1/meter/list?meter_type=${encodeURIComponent(type)}`);
      if (!r.ok) return;
      const data = await r.json();
      DOM.meterPatternList.innerHTML = (data.patterns || []).map(p => `<option value="${escapeHtml(p)}">`).join('');
    } catch (err) {
      console.error('加载格律模板失败', err);
    }
  },

  async meterCheck() {
    const text = DOM.meterText.value.trim();
    if (!text) { UI.toast('请输入待检测文本', 'warning'); return; }
    DOM.meterOutput.classList.remove('hidden');
    DOM.meterBody.innerHTML = '<p style="color:var(--text-3);font-size:.9rem;">检测中…</p>';
    DOM.meterComplianceTag.textContent = '';
    DOM.meterComplianceTag.className = 'compliance-tag';
    try {
      const r = await API.meterCheck(text, DOM.meterType.value, DOM.meterPattern.value);
      this.renderMeter(r);
    } catch (err) {
      DOM.meterBody.innerHTML = `<p style="color:var(--vermilion);">请求失败：${escapeHtml(err.message)}</p>`;
    }
  },

  renderMeter(r) {
    const ok = r.is_compliant;
    DOM.meterComplianceTag.textContent = ok ? '合规' : '不合规';
    DOM.meterComplianceTag.className = `compliance-tag ${ok ? 'ok' : 'bad'}`;
    DOM.meterBody.innerHTML = '';

    // 平仄序列结构化展示
    if (r.tone_details && r.tone_details.length) {
      const sec = document.createElement('div');
      sec.className = 'meter-section';
      sec.innerHTML = '<h4>平仄逐字</h4>';
      const lines = document.createElement('div');
      lines.className = 'meter-pattern';
      r.tone_details.forEach((line, li) => {
        const row = document.createElement('div');
        line.forEach(t => {
          const sp = document.createElement('span');
          sp.className = 'meter-char';
          if (t.tone === 1) sp.classList.add('ping');
          else if (t.tone === -1) sp.classList.add('ze');
          else sp.classList.add('zhong');
          sp.textContent = t.char || '？';
          if (t.violation) sp.classList.add('bad');
          row.appendChild(sp);
        });
        lines.appendChild(row);
      });
      sec.appendChild(lines);
      DOM.meterBody.appendChild(sec);
    }

    // 违规列表
    if (r.violations && r.violations.length) {
      const sec = document.createElement('div');
      sec.className = 'meter-section';
      sec.innerHTML = '<h4>违规项</h4>';
      const ul = document.createElement('ul');
      ul.className = 'meter-violations';
      r.violations.forEach(v => { const li = document.createElement('li'); li.textContent = v; ul.appendChild(li); });
      sec.appendChild(ul);
      DOM.meterBody.appendChild(sec);
    }

    // 匹配格律
    if (r.matched_meters && r.matched_meters.length) {
      const sec = document.createElement('div');
      sec.className = 'meter-section';
      sec.innerHTML = '<h4>匹配格律</h4>';
      const list = document.createElement('div');
      r.matched_meters.forEach(m => {
        const d = document.createElement('div');
        d.style.cssText = 'padding:6px 0;border-bottom:1px dashed var(--border-soft);font-size:.88rem;';
        d.innerHTML = `<b style="color:var(--vermilion);">${escapeHtml(m.name || '')}</b> · 匹配率 ${(m.match_rate * 100 || 0).toFixed(0)}%`;
        list.appendChild(d);
      });
      sec.appendChild(list);
      DOM.meterBody.appendChild(sec);
    }

    // 韵字建议
    if (r.rhyme_suggestions && r.rhyme_suggestions.length) {
      const sec = document.createElement('div');
      sec.className = 'meter-section';
      sec.innerHTML = '<h4>押韵候选</h4>';
      const d = document.createElement('div');
      d.className = 'meter-pattern';
      d.textContent = r.rhyme_suggestions.join(' · ');
      sec.appendChild(d);
      DOM.meterBody.appendChild(sec);
    }

    // 元信息
    const meta = document.createElement('div');
    meta.className = 'meter-meta';
    meta.innerHTML = `
      <div class="meter-meta-item"><span>类型</span><strong>${escapeHtml(r.meter_type)}</strong></div>
      <div class="meter-meta-item"><span>合规</span><strong>${ok ? '是' : '否'}</strong></div>`;
    DOM.meterBody.appendChild(meta);
  },

  async knowledgeSearch() {
    const q = DOM.knowledgeQuery.value.trim();
    if (!q) { UI.toast('请输入检索词', 'warning'); return; }
    DOM.knowledgeOutput.classList.remove('hidden');
    DOM.knowledgeList.innerHTML = '<p style="color:var(--text-3);padding:var(--sp-4);">检索中…</p>';
    DOM.knowledgeMeta.textContent = '';
    try {
      const r = await API.knowledgeSearch(q, parseInt(DOM.knowledgeTopK.value, 10), DOM.knowledgeTaskType.value || null);
      const total = r.total_candidates ?? 0;
      const cnt = r.results?.length ?? 0;
      const latency = r.latency_ms ?? '—';
      const stages = r.pipeline_stages?.join(' → ') || '召回 → 融合 → 重排';
      DOM.knowledgeMeta.innerHTML = `候选 <b>${total}</b> · 返回 <b>${cnt}</b> · 耗时 <b>${latency}ms</b> · 流水线：${stages}`;
      if (!r.results.length) {
        DOM.knowledgeList.innerHTML = '<p style="color:var(--text-3);padding:var(--sp-4);">无匹配结果。知识层可能未启用或语料为空。</p>';
        return;
      }
      DOM.knowledgeList.innerHTML = r.results.map(h => `
        <article class="knowledge-item">
          <div class="ki-head">
            <span class="ki-score">${(h.final_score * 100).toFixed(1)}</span>
            <span class="ki-type">${escapeHtml(h.chunk_type)}</span>
          </div>
          <div class="ki-content">${escapeHtml(h.content)}</div>
          ${h.annotated ? `<div class="ki-content" style="font-size:.85rem;color:var(--text-2);">${escapeHtml(h.annotated)}</div>` : ''}
          <div class="ki-prov">
            ${h.provenance?.title ? `<span>《${escapeHtml(h.provenance.title)}》</span>` : ''}
            ${h.provenance?.author ? `<span>${escapeHtml(h.provenance.author)}</span>` : ''}
            ${h.provenance?.dynasty ? `<span>${escapeHtml(h.provenance.dynasty)}</span>` : ''}
            <span>语义 ${(h.semantic_score * 100).toFixed(0)}%</span>
            ${h.rerank_score != null ? `<span>重排 ${(h.rerank_score * 100).toFixed(0)}%</span>` : ''}
          </div>
        </article>`).join('');
    } catch (err) {
      DOM.knowledgeList.innerHTML = `<p style="color:var(--vermilion);padding:var(--sp-4);">检索失败：${escapeHtml(err.message)}</p>`;
    }
  },

  async loadTraces() {
    DOM.traceList.innerHTML = '<p style="color:var(--text-3);padding:var(--sp-4);">加载中…</p>';
    try {
      const rows = await API.listTraces(20);
      if (!rows?.length) {
        DOM.traceList.innerHTML = '';
        DOM.traceList.appendChild(DOM.traceEmpty.cloneNode(true));
        return;
      }
      DOM.traceList.innerHTML = rows.map(r => `
        <div class="trace-item">
          <div class="trace-head">
            <span class="trace-name">${escapeHtml(r.task_name)}</span>
            <span class="trace-status ${r.success ? 'ok' : 'fail'}">${r.success ? '成功' : '失败'}</span>
          </div>
          <div class="trace-meta">
            <span><b>耗时</b> ${r.total_duration_ms.toFixed(0)}ms</span>
            <span><b>LLM</b> ${r.llm_calls}</span>
            <span><b>工具</b> ${r.tool_calls}</span>
            <span><b>RAG</b> ${r.rag_calls}</span>
            ${r.finished_at ? `<span><b>完成</b> ${escapeHtml(r.finished_at)}</span>` : ''}
          </div>
          ${r.error ? `<div style="color:var(--vermilion);font-size:.8rem;margin-top:6px;">${escapeHtml(r.error)}</div>` : ''}
          <div class="trace-id">${escapeHtml(r.task_id)}</div>
        </div>`).join('');
    } catch (err) {
      DOM.traceList.innerHTML = `<p style="color:var(--vermilion);padding:var(--sp-4);">加载失败：${escapeHtml(err.message)}</p>`;
    }
  },

  reset() {
    DOM.upper.value = '';
    DOM.lower.value = '';
    UI.updateInputMeta();
    State.set('idle');
    UI.syncVisibility();
    DOM.scoreInput.scrollIntoView({ behavior: 'smooth' });
  },

  share() {
    const r = State.result;
    if (!r) return;
    const text = `【OpenPROM 评鉴】\n上联：${r.upper}\n下联：${r.lower}\n总分：${r.total_score}分（${r.grade}）\n\n来自 OpenPROM`;
    if (navigator.share) navigator.share({ title: '对联评鉴', text }).catch(() => {});
    else navigator.clipboard.writeText(text).then(() => UI.toast('已复制到剪贴板', 'success'));
  },

  save() {
    const r = State.result;
    if (!r) return;
    History.add({ upper: r.upper, lower: r.lower, total_score: r.total_score, grade: r.grade, time: Date.now(), raw: r });
    UI.toast('已保存到轨迹', 'success');
  },

  fillExample() {
    const ex = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
    DOM.upper.value = ex.upper;
    DOM.lower.value = ex.lower;
    UI.updateInputMeta();
    UI.toast('已填入示例', 'info');
  },
};

/* ========== Boot ========== */
document.addEventListener('DOMContentLoaded', () => UI.init());