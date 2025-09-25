document.addEventListener('DOMContentLoaded', function () {
    const btnExportar = document.getElementById('btn-exportar');
    const btnActualizar = document.getElementById('btn-actualizar');
    const btnFiltrar = document.querySelector('.btn-aplicar-filtros');
    const formatoBtns = document.querySelectorAll('.btn-formato');
    const presetBtns = document.querySelectorAll('.btn-preset');
    let formatoSeleccionado = null;

    const presets = {
        'Datos Basicos': ['Nombres', 'Apellidos', 'Grado', 'Telefono', 'Genero', 'Fecha Nacimiento', 'Documento', 'Direccion'],
        'Datos Completos': ['Nombres', 'Apellidos', 'Documento', 'Fecha Nacimiento', 'Genero', 'Direccion', 'Telefono', 'Correo', 'Grado', 'Año Lectivo', 'Estado', 'Promedio General'],
        'Datos Academicos': ['Nombres', 'Apellidos', 'Grado', 'Estado', 'Año Lectivo', 'Promedio General'],
    };

    // Función para mostrar notificación en esquina superior derecha
    function mostrarNotificacion(mensaje, tipo = 'error') {
        // Usar Toast de SweetAlert para notificaciones en esquina superior derecha
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
            icon: tipo,
            background: tipo === 'error' ? '#f8d7da' : '#d4edda',
            iconColor: tipo === 'error' ? '#dc3545' : '#28a745',
            didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer)
                toast.addEventListener('mouseleave', Swal.resumeTimer)
            }
        });

        Toast.fire({
            title: mensaje,
            icon: tipo
        });
    }

    // Manejo de presets
    presetBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const tipo = this.getAttribute('data-preset');
            const seleccionados = presets[tipo] || [];

            // Quitar activo de otros botones
            presetBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Desmarcar todos
            document.querySelectorAll('input.form-check-input[name="campos[]"]').forEach(input => {
                input.checked = false;
            });

            // Marcar campos del preset
            seleccionados.forEach(nombreCampo => {
                const input = Array.from(document.querySelectorAll('input.form-check-input[name="campos[]"]'))
                    .find(i => i.value === nombreCampo);
                if (input) input.checked = true;
            });
        });
    });

    // Selección de formato
    formatoBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            formatoBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            formatoSeleccionado = btn.getAttribute('data-formato');
        });
    });

    // Función para actualizar tabla
    function actualizarTabla() {
        const grado = document.querySelector('[name="grado"]').value;
        const estado = document.querySelector('[name="estado"]').value;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const camposSeleccionados = Array.from(document.querySelectorAll('input[name="campos[]"]:checked')).map(cb => cb.value);

        const formData = new FormData();
        formData.append('grado', grado);
        formData.append('estado', estado);
        formData.append('csrf_token', csrfToken);
        camposSeleccionados.forEach(campo => {
            formData.append('campos[]', campo);
        });

        fetch('/exportar_datos/vista_previa', {
            method: 'POST',
            body: formData
        })
            .then(resp => resp.json())
            .then(data => {
                const thead = document.querySelector('#vista-previa-head');
                const tbody = document.querySelector('#vista-previa-body');
                const camposSeleccionados = Array.from(document.querySelectorAll('input[name="campos[]"]:checked')).map(cb => cb.value);
                
                thead.innerHTML = '';
                tbody.innerHTML = '';

                // Definir la cabecera de la tabla
                const headerRow = document.createElement('tr');
                const thCounter = document.createElement('th');
                thCounter.textContent = '#';
                headerRow.appendChild(thCounter);

                if (camposSeleccionados.length > 0) {
                    camposSeleccionados.forEach(headerText => {
                        const th = document.createElement('th');
                        th.textContent = headerText;
                        headerRow.appendChild(th);
                    });
                }
                thead.appendChild(headerRow);

                if (data.length === 0) {
                    const colspan = (camposSeleccionados.length || 0) + 1;
                    tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center text-muted p-4"><i class="fas fa-info-circle me-2"></i>No hay datos para mostrar.</td></tr>`;
                    return;
                }

                // Crear filas de datos
                data.forEach((row, index) => {
                    const tr = document.createElement('tr');
                    
                    const tdCounter = document.createElement('td');
                    tdCounter.textContent = index + 1;
                    tr.appendChild(tdCounter);

                    camposSeleccionados.forEach(header => {
                        const td = document.createElement('td');
                        td.textContent = row[header] !== undefined ? row[header] : '';
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });

                const footerInfo = document.querySelector('.card-footer .text-muted');
                if (footerInfo) {
                    footerInfo.textContent = `Mostrando ${data.length} registro${data.length !== 1 ? 's' : ''} (vista previa)`;
                }
            })
            .catch(err => {
                console.error('Error al filtrar:', err);
                mostrarNotificacion('Error al aplicar filtros', 'error');
            });
    }

    // Botones de filtro y actualizar
    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', actualizarTabla);
    }
    if (btnActualizar) {
        btnActualizar.addEventListener('click', actualizarTabla);
    }

    // Exportar
    btnExportar.addEventListener('click', () => {
        if (!formatoSeleccionado) {
            // Mostrar advertencia con SweetAlert (solo para este caso)
            Swal.fire({
                title: 'Exportación',
                html: 'Por favor selecciona un formato de exportación asi sea en (Excel, CSV o PDF).',
                icon: 'warning',
                confirmButtonText: 'Aceptar',
                confirmButtonColor: '#3085d6',
            });
            return;
        }

        // Ocultar el modal de exportar (si existe)
        const modalExportar = document.getElementById('modalExportar');
        if (modalExportar) {
            const bsModal = bootstrap.Modal.getInstance(modalExportar);
            if (bsModal) bsModal.hide();
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const formData = new FormData();
        formData.append('grado', document.querySelector('[name="grado"]').value);
        formData.append('estado', document.querySelector('[name="estado"]').value);
        formData.append('formato', formatoSeleccionado);
        formData.append('csrf_token', csrfToken);

        // Añadir campos seleccionados
        document.querySelectorAll('.form-check-input:checked').forEach(cb => {
            formData.append('campos[]', cb.value);
        });

        fetch('/exportar_datos/exportar_estudiantes', {
            method: 'POST',
            body: formData
        })
            .then(resp => {
                if (!resp.ok) throw new Error('Error exportando');
                return resp.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const ext = formatoSeleccionado === 'excel' ? 'xlsx' : formatoSeleccionado;
                a.download = `estudiantes.${ext}`;
                document.body.appendChild(a);
                a.click();
                a.remove();

            })
            .catch(err => {
                // Mostrar error como notificación en esquina superior derecha
                mostrarNotificacion('Error al exportar: ' + err.message, 'error');
            });
    });
});