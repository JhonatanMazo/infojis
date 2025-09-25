document.addEventListener('DOMContentLoaded', function () {
    // Mostrar detalles (PDF o imagen)
    const botonesDetalles = document.querySelectorAll('.btn-ver-detalles');
    const iframe = document.getElementById('iframe-detalles');
    const divDescargar = document.getElementById('descargar-detalles');
    const linkDescarga = document.getElementById('download-link');

    botonesDetalles.forEach(btn => {
        btn.addEventListener('click', function () {
            const url = this.getAttribute('data-url');
            const isPDF = url.toLowerCase().endsWith('.pdf');

            if (isPDF) {
                iframe.style.display = 'block';
                iframe.src = url;

                divDescargar.style.display = 'none';
                linkDescarga.href = '';
            } else {
                iframe.style.display = 'none';
                iframe.src = '';

                divDescargar.style.display = 'block';
                linkDescarga.href = url;
            }
        });
    });

    // Editar inclusión
    const botonesEditar = document.querySelectorAll('.btn-editar');
    const formEditar = document.getElementById("form-editar-inclusion");

    botonesEditar.forEach(boton => {
        boton.addEventListener('click', function () {
            const id = this.dataset.id;
            const idMatricula = this.dataset.idMatricula;

            // Asignar valores a inputs
            document.getElementById('edit-id-inclusion').value = id;
            document.getElementById('edit-tipo').value = this.dataset.tipo;
            document.getElementById('edit-plan').value = this.dataset.plan;
            document.getElementById('edit-fecha-ingreso').value = this.dataset.fechaIngreso;

            formEditar.action = `/inclusion/editar/${id}`;

            // Consultar info de matrícula
            fetch(`/inclusion/info_matricula/${idMatricula}`)
                .then(res => res.json())
                .then(data => {
                    const cursoId = data.curso_id;
                    const foto = data.foto;

                    document.getElementById('edit-id-curso').value = cursoId;
                    document.getElementById('edit-id-curso-hidden').value = cursoId;


                    fetch(`/inclusion/matriculas_por_curso/${cursoId}`)
                        .then(res => res.json())
                        .then(lista => {
                            const selectMatricula = document.getElementById('edit-id-matricula');
                            const hiddenMatricula = document.getElementById('edit-id-matricula-hidden');
                            const previewImg = document.getElementById('foto-preview');

                            selectMatricula.innerHTML = '';

                            lista.forEach(m => {
                                const option = document.createElement('option');
                                option.value = m.id;
                                option.textContent = m.nombre;
                                option.dataset.foto = m.foto;
                                selectMatricula.appendChild(option);
                            });

                            // Forzar selección
                            selectMatricula.value = idMatricula;
                            hiddenMatricula.value = idMatricula;

                            // Mostrar foto
                            const selected = selectMatricula.options[selectMatricula.selectedIndex];
                            if (selected && selected.dataset.foto) {
                                previewImg.src = selected.dataset.foto;
                                previewImg.style.display = 'inline-block';
                            } else {
                                previewImg.style.display = 'none';
                            }
                        });
                });
        });
    });

    // Eliminar inclusión con confirmación
    const botonesEliminar = document.querySelectorAll('.btn-eliminar-inclusion');
    const formEliminar = document.getElementById('formEliminarInclusion');

    botonesEliminar.forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.dataset.id;
            const nombre = this.dataset.nombre;

            Swal.fire({
                title: '¿Eliminar inclusión?',
                html: `¿Estás seguro de eliminar al estudiante <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminar.action = `/inclusion/eliminar/${id}`;
                    formEliminar.submit();
                }
            });
        });
    });

    // Previsualizar imagen al cambiar matrícula en el formulario de edición
    const selectMatriculaEditar = document.getElementById('edit-id-matricula');
    if (selectMatriculaEditar && previewImg) {
        selectMatriculaEditar.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            const foto = selectedOption.dataset.foto;

            if (foto) {
                previewImg.src = foto;
                previewImg.style.display = 'inline-block';
            } else {
                previewImg.src = '';
                previewImg.style.display = 'none';
            }
        });
    }
});



document.addEventListener('DOMContentLoaded', function () {
    const selectCurso = document.getElementById('select-inclusion-curso');
    const selectMatricula = document.getElementById('select-inclusion-matricula');
    const previewFoto = document.getElementById('preview-foto');

    if (selectCurso && selectMatricula) {
        selectCurso.addEventListener('change', function () {
            const cursoId = this.value;
            selectMatricula.innerHTML = '<option disabled selected>Cargando...</option>';
            previewFoto.style.display = 'none';

            fetch(`/inclusion/matriculas_por_curso/${cursoId}`)
                .then(response => response.json())
                .then(data => {
                    selectMatricula.innerHTML = '';

                    if (data.length === 0) {
                        selectMatricula.innerHTML = '<option disabled selected>No hay estudiantes</option>';
                        return;
                    }

                    const defaultOption = document.createElement('option');
                    defaultOption.textContent = 'Seleccionar estudiante';
                    defaultOption.disabled = true;
                    defaultOption.selected = true;
                    selectMatricula.appendChild(defaultOption);

                    data.forEach(m => {
                        const option = document.createElement('option');
                        option.value = m.id;
                        option.textContent = m.nombre;
                        option.dataset.foto = m.foto;
                        selectMatricula.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Error al cargar matrículas:', error);
                    selectMatricula.innerHTML = '<option disabled selected>Error al cargar</option>';
                });
        });

        // Mostrar foto al seleccionar estudiante
        selectMatricula.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            const fotoUrl = selectedOption.dataset.foto;

            if (fotoUrl) {
                previewFoto.src = fotoUrl;
                previewFoto.style.display = 'inline-block';
            } else {
                previewFoto.src = '';
                previewFoto.style.display = 'none';
            }
        });
    }
});