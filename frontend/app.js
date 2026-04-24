/**
 * PORM - 对联评鉴系统
 * 前端应用逻辑
 */

// API 配置
const API_BASE_URL = window.location.origin;
const API_ENDPOINT = '/api/v1/couplet/analyze';

// DOM 元素
const elements = {
  upper: document.getElementById('upper'),
  lower: document.getElementById('lower'),
  analyzeBtn: document.getElementById('analyzeBtn'),
  loadingSection: document.getElementById('loadingSection'),
  resultSection: document.getElementById('resultSection'),
  inputSection: document.querySelector('.input-section'),
  totalScore: document.getElementById('totalScore'),
  gradeBadge: document.getElementById('gradeBadge'),
  resultUpper: document.getElementById('resultUpper'),
  resultLower: document.getElementById('resultLower'),
  formalScore: document.getElementById('formalScore'),
  techniqueScore: document.getElementById('techniqueScore'),
  artisticScore: document.getElementById('artisticScore'),
  impressionScore: document.getElementById('impressionScore'),
  pingzeScore: document.getElementById('pingzeScore'),
  formalBar: document.getElementById('formalBar'),
  techniqueBar: document.getElementById('techniqueBar'),
  artisticBar: document.getElementById('artisticBar'),
  impressionBar: document.getElementById('impressionBar'),
  impressionReason: document.getElementById('impressionReason'),
  techniqueComment: document.getElementById('techniqueComment'),
  artisticComment: document.getElementById('artisticComment'),
  warningsCard: document.getElementById('warningsCard'),
  warningsList: document.getElementById('warningsList'),
  newAnalysisBtn: document.getElementById('newAnalysisBtn'),
  shareBtn: document.getElementById('shareBtn'),
  toast: document.getElementById('toast'),
  scoreProgress: document.querySelector('.score-progress')
};

// 状态
let currentResult = null;

// 初始化
function init() {
  bindEvents();
}

// 绑定事件
function bindEvents() {
  elements.analyzeBtn.addEventListener('click', handleAnalyze);
  elements.newAnalysisBtn.addEventListener('click', handleNewAnalysis);
  elements.shareBtn.addEventListener('click', handleShare);
  
  // 回车提交
  elements.upper.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      elements.lower.focus();
    }
  });
  
  elements.lower.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAnalyze();
    }
  });
}

// 处理分析
async function handleAnalyze() {
  const upper = elements.upper.value.trim();
  const lower = elements.lower.value.trim();
  
  if (!upper || !lower) {
    showToast('请输入上联和下联');
    return;
  }
  
  if (upper.length !== lower.length) {
    showToast(`上下联字数不等：上联${upper.length}字，下联${lower.length}字`);
    return;
  }
  
  // 显示加载状态
  showLoading();
  
  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        upper: upper,
        lower: lower,
        stream: false
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '评鉴失败');
    }
    
    const result = await response.json();
    currentResult = result;
    
    // 显示结果
    showResult(result);
    
  } catch (error) {
    console.error('评鉴失败:', error);
    showToast(`评鉴失败：${error.message}`);
    hideLoading();
  }
}

// 显示加载状态
function showLoading() {
  elements.inputSection.classList.add('hidden');
  elements.resultSection.classList.add('hidden');
  elements.loadingSection.classList.remove('hidden');
  
  // 重置动画
  const steps = document.querySelectorAll('.loading-step');
  steps.forEach(step => {
    step.style.animation = 'none';
    step.offsetHeight; // 触发重绘
    step.style.animation = null;
  });
}

// 隐藏加载状态
function hideLoading() {
  elements.loadingSection.classList.add('hidden');
  elements.inputSection.classList.remove('hidden');
}

// 显示结果
function showResult(result) {
  elements.loadingSection.classList.add('hidden');
  elements.resultSection.classList.remove('hidden');
  
  // 更新总分
  animateScore(elements.totalScore, result.total_score);
  updateScoreCircle(result.total_score);
  
  // 更新等级
  elements.gradeBadge.textContent = result.grade;
  updateGradeBadge(result.grade);
  
  // 更新对联
  elements.resultUpper.textContent = result.upper;
  elements.resultLower.textContent = result.lower;
  
  // 更新各维度分数
  updateDimensionScore('formal', result.formal_score * 100);
  updateDimensionScore('technique', result.technique_score * 100);
  updateDimensionScore('artistic', result.artistic_score * 100);
  updateDimensionScore('impression', result.impression_score * 100);
  
  // 更新平仄分数
  elements.pingzeScore.textContent = (result.pingze_score * 100).toFixed(0);
  
  // 更新评语
  elements.impressionReason.textContent = result.comments?.impression_comment || '暂无 AI 印象';
  elements.techniqueComment.textContent = result.comments?.technique_comment || '暂无技法点评';
  elements.artisticComment.textContent = result.comments?.artistic_comment || '暂无艺术赏析';
  
  // 更新注意事项
  if (result.warnings && result.warnings.length > 0) {
    elements.warningsCard.classList.remove('hidden');
    elements.warningsList.innerHTML = result.warnings
      .map(w => `<li>${w}</li>`)
      .join('');
  } else {
    elements.warningsCard.classList.add('hidden');
  }
}

// 更新维度分数
function updateDimensionScore(type, score) {
  const scoreEl = elements[`${type}Score`];
  const barEl = elements[`${type}Bar`];
  
  if (scoreEl) {
    animateScore(scoreEl, score);
  }
  
  if (barEl) {
    setTimeout(() => {
      barEl.style.width = `${Math.min(score, 100)}%`;
    }, 300);
  }
}

// 分数动画
function animateScore(element, targetValue) {
  const duration = 1000;
  const startValue = 0;
  const startTime = performance.now();
  
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // Ease out quart
    const ease = 1 - Math.pow(1 - progress, 4);
    
    const currentValue = startValue + (targetValue - startValue) * ease;
    element.textContent = Math.round(currentValue);
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

// 更新分数圆环
function updateScoreCircle(score) {
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;
  
  setTimeout(() => {
    elements.scoreProgress.style.strokeDashoffset = offset;
  }, 300);
}

// 更新等级徽章
function updateGradeBadge(grade) {
  const colors = {
    '优秀': 'linear-gradient(135deg, #4a9c6e 0%, #6ec98e 100%)',
    '良好': 'linear-gradient(135deg, #5b8db8 0%, #7da8d4 100%)',
    '及格': 'linear-gradient(135deg, #d4a04a 0%, #e8b96a 100%)',
    '不合格': 'linear-gradient(135deg, #c43c3c 0%, #e05656 100%)'
  };
  
  elements.gradeBadge.style.background = colors[grade] || colors['不合格'];
}

// 处理新的评鉴
function handleNewAnalysis() {
  elements.upper.value = '';
  elements.lower.value = '';
  elements.resultSection.classList.add('hidden');
  elements.inputSection.classList.remove('hidden');
  elements.upper.focus();
}

// 处理分享
async function handleShare() {
  if (!currentResult) return;
  
  const shareText = `【对联评鉴】
上联：${currentResult.upper}
下联：${currentResult.lower}
总分：${currentResult.total_score}分 (${currentResult.grade})

来自 PORM 对联评鉴系统`;
  
  try {
    if (navigator.share) {
      await navigator.share({
        title: '对联评鉴结果',
        text: shareText
      });
    } else {
      await navigator.clipboard.writeText(shareText);
      showToast('结果已复制到剪贴板');
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('分享失败:', error);
      showToast('分享失败');
    }
  }
}

// 显示 Toast
function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add('show');
  
  setTimeout(() => {
    elements.toast.classList.remove('show');
  }, 3000);
}

// 启动应用
init();
