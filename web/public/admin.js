// HRMD Admin Dashboard

(function () {
  'use strict';

  const ADMIN_EMAILS = ['codefortaiwan.com@gmail.com', 'shuotao.as@gmail.com'];

  const authSection = document.getElementById('auth-section');
  const dashboardSection = document.getElementById('dashboard-section');
  const googleLoginBtn = document.getElementById('google-login-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const userEmail = document.getElementById('user-email');
  const candidatesTbody = document.getElementById('candidates-tbody');
  const loading = document.getElementById('loading');
  const noData = document.getElementById('no-data');
  const permissionDenied = document.getElementById('permission-denied');
  const searchInput = document.getElementById('search-input');
  const sortBy = document.getElementById('sort-by');
  const detailModal = document.getElementById('detail-modal');
  const closeBtn = document.querySelector('.close-btn');

  let allCandidates = [];
  let currentUser = null;

  // Google Login
  googleLoginBtn.addEventListener('click', async function () {
    const provider = new firebase.auth.GoogleAuthProvider();
    try {
      await firebase.auth().signInWithPopup(provider);
    } catch (err) {
      try {
        await firebase.auth().signInWithRedirect(provider);
      } catch (err2) {
        alert('登入失敗: ' + err2.message);
      }
    }
  });

  // Logout
  logoutBtn.addEventListener('click', function () {
    firebase.auth().signOut();
  });

  // Close Modal
  closeBtn.addEventListener('click', function () {
    detailModal.style.display = 'none';
  });

  window.addEventListener('click', function (e) {
    if (e.target === detailModal) {
      detailModal.style.display = 'none';
    }
  });

  // Search and Sort
  searchInput.addEventListener('input', renderCandidates);
  sortBy.addEventListener('change', renderCandidates);

  // Auth State Changed
  firebase.auth().onAuthStateChanged(function (user) {
    if (user) {
      currentUser = user;
      userEmail.textContent = user.email;

      if (ADMIN_EMAILS.includes(user.email)) {
        authSection.style.display = 'none';
        dashboardSection.style.display = 'block';
        permissionDenied.style.display = 'none';
        loadCandidates();
      } else {
        authSection.style.display = 'none';
        dashboardSection.style.display = 'block';
        permissionDenied.style.display = 'block';
        candidatesTbody.innerHTML = '';
        setTimeout(() => {
          firebase.auth().signOut();
        }, 3000);
      }
    } else {
      currentUser = null;
      authSection.style.display = 'block';
      dashboardSection.style.display = 'none';
      allCandidates = [];
    }
  });

  function loadCandidates() {
    loading.style.display = 'block';
    candidatesTbody.innerHTML = '';
    noData.style.display = 'none';

    const db = firebase.firestore();
    db.collection('candidates')
      .orderBy('sequence', 'desc')
      .get()
      .then(snapshot => {
        allCandidates = [];
        snapshot.forEach(doc => {
          allCandidates.push({
            id: doc.id,
            ...doc.data()
          });
        });
        loading.style.display = 'none';
        renderCandidates();
      })
      .catch(err => {
        loading.style.display = 'none';
        alert('載入失敗: ' + err.message);
      });
  }

  function renderCandidates() {
    let filtered = allCandidates;

    // Search
    const search = searchInput.value.toLowerCase();
    if (search) {
      filtered = filtered.filter(c =>
        c.email.toLowerCase().includes(search) ||
        (c.name && c.name.toLowerCase().includes(search))
      );
    }

    // Sort
    const sortValue = sortBy.value;
    filtered = filtered.sort((a, b) => {
      if (sortValue === 'sequence-desc') return (b.sequence || 0) - (a.sequence || 0);
      if (sortValue === 'sequence-asc') return (a.sequence || 0) - (b.sequence || 0);
      if (sortValue === 'upload-desc') return (b.uploadCount || 0) - (a.uploadCount || 0);
      if (sortValue === 'lastupload-desc') {
        const aTime = a.lastUploadTime ? a.lastUploadTime.toMillis() : 0;
        const bTime = b.lastUploadTime ? b.lastUploadTime.toMillis() : 0;
        return bTime - aTime;
      }
      return 0;
    });

    candidatesTbody.innerHTML = '';
    if (filtered.length === 0) {
      noData.style.display = 'block';
      return;
    }

    filtered.forEach(candidate => {
      const row = document.createElement('tr');
      const generalScore = candidate.generalScore || {};
      const bimScore = candidate.bimScore || {};
      const lastUpload = candidate.lastUploadTime
        ? new Date(candidate.lastUploadTime.toMillis()).toLocaleDateString('zh-TW')
        : '—';

      row.innerHTML = `
        <td>${candidate.sequence || '—'}</td>
        <td>${candidate.name || '—'}</td>
        <td>${candidate.email}</td>
        <td>${candidate.uploadCount || 0}</td>
        <td><strong>${generalScore.score || 0}</strong></td>
        <td>${bimScore.match_percentage || 0}%</td>
        <td>${lastUpload}</td>
        <td><button class="detail-btn" onclick="showDetail('${candidate.id}')">檢視</button></td>
      `;
      candidatesTbody.appendChild(row);
    });
  }

  window.showDetail = function (candidateId) {
    const candidate = allCandidates.find(c => c.id === candidateId);
    if (!candidate) return;

    const generalScore = candidate.generalScore || {};
    const bimScore = candidate.bimScore || {};
    const bimDetails = bimScore.details || {};

    let detailHtml = `
      <div class="detail-info">
        <div class="info-row"><strong>姓名：</strong> ${candidate.name || '—'}</div>
        <div class="info-row"><strong>Email：</strong> ${candidate.email}</div>
        <div class="info-row"><strong>序號：</strong> ${candidate.sequence || '—'}</div>
        <div class="info-row"><strong>上傳次數：</strong> ${candidate.uploadCount || 0}</div>

        <hr>
        <h3>通用工程人才評分</h3>
        <div class="info-row"><strong>評分：</strong> ${generalScore.score || 0}</div>
        <div class="info-row"><strong>狀態：</strong> ${generalScore.passed ? '合格' : '未達門檻'} ${generalScore.excluded ? '（排除）' : ''}</div>
        <div class="info-row"><strong>門檻：</strong> ${generalScore.threshold || '—'}</div>
        ${(generalScore.reasons || []).length > 0 ? `
        <div class="info-row">
          <strong>評分理由：</strong>
          <ul>
            ${generalScore.reasons.map(r => `<li>${r}</li>`).join('')}
          </ul>
        </div>
        ` : ''}

        <hr>
        <h3>BIM 主任職缺適配度</h3>
        <div class="info-row"><strong>匹配度：</strong> ${bimScore.match_percentage || 0}%</div>
        <div class="info-row"><strong>評等：</strong> ${bimScore.level || '—'}</div>
        <div class="info-row"><strong>建議：</strong> ${bimScore.recommendation || '—'}</div>

        ${Object.keys(bimDetails).length > 0 ? `
        <div class="info-row">
          <strong>各維度評分：</strong>
          <table class="detail-table">
            <tr>
              <td>學歷對口</td>
              <td>${bimDetails.education_match?.score || 0} / ${bimDetails.education_match?.max || 0}</td>
              <td>${bimDetails.education_match?.reason || ''}</td>
            </tr>
            <tr>
              <td>BIM 經驗</td>
              <td>${bimDetails.bim_experience?.score || 0} / ${bimDetails.bim_experience?.max || 0}</td>
              <td>${bimDetails.bim_experience?.reason || ''}</td>
            </tr>
            <tr>
              <td>英語能力</td>
              <td>${bimDetails.english_proficiency?.score || 0} / ${bimDetails.english_proficiency?.max || 0}</td>
              <td>${bimDetails.english_proficiency?.reason || ''}</td>
            </tr>
            <tr>
              <td>工程專業</td>
              <td>${bimDetails.engineering_skills?.score || 0} / ${bimDetails.engineering_skills?.max || 0}</td>
              <td>${bimDetails.engineering_skills?.reason || ''}</td>
            </tr>
            <tr>
              <td>管理層級</td>
              <td>${bimDetails.management_level?.score || 0} / ${bimDetails.management_level?.max || 0}</td>
              <td>${bimDetails.management_level?.reason || ''}</td>
            </tr>
          </table>
        </div>
        ` : ''}
      </div>
    `;

    document.getElementById('modal-body').innerHTML = detailHtml;
    document.getElementById('modal-title').textContent = `${candidate.name || 'N/A'} - 詳細評分`;
    detailModal.style.display = 'block';
  };
})();
