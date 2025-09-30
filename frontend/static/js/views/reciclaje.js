document.addEventListener('DOMContentLoaded', function () {
    // Restaurar elemento
    document.querySelectorAll('.btn-restaurar').forEach(button => {
        button.addEventListener('click', function (event) {
            event.preventDefault();
            const form = this.closest('form');
            const nombre = this.getAttribute('data-nombre');

            Swal.fire({
                title: `¿Restaurar ${nombre}?`,
                text: "El elemento volverá a estar disponible en el sistema.",
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, restaurar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });

    // Eliminar elemento permanentemente
    document.querySelectorAll('.btn-eliminar-definitivo').forEach(button => {
        button.addEventListener('click', function (event) {
            event.preventDefault();
            const form = this.closest('form');
            const nombre = this.getAttribute('data-nombre');

            Swal.fire({
                title: `¿Eliminar ${nombre} permanentemente?`,
                text: "¡Esta acción no se puede deshacer!",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });

    // Restaurar todo
    const btnRestaurarTodo = document.getElementById('btn-exportar');
    if (btnRestaurarTodo) {
        btnRestaurarTodo.addEventListener('click', function (event) {
            event.preventDefault();
            const hayElementos = document.querySelector('#tabla-reciclaje .deleted-item');
            if (!hayElementos) {
                Swal.fire({
                    title: 'Papelera Vacía',
                    text: 'No hay elementos para restaurar en el año lectivo actual.',
                    icon: 'info',
                    confirmButtonText: 'Entendido'
                });
                return;
            }
            Swal.fire({
                title: '¿Restaurar todos los elementos?',
                text: 'Todos los elementos de la papelera serán restaurados.',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, restaurar todo',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    // Crear y enviar formulario POST
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = '/reciclaje/restaurar_todo';
                    // CSRF token
                    const csrf = document.querySelector('input[name="csrf_token"]');
                    if (csrf) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'csrf_token';
                        input.value = csrf.value;
                        form.appendChild(input);
                    }
                    document.body.appendChild(form);
                    form.submit();
                }
            });
        });
    }

    // Limpiar papelera
    const btnLimpiarPapelera = document.getElementById('btn-limpiar-papelera');
    if (btnLimpiarPapelera) {
        btnLimpiarPapelera.addEventListener('click', function (event) {
            event.preventDefault();
            const hayElementos = document.querySelector('#tabla-reciclaje .deleted-item');
            if (!hayElementos) {
                Swal.fire({
                    title: 'Papelera Vacía',
                    text: 'No hay elementos para eliminar en el año lectivo actual.',
                    icon: 'info',
                    confirmButtonText: 'Entendido'
                });
                return;
            }
            Swal.fire({
                title: '¿Limpiar la papelera?',
                text: 'Todos los elementos serán eliminados permanentemente. ¡Esta acción no se puede deshacer!',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, limpiar todo',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    // Crear y enviar formulario POST
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = '/reciclaje/eliminar_todo_definitivo';
                    // CSRF token
                    const csrf = document.querySelector('input[name="csrf_token"]');
                    if (csrf) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'csrf_token';
                        input.value = csrf.value;
                        form.appendChild(input);
                    }
                    document.body.appendChild(form);
                    form.submit();
                }
            });
        });
    }

    // Filtrado por tipo de elemento
    const btnFiltrar = document.getElementById('btn-filtrar');
    const selectTipoElemento = document.getElementById('select-tipo-elemento');
    if (btnFiltrar && selectTipoElemento) {
        btnFiltrar.addEventListener('click', function (event) {
            event.preventDefault();
            const tipo = selectTipoElemento.value;
            // Redirigir con query param
            const url = new URL(window.location.href);
            url.searchParams.set('tipo_modelo', tipo);
            window.location.href = url.toString();
        });
    }
});