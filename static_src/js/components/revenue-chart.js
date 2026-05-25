import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

export default () => ({
  chart: null,
  init() {
    const canvas = this.$el
    this.chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Revenue',
          data: [],
          borderColor: '#4F46E5',
          backgroundColor: 'rgba(79, 70, 229, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#4F46E5',
          borderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: (v) => '$' + v },
          },
        },
      },
    })
  },
  destroy() {
    if (this.chart) this.chart.destroy()
  },
})
