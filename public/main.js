fetch('github_action_data.json')
  .then((res) => res.json())
  .then((json) => {
    const healthCheck = json.workflow_time["health-check"];
    const dockerBuildAndPush = json.workflow_time["docker-build-and-push"];

    // Build duration chart
    const healthCheckTimeOptions = {
      series: [
        {
          name: 'main-amd64',
          data: healthCheck.map((data) => {
            if (!data.jobs['main-amd64']) return null;
            return [new Date(data.date), data.jobs['main-amd64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'main-arm64',
          data: healthCheck.map((data) => {
            if (!data.jobs['main-arm64']) return null;
            return [new Date(data.date), data.jobs['main-arm64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'nightly-amd64',
          data: healthCheck.map((data) => {
            if (!data.jobs['nightly-amd64']) return null;
            return [new Date(data.date), data.jobs['nightly-amd64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
      ],
      chart: {
        height: 500,
        type: 'line',
        zoom: {
          enabled: true,
        },
        selection: {
          enabled: true,
        },
      },
      dataLabels: {
        enabled: false,
      },
      title: {
        text: 'Build duration',
        align: 'left',
      },
      grid: {
        row: {
          colors: ['#f3f3f3', 'transparent'], // takes an array which will be repeated on columns
          opacity: 0.5,
        },
      },
      xaxis: {
        type: 'datetime',
      },
      yaxis: {
        min: 0,
        labels: {
          formatter: (val) => `${val.toFixed(2)}h`,
        },
        title: {
          text: 'Duration',
        },
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return `${val.toFixed(2)}h`;
          },
        },
      },
    };

    const healthCheckTimeChart = new ApexCharts(
      document.querySelector('#health-check-time-chart'),
      healthCheckTimeOptions,
    );
    healthCheckTimeChart.render();

    const dockerBuildAndPushTimeOptions = {
      series: [
        {
          name: 'main-amd64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['main-amd64']) return null;
            return [new Date(data.date), data.jobs['main-amd64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'main-arm64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['main-arm64']) return null;
            return [new Date(data.date), data.jobs['main-arm64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'cuda-amd64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['cuda-amd64']) return null;
            return [new Date(data.date), data.jobs['cuda-amd64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'cuda-arm64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['cuda-arm64']) return null;
            return [new Date(data.date), data.jobs['cuda-arm64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'tools-amd64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['tools-amd64']) return null;
            return [new Date(data.date), data.jobs['tools-amd64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
        {
          name: 'tools-arm64',
          data: dockerBuildAndPush.map((data) => {
            if (!data.jobs['tools-arm64']) return null;
            return [new Date(data.date), data.jobs['tools-arm64'] / 3600.0];
          }).filter(item => item !== null && item[1] > 0),
        },
      ],
      chart: {
        height: 500,
        type: 'line',
        zoom: {
          enabled: true,
        },
        selection: {
          enabled: true,
        },
      },
      dataLabels: {
        enabled: false,
      },
      title: {
        text: 'Build duration',
        align: 'left',
      },
      grid: {
        row: {
          colors: ['#f3f3f3', 'transparent'], // takes an array which will be repeated on columns
          opacity: 0.5,
        },
      },
      xaxis: {
        type: 'datetime',
      },
      yaxis: {
        min: 0,
        labels: {
          formatter: (val) => `${val.toFixed(2)}h`,
        },
        title: {
          text: 'Duration',
        },
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return `${val.toFixed(2)}h`;
          },
        },
      },
    };

    const dockerBuildAndPushTimeChart = new ApexCharts(
      document.querySelector('#docker-build-and-push-time-chart'),
      dockerBuildAndPushTimeOptions,
    );
    dockerBuildAndPushTimeChart.render();

    // Docker
    const dockerOptions = {
      series: [
        {
          name: 'core',
          data: json.docker_images['core'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'core-devel',
          data: json.docker_images['core-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'core-common-devel',
          data: json.docker_images['core-common-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-sensing-perception',
          data: json.docker_images['universe-sensing-perception'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-sensing-perception-devel',
          data: json.docker_images['universe-sensing-perception-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-localization-mapping',
          data: json.docker_images['universe-localization-mapping'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-localization-mapping-devel',
          data: json.docker_images['universe-localization-mapping-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-planning-control',
          data: json.docker_images['universe-planning-control'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-planning-control-devel',
          data: json.docker_images['universe-planning-control-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-visualization',
          data: json.docker_images['universe-visualization'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-visualization-devel',
          data: json.docker_images['universe-visualization-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe',
          data: json.docker_images['universe'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-devel',
          data: json.docker_images['universe-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-common-devel',
          data: json.docker_images['universe-common-devel'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-sensing-perception-cuda',
          data: json.docker_images['universe-sensing-perception-cuda'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-sensing-perception-devel-cuda',
          data: json.docker_images['universe-sensing-perception-devel-cuda'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-cuda',
          data: json.docker_images['universe-cuda'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
        {
          name: 'universe-devel-cuda',
          data: json.docker_images['universe-devel-cuda'].map((data) => {
            return [new Date(data.date), data.size / 1024 / 1024 / 1024];
          }),
        },
      ],
      chart: {
        height: 500,
        type: 'line',
        zoom: {
          enabled: true,
        },
      },
      dataLabels: {
        enabled: false,
      },
      title: {
        text: 'Docker Image Size',
        align: 'left',
      },
      xaxis: {
        type: 'datetime',
      },
      yaxis: {
        min: 0,
        labels: {
          formatter: (val) => `${val.toFixed(2)}GB`,
        },
        title: {
          text: 'Size',
        },
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return `${val.toFixed(2)}GB`;
          },
        },
      },
    };

    const dockerChart = new ApexCharts(
      document.querySelector('#docker-chart'),
      dockerOptions,
    );
    dockerChart.render();
  })
  .catch((error) => {
    console.log('Error loading github_action_data.json:', error);
  });

// Load and visualize stars history
fetch('stars_history.json')
  .then((res) => res.json())
  .then((json) => {
    const series = [];

    // Add total stars history
    series.push({
      name: 'Total Stars',
      data: json.total_stars_history.map((item) => [
        new Date(item.date),
        item.star_count,
      ]),
    });

    // Add a few key repositories
    const keyRepos = [
      'autoware_stars_history',
      'autoware_core_stars_history',
      'autoware_universe_stars_history',
      'autoware.privately-owned-vehicles_stars_history',
    ];

    keyRepos.forEach((repoKey) => {
      if (json[repoKey]) {
        const repoName = repoKey.replace('_stars_history', '');
        series.push({
          name: repoName,
          data: json[repoKey].map((item) => [
            new Date(item.date),
            item.star_count,
          ]),
        });
      }
    });

    const starsOptions = {
      series: series,
      chart: {
        height: 500,
        type: 'line',
        zoom: {
          enabled: true,
        },
        selection: {
          enabled: true,
        },
      },
      dataLabels: {
        enabled: false,
      },
      title: {
        text: 'GitHub Stars Over Time',
        align: 'left',
      },
      grid: {
        row: {
          colors: ['#f3f3f3', 'transparent'],
          opacity: 0.5,
        },
      },
      xaxis: {
        type: 'datetime',
      },
      yaxis: {
        min: 0,
        title: {
          text: 'Number of Stars',
        },
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return `${Math.round(val).toLocaleString()}`;
          },
        },
      },
      colors: ['#00D9FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3', '#F38181'],
    };

    const starsChart = new ApexCharts(
      document.querySelector('#stars-chart'),
      starsOptions,
    );
    starsChart.render();

    // Display latest numbers above the chart
    const latestTotalStarsEntry = json.total_stars_history.length > 0
      ? json.total_stars_history[json.total_stars_history.length - 1]
      : null;
    const latestTotalStars = latestTotalStarsEntry ? latestTotalStarsEntry.star_count : 0;
    const latestDate = latestTotalStarsEntry
      ? new Date(latestTotalStarsEntry.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      : 'N/A';
    const statsHtml = `
      <div style="margin-bottom: 10px;">
        <span style="font-size: 14px; color: #666;">Last updated: <strong>${latestDate}</strong></span>
      </div>
      <div style="display: flex; gap: 30px; flex-wrap: wrap;">
        <div>
          <strong style="font-size: 14px; color: #666;">Total Stars:</strong>
          <span style="font-size: 24px; font-weight: bold; color: #00D9FF; margin-left: 10px;">${latestTotalStars.toLocaleString()}</span>
        </div>
        ${keyRepos.map((repoKey) => {
          if (json[repoKey] && json[repoKey].length > 0) {
            const repoName = repoKey.replace('_stars_history', '');
            const latestCount = json[repoKey][json[repoKey].length - 1].star_count;
            return `
              <div>
                <strong style="font-size: 14px; color: #666;">${repoName}:</strong>
                <span style="font-size: 24px; font-weight: bold; color: #333; margin-left: 10px;">${latestCount.toLocaleString()}</span>
              </div>
            `;
          }
          return '';
        }).join('')}
      </div>
    `;
    document.querySelector('#stars-stats').innerHTML = statsHtml;
  })
  .catch((error) => {
    console.log('Error loading stars/stars_history.json:', error);
    document.querySelector('#stars-chart').innerHTML =
      '<p style="color: #666;">Stars history data not available</p>';
  });

// Load and visualize contributor history
fetch('contributors_history.json')
  .then((res) => res.json())
  .then((json) => {
    const series = [
      {
        name: 'All Contributors',
        data: json.autoware_contributors.map((item) => [
          new Date(item.date),
          item.contributors_count,
        ]),
      },
      {
        name: 'Code Contributors',
        data: json.autoware_code_contributors.map((item) => [
          new Date(item.date),
          item.contributors_count,
        ]),
      },
      {
        name: 'Community Contributors',
        data: json.autoware_community_contributors.map((item) => [
          new Date(item.date),
          item.contributors_count,
        ]),
      },
    ];

    const contributorsOptions = {
      series: series,
      chart: {
        height: 500,
        type: 'line',
        zoom: {
          enabled: true,
        },
        selection: {
          enabled: true,
        },
      },
      dataLabels: {
        enabled: false,
      },
      title: {
        text: 'Contributor Growth Over Time',
        align: 'left',
      },
      grid: {
        row: {
          colors: ['#f3f3f3', 'transparent'],
          opacity: 0.5,
        },
      },
      xaxis: {
        type: 'datetime',
      },
      yaxis: {
        min: 0,
        title: {
          text: 'Number of Contributors',
        },
      },
      tooltip: {
        y: {
          formatter: function (val) {
            return `${Math.round(val).toLocaleString()}`;
          },
        },
      },
      colors: ['#00D9FF', '#FF6B6B', '#4ECDC4'],
      legend: {
        position: 'top',
        horizontalAlign: 'right',
      },
    };

    const contributorsChart = new ApexCharts(
      document.querySelector('#contributors-chart'),
      contributorsOptions,
    );
    contributorsChart.render();

    // Display latest numbers above the chart
    const latestAllContributorsEntry = json.autoware_contributors.length > 0
      ? json.autoware_contributors[json.autoware_contributors.length - 1]
      : null;
    const latestAllContributors = latestAllContributorsEntry ? latestAllContributorsEntry.contributors_count : 0;
    const latestCodeContributors = json.autoware_code_contributors.length > 0
      ? json.autoware_code_contributors[json.autoware_code_contributors.length - 1].contributors_count
      : 0;
    const latestCommunityContributors = json.autoware_community_contributors.length > 0
      ? json.autoware_community_contributors[json.autoware_community_contributors.length - 1].contributors_count
      : 0;
    const latestDate = latestAllContributorsEntry
      ? new Date(latestAllContributorsEntry.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      : 'N/A';
    const statsHtml = `
      <div style="margin-bottom: 10px;">
        <span style="font-size: 14px; color: #666;">Last updated: <strong>${latestDate}</strong></span>
      </div>
      <div style="display: flex; gap: 30px; flex-wrap: wrap;">
        <div>
          <strong style="font-size: 14px; color: #666;">All Contributors:</strong>
          <span style="font-size: 24px; font-weight: bold; color: #00D9FF; margin-left: 10px;">${latestAllContributors.toLocaleString()}</span>
        </div>
        <div>
          <strong style="font-size: 14px; color: #666;">Code Contributors:</strong>
          <span style="font-size: 24px; font-weight: bold; color: #FF6B6B; margin-left: 10px;">${latestCodeContributors.toLocaleString()}</span>
        </div>
        <div>
          <strong style="font-size: 14px; color: #666;">Community Contributors:</strong>
          <span style="font-size: 24px; font-weight: bold; color: #4ECDC4; margin-left: 10px;">${latestCommunityContributors.toLocaleString()}</span>
        </div>
      </div>
    `;
    document.querySelector('#contributors-stats').innerHTML = statsHtml;
  })
  .catch((error) => {
    console.log('Error loading contributor_history/contributors_history.json:', error);
    document.querySelector('#contributors-chart').innerHTML =
      '<p style="color: #666;">Contributor history data not available</p>';
  });
