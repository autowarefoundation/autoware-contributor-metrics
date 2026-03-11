// =============================================================================
// Theme Management
// =============================================================================

const THEME_ICONS = {
  system: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
  light: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
  dark: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
};

function getThemePreference() {
  return localStorage.getItem('theme-preference') || 'system';
}

function getEffectiveTheme() {
  const pref = getThemePreference();
  if (pref === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return pref;
}

function applyTheme() {
  document.documentElement.setAttribute('data-theme', getEffectiveTheme());
  updateThemeToggle();
}

function updateThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const pref = getThemePreference();
  btn.innerHTML = THEME_ICONS[pref];
  const labels = { system: 'System theme', light: 'Light theme', dark: 'Dark theme' };
  btn.setAttribute('aria-label', labels[pref]);
  btn.setAttribute('title', labels[pref]);
}

function cycleTheme() {
  const order = ['system', 'light', 'dark'];
  const current = getThemePreference();
  const next = order[(order.indexOf(current) + 1) % order.length];
  localStorage.setItem('theme-preference', next);
  applyTheme();
}

// Listen for system preference changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (getThemePreference() === 'system') {
    applyTheme();
  }
});

// Set up toggle button
document.getElementById('theme-toggle')?.addEventListener('click', cycleTheme);
applyTheme();

// =============================================================================
// Constants
// =============================================================================

const COLORS = {
  stars: [
    '#00D9FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3', '#F38181',
    '#A8E6CF', '#DDA0DD', '#87CEEB', '#F0E68C', '#E6E6FA', '#FFA07A',
    '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8B500', '#7DCEA0',
    '#F1948A', '#AED6F1', '#D7BDE2', '#A3E4D7', '#FAD7A0', '#D5DBDB',
    '#ABEBC6', '#F9E79F',
  ],
  contributors: ['#00D9FF', '#FF6B6B', '#4ECDC4'],
};

const COLOR_CLASSES = ['cyan', 'coral', 'teal', 'gold'];

let REPOSITORIES = [];

// =============================================================================
// Utility Functions
// =============================================================================

function getLastEntry(array) {
  return array.length > 0 ? array[array.length - 1] : null;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatNumber(val) {
  return Math.round(val).toLocaleString();
}

function rankPrefix(rank) {
  return rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}.`;
}

function getRepoStarsSorted(json) {
  return REPOSITORIES
    .filter(repo => json[`${repo}_stars_history`])
    .map(repo => {
      const lastEntry = getLastEntry(json[`${repo}_stars_history`]);
      return { repo, starCount: lastEntry ? lastEntry.star_count : 0 };
    })
    .sort((a, b) => b.starCount - a.starCount);
}

function mapToChartData(dataArray, valueKey) {
  return dataArray.map((item) => [new Date(item.date), item[valueKey]]);
}

function getChartHeight(base) {
  if (window.innerWidth < 768) return Math.min(base, 300);
  if (window.innerWidth < 1200) return Math.min(base, 350);
  return base;
}

function isMobile() {
  return window.innerWidth < 768;
}

// =============================================================================
// Chart Configuration
// =============================================================================

function createChartOptions({ series, title, yAxisTitle, colors, showLegend = false, height = 400 }) {
  return {
    series,
    chart: {
      height: getChartHeight(height),
      type: 'line',
      zoom: { enabled: true },
      selection: { enabled: true },
      background: 'transparent',
    },
    dataLabels: { enabled: false },
    title: {
      text: title,
      align: 'left',
      style: {
        fontSize: '16px',
        fontFamily: 'Outfit, sans-serif',
        fontWeight: 600,
      },
    },
    grid: {
      row: { opacity: 0 },
    },
    xaxis: { type: 'datetime' },
    yaxis: {
      min: 0,
      title: { text: yAxisTitle },
      labels: { formatter: formatNumber },
    },
    tooltip: {
      theme: 'dark',
      y: { formatter: formatNumber },
    },
    stroke: {
      width: 2,
      curve: 'smooth',
    },
    colors,
    ...(showLegend && {
      legend: {
        position: 'bottom',
        horizontalAlign: 'center',
        fontSize: '12px',
        fontFamily: 'Outfit, sans-serif',
        markers: { width: 10, height: 10, radius: 3 },
      },
    }),
  };
}

// =============================================================================
// Stats Display (Card-based)
// =============================================================================

function renderMetricCards(containerId, cards) {
  const container = document.getElementById(containerId);
  container.innerHTML = cards.map(card => card).join('');
}

function createMetricCard(label, value, colorClass, sub) {
  return `
    <div class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value ${colorClass}">${formatNumber(value)}</div>
      ${sub ? `<div class="metric-sub">${sub}</div>` : ''}
    </div>
  `;
}

function showError(selector, message) {
  document.querySelector(selector).innerHTML =
    `<p style="color: var(--text-muted); padding: 24px;">${message}</p>`;
}

// =============================================================================
// Stars Section
// =============================================================================

function renderStarsChart(json) {
  const chartEl = document.querySelector('#stars-chart');
  chartEl.innerHTML = '';

  const series = [
    {
      name: 'Total Unique Stars',
      data: mapToChartData(json.total_stars_history, 'star_count'),
    },
  ];

  getRepoStarsSorted(json).forEach(({ repo }, index) => {
    series.push({
      name: `${rankPrefix(index + 1)} ${repo}`,
      data: mapToChartData(json[`${repo}_stars_history`], 'star_count'),
    });
  });

  const options = createChartOptions({
    series,
    title: 'GitHub Star Growth Over Time',
    yAxisTitle: 'Number of Stars',
    colors: COLORS.stars,
    showLegend: true,
    height: 400,
  });

  new ApexCharts(chartEl, options).render();
}

function renderStarsStats(json) {
  const latestEntry = getLastEntry(json.total_stars_history);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  const cards = [];

  cards.push(createMetricCard('Total Unique Stars', latestEntry?.star_count || 0, 'cyan', `Updated ${date}`));

  // Top repos card
  const topRepos = getRepoStarsSorted(json).slice(0, 10);
  const repoItems = topRepos.map(({ repo, starCount }, index) =>
    `<div class="repo-item">
      <span class="repo-rank">${rankPrefix(index + 1)}</span>
      <a class="repo-name" href="https://github.com/autowarefoundation/${repo}" target="_blank" rel="noopener noreferrer">${repo}</a>
      <span class="repo-stars">${formatNumber(starCount)}</span>
    </div>`
  ).join('');

  cards.push(
    `<div class="metric-card top-repos-card">
      <div class="metric-label">Top Repositories by Stars</div>
      <div class="top-repos-list">${repoItems}</div>
    </div>`
  );

  renderMetricCards('stars-stats', cards);
}

// =============================================================================
// Contributors Section
// =============================================================================

function renderContributorsChart(json) {
  const chartEl = document.querySelector('#contributors-chart');
  chartEl.innerHTML = '';

  const series = [
    {
      name: 'Total Unique Contributors',
      data: mapToChartData(json.autoware_contributors, 'contributors_count'),
    },
    {
      name: 'Code Contributors',
      data: mapToChartData(json.autoware_code_contributors, 'contributors_count'),
    },
    {
      name: 'Community Contributors',
      data: mapToChartData(json.autoware_community_contributors, 'contributors_count'),
    },
  ];

  const options = createChartOptions({
    series,
    title: 'Contributor Growth Over Time',
    yAxisTitle: 'Number of Contributors',
    colors: COLORS.contributors,
    showLegend: true,
  });

  new ApexCharts(chartEl, options).render();
}

function renderContributorsStats(json) {
  const latestEntry = getLastEntry(json.autoware_contributors);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  const cards = [
    createMetricCard('Total Contributors', latestEntry?.contributors_count || 0, 'cyan', `Updated ${date}`),
    createMetricCard('Code Contributors', getLastEntry(json.autoware_code_contributors)?.contributors_count || 0, 'coral'),
    createMetricCard('Community Contributors', getLastEntry(json.autoware_community_contributors)?.contributors_count || 0, 'teal'),
  ];

  renderMetricCards('contributors-stats', cards);
}

// =============================================================================
// Rankings
// =============================================================================

let rankingsData = null;
let currentPeriodType = 'monthly';
let mvpChart = null;
let codeChart = null;
let communityChart = null;
let reviewChart = null;

const RANKING_COLORS = {
  mvp: '#FFD700',
  code: '#00D9FF',
  community: '#FF6B6B',
  review: '#4ECDC4',
};

function createRankingChart(elementId, data, color, valueKey = 'count', valueName = 'Count') {
  const topData = data.slice(0, 15);

  const options = {
    series: [{
      name: valueName,
      data: topData.map(item => item[valueKey]),
    }],
    chart: {
      type: 'bar',
      height: getChartHeight(400),
      toolbar: { show: false },
      background: 'transparent',
      events: {
        dataPointSelection: function(event, chartContext, config) {
          const author = topData[config.dataPointIndex].author;
          window.open(`https://github.com/${author}`, '_blank', 'noopener,noreferrer');
        },
      },
    },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 4,
        dataLabels: {
          position: 'top',
        },
      },
    },
    dataLabels: {
      enabled: true,
      offsetX: 25,
      style: {
        fontSize: '11px',
        fontFamily: 'IBM Plex Mono, monospace',
      },
    },
    xaxis: {
      categories: topData.map(item => item.author),
    },
    yaxis: {
      labels: {
        style: { fontSize: '11px' },
      },
    },
    colors: [color],
    tooltip: {
      theme: 'dark',
      y: {
        formatter: function(val) { return val; },
      },
    },
    grid: {
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: false } },
    },
  };

  return new ApexCharts(document.querySelector(`#${elementId}`), options);
}

function updateRankingCharts(periodKey) {
  const periodData = rankingsData[currentPeriodType][periodKey];
  if (!periodData) return;

  if (mvpChart) mvpChart.destroy();
  mvpChart = createRankingChart('mvp-ranking-table', periodData.mvp || [], RANKING_COLORS.mvp, 'score', 'Score');
  mvpChart.render();

  if (codeChart) codeChart.destroy();
  codeChart = createRankingChart('code-ranking-table', periodData.code || [], RANKING_COLORS.code);
  codeChart.render();

  if (communityChart) communityChart.destroy();
  communityChart = createRankingChart('community-ranking-table', periodData.community || [], RANKING_COLORS.community);
  communityChart.render();

  if (reviewChart) reviewChart.destroy();
  reviewChart = createRankingChart('review-ranking-table', periodData.review || [], RANKING_COLORS.review);
  reviewChart.render();
}

function populatePeriodSelector() {
  const select = document.getElementById('period-select');
  select.innerHTML = '';

  const periods = Object.keys(rankingsData[currentPeriodType]).sort().reverse();

  periods.forEach((period) => {
    const option = document.createElement('option');
    option.value = period;
    option.textContent = period;
    select.appendChild(option);
  });

  if (periods.length > 0) {
    updateRankingCharts(periods[0]);
  }
}

function setupRankingsUI() {
  const btnMonthly = document.getElementById('btn-monthly');
  const btnQuarterly = document.getElementById('btn-quarterly');
  const btnYearly = document.getElementById('btn-yearly');
  const periodSelect = document.getElementById('period-select');
  const updatedSpan = document.getElementById('rankings-updated');
  const allButtons = [btnMonthly, btnQuarterly, btnYearly];

  if (rankingsData.last_updated) {
    updatedSpan.textContent = `Last updated: ${formatDate(rankingsData.last_updated)}`;
  }

  function activateButton(activeBtn, periodType) {
    currentPeriodType = periodType;
    allButtons.forEach(btn => btn.classList.remove('active'));
    activeBtn.classList.add('active');
    populatePeriodSelector();
  }

  btnMonthly.addEventListener('click', () => activateButton(btnMonthly, 'monthly'));
  btnQuarterly.addEventListener('click', () => activateButton(btnQuarterly, 'quarterly'));
  btnYearly.addEventListener('click', () => activateButton(btnYearly, 'yearly'));

  periodSelect.addEventListener('change', (e) => {
    updateRankingCharts(e.target.value);
  });

  populatePeriodSelector();
}

// =============================================================================
// Mobile Ranking Tabs
// =============================================================================

function setupRankingTabs() {
  const tabButtons = document.querySelectorAll('.ranking-tab-btn');
  const columns = document.querySelectorAll('.ranking-column');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;

      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      columns.forEach(col => {
        if (col.dataset.ranking === tab) {
          col.classList.add('active-tab');
        } else {
          col.classList.remove('active-tab');
        }
      });
    });
  });
}

// =============================================================================
// Scroll Animations & Nav Active State
// =============================================================================

function setupScrollObserver() {
  const sections = document.querySelectorAll('.dashboard-section');
  const navLinks = document.querySelectorAll('.nav-link[data-section]');

  // Fade-in sections
  const fadeObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    },
    { threshold: 0.05 }
  );

  sections.forEach(section => fadeObserver.observe(section));

  // Active nav tracking
  const navObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.section === id);
          });
        }
      });
    },
    { rootMargin: '-20% 0px -70% 0px' }
  );

  sections.forEach(section => navObserver.observe(section));
}

// =============================================================================
// Initialize
// =============================================================================

setupScrollObserver();
setupRankingTabs();

// Load repositories first, then load chart data
fetch('repositories.json')
  .then((res) => res.json())
  .then((repoData) => {
    REPOSITORIES = repoData.repositories || [];

    fetch('stars_history.json')
      .then((res) => res.json())
      .then((json) => {
        renderStarsChart(json);
        renderStarsStats(json);
      })
      .catch(() => showError('#stars-chart', 'Stars history data not available'));

    fetch('contributors_history.json')
      .then((res) => res.json())
      .then((json) => {
        renderContributorsChart(json);
        renderContributorsStats(json);
      })
      .catch(() => showError('#contributors-chart', 'Contributor history data not available'));
  })
  .catch(() => {
    fetch('stars_history.json')
      .then((res) => res.json())
      .then((json) => {
        renderStarsChart(json);
        renderStarsStats(json);
      })
      .catch(() => showError('#stars-chart', 'Stars history data not available'));

    fetch('contributors_history.json')
      .then((res) => res.json())
      .then((json) => {
        renderContributorsChart(json);
        renderContributorsStats(json);
      })
      .catch(() => showError('#contributors-chart', 'Contributor history data not available'));
  });

fetch('rankings.json')
  .then((res) => res.json())
  .then((json) => {
    rankingsData = json;
    setupRankingsUI();
  })
  .catch(() => {
    document.getElementById('mvp-ranking-table').innerHTML =
      '<p style="color: var(--text-muted); padding: 24px;">Rankings data not available</p>';
  });
