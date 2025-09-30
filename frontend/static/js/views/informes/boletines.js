document.addEventListener('DOMContentLoaded', function () {

    const btnDescargarTodo = document.getElementById('btn-descargar-todo');
    // === Filtrar (curso + búsqueda) ===
    const btnFiltrar = document.getElementById('btn-filtrar');
    const searchInput = document.getElementById('student-search-input');

    function aplicarFiltros() {
        const curso = document.getElementById('select-curso')?.value || 'todos';
        const periodo = document.getElementById('select-periodo')?.value || '';
        const busqueda = searchInput?.value || '';
        const baseUrl = btnFiltrar.dataset.urlBase;
        window.location.href = `${baseUrl}?curso=${curso}&periodo=${periodo}&busqueda=${encodeURIComponent(busqueda)}`;
    }

    function actualizarEnlaceDescarga() {
        const curso = document.getElementById('select-curso')?.value;
        const periodo = document.getElementById('select-periodo')?.value;
        const url = new URL(btnDescargarTodo.href, window.location.origin);
        url.pathname = '/boletines/descargar_todos_zip';
        url.searchParams.set('curso', curso || '');
        url.searchParams.set('periodo', periodo || '');
        btnDescargarTodo.href = url.toString();
    }

    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', aplicarFiltros);
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                aplicarFiltros();
            }
        });
    }

    if (btnDescargarTodo) {
        // Actualizar al cargar la página
        actualizarEnlaceDescarga();

        // Actualizar cuando cambien los filtros
        document.getElementById('select-curso')?.addEventListener('change', actualizarEnlaceDescarga);
        document.getElementById('select-periodo')?.addEventListener('change', actualizarEnlaceDescarga);

        btnDescargarTodo.addEventListener('click', function(e) {
            actualizarEnlaceDescarga(); // Asegurarse de que la URL está actualizada antes de hacer clic
            e.preventDefault();
            
            const curso = document.getElementById('select-curso')?.value;
            const periodo = document.getElementById('select-periodo')?.value;
            
            if (!curso) {
                Swal.fire('Error', 'Seleccione un curso primero', 'warning');
                return;
            }
    
            // Mostrar modal de progreso
            const progresoModal = new bootstrap.Modal(document.getElementById('modalProgresoDescarga'));
            const progressBar = document.querySelector('#modalProgresoDescarga .progress-bar');
            const progresoTexto = document.getElementById('progreso-texto');
            
            progresoModal.show();
            progressBar.style.width = '0%';
            progresoTexto.textContent = 'Iniciando generación de boletines...';
    
            // Simular progreso (en una implementación real, usarías WebSockets o polling)
            let progreso = 0;
            const intervalo = setInterval(() => {
                progreso += 5;
                progressBar.style.width = `${progreso}%`;
                progresoTexto.textContent = `Generando boletines... ${progreso}%`;
                
                if (progreso >= 100) {
                    clearInterval(intervalo);
                    // Redirigir a la descarga real
                    actualizarEnlaceDescarga(); // Asegurarse de que la URL está actualizada antes de hacer clic
                    window.location.href = btnDescargarTodo.href;
                    setTimeout(() => progresoModal.hide(), 1000);
                }
            }, 200);
        });
    }

   

    // === Ver detalles del boletín en modal y Enviar por Correo ===
    const modalVerBoletin = document.getElementById('modalVerBoletin');
    if (modalVerBoletin) {
        let currentBoletinId = null;

        modalVerBoletin.addEventListener('show.bs.modal', async (event) => {
            const button = event.relatedTarget;
            currentBoletinId = button.getAttribute('data-boletin-id');
            const modalBody = modalVerBoletin.querySelector('#boletin-details-content');
            const downloadBtn = modalVerBoletin.querySelector('#btn-descargar-boletin-modal');

            // Set download link
            downloadBtn.href = `/boletines/descargar_pdf/${currentBoletinId}`;

            // Show spinner while loading
            modalBody.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Cargando...</span></div></div>';

            try {
                console.log('Fetching bulletin details for ID:', currentBoletinId);
                const response = await fetch(`/boletines/${currentBoletinId}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                console.log('Response status:', response.status, response.statusText);

                if (!response.ok) {
                    const errorText = await response.text(); // Get raw error text
                    console.error('Server error response:', errorText);
                    throw new Error(`Error al cargar los detalles del boletín: ${response.status} ${response.statusText}. Detalles: ${errorText}`);
                }

                const data = await response.json();
                console.log('Received data:', data);

                let gradesHtml = '';
                if (data.grades && data.grades.length > 0) {
                    gradesHtml = data.grades.map(grade => `
                        <tr>
                            <td>${grade.asignatura}</td>
                            <td>${grade.nota}</td>
                            <td>${grade.desempeno}</td>
                            <td>${grade.observacion}</td>
                        </tr>
                    `).join('');
                } else {
                    gradesHtml = '<tr><td colspan="4" class="text-center">No hay calificaciones registradas.</td></tr>';
                }

                const contentHtml = `
                    <div class="row mb-3">
                        <div class="col-md-6"><strong>Estudiante:</strong> ${data.estudiante}</div>
                        <div class="col-md-6"><strong>Curso:</strong> ${data.curso}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-6"><strong>Año Lectivo:</strong> ${data.anio_lectivo}</div>
                        <div class="col-md-6"><strong>Fecha de Generación:</strong> ${data.fecha_generacion}</div>
                    </div>
                    <div class="row mb-4">
                        <div class="col-md-6"><strong>Generado por:</strong> ${data.generado_por}</div>
                    </div>

                    <h5>Calificaciones</h5>
                    <div class="table-responsive">
                        <table class="table table-hover table-striped align-middle">
                            <thead>
                                <tr>
                                    <th>Asignatura</th>
                                    <th>Nota</th>
                                    <th>Desempeño</th>
                                    <th>Observación</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${gradesHtml}
                            </tbody>
                        </table>
                    </div>

                    ${data.observaciones_generales ? `
                    <h5 class="mt-4">Observaciones Generales</h5>
                    <p>${data.observaciones_generales}</p>
                    ` : ''}
                `;

                modalBody.innerHTML = contentHtml;

            } catch (error) {
                console.error('Error in fetch or processing:', error);
                modalBody.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
            }
        });

        const btnEnviar = document.getElementById('btn-enviar-boletin-modal');
        btnEnviar.addEventListener('click', async () => {
            if (!currentBoletinId) return;

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || document.querySelector('input[name="csrf_token"]')?.value;

            btnEnviar.disabled = true;
            btnEnviar.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Enviando...`;

            try {
                const response = await fetch(`/boletines/enviar_boletin/${currentBoletinId}`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    if (data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: '¡Correo Enviado!',
                            text: data.message,
                            showCancelButton: true,
                            confirmButtonText: '<i class="fab fa-whatsapp"></i> Notificar por WhatsApp',
                            cancelButtonText: 'Cerrar',
                            confirmButtonColor: '#25D366',
                        }).then((result) => {
                            if (result.isConfirmed) {
                                fetch(`/boletines/info_contacto_boletin/${currentBoletinId}`)
                                    .then(res => res.json())
                                    .then(contactInfo => {
                                        if (contactInfo.whatsapp) {
                                            const studentName = contactInfo.nombre || 'el estudiante';
                                            const message = `Hola estimado/a acudiente de  ${data.nombre}, te informamos que el boletín académico ha sido enviado a tu correo electrónico ${data.correo}. ¿Podría confirmar si lo ha recibido?.`;
                                            const whatsappUrl = `https://wa.me/${contactInfo.whatsapp}?text=${encodeURIComponent(message)}`;
                                            window.open(whatsappUrl, '_blank');
                                        } else {
                                            Swal.fire('Error', 'El estudiante no tiene un número de WhatsApp registrado.', 'error');
                                        }
                                    })
                                    .catch(() => Swal.fire('Error', 'No se pudo obtener la información de contacto.', 'error'));
                            }
                        });
                    } else {
                        throw new Error(data.message);
                    }
                } else {
                    const errorText = data.message || `Error del servidor: ${response.status}`;
                    throw new Error(errorText);
                }

            } catch (error) {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: error.message || 'No se pudo enviar el correo.',
                });
            } finally {
                btnEnviar.disabled = false;
                btnEnviar.innerHTML = `<i class="fas fa-envelope me-1"></i> Enviar por Correo`;
            }
        });
    }
});