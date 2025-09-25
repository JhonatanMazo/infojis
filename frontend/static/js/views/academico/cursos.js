document.addEventListener('DOMContentLoaded', function () {
    // 1. Edición de cursos
    const editButtons = document.querySelectorAll('.btn-edit-curso');
    const formEditar = document.getElementById('formEditarCurso');

    editButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log('Botón de editar presionado');
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const maxEstudiantes = button.getAttribute('data-max_estudiantes');
            const estado = button.getAttribute('data-estado');
            const descripcion = button.getAttribute('data-descripcion');

            formEditar.action = `/cursos/editar/${id}`;
            formEditar.querySelector('#edit-nombre').value = nombre;
            if (formEditar.querySelector('#edit-estado')) {
                formEditar.querySelector('#edit-estado').value = estado;
            }
            if (formEditar.querySelector('#edit-descripcion')) {
                formEditar.querySelector('#edit-descripcion').value = descripcion;
            }
        });
    });

    // 2. Validación de formularios
    document.querySelectorAll('#modalCurso form, #modalEditarCursos form').forEach(form => {
        form.addEventListener('submit', function (e) {
            const maxInput = this.querySelector('input[name="max_estudiantes"]');
            if (maxInput) {
                const maxConfig = parseInt(maxInput.getAttribute('max'));
                const valorActual = parseInt(maxInput.value);

                if (valorActual < 1) {
                    e.preventDefault();
                    Swal.fire({
                        title: 'Valor inválido',
                        text: 'El mínimo de estudiantes debe ser 1',
                        icon: 'error',
                        confirmButtonText: 'Entendido'
                    });
                    maxInput.focus();
                    return;
                }

                if (valorActual > maxConfig) {
                    e.preventDefault();
                    Swal.fire({
                        title: 'Límite excedido',
                        text: `El máximo permitido es ${maxConfig} estudiantes (configuración del sistema)`,
                        icon: 'error',
                        confirmButtonText: 'Entendido'
                    });
                    maxInput.focus();
                }
            }
        });
    });

    // 3. Eliminación de cursos
    const deleteButtons = document.querySelectorAll('.btn-eliminar-curso');
    const formEliminar = document.createElement('form');
    formEliminar.method = 'POST';
    formEliminar.style.display = 'none';
    document.body.appendChild(formEliminar);

    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrfToken;
    formEliminar.appendChild(csrfInput);

    deleteButtons.forEach(button => {
        button.addEventListener('click', () => {
            console.log('Botón de eliminar presionado');
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');

            Swal.fire({
                title: `Eliminar curso`,
                html: `¿Estás seguro que desea eliminar el curso <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminar.action = `/cursos/eliminar/${id}`;
                    formEliminar.submit();
                }
            });
        });
    });

    // 4. Filtrado
    const btnFiltrar = document.getElementById('btn-filtrar');
    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', () => {
            const estado = document.getElementById('filtro_estado').value;
            const url = new URL(window.location.href);

            if (estado) {
                url.searchParams.set('estado', estado);
            } else {
                url.searchParams.delete('estado');
            }
            url.searchParams.set('page', 1);

            window.location.href = url.toString();
        });
    }
});