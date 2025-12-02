// =============================================================================
// Constants
// =============================================================================

const COLORS = {
  stars: ['#00D9FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3', '#F38181'],
  contributors: ['#00D9FF', '#FF6B6B', '#4ECDC4'],
};

const STARS_KEY_REPOS = [
  'autoware_stars_history',
  'autoware_core_stars_history',
  'autoware_universe_stars_history',
  'autoware.privately-owned-vehicles_stars_history',
];

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

function mapToChartData(dataArray, valueKey) {
  return dataArray.map((item) => [new Date(item.date), item[valueKey]]);
}

// =============================================================================
// Chart Configuration
// =============================================================================

function createChartOptions({ series, title, yAxisTitle, colors, showLegend = false }) {
  return {
    series,
    chart: {
      height: 500,
      type: 'line',
      zoom: { enabled: true },
      selection: { enabled: true },
    },
    dataLabels: { enabled: false },
    title: { text: title, align: 'left' },
    grid: {
      row: {
        colors: ['#f3f3f3', 'transparent'],
        opacity: 0.5,
      },
    },
    xaxis: { type: 'datetime' },
    yaxis: {
      min: 0,
      title: { text: yAxisTitle },
    },
    tooltip: {
      y: { formatter: formatNumber },
    },
    colors,
    ...(showLegend && {
      legend: {
        position: 'top',
        horizontalAlign: 'right',
      },
    }),
  };
}

// =============================================================================
// Stats Display
// =============================================================================

function createStatsHtml(date, items, colors) {
  const itemsHtml = items
    .map(
      ({ label, value }, index) => `
        <div>
          <strong style="font-size: 14px; color: #666;">${label}:</strong>
          <span style="font-size: 24px; font-weight: bold; color: ${colors[index]}; margin-left: 10px;">
            ${formatNumber(value)}
          </span>
        </div>
      `,
    )
    .join('');

  return `
    <div style="margin-bottom: 10px;">
      <span style="font-size: 14px; color: #666;">Last updated: <strong>${date}</strong></span>
    </div>
    <div style="display: flex; gap: 30px; flex-wrap: wrap;">
      ${itemsHtml}
    </div>
  `;
}

function showError(selector, message) {
  document.querySelector(selector).innerHTML = `<p style="color: #666;">${message}</p>`;
}

// =============================================================================
// Stars Chart
// =============================================================================

function renderStarsChart(json) {
  const series = [
    {
      name: 'Total Unique Stars',
      data: mapToChartData(json.total_stars_history, 'star_count'),
    },
  ];

  STARS_KEY_REPOS.forEach((repoKey) => {
    if (json[repoKey]) {
      series.push({
        name: repoKey.replace('_stars_history', ''),
        data: mapToChartData(json[repoKey], 'star_count'),
      });
    }
  });

  const options = createChartOptions({
    series,
    title: 'GitHub Star Growth Over Time',
    yAxisTitle: 'Number of Stars',
    colors: COLORS.stars,
  });

  new ApexCharts(document.querySelector('#stars-chart'), options).render();
}

function renderStarsStats(json) {
  const latestEntry = getLastEntry(json.total_stars_history);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  const items = [{ label: 'Total Unique Stars', value: latestEntry?.star_count || 0 }];

  STARS_KEY_REPOS.forEach((repoKey) => {
    const entry = getLastEntry(json[repoKey] || []);
    if (entry) {
      items.push({
        label: repoKey.replace('_stars_history', ''),
        value: entry.star_count,
      });
    }
  });

  document.querySelector('#stars-stats').innerHTML = createStatsHtml(date, items, COLORS.stars);
}

// =============================================================================
// Contributors Chart
// =============================================================================

function renderContributorsChart(json) {
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

  new ApexCharts(document.querySelector('#contributors-chart'), options).render();
}

function renderContributorsStats(json) {
  const latestEntry = getLastEntry(json.autoware_contributors);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  const items = [
    {
      label: 'Total Unique Contributors',
      value: latestEntry?.contributors_count || 0,
    },
    {
      label: 'Code Contributors',
      value: getLastEntry(json.autoware_code_contributors)?.contributors_count || 0,
    },
    {
      label: 'Community Contributors',
      value: getLastEntry(json.autoware_community_contributors)?.contributors_count || 0,
    },
  ];

  document.querySelector('#contributors-stats').innerHTML = createStatsHtml(
    date,
    items,
    COLORS.contributors,
  );
}

// =============================================================================
// Initialize
// =============================================================================

fetch('stars_history.json')
  .then((res) => res.json())
  .then((json) => {
    renderStarsChart(json);
    renderStarsStats(json);
  })
  .catch((error) => {
    console.log('Error loading stars_history.json:', error);
    showError('#stars-chart', 'Stars history data not available');
  });

fetch('contributors_history.json')
  .then((res) => res.json())
  .then((json) => {
    renderContributorsChart(json);
    renderContributorsStats(json);
  })
  .catch((error) => {
    console.log('Error loading contributors_history.json:', error);
    showError('#contributors-chart', 'Contributor history data not available');
  });

// =============================================================================
// Rankings Tables
// =============================================================================

let rankingsData = null;
let currentPeriodType = 'monthly';
let codeTable = null;
let communityTable = null;
let reviewTable = null;

function createRankingTable(elementId, data) {
  return new Tabulator(`#${elementId}`, {
    data: data,
    layout: 'fitColumns',
    height: '400px',
    columns: [
      { title: 'Rank', field: 'rank', width: 60, hozAlign: 'center' },
      {
        title: 'Author',
        field: 'author',
        formatter: function (cell) {
          const author = cell.getValue();
          return `<a href="https://github.com/${author}" target="_blank" rel="noopener noreferrer">${author}</a>`;
        },
      },
      { title: 'Count', field: 'count', width: 80, hozAlign: 'right', sorter: 'number' },
    ],
    pagination: 'local',
    paginationSize: 10,
    paginationSizeSelector: [10, 25, 50],
  });
}

function updateRankingTables(periodKey) {
  const periodData = currentPeriodType === 'monthly'
    ? rankingsData.monthly[periodKey]
    : rankingsData.yearly[periodKey];

  if (!periodData) {
    console.log('No data for period:', periodKey);
    return;
  }

  if (codeTable) {
    codeTable.setData(periodData.code || []);
  } else {
    codeTable = createRankingTable('code-ranking-table', periodData.code || []);
  }

  if (communityTable) {
    communityTable.setData(periodData.community || []);
  } else {
    communityTable = createRankingTable('community-ranking-table', periodData.community || []);
  }

  if (reviewTable) {
    reviewTable.setData(periodData.review || []);
  } else {
    reviewTable = createRankingTable('review-ranking-table', periodData.review || []);
  }
}

function populatePeriodSelector() {
  const select = document.getElementById('period-select');
  select.innerHTML = '';

  const periods = currentPeriodType === 'monthly'
    ? Object.keys(rankingsData.monthly).sort().reverse()
    : Object.keys(rankingsData.yearly).sort().reverse();

  periods.forEach((period) => {
    const option = document.createElement('option');
    option.value = period;
    option.textContent = period;
    select.appendChild(option);
  });

  if (periods.length > 0) {
    updateRankingTables(periods[0]);
  }
}

function setupRankingsUI() {
  const btnMonthly = document.getElementById('btn-monthly');
  const btnYearly = document.getElementById('btn-yearly');
  const periodSelect = document.getElementById('period-select');
  const updatedSpan = document.getElementById('rankings-updated');

  if (rankingsData.last_updated) {
    updatedSpan.textContent = `Last updated: ${formatDate(rankingsData.last_updated)}`;
  }

  btnMonthly.addEventListener('click', () => {
    currentPeriodType = 'monthly';
    btnMonthly.classList.remove('btn-outline-primary');
    btnMonthly.classList.add('btn-primary');
    btnYearly.classList.remove('btn-primary');
    btnYearly.classList.add('btn-outline-primary');
    populatePeriodSelector();
  });

  btnYearly.addEventListener('click', () => {
    currentPeriodType = 'yearly';
    btnYearly.classList.remove('btn-outline-primary');
    btnYearly.classList.add('btn-primary');
    btnMonthly.classList.remove('btn-primary');
    btnMonthly.classList.add('btn-outline-primary');
    populatePeriodSelector();
  });

  periodSelect.addEventListener('change', (e) => {
    updateRankingTables(e.target.value);
  });

  populatePeriodSelector();
}

fetch('rankings.json')
  .then((res) => res.json())
  .then((json) => {
    rankingsData = json;
    setupRankingsUI();
  })
  .catch((error) => {
    console.log('Error loading rankings.json:', error);
    document.getElementById('code-ranking-table').innerHTML =
      '<p style="color: #666;">Rankings data not available</p>';
  });
