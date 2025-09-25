document.addEventListener('DOMContentLoaded', function () {
    // Editar asignatura
    const editButtons = document.querySelectorAll('.btn-edit-asignatura');
    const formEditar = document.getElementById('formEditarAsignatura');

    editButtons.forEach(button => {
        button.addEventListener('click', () => {
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const descripcion = button.getAttribute('data-descripcion');
            const estado = button.getAttribute('data-estado');

            formEditar.action = `/asignaturas/editar/${id}`;
            formEditar.querySelector('#edit-nombre').value = nombre;
            formEditar.querySelector('#edit-descripcion').value = descripcion;
            formEditar.querySelector('#edit-estado').value = estado;
        });
    });

    // Eliminar asignatura con confirmación
    const deleteButtons = document.querySelectorAll('.btn-eliminar-asignatura');
    const formEliminar = document.createElement('form');
    formEliminar.method = 'POST';
    formEliminar.style.display = 'none';
    document.body.appendChild(formEliminar);

    // Agregar token CSRF al formulario de eliminación
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrfToken;
    formEliminar.appendChild(csrfInput);

    deleteButtons.forEach(button => {
        button.addEventListener('click', () => {
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');

            Swal.fire({
                title: `Eliminar asignatura`,
                html: `¿Está seguro que desea eliminar la asignatura <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminar.action = `/asignaturas/eliminar/${id}`;
                    formEliminar.submit();
                }
            });
        });
    });

    // Botón de filtrar
    const btnFiltrar = document.getElementById('btn-filtrar');
    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', () => {
            const estado = document.getElementById('filtro_estado').value;
            const url = new URL(window.location.href);

            // Setear estado y reiniciar a página 1
            if (estado) {
                url.searchParams.set('estado', estado);
            } else {
                url.searchParams.delete('estado');
            }
            url.searchParams.set('page', 1); // Reiniciar a la primera página al filtrar

            window.location.href = url.toString();
        });
    }
});