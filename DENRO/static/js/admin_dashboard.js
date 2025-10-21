// document.addEventListener("DOMContentLoaded", function() {
//   // Report Status Overview Chart
//   const reportStatusCtx = document.getElementById('reportStatusChart');
//   if (reportStatusCtx) {
//     new Chart(reportStatusCtx, {
//       type: 'bar',
//       data: {
//         labels: ['Pending', 'Accepted', 'Declined'],
//         datasets: [{
//           label: 'Report Counts',
//           data: [
//             parseInt(reportStatusCtx.dataset.pending) || 0,
//             parseInt(reportStatusCtx.dataset.accepted) || 0,
//             parseInt(reportStatusCtx.dataset.declined) || 0
//           ],
//           backgroundColor: ['#ffc107', '#20c997', '#dc3545'],
//           borderRadius: 6
//         }]
//       },
//       options: {
//         responsive: true,
//         maintainAspectRatio: false,
//         plugins: {
//           legend: { position: 'bottom' },
//           title: { display: false }
//         },
//         scales: {
//           x: { stacked: true },
//           y: { beginAtZero: true, stacked: true }
//         }
//       }
//     });
//   }

//   // Account Status Doughnut Chart
//   const accountStatusCtx = document.getElementById('accountStatusChart');
//   if (accountStatusCtx) {
//     new Chart(accountStatusCtx, {
//       type: 'doughnut',
//       data: {
//         labels: ['Approved', 'Pending', 'Rejected', 'Deactivated'],
//         datasets: [{
//           data: [
//             parseInt(accountStatusCtx.dataset.approved) || 0,
//             parseInt(accountStatusCtx.dataset.pending) || 0,
//             parseInt(accountStatusCtx.dataset.rejected) || 0,
//             parseInt(accountStatusCtx.dataset.deactivated) || 0
//           ],
//           backgroundColor: ['#20c997', '#dc3545', '#6c757d', '#ffc107']
//         }]
//       },
//       options: {
//         responsive: true,
//         maintainAspectRatio: false,
//         plugins: {
//           legend: { display: true, position: 'bottom' },
//           title: { display: false }
//         }
//       }
//     });
//   }

//   // Notifications toggle
//   const notifBtn = document.getElementById("notifBtn");
//   const notifDropdown = document.getElementById("notifDropdown");
//   if (notifBtn && notifDropdown) {
//     notifBtn.addEventListener("click", function(e) {
//       e.stopPropagation();
//       notifDropdown.style.display =
//         notifDropdown.style.display === "block" ? "none" : "block";
//     });
//     document.addEventListener("click", function(event) {
//       if (!notifBtn.contains(event.target) && !notifDropdown.contains(event.target)) {
//         notifDropdown.style.display = "none";
//       }
//     });
//   }
// });

document.addEventListener("DOMContentLoaded", function() {
  // Report Status Overview Chart
  const reportStatusCtx = document.getElementById('reportStatusChart');
  if (reportStatusCtx) {
    new Chart(reportStatusCtx, {
      type: 'bar',
      data: {
        labels: ['Pending', 'Accepted', 'Declined'],
        datasets: [{
          label: 'Report Counts',
          data: [
            parseInt(reportStatusCtx.dataset.pending) || 0,
            parseInt(reportStatusCtx.dataset.accepted) || 0,
            parseInt(reportStatusCtx.dataset.declined) || 0
          ],
          backgroundColor: ['#ffc107', '#20c997', '#dc3545'],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          title: { display: false }
        },
        scales: {
          x: { stacked: true },
          y: { beginAtZero: true, stacked: true }
        }
      }
    });
  }

  // Account Status Doughnut Chart
  const accountStatusCtx = document.getElementById('accountStatusChart');
  if (accountStatusCtx) {
    new Chart(accountStatusCtx, {
      type: 'doughnut',
      data: {
        labels: ['Approved', 'Pending', 'Rejected', 'Deactivated'],
        datasets: [{
          data: [
            parseInt(accountStatusCtx.dataset.approved) || 0,
            parseInt(accountStatusCtx.dataset.pending) || 0,
            parseInt(accountStatusCtx.dataset.rejected) || 0,
            parseInt(accountStatusCtx.dataset.deactivated) || 0
          ],
          backgroundColor: ['#20c997', '#dc3545', '#6c757d', '#ffc107']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'bottom' },
          title: { display: false }
        }
      }
    });
  }

  // Reports per Protected Area Chart
  const reportsPerPACtx = document.getElementById('reportsPerPAChart');
  if (reportsPerPACtx) {
    const labels = reportsPerPACtx.dataset.labels ? reportsPerPACtx.dataset.labels.split(',') : [];
    const counts = reportsPerPACtx.dataset.counts ? reportsPerPACtx.dataset.counts.split(',').map(Number) : [];
    console.log('Reports per PA labels:', labels);
    console.log('Reports per PA counts:', counts);
    new Chart(reportsPerPACtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Number of Reports',
          data: counts,
          backgroundColor: '#007bff',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          title: { display: false }
        },
        scales: {
          x: { beginAtZero: true },
          y: { beginAtZero: true }
        }
      }
    });
  } else {
    console.log('Reports per PA Canvas not found');
  }

  // Notifications toggle
  const notifBtn = document.getElementById("notifBtn");
  const notifDropdown = document.getElementById("notifDropdown");
  if (notifBtn && notifDropdown) {
    notifBtn.addEventListener("click", function(e) {
      e.stopPropagation();
      notifDropdown.style.display =
        notifDropdown.style.display === "block" ? "none" : "block";
    });
    document.addEventListener("click", function(event) {
      if (!notifBtn.contains(event.target) && !notifDropdown.contains(event.target)) {
        notifDropdown.style.display = "none";
      }
    });
  }
});
