document.addEventListener('DOMContentLoaded', function () {
    let cursoSeleccionado = null;
    let currentPage = 1;
    let datosCache = {};

    const selectGrado = document.getElementById('select-grado');
    const btnFiltrar = document.getElementById('btn-filtrar');
    const tablaLibroFinal = document.getElementById('tabla-libro-final');
    const totalEstudiantesEl = document.getElementById('total-estudiantes');
    const totalAprobadosEl = document.getElementById('total-aprobados');
    const totalNoAprobadosEl = document.getElementById('total-no-aprobados');
    const btnExportar = document.getElementById('btn-exportar');
    const modalConfiguracion = document.getElementById('modalConfiguracionLibro');
    const btnGuardarConfig = document.getElementById('btn-guardar-config');

    btnFiltrar?.addEventListener('click', () => filtrarDatos(1));

    btnExportar?.addEventListener('click', () => {
        if (!cursoSeleccionado) {
            mostrarNotificacion('Por favor, filtre los datos antes de exportar.', 'warning');
            return;
        }
        const modal = new bootstrap.Modal(document.getElementById('modalExportacion'));
        modal.show();
    });

    modalConfiguracion?.addEventListener('show.bs.modal', cargarConfiguracion);
    btnGuardarConfig?.addEventListener('click', guardarConfiguracion);

    function filtrarDatos(page = 1) {
        const cursoId = selectGrado.value;

        if (!cursoId || cursoId === 'Seleccionar Grado...') {
            mostrarNotificacion('Por favor, seleccione un grado.', 'warning');
            return;
        }

        cursoSeleccionado = cursoId;
        currentPage = page;
        mostrarLoading();

        const cacheKey = `${cursoId}-${page}`;
        if (datosCache[cacheKey]) {
            actualizarInterfaz(datosCache[cacheKey]);
            return;
        }

        fetch(`/libro_final/datos?curso=${cursoId}&page=${page}`)
            .then(response => {
                if (!response.ok) throw new Error('Error en la respuesta del servidor');
                return response.json();
            })
            .then(data => {
                if (data.error) throw new Error(data.error);

                datosCache[cacheKey] = data;
                actualizarInterfaz(data);
            })
            .catch(error => {
                console.error('Error al filtrar datos:', error);
                mostrarNotificacion('Error al cargar datos: ' + error.message, 'danger');
                mostrarMensajeError(error.message);
            });
    }

    function actualizarInterfaz(data) {
        actualizarTabla(data.estudiantes);
        actualizarEstadisticas(data.estadisticas);
        actualizarPaginacion(data.pagination);
    }

    function actualizarTabla(estudiantes) {
        tablaLibroFinal.innerHTML = '';

        if (estudiantes.length === 0) {
            tablaLibroFinal.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted p-4">
                    <i class="fas fa-info-circle me-2"></i>No hay estudiantes para los criterios seleccionados.
                </td>
            </tr>`;
            return;
        }

        estudiantes.forEach((estudiante, index) => {
            const row = document.createElement('tr');
            const estadoBadge = getEstadoBadge(estudiante.estado);
            const promedioColor = estudiante.estado === 'Aprobado' ? 'text-success' :
                (estudiante.estado === 'No Aprobado' ? 'text-danger' : '');

            row.innerHTML = `
            <td>${((currentPage - 1) * 10) + index + 1}</td>
            <td>
                <img src="/static/uploads/profiles/${estudiante.foto}" 
                         class="rounded-circle me-3" 
                         style="width: 40px; height: 40px; object-fit: cover;" 
                         onerror="this.onerror=null;this.src='/static/img/default-profile.png';">
            </td>
            <td>${estudiante.nombres}</td>
            <td>${estudiante.documento}</td>
            <td class="fw-bold ${promedioColor}">${estudiante.promedio_periodo}</td>
            <td><span class="badge ${estadoBadge}">${estudiante.estado}</span></td>
            <td>
                <button class="btn btn-sm btn-outline-info btn-ver-detalle" 
                        title="Ver Detalle"
                        data-id="${estudiante.id}">
                    <i class="fas fa-eye"></i>
                </button>
                <a href="/libro_final/exportar_individual_pdf/${estudiante.id}" class="btn btn-sm btn-outline-success" onclick="exportarPDF()" title="Descargar Detalle (PDF)">
                    <i class="fas fa-download"></i>
                </a>

            </td>`;

            tablaLibroFinal.appendChild(row);
        });

        document.querySelectorAll('.btn-ver-detalle').forEach(btn => {
            btn.addEventListener('click', function () {
                const estudianteId = this.getAttribute('data-id');
                verDetalleEstudiante(estudianteId);
            });
        });
    }

    function actualizarPaginacion(pagination) {
        const paginationContainer = document.getElementById('pagination-container');
        if (!paginationContainer) return;

        paginationContainer.innerHTML = '';

        if (pagination.total === 0) return;

        let paginationHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="text-muted small">
                Mostrando ${((pagination.page - 1) * pagination.per_page) + 1} - ${Math.min(pagination.page * pagination.per_page, pagination.total)} de ${pagination.total} registros
            </div>
            <nav aria-label="Paginación">
                <ul class="pagination pagination-sm mb-0">
    `;

        if (pagination.has_prev) {
            paginationHTML += `<li class="page-item"><a class="page-link" href="#" data-page="${pagination.prev_num}"><i class="fas fa-chevron-left"></i></a></li>`;
        } else {
            paginationHTML += `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-left"></i></span></li>`;
        }

        // Generar páginas abreviadas como en Flask iter_pages
        const pages = generatePageList(pagination.page, pagination.pages, 1, 1, 2, 3);
        pages.forEach(item => {
            if (item === '...') {
                paginationHTML += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            } else if (item === pagination.page) {
                paginationHTML += `<li class="page-item active"><span class="page-link">${item}</span></li>`;
            } else {
                paginationHTML += `<li class="page-item"><a class="page-link" href="#" data-page="${item}">${item}</a></li>`;
            }
        });

        if (pagination.has_next) {
            paginationHTML += `<li class="page-item"><a class="page-link" href="#" data-page="${pagination.next_num}"><i class="fas fa-chevron-right"></i></a></li>`;
        } else {
            paginationHTML += `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-right"></i></span></li>`;
        }

        paginationHTML += `
                </ul>
            </nav>
        </div>
    `;

        paginationContainer.innerHTML = paginationHTML;

        paginationContainer.querySelectorAll('.page-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.closest('.page-link').dataset.page);
                filtrarDatos(page);
            });
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

    function verDetalleEstudiante(estudianteId, page = 1) {
        console.log('verDetalleEstudiante called with estudianteId:', estudianteId, 'page:', page);
        if (!estudianteId) {
            mostrarNotificacion('Datos incompletos para cargar el detalle.', 'warning');
            return;
        }

        const modalElement = document.getElementById('modalDetalleEstudiante');
        const modal = bootstrap.Modal.getInstance(modalElement) || new bootstrap.Modal(modalElement);
        const modalBody = modalElement.querySelector('.modal-body');

        // Mostrar loading
        modalBody.innerHTML = `
        <div class="text-center p-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <p class="mt-2">Cargando detalles del estudiante...</p>
        </div>`;

        // Solo mostrar el modal si no está ya visible
        if (!modalElement.classList.contains('show')) {
            modal.show();
            console.log('Modal shown');
        } else {
            console.log('Modal already visible');
        }

        // Verificar caché primero (incluyendo página)
        const cacheKey = `detalle-${estudianteId}-page-${page}`;
        if (datosCache[cacheKey]) {
            console.log('Using cached data for', cacheKey);
            mostrarDetalleEnModal(datosCache[cacheKey], modalBody, estudianteId);
            return;
        }

        console.log('Fetching data from /libro_final/detalle_estudiante/' + estudianteId + '?page=' + page);
        fetch(`/libro_final/detalle_estudiante/${estudianteId}?page=${page}`)
            .then(response => {
                console.log('Fetch response status:', response.status);
                if (!response.ok) throw new Error('Error al cargar detalles (status: ' + response.status + ')');
                return response.json();
            })
            .then(data => {
                console.log('Data received:', data);
                if (data.error) throw new Error(data.error);

                // Almacenar en caché
                datosCache[cacheKey] = data;
                mostrarDetalleEnModal(data, modalBody, estudianteId);
            })
            .catch(error => {
                console.error('Error in fetch:', error);
                modalBody.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    ${error.message || 'Error al cargar los detalles del estudiante'}
                </div>`;
            });
    }

    function mostrarDetalleEnModal(datos, modalBody, estudianteId) {
        console.log('mostrarDetalleEnModal called with datos:', datos);
        const config = { minimumFractionDigits: 1, maximumFractionDigits: 1 };

        let paginationHTML = '';
        if (datos.pagination && datos.pagination.pages > 1) {
            paginationHTML = `
            <div class="d-flex justify-content-center mt-3">
                <nav aria-label="Paginación de asignaturas">
                    <ul class="pagination pagination-sm mb-0">
                        ${datos.pagination.has_prev ? `<li class="page-item"><a class="page-link" href="#" data-page="${datos.pagination.prev_num}"><i class="fas fa-chevron-left"></i></a></li>` : `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-left"></i></span></li>`}
                        <li class="page-item active"><span class="page-link">${datos.pagination.page}</span></li>
                        ${datos.pagination.has_next ? `<li class="page-item"><a class="page-link" href="#" data-page="${datos.pagination.next_num}"><i class="fas fa-chevron-right"></i></a></li>` : `<li class="page-item disabled"><span class="page-link"><i class="fas fa-chevron-right"></i></span></li>`}
                    </ul>
                </nav>
            </div>
            <div class="text-center text-muted small mt-2">
                Mostrando ${((datos.pagination.page - 1) * datos.pagination.per_page) + 1} - ${Math.min(datos.pagination.page * datos.pagination.per_page, datos.pagination.total)} de ${datos.pagination.total} asignaturas
            </div>`;
        }

        modalBody.innerHTML = `
    <div class="row">
        <div class="col-md-4 text-center">
            <img src="/static/uploads/profiles/${datos.foto || 'default-profile.png'}"
                 class="img-fluid rounded-circle mb-3 shadow-sm"
                 style="width: 150px; height: 150px; object-fit: cover;"
                 onerror="this.onerror=null;this.src='/static/img/default-profile.png';">
            <h5 class="mb-1">${datos.nombres}</h5>
            <p class="text-muted mb-3">${datos.documento || 'Sin documento'}</p>
            <div class="card bg-light mb-3">
                <div class="card-body py-2">
                    <p class="mb-1"><strong>Promedio General:</strong>
                        <span class="badge bg-primary">${datos.promedio_general.toLocaleString(undefined, config)}</span>
                    </p>
                    <p class="mb-1"><strong>Estado:</strong>
                        <span class="badge ${datos.estado_general === 'Aprobado' ? 'bg-success' : 'bg-danger'}">
                            ${datos.estado_general}
                        </span>
                    </p>
                    <p class="mb-0"><small class="text-dark"><strong>Nivel de aprobación:</strong> ${datos.nota_basico}</small></p>
                </div>
            </div>
        </div>
        <div class="col-md-8">
            <h5 class="mb-3 border-bottom pb-2">
                <i class="fas fa-book-open me-2"></i>Calificaciones por asignatura
            </h5>
            <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead class="table-light">
                        <tr>
                            <th>Asignatura</th>
                            <th class="text-center">Promedio</th>
                            <th class="text-center">N° Notas</th>
                            <th class="text-center">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${datos.calificaciones.length > 0 ? datos.calificaciones.map(cal => `
                            <tr>
                                <td>${cal.asignatura}</td>
                                <td class="text-center fw-bold ${cal.promedio >= datos.nota_basico ? 'text-success' : 'text-danger'}">
                                    ${cal.promedio.toLocaleString(undefined, config)}
                                </td>
                                <td class="text-center">${cal.cantidad_notas}</td>
                                <td class="text-center">
                                    <span class="badge ${cal.promedio >= datos.nota_basico ? 'bg-success' : 'bg-danger'}">
                                        ${cal.estado}
                                    </span>
                                </td>
                            </tr>
                        `).join('') : '<tr><td colspan="4" class="text-center text-muted">No hay calificaciones disponibles</td></tr>'}
                    </tbody>
                </table>
            </div>
            ${paginationHTML}
        </div>
    </div>`;

        // Agregar event listeners para la paginación
        modalBody.querySelectorAll('.page-link[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.closest('.page-link').dataset.page);
                verDetalleEstudiante(estudianteId, page);
            });
        });
    }
    function actualizarEstadisticas(stats) {
        totalEstudiantesEl.textContent = stats.total_estudiantes || 0;
        totalAprobadosEl.textContent = stats.aprobados || 0;
        totalNoAprobadosEl.textContent = stats.no_aprobados || 0;
    }

    function getEstadoBadge(estado) {
        switch (estado) {
            case 'Aprobado': return 'bg-success';
            case 'No Aprobado': return 'bg-danger';
            case 'Sin Calificar': return 'bg-warning text-dark';
            default: return 'bg-secondary';
        }
    }

    function mostrarLoading() {
        tablaLibroFinal.innerHTML = `
        <tr>
            <td colspan="7" class="text-center p-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p class="mt-2 mb-0">Consultando información...</p>
            </td>
        </tr>`;
    }

    function mostrarMensajeError(mensaje) {
        tablaLibroFinal.innerHTML = `
        <tr>
            <td colspan="7" class="text-center text-danger p-4">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${mensaje || 'Error al cargar los datos'}
            </td>
        </tr>`;
    }

    function mostrarNotificacion(mensaje, tipo = 'info') {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
        <div class="alert alert-${tipo} alert-dismissible fade show" role="alert" 
             style="position: fixed; top: 20px; right: 20px; z-index: 1056; min-width: 300px;">
            <div class="d-flex align-items-center">
                <i class="fas ${tipo === 'success' ? 'fa-check-circle' :
                tipo === 'danger' ? 'fa-exclamation-circle' :
                    'fa-info-circle'} me-2"></i>
                <div>${mensaje}</div>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;

        document.body.append(wrapper);

        // Eliminar después de 5 segundos
        setTimeout(() => {
            wrapper.querySelector('.alert')?.classList.add('fade');
            setTimeout(() => wrapper.remove(), 150);
        }, 5000);
    }

    function cargarConfiguracion() {
        fetch('/libro_final/configuracion')
            .then(response => {
                if (!response.ok) throw new Error('Error en la respuesta del servidor');
                return response.json();
            })
            .then(data => {
                if (data.error) throw new Error(data.error);
                document.getElementById('config-nota-superior').value = data.nota_superior;
                document.getElementById('config-nota-alto').value = data.nota_alto;
                document.getElementById('config-nota-basico').value = data.nota_basico;
            })
            .catch(error => {
                console.error('Error cargando configuración:', error);
                mostrarNotificacion('Error al cargar configuración: ' + error.message, 'danger');
            });
    }

    function guardarConfiguracion() {
        const form = document.getElementById('formConfigLibro');
        const notaSuperior = parseFloat(form.elements['nota_superior'].value);
        const notaAlto = parseFloat(form.elements['nota_alto'].value);
        const notaBasico = parseFloat(form.elements['nota_basico'].value);
        const csrfToken = form.elements['csrf_token'].value;

        // Validación del lado del cliente
        if (isNaN(notaSuperior) || isNaN(notaAlto) || isNaN(notaBasico) ||
            notaSuperior < 0 || notaSuperior > 5 ||
            notaAlto < 0 || notaAlto > 5 ||
            notaBasico < 0 || notaBasico > 5) {
            mostrarNotificacion('Las notas de desempeño deben ser números válidos entre 0 y 5.', 'warning');
            return;
        }

        if (!(notaBasico < notaAlto && notaAlto < notaSuperior)) {
            mostrarNotificacion('Las notas de desempeño deben seguir el orden: Básico < Alto < Superior.', 'warning');
            return;
        }

        const params = new URLSearchParams();
        params.append('nota_superior', notaSuperior);
        params.append('nota_alto', notaAlto);
        params.append('nota_basico', notaBasico);
        params.append('csrf_token', csrfToken);

        fetch('/libro_final/configuracion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: params
        })
            .then(response => {
                if (!response.ok) return response.json().then(err => { throw new Error(err.error || 'Error en el servidor'); });
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    mostrarNotificacion('Configuración guardada correctamente', 'success');
                    bootstrap.Modal.getInstance(modalConfiguracion).hide();

                    // Limpiar caché porque el nivel de aprobación cambió
                    datosCache = {};

                    // Recargar datos si hay filtros aplicados
                    if (cursoSeleccionado) {
                        filtrarDatos();
                    }
                } else {
                    throw new Error(data.error || 'Error desconocido');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                mostrarNotificacion('Error al guardar: ' + error.message, 'danger');
            });
    }

    // Funciones globales para exportación
    window.exportarExcel = function () {
        if (!cursoSeleccionado) return;
        window.location.href = `/libro_final/exportar_excel?curso=${cursoSeleccionado}`;
        bootstrap.Modal.getInstance(document.getElementById('modalExportacion')).hide();
    };

    window.exportarPDF = function () {
        if (!cursoSeleccionado) return;
        window.location.href = `/libro_final/exportar_pdf?curso=${cursoSeleccionado}`;
        bootstrap.Modal.getInstance(document.getElementById('modalExportacion')).hide();
    };
    // Fin de la función DOMContentLoaded
});