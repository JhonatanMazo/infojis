document.addEventListener('DOMContentLoaded', function () {
    const selectCurso = document.getElementById('select-pagos-curso');
    const selectMatricula = document.getElementById('select-pagos-matricula');
    const previewFoto = document.getElementById('preview-foto');
    const formEditar = document.getElementById("formEditarPago");

    // 1. Cargar matrículas por curso (Nuevo Pago)
    if (selectCurso && selectMatricula) {
        selectCurso.addEventListener('change', function () {
            const cursoId = this.value;
            previewFoto.style.display = 'none';
            selectMatricula.innerHTML = '<option disabled selected>Cargando...</option>';

            fetch(`/pagos/matriculas_por_curso/${cursoId}`)
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
                .catch(err => {
                    console.error('Error al cargar estudiantes:', err);
                    selectMatricula.innerHTML = '<option disabled selected>Error al cargar</option>';
                });
        });

        selectMatricula.addEventListener('change', function () {
            const selected = this.options[this.selectedIndex];
            const foto = selected.dataset.foto;
            if (foto) {
                previewFoto.src = foto;
                previewFoto.style.display = 'block';
            } else {
                previewFoto.style.display = 'none';
            }
        });
    }

    // 2. Editar pago
    document.querySelectorAll('.btn-editar-pago').forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.dataset.id;
            const idCurso = this.dataset.idCurso;
            const idMatricula = this.dataset.idMatricula;
            const concepto = (this.dataset.concepto || '').trim().toLowerCase();

            document.getElementById('editar-id-curso').value = idCurso;
            document.getElementById('editar-id-curso-hidden').value = idCurso;
            document.getElementById('editar-id-matricula-hidden').value = idMatricula;

            // ⚠️ Asegurar que el valor coincida con los del <option>
            const selectConcepto = document.getElementById('editar-concepto');
            selectConcepto.value = concepto;

            // Extra: si por algún motivo no coincide exactamente
            Array.from(selectConcepto.options).forEach(opt => {
                if (opt.value.toLowerCase() === concepto) {
                    opt.selected = true;
                }
            });

            document.getElementById('editar-monto').value = this.dataset.monto;
            document.getElementById('editar-metodo').value = this.dataset.metodo;
            document.getElementById('editar-fecha').value = this.dataset.fecha;
            document.getElementById('editar-estado').value = this.dataset.estado;

            formEditar.action = `/pagos/editar/${id}`;

            // Cargar estudiantes del curso actual
            fetch(`/pagos/matriculas_por_curso/${idCurso}`)
                .then(res => res.json())
                .then(lista => {
                    const selectEditMatricula = document.getElementById('editar-id-matricula');
                    const hiddenEditMatricula = document.getElementById('editar-id-matricula-hidden');
                    const previewImg = document.getElementById('preview-foto');

                    selectEditMatricula.innerHTML = '';
                    lista.forEach(m => {
                        const option = document.createElement('option');
                        option.value = m.id;
                        option.textContent = m.nombre;
                        option.dataset.foto = m.foto;
                        selectEditMatricula.appendChild(option);
                    });

                    selectEditMatricula.value = idMatricula;
                    hiddenEditMatricula.value = idMatricula;

                    const selected = selectEditMatricula.options[selectEditMatricula.selectedIndex];
                    if (selected && selected.dataset.foto) {
                        previewImg.src = selected.dataset.foto;
                        previewImg.style.display = 'block';
                    } else {
                        previewImg.style.display = 'none';
                    }
                });
        });
    });

    // 3. Eliminar pago
    document.querySelectorAll('.btn-eliminar-pago').forEach(btn => {
        btn.addEventListener('click', function () {
            const form = this.closest('form');
            const nombre = this.dataset.nombre;

            Swal.fire({
                title: 'Eliminar pago',
                html: `¿Deseas eliminar el pago de <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then(result => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });

    // 4. Ver detalles de comprobante
    document.querySelectorAll('.btn-ver-detalles').forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.dataset.id;
            const url = `/pagos/comprobante/${id}`;
            const iframe = document.getElementById('iframe-comprobante');
            const descargar = document.getElementById('btn-descargar-comprobante');
            const whatsapp = document.getElementById('btn-enviar-whatsapp');
            const correo = document.getElementById('btn-enviar-correo');

            iframe.src = url;
            descargar.href = url;

            fetch(`/pagos/info_contacto/${id}`)
                .then(res => res.json())
                .then(data => {
                    // Configurar WhatsApp
                    const mensajeWhatsApp = `Hola estimado/a acudiente de  ${data.nombre}, acabo de enviar el comprobante de pago a su correo electrónico ${data.correo}. ¿Podría confirmar si lo ha recibido?`;
                    const urlWhatsApp = `https://wa.me/${data.whatsapp}?text=${encodeURIComponent(mensajeWhatsApp)}`;
                    whatsapp.href = urlWhatsApp;

                    // Configurar correo electrónico
                    correo.onclick = function () {
                        Swal.fire({
                            title: 'Enviando comprobante...',
                            text: 'Por favor espere',
                            allowOutsideClick: false,
                            didOpen: () => {
                                Swal.showLoading();
                            }
                        });

                        fetch(`/pagos/enviar_comprobante/${id}`, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                            }
                        })
                            .then(response => response.json())
                            .then(result => {
                                Swal.close();
                                if (result.success) {
                                    Swal.fire({
                                        title: '¡Éxito!',
                                        html: `Comprobante enviado a <strong>${data.correo}</strong><br><br>
                                   <button class="btn btn-success mt-3" onclick="window.open('${urlWhatsApp}', '_blank')">
                                       <i class="fab fa-whatsapp"></i> Abrir WhatsApp
                                   </button>`,
                                        icon: 'success',
                                        showConfirmButton: true,
                                        confirmButtonText: 'Cerrar'
                                    });
                                } else {
                                    Swal.fire('Error', result.message, 'error');
                                }
                            })
                            .catch(err => {
                                Swal.close();
                                Swal.fire('Error', 'No se pudo enviar el correo', 'error');
                            });
                    };
                });
        });
    });
});