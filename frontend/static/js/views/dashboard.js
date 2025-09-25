
 // Gráfico de Matrículas por Grado
const matriculasCtx = document.getElementById('matriculasChart').getContext('2d');
const matriculasChart = new Chart(matriculasCtx, {
    type: 'bar',
    data: {
        labels: {{ cursos_nombres|tojson }},
        datasets: [{
            label: 'Matrículas',
            data: {{ matriculas_por_curso|tojson }},
            backgroundColor: 'rgba(255, 102, 0, 0.7)',
            borderColor: 'rgba(255, 102, 0, 1)',
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    precision: 0
                }
            }
        }
    }
});

// Gráfico de Asistencia Semanal
const asistenciaCtx = document.getElementById('asistenciaChart').getContext('2d');
const asistenciaChart = new Chart(asistenciaCtx, {
    type: 'line',
    data: {
        labels: {{ dias_semana|tojson }},
        datasets: [{
            label: 'Porcentaje de Asistencia',
            data: {{ asistencia_semanal|tojson }},
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 2,
            tension: 0.1,
            fill: true
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: false,
                min: 80,
                max: 100,
                ticks: {
                    callback: function(value) {
                        return value + '%';
                    }
                }
            }
        }
    }
});

// Gráfico de Docentes por Asignatura
const docentesCtx = document.getElementById('docentesChart').getContext('2d');
const docentesChart = new Chart(docentesCtx, {
    type: 'doughnut',
    data: {
        labels: {{ asignaturas_nombres|tojson }},
        datasets: [{
            data: {{ docentes_por_asignatura|tojson }},
            backgroundColor: [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)',
                'rgba(255, 159, 64, 0.7)'
            ],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'right',
            }
        }
    }
});