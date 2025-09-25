$(document).ready(function () {

    let currentPage = 1;
    let lastGrado = null;
    let lastTotal = 0;
    let lastPages = 1;
    let lastPerPage = 10;

    $('#btn-filtrar').click(function () {
        currentPage = 1;
        cargarDatosPaginado();
    });

    function cargarDatosPaginado(page = 1) {
        const grado = $('#select-grado').val();
        lastGrado = grado;
        $('#tabla-posiciones').html(`
            <tr>
                <td colspan="7" class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos...</p>
                </td>
            </tr>
        `);
        $.ajax({
            url: baseUrl,
            type: 'GET',
            data: {
                curso: grado,
                page: page,
                per_page: lastPerPage
            },
            success: function (response) {
                if (response.error) {
                    mostrarError(response.error);
                    $('#tabla-posiciones').html(`
                        <tr>
                            <td colspan="7" class="text-center py-5 text-danger">
                                ${response.error}
                            </td>
                        </tr>
                    `);
                    $('#texto-resultados').text('');
                    $('#pagination-container').html('');
                    return;
                }
                actualizarTabla(response.data);
                $('#texto-resultados').text(`${response.total_estudiantes} estudiantes encontrados`);
                lastTotal = response.total_estudiantes;
                if (response.pagination) {
                    lastPages = response.pagination.pages;
                    lastPerPage = response.pagination.per_page;
                    renderPaginacion(response.pagination);
                } else {
                    $('#pagination-container').html('');
                }
            },
            error: function () {
                mostrarError('Error al cargar los datos');
                $('#tabla-posiciones').html(`
                    <tr>
                        <td colspan="7" class="text-center py-5 text-danger">
                            Error al cargar los datos
                        </td>
                    </tr>
                `);
                $('#pagination-container').html('');
            }
        });
    }

    function renderPaginacion(pagination) {
        let html = '';
        if (pagination.total === 0) {
            $('#pagination-container').html('');
            return;
        }
        html += `<div class="d-flex justify-content-between align-items-center">
            <div class="text-muted small">
                Mostrando ${(pagination.page - 1) * pagination.per_page + 1} - ${Math.min(pagination.page * pagination.per_page, pagination.total)} de ${pagination.total} registros
            </div>
            <nav aria-label="Paginación">
                <ul class="pagination pagination-sm mb-0">
        `;
        if (pagination.has_prev) {
            html += `<li class="page-item"><a class="page-link" href="#" data-page="${pagination.prev_num}"><i class="fas fa-chevron-left"></i></a></li>`;
        } else {
            html += `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-left"></i></span></li>`;
        }
        // Generar páginas abreviadas como en Flask iter_pages
        const pages = generatePageList(pagination.page, pagination.pages, 1, 1, 2, 3);
        pages.forEach(item => {
            if (item === '...') {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            } else if (item === pagination.page) {
                html += `<li class="page-item active"><span class="page-link">${item}</span></li>`;
            } else {
                html += `<li class="page-item"><a class="page-link" href="#" data-page="${item}">${item}</a></li>`;
            }
        });
        if (pagination.has_next) {
            html += `<li class="page-item"><a class="page-link" href="#" data-page="${pagination.next_num}"><i class="fas fa-chevron-right"></i></a></li>`;
        } else {
            html += `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-right"></i></span></li>`;
        }
        html += `</ul></nav></div>`;
        $('#pagination-container').html(html);
        $('#pagination-container .page-link[data-page]').click(function (e) {
            e.preventDefault();
            const page = parseInt($(this).data('page'));
            if (!isNaN(page)) {
                currentPage = page;
                cargarDatosPaginado(page);
            }
        });
    }

    // Función helper para generar lista de páginas abreviadas
    function generatePageList(current, total, leftEdge, rightEdge, leftCurrent, rightCurrent) {
        const pages = [];
        if (total <= 1) return [1];

        // Siempre incluir primera página
        pages.push(1);

        // Calcular rango alrededor de la página actual
        const start = Math.max(2, current - leftCurrent);
        const end = Math.min(total - 1, current + rightCurrent);

        // Agregar ... si hay gap después de 1
        if (start > 2) {
            pages.push('...');
        }

        // Agregar páginas del rango
        for (let i = start; i <= end; i++) {
            if (!pages.includes(i)) {
                pages.push(i);
            }
        }

        // Agregar ... si hay gap antes de la última
        if (end < total - 1) {
            pages.push('...');
        }

        // Siempre incluir última página si no es 1
        if (total > 1 && !pages.includes(total)) {
            pages.push(total);
        }

        return pages;
    }

    // Actualizar tabla con los datos recibidos
    function actualizarTabla(datos) {
        const $tbody = $('#tabla-posiciones');
        $tbody.empty();

        if (datos.length === 0) {
            $tbody.html(`
                    <tr>
                        <td colspan="7" class="text-center py-5 text-muted">
                            No se encontraron resultados para los filtros seleccionados
                        </td>
                    </tr>
                `);
            return;
        }

        datos.forEach((estudiante, index) => {
            let iconoMedalla = '';
            let claseMedalla = '';

            if (estudiante.posicion === 1) {
                iconoMedalla = '<i class="fas fa-trophy medal-icon gold"></i>';
                claseMedalla = 'gold';
            } else if (estudiante.posicion === 2) {
                iconoMedalla = '<i class="fas fa-medal medal-icon silver"></i>';
                claseMedalla = 'silver';
            } else if (estudiante.posicion === 3) {
                iconoMedalla = '<i class="fas fa-medal medal-icon bronze"></i>';
                claseMedalla = 'bronze';
            }

            const fotoUrl = estudiante.foto
                ? `/static/uploads/profiles/${estudiante.foto}`
                : '/static/img/default-profile.png';

            const $fila = $(`
                <tr class="cursor-pointer" data-id="${estudiante.id}">
                    <td class="${claseMedalla}">
                        ${iconoMedalla}
                        <span class="fw-bold">${estudiante.posicion}°</span>
                    </td>
                    <td>
                        <img src="${fotoUrl}" class="student-avatar">
                    </td>
                    <td>${estudiante.nombre}</td>
                    <td>${estudiante.curso}</td>
                    <td>
                        <span class="fw-bold">${estudiante.promedio}</span>
                        <div class="progress progress-thin mt-1">
                            <div class="progress-bar bg-success" 
                                 role="progressbar" 
                                 style="width: ${estudiante.promedio * 10}%" 
                                 aria-valuenow="${estudiante.promedio}" 
                                 aria-valuemin="0" 
                                 aria-valuemax="10">
                            </div>
                        </div>
                    </td>
                    <td>${estudiante.cantidad_asignaturas}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-info btn-ver-detalles">
                            <i class="fas fa-eye me-1"></i>
                        </button>
                    </td>
                </tr>
                `);

            $tbody.append($fila);

            // Evento para el botón de detalles
            $fila.find('.btn-detalles').click(function (e) {
                e.stopPropagation();
                mostrarDetalles(estudiante);
            });

            // Evento para hacer clic en toda la fila
            $fila.click(function () {
                mostrarDetalles(estudiante);
            });
        });
    }

    // Mostrar detalles del estudiante
    function mostrarDetalles(estudiante) {
        const fotoUrl = estudiante.foto
            ? `/static/uploads/profiles/${estudiante.foto}`
            : '/static/img/default-profile.png';

        // Actualizar información básica
        $('#detalle-foto').attr('src', fotoUrl);
        $('#detalle-nombre').text(estudiante.nombre);
        $('#detalle-documento').text(estudiante.documento);
        $('#detalle-curso').text(estudiante.curso);
        $('#detalle-promedio').text(estudiante.promedio);

        // Configurar barra de progreso
        const porcentaje = estudiante.promedio * 10;
        const $progress = $('#detalle-progress');
        $progress.css('width', porcentaje + '%');

        if (estudiante.promedio >= 9) {
            $progress.removeClass('bg-warning bg-danger').addClass('bg-success');
        } else if (estudiante.promedio >= 7) {
            $progress.removeClass('bg-success bg-danger').addClass('bg-warning');
        } else {
            $progress.removeClass('bg-success bg-warning').addClass('bg-danger');
        }

        // Cargar calificaciones
        $('#detalle-calificaciones').html(`
                <tr>
                    <td colspan="4" class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Cargando...</span>
                        </div>
                    </td>
                </tr>
            `);

        $.ajax({
            url: `${baseUrlDetalles}/${estudiante.id}`,
            type: 'GET',
            success: function (response) {
                const $tbody = $('#detalle-calificaciones');
                $tbody.empty();

                if (response.historial.length === 0) {
                    $tbody.html(`
                            <tr>
                                <td colspan="4" class="text-center py-4 text-muted">
                                    No se encontraron calificaciones registradas
                                </td>
                            </tr>
                        `);
                    return;
                }

                response.historial.forEach(calificacion => {
                    let claseNota = '';
                    if (calificacion.nota >= 9) {
                        claseNota = 'text-success fw-bold';
                    } else if (calificacion.nota >= 7) {
                        claseNota = 'text-primary';
                    } else {
                        claseNota = 'text-danger';
                    }

                    $tbody.append(`
                            <tr>
                                <td>${calificacion.asignatura}</td>
                                <td class="${claseNota}">${calificacion.nota}</td>
                                <td>${calificacion.fecha}</td>
                                <td class="small">${calificacion.observacion}</td>
                            </tr>
                        `);
                });
            },
            error: function () {
                $('#detalle-calificaciones').html(`
                        <tr>
                            <td colspan="4" class="text-center py-4 text-danger">
                                Error al cargar las calificaciones
                            </td>
                        </tr>
                    `);
            }
        });

        // Mostrar modal
        $('#modalDetalles').modal('show');
    }

    // Función para mostrar errores
    function mostrarError(mensaje) {
        const toastHTML = `
                <div class="toast align-items-center text-white bg-danger border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas fa-exclamation-circle me-2"></i> ${mensaje}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                </div>
            `;

        // Mostrar toast
        $('.position-fixed').append(toastHTML);
        setTimeout(() => {
            $('.toast').last().remove();
        }, 5000);
    }

    // Cargar datos iniciales si hay parámetros en la URL
    const urlParams = new URLSearchParams(window.location.search);
    const gradoParam = urlParams.get('curso');

    if (gradoParam) {
        $('#btn-filtrar').click();
    }
});