// [file name]: transferir.js (actualizado con SweetAlert)
document.addEventListener('DOMContentLoaded', function () {
    // Manejo del filtrado
    const filtrarBtn = document.getElementById('filtrar-btn');
    if (filtrarBtn) { // Add check if button exists
        filtrarBtn.addEventListener('click', function () {
            const cursoId = document.getElementById('curso-select').value;
            const estado = document.getElementById('estado-select').value;

            let url = new URL(window.location.href.split('?')[0]); // Base URL without old params
            url.searchParams.set('filtro_aplicado', '1'); // Mark that a filter attempt was made

            if (cursoId) {
                url.searchParams.set('curso', cursoId);
            }
            if (estado) {
                url.searchParams.set('estado', estado);
            }
            url.searchParams.set('page', 1);

            window.location.href = url.toString();
        });
    }

    // Manejo de selección múltiple
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.matricula-checkbox');
    const contadorSeleccionados = document.getElementById('contadorSeleccionados');
    const matriculasIdsMultiple = document.getElementById('matriculas_ids_multiple');

    if (selectAll) {
        selectAll.addEventListener('change', function (e) {
            checkboxes.forEach(checkbox => {
                checkbox.checked = e.target.checked;
            });
            actualizarContador();
        });
    }

    if (checkboxes) {
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', actualizarContador);
        });
    }

    function actualizarContador() {
        const seleccionados = Array.from(checkboxes).filter(c => c.checked);
        contadorSeleccionados.textContent = `Estudiantes seleccionados: ${seleccionados.length}`;

        const ids = seleccionados.map(c => c.value);
        matriculasIdsMultiple.value = JSON.stringify(ids);
    }

    // Manejo de transferencia individual
    const modalIndividual = document.getElementById('modalTransferenciaIndividual');
    if (modalIndividual) {
        modalIndividual.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const matriculaId = button.getAttribute('data-matricula-id');
            const cursoActual = button.getAttribute('data-curso-actual');

            // Establecer el ID de la matrícula en el campo oculto
            document.getElementById('matricula-id-individual').value = JSON.stringify([matriculaId]);

            // Obtener el select de cursos destino
            const selectDestino = document.getElementById('curso-destino-individual');

            // Reiniciar la selección
            selectDestino.selectedIndex = 0;
        });

        // Restaurar opciones al cerrar el modal
        modalIndividual.addEventListener('hidden.bs.modal', function () {
            const selectDestino = document.getElementById('curso-destino-individual');
            selectDestino.selectedIndex = 0; // Solo reiniciar la selección
        });
    }

    // Manejo de transferencia múltiple
    const modalMultiple = document.getElementById('modalTransferenciaMultiple');
    if (modalMultiple) {
        modalMultiple.addEventListener('show.bs.modal', function () {
            // Obtener IDs de estudiantes seleccionados
            const checkboxes = document.querySelectorAll('.matricula-checkbox:checked');
            const ids = Array.from(checkboxes).map(cb => cb.value);

            // Actualizar contador y campo oculto
            document.getElementById('contadorSeleccionados').textContent = `Estudiantes seleccionados: ${ids.length}`;
            document.getElementById('matriculas_ids_multiple').value = JSON.stringify(ids);

            // Obtener el curso actual del filtro
            const cursoFiltrado = document.getElementById('curso-select').value;

            // Obtener el select de cursos destino
            const selectDestino = document.getElementById('curso-destino-multiple');

            // Reiniciar la selección al abrir el modal
            selectDestino.selectedIndex = 0;
        });

        // Restaurar opciones al cerrar el modal
        modalMultiple.addEventListener('hidden.bs.modal', function () {
            const selectDestino = document.getElementById('curso-destino-multiple');
            selectDestino.selectedIndex = 0; // Solo reiniciar la selección
        });
    }

    // Eliminar el código del modal de confirmación y reemplazar con SweetAlert
    document.querySelectorAll('.eliminar-historial').forEach(button => {
        button.addEventListener('click', function () {
            const historialId = this.getAttribute('data-id');
            const estudianteNombre = this.getAttribute('data-estudiante') || 'este registro';

            Swal.fire({
                title: '¿Eliminar registro de transferencia?',
                text: `¿Estás seguro de eliminar el registro de transferencia de ${estudianteNombre}?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then(result => {
                if (result.isConfirmed) {
                    // Realizar la petición AJAX para eliminar
                    fetch(`/transferir/eliminar_historial/${historialId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                        }
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                // Mostrar mensaje de éxito
                                Swal.fire({
                                    title: '¡Eliminado!',
                                    text: data.message,
                                    icon: 'success',
                                    timer: 1500,
                                    showConfirmButton: false
                                });

                                // Recargar la página después de un breve delay
                                setTimeout(() => {
                                    location.reload();
                                }, 1600);
                            } else {
                                Swal.fire('Error', data.message, 'error');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            Swal.fire('Error', 'Error al eliminar el registro', 'error');
                        });
                }
            });
        });
    });

    // Limpiar variable cuando se cierra el modal
    const modalConfirmacion = document.getElementById('modalConfirmacionEliminar');
    if (modalConfirmacion) {
        modalConfirmacion.addEventListener('hidden.bs.modal', function () {
            historialIdAEliminar = null;
        });
    }

    // Habilitar/deshabilitar botones según filtros
    const cursoSelect = document.getElementById('curso-select');
    const estadoSelect = document.getElementById('estado-select');

    function checkFilters() {
        const hasFilters = cursoSelect.value || estadoSelect.value;
        if (transferirBtn) {
            transferirBtn.disabled = !hasFilters;
        }
    }

    cursoSelect.addEventListener('change', checkFilters);
    estadoSelect.addEventListener('change', checkFilters);
    checkFilters(); // Estado inicial
});