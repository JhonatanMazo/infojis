document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.btn-eliminar-actividad').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const form = btn.closest('form');
            const titulo = btn.getAttribute('data-titulo') || 'esta actividad';
            Swal.fire({
                title: '¿Estás seguro?',
                text: `¿Deseas eliminar ${titulo}? Esta acción no se puede deshacer.`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });

    const formEliminarTodas = document.getElementById('form-eliminar-todas');
    if (formEliminarTodas) {
        formEliminarTodas.addEventListener('submit', function (e) {
            e.preventDefault();
            Swal.fire({
                title: '¿Estás seguro?',
                text: '¿Deseas eliminar todas las notificaciones? Esta acción no se puede deshacer.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, eliminar todas',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminarTodas.submit();
                }
            });
        });
    }
});