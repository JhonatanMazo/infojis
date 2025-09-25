document.addEventListener('DOMContentLoaded', function () {
    console.log("Script asistencias.js cargado correctamente");



    // Inicialización
    initEventListeners();
    loadInitialData();

    function initEventListeners() {
        console.log("Inicializando event listeners");

        // Filtro de curso
        const cursoSelect = document.getElementById('select-curso');
        if (cursoSelect) {
            cursoSelect.addEventListener('change', function () {
                console.log("Curso cambiado:", this.value);
                loadAsignaturas(this.value);
            });
        }

        // Guardar asistencias
        const guardarBtn = document.getElementById('guardar');
        if (guardarBtn) {
            guardarBtn.addEventListener('click', function (e) {
                e.preventDefault();
                console.log("Botón guardar clickeado");
                saveAttendances();
            });
        }

        // Búsqueda de estudiantes al presionar Enter
        const searchInput = document.getElementById('student-search-input');
        const filtrosForm = document.getElementById('form-filtros');
        if (searchInput && filtrosForm) {
            searchInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault(); // Prevenir envío doble si está dentro de un form
                    filtrosForm.submit();
                }
            });
        }

        // Modal de observaciones (como en calificaciones)
        const modalObservaciones = document.getElementById('modalObservaciones');
        const formObservacion = document.getElementById('form-observacion');
        const observacionTexto = document.getElementById('observacion-texto');
        if (modalObservaciones && formObservacion && observacionTexto) {
            modalObservaciones.addEventListener('show.bs.modal', function (event) {
                const button = event.relatedTarget;
                const studentId = button.getAttribute('data-matricula-id');
                const hiddenInput = document.getElementById(`observacion_${studentId}`);
                observacionTexto.value = hiddenInput ? hiddenInput.value : '';
                formObservacion.dataset.studentId = studentId;
            });

            formObservacion.addEventListener('submit', function (event) {
                event.preventDefault();
                const studentId = formObservacion.dataset.studentId;
                const hiddenInput = document.getElementById(`observacion_${studentId}`);
                if (hiddenInput) hiddenInput.value = observacionTexto.value;
                bootstrap.Modal.getInstance(modalObservaciones).hide();
            });
        }
    }

    function loadInitialData() {
        console.log("Cargando datos iniciales");

        const urlParams = new URLSearchParams(window.location.search);
        const cursoId = urlParams.get('curso');
        const asignaturaId = urlParams.get('asignatura');
        const fecha = urlParams.get('fecha');

        console.log("Parámetros URL:", { cursoId, asignaturaId, fecha });

        const cursoSelect = document.getElementById('select-curso');
        const asignaturaSelect = document.getElementById('select-asignatura');
        const fechaInput = document.getElementById('filter-fecha');

        if (cursoId && cursoSelect) {
            cursoSelect.value = cursoId;
            loadAsignaturas(cursoId).then(() => {
                if (asignaturaId && asignaturaSelect) {
                    asignaturaSelect.value = asignaturaId;
                }
            });
        }
        if (fecha && fechaInput) {
            fechaInput.value = fecha;
        }
    }

    function loadAsignaturas(cursoId) {
        console.log(`Cargando asignaturas para curso ${cursoId}`);

        const asignaturaSelect = document.getElementById('select-asignatura');
        if (!asignaturaSelect) return Promise.reject("Elemento select-asignatura no encontrado");

        return fetch(`/asistencias/asignaturas?curso_id=${cursoId}`)
            .then(response => {
                if (!response.ok) throw new Error('Error al cargar asignaturas');
                return response.json();
            })
            .then(data => {
                console.log("Asignaturas recibidas:", data);

                asignaturaSelect.innerHTML = '<option value="" selected disabled>Seleccione una asignatura</option>';

                if (data.error) {
                    showToast('warning', data.error);
                    return;
                }

                data.forEach(asignatura => {
                    const option = document.createElement('option');
                    option.value = asignatura.id;
                    option.textContent = asignatura.nombre;
                    asignaturaSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('danger', 'Error al cargar asignaturas');
            });
    }


    function saveAttendances() {
        console.log("Intentando guardar asistencias");

        const cursoId = document.getElementById('select-curso')?.value;
        const asignaturaId = document.getElementById('select-asignatura')?.value;
        const fecha = document.getElementById('filter-fecha')?.value;

        if (!cursoId || !asignaturaId || !fecha) {
            showToast('warning', 'Seleccione curso, asignatura y fecha antes de guardar');
            return;
        }

        const attendanceData = [];
        const selects = document.querySelectorAll('.attendance-select');

        selects.forEach(select => {
            const matriculaId = select.getAttribute('data-matricula-id');
            const observacionInput = document.getElementById(`observacion_${matriculaId}`);
            attendanceData.push({
                matricula_id: matriculaId,
                estado: select.value,
                observacion: observacionInput ? observacionInput.value : ''
            });
        });

        // Construir FormData
        const formData = new FormData();
        formData.append('curso_id', cursoId);
        formData.append('asignatura_id', asignaturaId);
        formData.append('fecha', fecha);
        formData.append('busqueda', document.getElementById('student-search-input')?.value || '');
        formData.append('page', new URLSearchParams(window.location.search).get('page') || 1);
        formData.append('asistencias_json', JSON.stringify(attendanceData));

        fetch('/asistencias/guardar', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
            .then(async response => {
                if (response.redirected) {
                    // Seguir la redirección para que se muestren los mensajes flash del backend
                    window.location.href = response.url;
                } else {
                    // Respuesta JSON para AJAX
                    const data = await response.json();
                    if (response.ok) {
                        showToast('success', data.message);
                        // Recargar la página para actualizar la tabla
                        setTimeout(() => window.location.reload(), 2000);
                    } else {
                        showToast('danger', data.error);
                    }
                }
            })
            .catch(error => {
                console.error('Error al guardar asistencias:', error);
                showToast('danger', 'Error al guardar asistencias');
            });
    }





    // Helper functions
    function showToast(type, message) {
        // Usar el mismo contenedor que renderiza Flask
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1100';
            document.body.appendChild(toastContainer);
        }

        // Crear toast dinámico
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 mb-2`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                    data-bs-dismiss="toast" aria-label="Cerrar"></button>
        </div>
    `;

        toastContainer.appendChild(toast);

        // Inicializar con Bootstrap
        const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 5000 });
        bsToast.show();

        // Remover del DOM cuando se oculta
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }



    function createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }

    function getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (!token) console.error("CSRF Token no encontrado!");
        return token || '';
    }
});
