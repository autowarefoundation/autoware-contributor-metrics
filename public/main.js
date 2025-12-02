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
    title: 'GitHub Stars Over Time',
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
