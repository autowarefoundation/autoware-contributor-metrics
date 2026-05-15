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

// Set up toggle button and apply theme synchronously (before IIFE await)
document.getElementById('theme-toggle')?.addEventListener('click', cycleTheme);
applyTheme();

// =============================================================================
// Main Application (IIFE to avoid global scope pollution)
// =============================================================================

(async function () {

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
  downloads: ['#00D9FF', '#FF6B6B', '#4ECDC4', '#FFE66D'],
  commits: ['#00D9FF', '#FF6B6B', '#4ECDC4'],
  visibility: ['#00D9FF', '#FF6B6B', '#FFE66D'],
};

const RANKING_CATEGORIES = [
  { key: 'mvp',       elementId: 'mvp-ranking-table',       color: '#FFD700', valueKey: 'score', valueName: 'Score' },
  { key: 'code',      elementId: 'code-ranking-table',      color: '#00D9FF', valueKey: 'count', valueName: 'Count' },
  { key: 'community', elementId: 'community-ranking-table', color: '#FF6B6B', valueKey: 'count', valueName: 'Count' },
  { key: 'review',    elementId: 'review-ranking-table',    color: '#4ECDC4', valueKey: 'count', valueName: 'Count' },
];

let REPOSITORIES = [];
let rankingsData = null;
let currentPeriodType = 'monthly';
const rankingCharts = {};

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

// Compute yearly new additions from a cumulative time-series.
// `history` is an array of objects with {date: 'YYYY-MM-DD', [valueKey]: number}
// sorted ascending. Returns [{year: 2022, new_count: N}, ...] using the last
// observed cumulative value within each calendar year.
function computeYearlyNew(history, valueKey) {
  if (!history || history.length === 0) return [];
  const lastByYear = {};
  history.forEach(item => {
    const y = new Date(item.date).getUTCFullYear();
    lastByYear[y] = item[valueKey];
  });
  const years = Object.keys(lastByYear).map(Number).sort((a, b) => a - b);
  const out = [];
  let prev = 0;
  years.forEach(y => {
    const total = lastByYear[y];
    out.push({ year: y, new_count: total - prev, cumulative: total });
    prev = total;
  });
  return out;
}

function createYearlyComboOptions({ yearly, title, barName, lineName, color }) {
  const categories = yearly.map(y => String(y.year));
  return {
    series: [
      { name: barName, type: 'column', data: yearly.map(y => y.new_count) },
      { name: lineName, type: 'line', data: yearly.map(y => y.cumulative) },
    ],
    chart: {
      type: 'line',
      height: getChartHeight(360),
      toolbar: { show: true },
      background: 'transparent',
      stacked: false,
    },
    title: {
      text: title,
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    stroke: { width: [0, 3], curve: 'smooth' },
    plotOptions: { bar: { borderRadius: 3, columnWidth: '55%' } },
    dataLabels: { enabled: false },
    xaxis: { categories },
    yaxis: [
      {
        seriesName: barName,
        min: 0,
        title: { text: barName },
        labels: { formatter: formatNumber },
      },
      {
        seriesName: lineName,
        opposite: true,
        min: 0,
        title: { text: lineName },
        labels: { formatter: formatNumber },
      },
    ],
    tooltip: { theme: 'dark', shared: true, y: { formatter: formatNumber } },
    colors: [color, '#FFE66D'],
    legend: {
      position: 'bottom', horizontalAlign: 'center',
      fontSize: '12px', fontFamily: 'Outfit, sans-serif',
      markers: { width: 10, height: 10, radius: 3 },
    },
    grid: { row: { opacity: 0 } },
  };
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
  container.innerHTML = cards.join('');
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

function renderStarsYearlyChart(json) {
  const chartEl = document.querySelector('#stars-yearly-chart');
  chartEl.innerHTML = '';
  const yearly = computeYearlyNew(json.total_stars_history || [], 'star_count');
  if (yearly.length === 0) return;
  const options = createYearlyComboOptions({
    yearly,
    title: 'New Stars Per Year (with Cumulative Total)',
    barName: 'New stars / year',
    lineName: 'Cumulative stars',
    color: COLORS.stars[0],
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

  // Build yearly buckets from the full contributors history; take the last
  // observed cumulative value within each calendar year as that year's snapshot.
  const total = json.autoware_contributors || [];
  const code = json.autoware_code_contributors || [];
  const community = json.autoware_community_contributors || [];

  const yearSet = new Set();
  [total, code, community].forEach(arr => arr.forEach(item => {
    yearSet.add(new Date(item.date).getUTCFullYear());
  }));
  const years = [...yearSet].sort((a, b) => a - b);

  function lastValueByYear(history, valueKey) {
    const map = {};
    history.forEach(item => {
      const y = new Date(item.date).getUTCFullYear();
      map[y] = item[valueKey];
    });
    // Forward-fill years where this series had no observation (carry the prior
    // cumulative value so the line stays monotonic across the full timeline).
    const out = [];
    let prev = null;
    years.forEach(y => {
      if (map[y] !== undefined) prev = map[y];
      out.push(prev);
    });
    return out;
  }

  const totalByYear = lastValueByYear(total, 'contributors_count');
  // New contributors per year = year-over-year delta of the cumulative total.
  const newPerYear = totalByYear.map((v, i) => {
    if (v === null) return 0;
    const prev = i === 0 ? 0 : (totalByYear[i - 1] ?? 0);
    return v - prev;
  });

  const series = [
    { name: 'New contributors / year', type: 'column', data: newPerYear },
    { name: 'Total Unique Contributors', type: 'line', data: totalByYear },
    { name: 'Code Contributors', type: 'line', data: lastValueByYear(code, 'contributors_count') },
    { name: 'Community Contributors', type: 'line', data: lastValueByYear(community, 'contributors_count') },
  ];

  const options = {
    series,
    chart: {
      type: 'line',
      height: getChartHeight(420),
      stacked: false,
      zoom: { enabled: false },
      background: 'transparent',
      toolbar: { show: true },
    },
    title: {
      text: 'Contributor Growth Over Time',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    stroke: { width: [0, 3, 2, 2], curve: 'smooth' },
    plotOptions: { bar: { borderRadius: 4, columnWidth: '60%' } },
    markers: { size: [0, 4, 3, 3] },
    dataLabels: { enabled: false },
    xaxis: { categories: years.map(String) },
    yaxis: [
      {
        seriesName: 'New contributors / year',
        min: 0,
        title: { text: 'New contributors / year' },
        labels: { formatter: formatNumber },
      },
      {
        seriesName: ['Total Unique Contributors', 'Code Contributors', 'Community Contributors'],
        opposite: true,
        min: 0,
        title: { text: 'Cumulative contributors' },
        labels: { formatter: formatNumber },
      },
    ],
    tooltip: { theme: 'dark', shared: true, y: { formatter: formatNumber } },
    colors: ['#FFE66D', ...COLORS.contributors],
    legend: {
      position: 'bottom', horizontalAlign: 'center',
      fontSize: '12px', fontFamily: 'Outfit, sans-serif',
      markers: { width: 10, height: 10, radius: 3 },
    },
    grid: { row: { opacity: 0 } },
  };

  new ApexCharts(chartEl, options).render();
}

function renderContributorsStats(json) {
  const latestEntry = getLastEntry(json.autoware_contributors);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  const cards = [
    createMetricCard('Total Unique Contributors', latestEntry?.contributors_count || 0, 'cyan', `Updated ${date}`),
    createMetricCard('Code Contributors', getLastEntry(json.autoware_code_contributors)?.contributors_count || 0, 'coral'),
    createMetricCard('Community Contributors', getLastEntry(json.autoware_community_contributors)?.contributors_count || 0, 'teal'),
  ];

  renderMetricCards('contributors-stats', cards);
}

// =============================================================================
// APT Downloads Section
// =============================================================================

function renderDownloadsChart(json) {
  const chartEl = document.querySelector('#downloads-chart');
  chartEl.textContent = '';

  // Stacked area: Humble + Jazzy + Rolling sums to Total at each point.
  // Restrict the displayed window to 2024-01 onward.
  const cumulative = (json.cumulative || []).filter(item => item.date >= '2024-01');
  const series = [
    {
      name: 'Humble',
      data: cumulative.map(item => [new Date(item.date + '-01'), item.humble]),
    },
    {
      name: 'Jazzy',
      data: cumulative.map(item => [new Date(item.date + '-01'), item.jazzy]),
    },
    {
      name: 'Rolling',
      data: cumulative.map(item => [new Date(item.date + '-01'), item.rolling]),
    },
  ];

  const options = {
    series,
    chart: {
      type: 'area',
      height: getChartHeight(400),
      stacked: true,
      zoom: { enabled: true },
      background: 'transparent',
      toolbar: { show: true },
    },
    title: {
      text: 'APT Package Download Growth (Cumulative, Stacked by Distro)',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    dataLabels: { enabled: false },
    stroke: { width: 2, curve: 'smooth' },
    fill: {
      type: 'gradient',
      gradient: { shadeIntensity: 1, opacityFrom: 0.55, opacityTo: 0.15 },
    },
    xaxis: { type: 'datetime' },
    yaxis: {
      min: 0,
      title: { text: 'Total Downloads' },
      labels: { formatter: formatNumber },
    },
    tooltip: {
      theme: 'dark',
      shared: true,
      y: { formatter: formatNumber },
    },
    colors: ['#FF6B6B', '#4ECDC4', '#FFE66D'],
    legend: {
      position: 'bottom',
      horizontalAlign: 'center',
      fontSize: '12px',
      fontFamily: 'Outfit, sans-serif',
      markers: { width: 10, height: 10, radius: 3 },
    },
    grid: { row: { opacity: 0 } },
  };

  new ApexCharts(chartEl, options).render();
}

function renderDownloadsRanking(json) {
  const chartEl = document.querySelector('#downloads-ranking-chart');
  chartEl.textContent = '';

  const entries = Object.entries(json.package_totals);
  const topData = entries.slice(0, 20);

  if (topData.length === 0) return;

  // Strip "ros-{distro}-autoware-" prefix for display
  const labels = topData.map(([pkg]) => pkg.replace(/^ros-(humble|jazzy|rolling)-/, ''));
  const values = topData.map(([, count]) => count);
  const barColors = topData.map(([pkg]) => {
    if (pkg.startsWith('ros-humble-')) return '#FF6B6B';
    if (pkg.startsWith('ros-jazzy-')) return '#4ECDC4';
    if (pkg.startsWith('ros-rolling-')) return '#FFE66D';
    return '#95E1D3';
  });

  const options = {
    series: [{ name: 'Downloads', data: values }],
    chart: {
      type: 'bar',
      height: 400,
      toolbar: { show: false },
      background: 'transparent',
    },
    title: {
      text: 'Top 20 Packages by Downloads (All Time)',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 4,
        distributed: true,
        barHeight: '70%',
        dataLabels: { position: 'top' },
      },
    },
    dataLabels: {
      enabled: true,
      offsetX: 25,
      formatter: formatNumber,
      style: { fontSize: '11px', fontFamily: 'IBM Plex Mono, monospace' },
    },
    xaxis: { categories: labels },
    yaxis: {
      labels: {
        style: { fontSize: '11px' },
        maxWidth: 350,
      },
    },
    colors: barColors,
    legend: { show: false },
    tooltip: {
      theme: 'dark',
      y: { formatter: formatNumber },
    },
    grid: {
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: false } },
    },
  };

  new ApexCharts(chartEl, options).render();
}

function renderDownloadsStats(json) {
  const cumulative = json.cumulative;
  const lastEntry = cumulative.length > 0 ? cumulative[cumulative.length - 1] : null;

  const monthKeys = Object.keys(json.monthly).sort();
  const latestMonthKey = monthKeys[monthKeys.length - 1];
  const latestMonth = json.monthly[latestMonthKey] || {};

  const firstMonthKey = monthKeys[0] || 'N/A';

  // Update subtitle under section heading
  const section = document.querySelector('#downloads');
  let subtitle = section.querySelector('.section-subtitle');
  if (!subtitle) {
    subtitle = document.createElement('p');
    subtitle.className = 'section-subtitle';
    section.querySelector('.section-heading').after(subtitle);
  }
  subtitle.textContent = `${firstMonthKey} \u2013 ${latestMonthKey || 'N/A'} (excl. Jan\u2013Jun 2025)`;

  const cards = [
    createMetricCard('Total Downloads', lastEntry?.total || 0, 'cyan'),
    createMetricCard('Humble', lastEntry?.humble || 0, 'coral'),
    createMetricCard('Jazzy', lastEntry?.jazzy || 0, 'teal'),
    createMetricCard('Rolling', lastEntry?.rolling || 0, 'yellow'),
  ];

  renderMetricCards('downloads-stats', cards);
}

// =============================================================================
// Commits Section
// =============================================================================

function renderCommitsChart(commitsJson, activityJson) {
  const chartEl = document.querySelector('#commits-chart');
  chartEl.innerHTML = '';

  const commitHistory = commitsJson.total_commits_history || [];
  const prHistory = activityJson ? (activityJson.total_merged_prs_history || []) : [];
  const issueHistory = activityJson ? (activityJson.total_resolved_issues_history || []) : [];

  // Merge years from all series
  const yearSet = new Set();
  commitHistory.forEach(item => yearSet.add(item.year));
  prHistory.forEach(item => yearSet.add(item.year));
  issueHistory.forEach(item => yearSet.add(item.year));
  const categories = Array.from(yearSet).sort();

  const commitMap = {};
  commitHistory.forEach(item => { commitMap[item.year] = item.commit_count; });
  const prMap = {};
  prHistory.forEach(item => { prMap[item.year] = item.merged_pr_count; });
  const issueMap = {};
  issueHistory.forEach(item => { issueMap[item.year] = item.resolved_issue_count; });

  const series = [
    { name: 'Commits', data: categories.map(y => commitMap[y] || 0) },
    { name: 'Merged PRs', data: categories.map(y => prMap[y] || 0) },
    { name: 'Resolved Issues', data: categories.map(y => issueMap[y] || 0) },
  ];

  const options = {
    series,
    chart: {
      type: 'bar',
      height: getChartHeight(400),
      toolbar: { show: true },
      background: 'transparent',
    },
    title: {
      text: 'Yearly Activity (All Repositories)',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    plotOptions: {
      bar: {
        borderRadius: 4,
        columnWidth: '60%',
      },
    },
    dataLabels: { enabled: false },
    xaxis: { categories },
    yaxis: {
      min: 0,
      title: { text: 'Count' },
      labels: { formatter: formatNumber },
    },
    tooltip: {
      theme: 'dark',
      y: { formatter: formatNumber },
    },
    colors: COLORS.commits,
    legend: {
      position: 'bottom',
      horizontalAlign: 'center',
      fontSize: '12px',
      fontFamily: 'Outfit, sans-serif',
      markers: { width: 10, height: 10, radius: 3 },
    },
    grid: {
      row: { opacity: 0 },
    },
  };

  new ApexCharts(chartEl, options).render();
}

function renderCommitsStats(commitsJson, activityJson) {
  const commitHistory = commitsJson.total_commits_history || [];
  const prHistory = activityJson ? (activityJson.total_merged_prs_history || []) : [];
  const issueHistory = activityJson ? (activityJson.total_resolved_issues_history || []) : [];

  const totalCommits = commitHistory.reduce((sum, item) => sum + item.commit_count, 0);
  const latestCommit = commitHistory.length > 0 ? commitHistory[commitHistory.length - 1] : null;

  const totalPRs = prHistory.reduce((sum, item) => sum + item.merged_pr_count, 0);
  const latestPR = prHistory.length > 0 ? prHistory[prHistory.length - 1] : null;

  const totalIssues = issueHistory.reduce((sum, item) => sum + item.resolved_issue_count, 0);
  const latestIssue = issueHistory.length > 0 ? issueHistory[issueHistory.length - 1] : null;

  const cards = [
    createMetricCard('Total Commits', totalCommits, 'cyan', 'Since 2022'),
    createMetricCard('Latest Year Commits', latestCommit?.commit_count || 0, 'cyan', latestCommit?.year || 'N/A'),
    createMetricCard('Total Merged PRs', totalPRs, 'coral', 'Since 2022'),
    createMetricCard('Latest Year Merged PRs', latestPR?.merged_pr_count || 0, 'coral', latestPR?.year || 'N/A'),
    createMetricCard('Total Resolved Issues', totalIssues, 'teal', 'Since 2022'),
    createMetricCard('Latest Year Resolved Issues', latestIssue?.resolved_issue_count || 0, 'teal', latestIssue?.year || 'N/A'),
  ];

  renderMetricCards('commits-stats', cards);
}


// =============================================================================
// External Visibility Section
// =============================================================================

function monthToDate(monthStr) {
  // "YYYY-MM" -> Date at first of month
  const [y, m] = monthStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1));
}

function renderArxivMentionsChart(arxivJson) {
  const chartEl = document.querySelector('#arxiv-mentions-chart');
  chartEl.innerHTML = '';
  const yearly = (arxivJson && arxivJson.yearly) || [];

  const series = [
    {
      name: 'New papers / year',
      type: 'column',
      data: yearly.map(y => y.count),
    },
    {
      name: 'Cumulative papers',
      type: 'line',
      data: yearly.map(y => y.cumulative),
    },
  ];
  const categories = yearly.map(y => String(y.year));

  const options = {
    series,
    chart: {
      type: 'line',
      height: getChartHeight(400),
      toolbar: { show: true },
      background: 'transparent',
      stacked: false,
    },
    title: {
      text: 'arXiv Papers Mentioning "Autoware" (Yearly)',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    stroke: { width: [0, 3], curve: 'smooth' },
    plotOptions: { bar: { borderRadius: 3, columnWidth: '55%' } },
    dataLabels: { enabled: false },
    xaxis: { categories },
    yaxis: [
      {
        seriesName: 'New papers / year',
        min: 0,
        title: { text: 'New papers' },
        labels: { formatter: formatNumber },
      },
      {
        seriesName: 'Cumulative papers',
        opposite: true,
        min: 0,
        title: { text: 'Cumulative' },
        labels: { formatter: formatNumber },
      },
    ],
    tooltip: { theme: 'dark', shared: true, y: { formatter: formatNumber } },
    colors: COLORS.visibility,
    legend: {
      position: 'bottom', horizontalAlign: 'center',
      fontSize: '12px', fontFamily: 'Outfit, sans-serif',
      markers: { width: 10, height: 10, radius: 3 },
    },
    grid: { row: { opacity: 0 } },
  };
  new ApexCharts(chartEl, options).render();
}

function renderGoogleTrendsChart(trendsJson) {
  const chartEl = document.querySelector('#google-trends-chart');
  chartEl.innerHTML = '';
  const monthly = (trendsJson && trendsJson.monthly) || [];

  const series = [{
    name: 'Search interest (0-100)',
    data: monthly.map(m => [monthToDate(m.month).getTime(), m.interest]),
  }];

  const options = {
    series,
    chart: {
      type: 'area',
      height: getChartHeight(380),
      toolbar: { show: true },
      background: 'transparent',
      zoom: { enabled: true },
    },
    title: {
      text: 'Google Trends: "Autoware" Worldwide Search Interest (Monthly)',
      align: 'left',
      style: { fontSize: '16px', fontFamily: 'Outfit, sans-serif', fontWeight: 600 },
    },
    subtitle: {
      text: 'Relative interest (100 = peak month). Not absolute search volume.',
      align: 'left',
      style: { fontSize: '12px', fontFamily: 'Outfit, sans-serif', color: 'var(--text-muted)' },
    },
    stroke: { width: 2, curve: 'smooth' },
    fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05 } },
    dataLabels: { enabled: false },
    xaxis: { type: 'datetime' },
    yaxis: { min: 0, max: 100, title: { text: 'Interest' } },
    tooltip: { theme: 'dark', x: { format: 'MMM yyyy' } },
    colors: [COLORS.visibility[0]],
    grid: { row: { opacity: 0 } },
  };
  new ApexCharts(chartEl, options).render();
}

function renderVisibilityStats(arxivJson, citationsJson, trendsJson) {
  const totalPapers = (arxivJson && arxivJson.total_papers) || 0;
  const latestPaperYear = arxivJson?.yearly?.length
    ? arxivJson.yearly[arxivJson.yearly.length - 1]
    : null;
  const totalCitations = (citationsJson && citationsJson.total_citations) || 0;
  const latestTrend = trendsJson?.monthly?.length
    ? trendsJson.monthly[trendsJson.monthly.length - 1]
    : null;

  const cards = [
    createMetricCard('Search Interest (Latest)', latestTrend?.interest || 0, 'yellow', latestTrend?.month || 'N/A'),
    createMetricCard('arXiv Papers (Total)', totalPapers, 'cyan', 'Mentioning "Autoware"'),
    createMetricCard('New Papers (Latest Year)', latestPaperYear?.count || 0, 'cyan', latestPaperYear?.year ? String(latestPaperYear.year) : 'N/A'),
    createMetricCard('Total Citations', totalCitations, 'coral', 'OpenAlex, all years'),
  ];
  renderMetricCards('visibility-stats', cards);
}


// =============================================================================
// Rankings
// =============================================================================

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

  for (const cat of RANKING_CATEGORIES) {
    if (rankingCharts[cat.key]) rankingCharts[cat.key].destroy();
    rankingCharts[cat.key] = createRankingChart(
      cat.elementId, periodData[cat.key] || [], cat.color, cat.valueKey, cat.valueName,
    );
    rankingCharts[cat.key].render();
  }
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
  const periodSelect = document.getElementById('period-select');
  const updatedSpan = document.getElementById('rankings-updated');
  const periodTypes = ['monthly', 'quarterly', 'yearly'];
  const buttons = periodTypes.map(type => document.getElementById(`btn-${type}`));

  if (rankingsData.last_updated) {
    updatedSpan.textContent = `Last updated: ${formatDate(rankingsData.last_updated)}`;
  }

  periodTypes.forEach((type, i) => {
    buttons[i].addEventListener('click', () => {
      currentPeriodType = type;
      buttons.forEach(btn => btn.classList.remove('active'));
      buttons[i].classList.add('active');
      populatePeriodSelector();
    });
  });

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

// 1. Load repos (graceful fallback)
try {
  const repoData = await fetch('repositories.json').then(r => r.json());
  REPOSITORIES = repoData.repositories || [];
} catch { /* REPOSITORIES stays [] */ }

// 2. Load data files in parallel
const [
  starsResult,
  contributorsResult,
  rankingsResult,
  downloadsResult,
  commitsResult,
  activityResult,
  arxivMentionsResult,
  arxivCitationsResult,
  googleTrendsResult,
] = await Promise.allSettled([
  fetch('stars_history.json').then(r => r.json()),
  fetch('contributors_history.json').then(r => r.json()),
  fetch('rankings.json').then(r => r.json()),
  fetch('apt_downloads.json').then(r => r.json()),
  fetch('commits_history.json').then(r => r.json()),
  fetch('activity_history.json').then(r => r.json()),
  fetch('arxiv_mentions_history.json').then(r => r.json()),
  fetch('arxiv_citations_history.json').then(r => r.json()),
  fetch('google_trends_history.json').then(r => r.json()),
]);

// 3. Render each independently (error per section)
if (starsResult.status === 'fulfilled') {
  renderStarsChart(starsResult.value);
  renderStarsYearlyChart(starsResult.value);
  renderStarsStats(starsResult.value);
} else {
  showError('#stars-chart', 'Stars history data not available');
  showError('#stars-yearly-chart', 'Stars history data not available');
}

if (contributorsResult.status === 'fulfilled') {
  renderContributorsChart(contributorsResult.value);
  renderContributorsStats(contributorsResult.value);
} else {
  showError('#contributors-chart', 'Contributor history data not available');
}

if (downloadsResult.status === 'fulfilled') {
  renderDownloadsChart(downloadsResult.value);
  renderDownloadsRanking(downloadsResult.value);
  renderDownloadsStats(downloadsResult.value);
} else {
  showError('#downloads-chart', 'APT download data not available');
}

if (commitsResult.status === 'fulfilled') {
  const activityData = activityResult.status === 'fulfilled' ? activityResult.value : null;
  renderCommitsChart(commitsResult.value, activityData);
  renderCommitsStats(commitsResult.value, activityData);
} else {
  showError('#commits-chart', 'Commit history data not available');
}

const arxivMentions = arxivMentionsResult.status === 'fulfilled' ? arxivMentionsResult.value : null;
const arxivCitations = arxivCitationsResult.status === 'fulfilled' ? arxivCitationsResult.value : null;
const googleTrends = googleTrendsResult.status === 'fulfilled' ? googleTrendsResult.value : null;

if (arxivMentions) {
  renderArxivMentionsChart(arxivMentions);
} else {
  showError('#arxiv-mentions-chart', 'arXiv mentions data not available');
}
if (googleTrends) {
  renderGoogleTrendsChart(googleTrends);
} else {
  showError('#google-trends-chart', 'Google Trends data not available');
}
renderVisibilityStats(arxivMentions, arxivCitations, googleTrends);

if (rankingsResult.status === 'fulfilled') {
  rankingsData = rankingsResult.value;
  setupRankingsUI();
} else {
  document.getElementById('mvp-ranking-table').innerHTML =
    '<p style="color: var(--text-muted); padding: 24px;">Rankings data not available</p>';
}

})();
