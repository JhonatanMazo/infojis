document.addEventListener('DOMContentLoaded', () => {
    const modalElement = document.getElementById('modalEditarMatricula');
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    // Al cerrar el modal, elimina manualmente cualquier sombra
    modalElement.addEventListener('hidden.bs.modal', () => {
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) backdrop.remove();
        document.body.classList.remove('modal-open');
        document.body.style = ''; // Limpia estilos en línea si quedaron
    });

    // Botones editar
    const botonesEditar = document.querySelectorAll('.btn-editar');
    botonesEditar.forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.id;

            document.getElementById('edit-id').value = id;
            document.getElementById('edit-nombres').value = btn.dataset.nombres;
            document.getElementById('edit-apellidos').value = btn.dataset.apellidos;
            document.getElementById('edit-genero').value = btn.dataset.genero;
            document.getElementById('edit-documento').value = btn.dataset.documento;
            document.getElementById('edit-telefono').value = btn.dataset.telefono || '';
            document.getElementById('edit-direccion').value = btn.dataset.direccion;
            document.getElementById('edit-email').value = btn.dataset.email;
            document.getElementById('edit-fecha-nacimiento').value = btn.dataset.fechaNacimiento;
            document.getElementById('edit-id-curso').value = btn.dataset.idCurso;
            document.getElementById('edit-estado').value = btn.dataset.estado;
            document.getElementById('edit-fecha-matricula').value = btn.dataset.fechaMatricula;

            // Bloquear edición del año lectivo
            document.getElementById('edit-año-lectivo').value = "{{ anio_lectivo }}";

            document.getElementById('form-editar').action = `/matriculas/editar/${id}`;

            modal.show();
        });
    });

    // Botones eliminar
    const botonesEliminar = document.querySelectorAll('.btn-eliminar-matricula');
    const formEliminar = document.getElementById('formEliminarMatricula');

    botonesEliminar.forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.dataset.id;
            const nombre = this.dataset.nombre;

            Swal.fire({
                title: '¿Eliminar matrícula?',
                html: `¿Estás seguro de eliminar al estudiante <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminar.action = `/matriculas/eliminar/${id}`;
                    formEliminar.submit();
                }
            });
        });
    });

    // Asegurar que la verificación de cupo funcione correctamente
    document.querySelector('select[name="id_curso"]').addEventListener('change', async function () {
        try {
            const cursoId = this.value;
            if (!cursoId) return;

            const response = await fetch(`/matriculas/verificar-cupo?curso_id=${cursoId}`);

            if (!response.ok) {
                throw new Error('Error al verificar cupo');
            }

            const data = await response.json();

            if (!data.disponible) {
                Swal.fire({
                    title: 'Cupo Completo',
                    text: `El curso "${data.curso}" ha alcanzado el límite de ${data.maximo} estudiantes (${data.actual}/${data.maximo})`,
                    icon: 'warning'
                });
            }
        } catch (error) {
            console.error('Error:', error);
        }
    });


    // Validación de formulario
    const formCrear = document.querySelector('#modalMatricula form');
    if (formCrear) {
        formCrear.addEventListener('submit', function (e) {
            const telefono = this.querySelector('input[name="telefono"]');
            if (telefono && !/^\d+$/.test(telefono.value)) {
                e.preventDefault();
                Swal.fire({
                    title: 'Teléfono inválido',
                    text: 'Solo se permiten números en el campo de teléfono',
                    icon: 'error',
                    confirmButtonText: 'Entendido'
                });
                telefono.focus();
            }
        });
    }
});