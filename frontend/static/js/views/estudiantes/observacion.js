document.addEventListener('DOMContentLoaded', function () {
    const selectCurso = document.getElementById('select-curso');
    const selectEstudiante = document.getElementById('select-estudiante');
    const formEditar = document.getElementById('form-editar-observacion');
    const modalEditar = new bootstrap.Modal(document.getElementById('modalEditarObservacion'));
    const modalVer = new bootstrap.Modal(document.getElementById('modalVerDetalles'));

    const btnsEditar = document.querySelectorAll('.btn-editar');
    const btnsEliminar = document.querySelectorAll('.btn-eliminar-observacion');
    const botonesDetalles = document.querySelectorAll('.btn-ver-detalles');

    const iframe = document.getElementById('iframe-detalles');
    const linkDescarga = document.getElementById('download-link');
    const contenedorDescarga = document.getElementById('descargar-detalles');

    // Cargar estudiantes según curso
    if (selectCurso && selectEstudiante) {
        selectCurso.addEventListener('change', function () {
            const cursoId = this.value;
            fetch(`/observaciones/matriculas_por_curso/${cursoId}`)
                .then(res => res.json())
                .then(data => {
                    selectEstudiante.innerHTML = '<option value="">Selecciona estudiante</option>';
                    data.forEach(est => {
                        const option = document.createElement('option');
                        option.value = est.id;
                        option.textContent = est.nombre;
                        option.dataset.foto = est.foto;
                        selectEstudiante.appendChild(option);
                    });
                });
        });

        selectEstudiante.addEventListener('change', function () {
            const selected = this.options[this.selectedIndex];
            const foto = selected.dataset.foto;
            const previewFoto = document.getElementById('preview-foto');
            if (foto) {
                previewFoto.src = foto;
                previewFoto.style.display = 'inline-block';
            } else {
                previewFoto.style.display = 'none';
            }
        });
    }

    // Botón Editar
    btnsEditar.forEach(btn => {
        btn.addEventListener('click', () => {
            const fila = btn.closest('tr');
            const estudiante = fila.children[2]?.innerText || 'N/A';
            const curso = fila.children[3]?.innerText || 'N/A';

            formEditar.action = `/observaciones/editar/${btn.dataset.id}`;
            formEditar.querySelector('#edit-estudiante').value = estudiante;
            formEditar.querySelector('#edit-curso').value = curso;

            formEditar.querySelector('#edit-estudiante-hidden').value = btn.dataset.idMatricula;
            formEditar.querySelector('#edit-curso-hidden').value = btn.dataset.idCurso;
            formEditar.querySelector('#edit-tipo').value = btn.dataset.tipo;
            formEditar.querySelector('#edit-fecha').value = btn.dataset.fecha;
            formEditar.querySelector('#edit-descripcion').value = btn.dataset.descripcion;

            const archivo = btn.dataset.detalles;
            const contenedorArchivo = document.getElementById('contenedor-archivo-actual');
            const nombreArchivo = document.getElementById('nombre-archivo-actual');
            const linkArchivo = document.getElementById('link-archivo-actual');

            if (archivo) {
                contenedorArchivo.style.display = 'block';
                nombreArchivo.textContent = archivo;
                linkArchivo.href = `/static/uploads/documents/${archivo}`;
            } else {
                contenedorArchivo.style.display = 'none';
            }

            modalEditar.show();
        });
    });

    // Botón Eliminar
    btnsEliminar.forEach(btn => {
        btn.addEventListener('click', () => {
            const nombre = btn.dataset.nombre;
            const id = btn.dataset.id;

            Swal.fire({
                title: 'Eliminar observación',
                html: `¿Estás seguro de eliminar la observación de <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then(result => {
                if (result.isConfirmed) {
                    const form = document.getElementById(`formEliminarObservacion-${id}`);
                    if (form) form.submit();
                }
            });
        });
    });

    // Botón Ver detalles
    botonesDetalles.forEach(btn => {
        btn.addEventListener('click', () => {
            const url = btn.dataset.url;
            const isPDF = url && url.toLowerCase().endsWith('.pdf');

            if (isPDF) {
                iframe.src = url;
                iframe.style.display = 'block';
                contenedorDescarga.style.display = 'none';
            } else {
                iframe.style.display = 'none';
                iframe.src = '';
                linkDescarga.href = url;
                contenedorDescarga.style.display = 'block';
            }

            modalVer.show();
        });
    });
});
