// HRMD Resume Health Check — Frontend Logic

(function () {
  'use strict';

  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileInfo = document.getElementById('file-info');
  const fileName = document.getElementById('file-name');
  const fileRemove = document.getElementById('file-remove');
  const analyzeBtn = document.getElementById('analyze-btn');
  const loading = document.getElementById('loading');
  const errorSection = document.getElementById('error-section');
  const errorMsg = document.getElementById('error-msg');
  const results = document.getElementById('results');

  let selectedFile = null;
  let lastAnalysisData = null;

  // --- Drag & Drop ---
  dropZone.addEventListener('dragover', function (e) {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', function () {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', function (e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  });

  dropZone.addEventListener('click', function () {
    fileInput.click();
  });

  fileInput.addEventListener('change', function () {
    if (fileInput.files.length > 0) {
      handleFile(fileInput.files[0]);
    }
  });

  fileRemove.addEventListener('click', function (e) {
    e.stopPropagation();
    clearFile();
  });

  analyzeBtn.addEventListener('click', function () {
    if (selectedFile) {
      analyze(selectedFile);
    }
  });

  function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showError('請上傳 PDF 格式的履歷檔案');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showError('檔案大小超過 10MB 限制');
      return;
    }
    selectedFile = file;
    fileName.textContent = file.name + ' (' + formatSize(file.size) + ')';
    fileInfo.style.display = 'flex';
    analyzeBtn.disabled = false;
    dropZone.style.display = 'none';
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.style.display = 'none';
    analyzeBtn.disabled = true;
    dropZone.style.display = 'block';
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  // --- API Call ---
  async function analyze(file) {
    showLoading();

    const formData = new FormData();
    formData.append('resume', file);

    try {
      const response = await fetch('https://railway-up-production-3d15.up.railway.app/api/analyze', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        showError(data.error || '伺服器錯誤，請稍後再試');
        return;
      }

      lastAnalysisData = data;
      renderResults(data);
    } catch (err) {
      showError('無法連接伺服器，請檢查網路連線後再試。錯誤: ' + err.message);
    }
  }

  function showLoading() {
    hideAll();
    loading.style.display = 'block';
  }

  function showError(msg) {
    hideAll();
    errorMsg.textContent = msg;
    errorSection.style.display = 'block';
  }

  function hideAll() {
    loading.style.display = 'none';
    errorSection.style.display = 'none';
    results.style.display = 'none';
  }

  window.resetUI = function () {
    hideAll();
    clearFile();
    document.querySelector('.upload-section').style.display = 'block';
    document.getElementById('user-name').value = '';
    document.getElementById('user-email').value = '';
    lastAnalysisData = null;
  };

  // --- Render Results ---
  function renderResults(data) {
    hideAll();
    document.querySelector('.upload-section').style.display = 'none';

    const c = data.candidate;
    document.getElementById('result-name').textContent = c.name || '(未擷取到姓名)';
    document.getElementById('result-age').textContent = c.age ? c.age + '歲' : '';
    document.getElementById('result-edu').textContent = c.education || '';
    document.getElementById('result-seniority').textContent = c.seniority ? '年資 ' + c.seniority + ' 年' : '';
    document.getElementById('result-lang').textContent = c.language_skills || '(未擷取)';
    document.getElementById('result-work').textContent = c.recent_work || '(未擷取)';

    const descRow = document.getElementById('result-desc-row');
    if (c.recent_work_desc) {
      document.getElementById('result-desc').textContent = c.recent_work_desc;
      descRow.style.display = 'flex';
    } else {
      descRow.style.display = 'none';
    }

    const prevRow = document.getElementById('result-prev-row');
    if (c.prev_companies) {
      document.getElementById('result-prev').textContent = c.prev_companies;
      prevRow.style.display = 'flex';
    } else {
      prevRow.style.display = 'none';
    }

    renderGeneralScore(data.general_score);
    renderBimScore(data.bim_score);

    results.style.display = 'block';
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });

    setTimeout(() => {
      const buttonContainer = document.createElement('div');
      buttonContainer.style.cssText = 'text-align: center; margin-top: 30px;';

      const confirmBtn = document.createElement('button');
      confirmBtn.textContent = '確定';
      confirmBtn.style.cssText = `
        padding: 12px 40px;
        background: #3498db;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
        font-weight: 600;
      `;
      confirmBtn.onclick = () => {
        resetUI();
      };

      buttonContainer.appendChild(confirmBtn);

      const contactInfo = document.createElement('p');
      contactInfo.style.cssText = 'margin-top: 20px; font-size: 14px; color: #666; line-height: 1.6;';
      contactInfo.innerHTML = '如果你對於自己的分數有信心，<br>歡迎寄履歷到 <strong>shuotao.chiang@ctci.com</strong>';
      buttonContainer.appendChild(contactInfo);

      results.appendChild(buttonContainer);
    }, 500);
  }

  function renderGeneralScore(gs) {
    const gauge = document.getElementById('general-gauge');
    const value = document.getElementById('general-value');
    const label = document.getElementById('general-label');
    const reasonsDiv = document.getElementById('general-reasons');

    let level, labelText;
    if (gs.excluded) {
      level = 'excluded';
      labelText = '不符合條件 (排除)';
    } else if (gs.passed) {
      if (gs.score >= 60) { level = 'excellent'; labelText = '優秀候選人'; }
      else if (gs.score >= 40) { level = 'good'; labelText = '合格候選人'; }
      else { level = 'partial'; labelText = '達標 (門檻' + gs.threshold + '分)'; }
    } else {
      level = 'low';
      labelText = '未達門檻 (' + gs.threshold + '分)';
    }

    const pct = Math.min(gs.score, 100);
    gauge.className = 'gauge ' + level;
    gauge.style.setProperty('--pct', (pct * 3.6) + 'deg');
    value.textContent = gs.score;
    label.className = 'gauge-label ' + level;
    label.textContent = labelText;

    reasonsDiv.innerHTML = '';
    (gs.reasons || []).forEach(function (r) {
      const div = document.createElement('div');
      div.className = 'reason-item';
      if (r.startsWith('排除')) div.className += ' exclude';
      else if (r.startsWith('N') || r.startsWith('M')) div.className += ' positive';
      else if (r.includes('降階') || r.includes('防呆') || r.includes('-')) div.className += ' negative';
      else div.className += ' neutral';
      div.textContent = r;
      reasonsDiv.appendChild(div);
    });
  }

  function renderBimScore(bs) {
    const gauge = document.getElementById('bim-gauge');
    const value = document.getElementById('bim-value');
    const label = document.getElementById('bim-label');
    const breakdown = document.getElementById('bim-breakdown');
    const rec = document.getElementById('bim-recommendation');

    const pct = bs.match_percentage;
    const level = bs.level;

    gauge.className = 'gauge ' + level;
    gauge.style.setProperty('--pct', (pct * 3.6) + 'deg');
    value.textContent = pct + '%';
    label.className = 'gauge-label ' + level;

    const levelLabels = {
      excellent: '強力推薦',
      good: '建議面試',
      partial: '部分符合',
      low: '差距較大',
    };
    label.textContent = levelLabels[level] || '';

    breakdown.innerHTML = '';
    const dimNames = {
      education_match: '學歷對口',
      bim_experience: 'BIM 經驗',
      english_proficiency: '英語能力',
      engineering_skills: '工程專業',
      management_level: '管理層級',
    };

    const order = ['education_match', 'bim_experience', 'english_proficiency', 'engineering_skills', 'management_level'];
    order.forEach(function (key) {
      const dim = bs.details[key];
      if (!dim) return;

      const dimDiv = document.createElement('div');
      dimDiv.className = 'bim-dim';

      const fillPct = dim.max > 0 ? (dim.score / dim.max * 100) : 0;
      let barLevel = 'low';
      if (fillPct >= 80) barLevel = 'excellent';
      else if (fillPct >= 60) barLevel = 'good';
      else if (fillPct >= 40) barLevel = 'partial';

      dimDiv.innerHTML =
        '<div class="bim-dim-header">' +
          '<span class="bim-dim-name">' + (dimNames[key] || key) + '</span>' +
          '<span class="bim-dim-score">' + dim.score + ' / ' + dim.max + '</span>' +
        '</div>' +
        '<div class="bim-bar">' +
          '<div class="bim-bar-fill ' + barLevel + '" style="width: ' + fillPct + '%"></div>' +
        '</div>' +
        '<div class="bim-dim-reason">' + dim.reason + '</div>';

      breakdown.appendChild(dimDiv);
    });

    rec.className = 'recommendation ' + level;
    rec.textContent = bs.recommendation;
  }

  // --- Job Description Toggle ---
  window.toggleJobDesc = function () {
    const desc = document.getElementById('job-full-desc');
    const text = document.getElementById('toggle-text');
    const arrow = document.getElementById('toggle-arrow');
    desc.classList.toggle('show');
    if (desc.classList.contains('show')) {
      text.textContent = '收起職務說明';
      arrow.innerHTML = '&#9650;';
    } else {
      text.textContent = '展開完整職務說明';
      arrow.innerHTML = '&#9660;';
    }
  };
})();
