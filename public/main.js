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

// Top 25 repositories by composite score (same order as repositories.py)
const REPOSITORIES = [
  'autoware',
  'autoware_universe',
  'autoware_ai_perception',
  'autoware_launch',
  'sample_sensor_kit_launch',
  'autoware_ai_planning',
  'sample_vehicle_launch',
  'autoware-documentation',
  'ros2_socketcan',
  'autoware_core',
  'autoware.privately-owned-vehicles',
  'autoware_msgs',
  'autoware_common',
  'autoware_tools',
  'AWSIM-Labs',
  'autoware-github-actions',
  'autoware_utils',
  'autoware_adapi_msgs',
  'autoware_lanelet2_extension',
  'autoware_internal_msgs',
  'autoware_cmake',
  'autoware.off-road',
  'autoware_ai',
  'autoware_rviz_plugins',
  'openadkit',
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

  // Add all 25 repositories
  REPOSITORIES.forEach((repo) => {
    const repoKey = `${repo}_stars_history`;
    if (json[repoKey]) {
      series.push({
        name: repo,
        data: mapToChartData(json[repoKey], 'star_count'),
      });
    }
  });

  const options = createChartOptions({
    series,
    title: 'GitHub Star Growth Over Time',
    yAxisTitle: 'Number of Stars',
    colors: COLORS.stars,
    showLegend: true,
  });

  // Increase chart height for better visibility with many series
  options.chart.height = 600;
  options.legend = {
    position: 'bottom',
    horizontalAlign: 'center',
    floating: false,
    fontSize: '12px',
    markers: { width: 10, height: 10 },
  };

  new ApexCharts(document.querySelector('#stars-chart'), options).render();
}

function renderStarsStats(json) {
  const latestEntry = getLastEntry(json.total_stars_history);
  const date = latestEntry ? formatDate(latestEntry.date) : 'N/A';

  // Show total and top 10 repositories by composite score (stars + forks + recency)
  const topRepos = [
    'autoware',
    'autoware_universe',
    'autoware_ai_perception',
    'autoware_launch',
    'sample_sensor_kit_launch',
    'autoware_ai_planning',
    'sample_vehicle_launch',
    'autoware-documentation',
    'ros2_socketcan',
    'autoware_core',
  ];
  const items = [{ label: 'Total Unique Stars', value: latestEntry?.star_count || 0 }];

  topRepos.forEach((repo) => {
    const repoKey = `${repo}_stars_history`;
    const entry = getLastEntry(json[repoKey] || []);
    if (entry) {
      items.push({
        label: repo,
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
// Rankings Charts
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
      height: 400,
      toolbar: { show: false },
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
        fontSize: '12px',
        colors: ['#333'],
      },
      formatter: function(val) {
        return val;
      },
    },
    xaxis: {
      categories: topData.map(item => item.author),
    },
    yaxis: {
      labels: {
        style: {
          fontSize: '11px',
        },
      },
    },
    colors: [color],
    tooltip: {
      y: {
        formatter: function(val) {
          return val;
        },
      },
    },
    grid: {
      xaxis: {
        lines: { show: true },
      },
      yaxis: {
        lines: { show: false },
      },
    },
  };

  return new ApexCharts(document.querySelector(`#${elementId}`), options);
}

function updateRankingCharts(periodKey) {
  const periodData = currentPeriodType === 'monthly'
    ? rankingsData.monthly[periodKey]
    : rankingsData.yearly[periodKey];

  if (!periodData) {
    console.log('No data for period:', periodKey);
    return;
  }

  if (mvpChart) {
    mvpChart.destroy();
  }
  mvpChart = createRankingChart('mvp-ranking-table', periodData.mvp || [], RANKING_COLORS.mvp, 'score', 'Score');
  mvpChart.render();

  if (codeChart) {
    codeChart.destroy();
  }
  codeChart = createRankingChart('code-ranking-table', periodData.code || [], RANKING_COLORS.code);
  codeChart.render();

  if (communityChart) {
    communityChart.destroy();
  }
  communityChart = createRankingChart('community-ranking-table', periodData.community || [], RANKING_COLORS.community);
  communityChart.render();

  if (reviewChart) {
    reviewChart.destroy();
  }
  reviewChart = createRankingChart('review-ranking-table', periodData.review || [], RANKING_COLORS.review);
  reviewChart.render();
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
    updateRankingCharts(periods[0]);
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
    updateRankingCharts(e.target.value);
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
