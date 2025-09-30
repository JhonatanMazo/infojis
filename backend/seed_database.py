from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.curso import Curso
from app.models.asignatura import Asignatura
from app.models.matricula import Matricula
from app.models.asignacion import Asignacion
from app.models.inclusion import Inclusion
from app.models.observacion import Observacion
from app.models.pago import Pago
from app.services.configuracion_service import get_active_config
import random
from datetime import date, timedelta

app = create_app()

def crear_usuarios():
    """Crear usuarios administradores y docentes"""
    print("=== CREANDO USUARIOS ===")
    
    try:
        # Crear 50 usuarios administradores
        for i in range(1, 51):
            email = f"admin{i}@infojis.com"
            documento = f"10000{i:02d}"
            if db.session.query(User).filter_by(email=email).first():
                print(f"El usuario {email} ya existe. Saltando.")
                continue
            
            admin = User(
                nombre=f"Admin",
                apellidos=f"User {i}",
                documento=documento,
                email=email,
                rol="admin",
                estado="activo",
                genero=random.choice(['femenino', 'masculino'])
            )
            admin.set_password("Password123")
            db.session.add(admin)
            print(f"Usuario administrador {email} preparado para creación.")

        # Crear 50 usuarios docentes
        for i in range(1, 51):
            email = f"docente{i}@infojis.com"
            documento = f"20000{i:02d}"
            if db.session.query(User).filter_by(email=email).first():
                print(f"El usuario {email} ya existe. Saltando.")
                continue

            docente = User(
                nombre=f"Docente",
                apellidos=f"User {i}",
                documento=documento,
                email=email,
                rol="docente",
                estado="activo",
                genero=random.choice(['femenino', 'masculino'])
            )
            docente.set_password("Password123")
            db.session.add(docente)
            print(f"Usuario docente {email} preparado para creación.")
        
        db.session.commit()
        print("¡100 usuarios de prueba creados exitosamente!")
        print("Contraseña para todos los usuarios: Password123")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear usuarios: {str(e)}")
        return False

def crear_cursos():
    """Crear cursos de prueba"""
    print("\n=== CREANDO CURSOS ===")
    
    cursos_a_crear = [
        {"nombre": "Párvulos"},
        {"nombre": "Pre-Jardín"},
        {"nombre": "Jardín"},
        {"nombre": "Transición"},
        {"nombre": "Primero"},
        {"nombre": "Segundo"},
        {"nombre": "Tercero"},
        {"nombre": "Cuarto"},
        {"nombre": "Quinto"},
        {"nombre": "Sexto"},
        {"nombre": "Séptimo"},
        {"nombre": "Octavo"},
        {"nombre": "Noveno"},
        {"nombre": "Décimo"},
        {"nombre": "Undécimo"}
    ]

    try:
        for curso_data in cursos_a_crear:
            nombre_curso = curso_data["nombre"]
            if db.session.query(Curso).filter_by(nombre=nombre_curso).first():
                print(f"El curso '{nombre_curso}' ya existe. Saltando.")
                continue
            
            nuevo_curso = Curso(nombre=nombre_curso)
            db.session.add(nuevo_curso)
            print(f"Curso '{nombre_curso}' preparado para creación.")
        
        db.session.commit()
        print("¡Cursos de prueba creados exitosamente!")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear los cursos: {str(e)}")
        return False

def crear_asignaturas():
    """Crear asignaturas de prueba"""
    print("\n=== CREANDO ASIGNATURAS ===")
    
    asignaturas_a_crear = [
        "Matemáticas",
        "Ciencias Naturales",
        "Ciencias Sociales",
        "Lengua Castellana",
        "Inglés",
        "Educación Física",
        "Artes Plásticas",
        "Música",
        "Tecnología e Informática",
        "Ética y Valores",
        "Religión"
    ]

    try:
        for nombre_asignatura in asignaturas_a_crear:
            if db.session.query(Asignatura).filter_by(nombre=nombre_asignatura).first():
                print(f"La asignatura '{nombre_asignatura}' ya existe. Saltando.")
                continue
            
            nueva_asignatura = Asignatura(nombre=nombre_asignatura)
            db.session.add(nueva_asignatura)
            print(f"Asignatura '{nombre_asignatura}' preparada para creación.")
        
        db.session.commit()
        print("¡Asignaturas de prueba creadas exitosamente!")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear las asignaturas: {str(e)}")
        return False

def crear_matriculas():
    """Crear matrículas de prueba"""
    print("\n=== CREANDO MATRÍCULAS ===")
    
    # Configuración
    ESTUDIANTES_POR_CURSO = 200

    # Datos de ejemplo
    NOMBRES = ["Sofía", "Hugo", "Martina", "Mateo", "Lucía", "Leo", "Valentina", "Daniel", "Camila", "Alejandro", "Isabella", "Manuel", "Valeria", "Pablo", "Gabriela"]
    APELLIDOS = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Martin", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno"]

    try:
        # Asegurarse de que hay una configuración activa antes de empezar
        if not get_active_config():
            print("Error: No hay un año lectivo configurado como activo.")
            print("Por favor, configure un año lectivo en la aplicación antes de ejecutar este script.")
            return False

        # Obtener el año lectivo activo
        config_activa = get_active_config()
        if not config_activa or 'anio' not in config_activa:
            print("Error: No se pudo obtener el año lectivo de la configuración activa.")
            print("Asegúrate de haber configurado un año lectivo en la sección de Configuración de la aplicación.")
            return False
        
        año_actual = config_activa['anio']
        print(f"Año lectivo activo: {año_actual}")

        # Obtener todos los cursos de la BD
        cursos = Curso.query.filter_by(estado='activo').all()
        if not cursos:
            print("Error: No se encontraron cursos activos en la base de datos.")
            return False

        # Generar matrículas
        total_creados = 0
        documento_counter = 10101010

        for curso in cursos:
            print(f"Creando matrículas para el curso: {curso.nombre}")
            for i in range(ESTUDIANTES_POR_CURSO):
                documento = str(documento_counter)
                documento_counter += 1

                # Evitar duplicados en el mismo año lectivo
                if Matricula.query.filter_by(documento=documento, año_lectivo=año_actual).first():
                    print(f"La matrícula para el documento {documento} en el año {año_actual} ya existe. Saltando.")
                    continue

                nombre = random.choice(NOMBRES)
                apellido = random.choice(APELLIDOS)
                email = f"{nombre.lower()}.{apellido.lower()}{i}@ejemplo.com"
                genero_choice = random.choice(['femenino', 'masculino'])
                
                # Fecha de nacimiento aleatoria (entre 6 y 17 años)
                hoy = date.today()
                año_nacimiento = hoy.year - random.randint(6, 17)
                fecha_nacimiento = date(año_nacimiento, random.randint(1, 12), random.randint(1, 28))

                nueva_matricula = Matricula(
                    nombres=nombre,
                    apellidos=apellido,
                    genero=genero_choice,
                    documento=documento,
                    email=email,
                    telefono=f"300{random.randint(1000000, 9999999)}",
                    direccion=f"Calle Falsa 123, Ciudad Ejemplo",
                    fecha_nacimiento=fecha_nacimiento,
                    id_curso=curso.id,
                    año_lectivo=año_actual,
                    estado='activo'
                )
                db.session.add(nueva_matricula)
                total_creados += 1
        
        if total_creados > 0:
            db.session.commit()
            print(f"¡{total_creados} matrículas de prueba creadas exitosamente para el año {año_actual}!")
            return True
        else:
            print("No se crearon nuevas matrículas. Es posible que ya existieran.")
            return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear las matrículas: {str(e)}")
        return False

def crear_asignaciones():
    """Crear asignaciones de prueba"""
    print("\n=== CREANDO ASIGNACIONES ===")
    
    # Configuración
    NUMERO_DE_ASIGNACIONES = 28

    try:
        # Obtener el año lectivo activo
        config_activa = get_active_config()
        if not config_activa or 'anio' not in config_activa:
            print("Error: No se pudo obtener el año lectivo de la configuración activa.")
            return False
        
        año_actual = config_activa['anio']
        print(f"Año lectivo activo: {año_actual}")

        # Obtener registros de la BD
        docentes = User.query.filter_by(rol='docente', estado='activo').all()
        cursos = Curso.query.filter_by(estado='activo').all()
        asignaturas = Asignatura.query.filter_by(estado='activo').all()

        if not all([docentes, cursos, asignaturas]):
            print("Error: Faltan datos para crear asignaciones.")
            print("Asegúrate de que existan docentes, cursos y asignaturas activos.")
            return False

        # Generar asignaciones
        asignaciones_creadas = 0
        intentos = 0
        max_intentos = NUMERO_DE_ASIGNACIONES * 5  # Evitar bucle infinito
        combinaciones_usadas = set()

        print(f"Intentando crear {NUMERO_DE_ASIGNACIONES} asignaciones")

        while asignaciones_creadas < NUMERO_DE_ASIGNACIONES and intentos < max_intentos:
            docente = random.choice(docentes)
            curso = random.choice(cursos)
            asignatura = random.choice(asignaturas)

            combinacion = (docente.id, curso.id, asignatura.id, año_actual)
            
            if combinacion in combinaciones_usadas:
                intentos += 1
                continue  # Combinación ya intentada en esta ejecución

            combinaciones_usadas.add(combinacion)

            # Verificar si ya existe en la BD
            existe = Asignacion.query.filter_by(
                id_docente=docente.id,
                id_curso=curso.id,
                id_asignatura=asignatura.id,
                anio_lectivo=año_actual
            ).first()

            if existe:
                print(f"Asignación ya existe: Docente {docente.id} -> {curso.nombre} -> {asignatura.nombre}. Saltando.")
                intentos += 1
                continue

            nueva_asignacion = Asignacion(
                id_docente=docente.id,
                id_curso=curso.id,
                id_asignatura=asignatura.id,
                anio_lectivo=año_actual
            )
            db.session.add(nueva_asignacion)
            asignaciones_creadas += 1
            print(f"(#{asignaciones_creadas}) Asignación preparada: {docente.nombre} -> {curso.nombre} -> {asignatura.nombre}")
            
            intentos += 1

        if asignaciones_creadas > 0:
            db.session.commit()
            print(f"¡{asignaciones_creadas} asignaciones de prueba creadas exitosamente para el año {año_actual}!")
            return True
        else:
            print("No se crearon nuevas asignaciones. Es posible que ya existieran todas las combinaciones generadas.")
            return True
            
        if asignaciones_creadas < NUMERO_DE_ASIGNACIONES:
            print(f"Advertencia: Se solicitaron {NUMERO_DE_ASIGNACIONES} pero solo se pudieron crear {asignaciones_creadas} únicas.")

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear las asignaciones: {str(e)}")
        return False

def crear_inclusiones():
    """Crear registros de inclusión de prueba"""
    print("\n=== CREANDO REGISTROS DE INCLUSIÓN ===")
    
    # Configuración
    NUMERO_DE_INCLUSIONES = 50

    # Datos de ejemplo
    TIPOS_NECESIDAD = [
        "Dificultades de aprendizaje (dislexia, discalculia)",
        "Trastorno por déficit de atención e hiperactividad (TDAH)",
        "Trastorno del espectro autista (TEA)",
        "Discapacidad intelectual leve",
        "Altas capacidades intelectuales",
        "Dificultades en el lenguaje y la comunicación",
        "Problemas de conducta y emocionales"
    ]
    PLANES_APOYO = [
        "Adaptaciones curriculares en matemáticas y lenguaje.",
        "Sesiones de refuerzo semanales con el psicopedagogo.",
        "Uso de material visual y manipulativo en clase.",
        "Evaluaciones orales en lugar de escritas.",
        "Plan de enriquecimiento curricular en ciencias.",
        "Tutoría entre pares para fomentar la colaboración.",
        "Estrategias de manejo del tiempo y organización de tareas."
    ]

    try:
        # Obtener el año lectivo activo
        config_activa = get_active_config()
        if not config_activa or 'anio' not in config_activa:
            print("Error: No se pudo obtener el año lectivo de la configuración activa.")
            return False
        
        año_actual = config_activa['anio']
        print(f"Año lectivo activo: {año_actual}")

        # Obtener matrículas y usuarios (admins) activos
        matriculas_activas = Matricula.query.filter_by(año_lectivo=año_actual, estado='activo').all()
        usuarios_admin = User.query.filter_by(estado='activo', rol='admin').all()

        if not matriculas_activas:
            print("Error: No se encontraron matrículas activas para el año lectivo actual.")
            return False
        
        if not usuarios_admin:
            print("Error: No se encontraron usuarios administradores activos.")
            return False

        # Generar inclusiones
        inclusiones_creadas = 0
        matriculas_usadas = set()

        print(f"Intentando crear {NUMERO_DE_INCLUSIONES} registros de inclusión")

        # Mezclar las matrículas para no elegir siempre las mismas al principio
        random.shuffle(matriculas_activas)

        for matricula in matriculas_activas:
            if inclusiones_creadas >= NUMERO_DE_INCLUSIONES:
                break

            # Evitar crear más de un registro de inclusión por estudiante en el seeder
            if matricula.id in matriculas_usadas:
                continue

            # Verificar si ya existe en la BD (por si se corre el script varias veces)
            existe = Inclusion.query.filter_by(id_matricula=matricula.id).first()
            if existe:
                print(f"El estudiante {matricula.nombres} ya tiene un registro de inclusión. Saltando.")
                matriculas_usadas.add(matricula.id)
                continue

            usuario = random.choice(usuarios_admin)
            tipo_necesidad = random.choice(TIPOS_NECESIDAD)
            plan_apoyo = random.choice(PLANES_APOYO)
            fecha_ingreso = date.today() - timedelta(days=random.randint(30, 365))

            nueva_inclusion = Inclusion(
                id_matricula=matricula.id,
                id_curso=matricula.id_curso,
                id_usuario=usuario.id,
                tipo_necesidad=tipo_necesidad,
                plan_apollo=plan_apoyo,
                fecha_ingreso=fecha_ingreso,
                detalles=None  # No se generan archivos en el seeder
            )
            db.session.add(nueva_inclusion)
            inclusiones_creadas += 1
            matriculas_usadas.add(matricula.id)
            print(f"(#{inclusiones_creadas}) Inclusión para {matricula.nombres} preparada.")

        if inclusiones_creadas > 0:
            db.session.commit()
            print(f"¡{inclusiones_creadas} registros de inclusión de prueba creados exitosamente para el año {año_actual}!")
            return True
        else:
            print("No se crearon nuevos registros de inclusión. Es posible que ya existieran para los estudiantes disponibles.")
            return True

        if inclusiones_creadas < NUMERO_DE_INCLUSIONES:
            print(f"Advertencia: Se solicitaron {NUMERO_DE_INCLUSIONES} pero solo se pudieron crear {inclusiones_creadas} (una por estudiante).")

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear los registros de inclusión: {str(e)}")
        return False

def crear_observaciones():
    """Crear observaciones de prueba"""
    print("\n=== CREANDO OBSERVACIONES ===")
    
    # Configuración
    NUMERO_DE_OBSERVACIONES = 150

    # Datos de ejemplo
    TIPOS_OBSERVACION = ['académica', 'asistencia', 'disciplinaria']
    DESCRIPCIONES = {
        'académica': [
            "Muestra un excelente progreso en la comprensión de conceptos matemáticos.",
            "Participa activamente en las discusiones de clase y aporta ideas valiosas.",
            "Necesita mejorar la organización de sus apuntes y tareas.",
            "Ha demostrado una notable mejoría en sus habilidades de lectura.",
            "Presenta dificultades para concentrarse durante las explicaciones."
        ],
        'asistencia': [
            "Llegó 15 minutos tarde a la primera hora de clase.",
            "Faltó a la jornada escolar sin justificación previa.",
            "Se retiró antes de finalizar la jornada por cita médica.",
            "Asistencia perfecta durante la última semana.",
            "Presentó excusa médica por su ausencia del día de ayer."
        ],
        'disciplinaria': [
            "Interrumpió la clase en repetidas ocasiones.",
            "Mostró una actitud colaborativa y respetuosa con sus compañeros.",
            "No cumplió con el material solicitado para la actividad.",
            "Ayudó a un compañero que tenía dificultades con la tarea.",
            "Fue sorprendido usando el teléfono móvil durante la lección."
        ]
    }

    try:
        # Obtener el año lectivo activo
        config_activa = get_active_config()
        if not config_activa or 'anio' not in config_activa:
            print("Error: No se pudo obtener el año lectivo de la configuración activa.")
            return False
        
        año_actual = config_activa['anio']
        print(f"Año lectivo activo: {año_actual}")

        # Obtener matrículas y usuarios activos
        matriculas_activas = Matricula.query.filter_by(año_lectivo=año_actual, estado='activo').all()
        usuarios_activos = User.query.filter_by(estado='activo').filter(User.rol.in_(['admin', 'docente'])).all()

        if not matriculas_activas:
            print("Error: No se encontraron matrículas activas para el año lectivo actual.")
            return False
        
        if not usuarios_activos:
            print("Error: No se encontraron usuarios (docentes/admins) activos.")
            return False

        # Generar observaciones
        observaciones_creadas = 0
        intentos = 0
        max_intentos = NUMERO_DE_OBSERVACIONES * 3  # Para evitar bucles infinitos si hay muchos duplicados

        print(f"Intentando crear {NUMERO_DE_OBSERVACIONES} observaciones")

        while observaciones_creadas < NUMERO_DE_OBSERVACIONES and intentos < max_intentos:
            matricula = random.choice(matriculas_activas)
            usuario = random.choice(usuarios_activos)
            tipo_obs = random.choice(TIPOS_OBSERVACION)
            descripcion = random.choice(DESCRIPCIONES[tipo_obs])
            fecha_obs = date.today() - timedelta(days=random.randint(0, 90))


            nueva_observacion = Observacion(
                id_matricula=matricula.id,
                id_usuario=usuario.id,
                id_curso=matricula.id_curso,
                tipo=tipo_obs,
                fecha=fecha_obs,
                descripcion=descripcion
            )
            db.session.add(nueva_observacion)
            observaciones_creadas += 1
            print(f"(#{observaciones_creadas}) Observación '{tipo_obs}' para {matricula.nombres} preparada.")
            
            intentos += 1

        if observaciones_creadas > 0:
            db.session.commit()
            print(f"¡{observaciones_creadas} observaciones de prueba creadas exitosamente para el año {año_actual}!")
            return True
        else:
            print("No se crearon nuevas observaciones.")
            return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear las observaciones: {str(e)}")
        return False

def crear_pagos():
    """Crear registros de pago de prueba"""
    print("\n=== CREANDO REGISTROS DE PAGO ===")
    
    # Configuración
    NUMERO_DE_PAGOS = 250

    # Datos de ejemplo
    CONCEPTOS = ['mensualidad', 'matricula', 'derecho a grado']
    METODOS_PAGO = ['efectivo', 'transferencia', 'consignacion', 'tarjeta']
    ESTADOS_PAGO = ['pagado', 'pendiente']
    MONTOS = {
        'mensualidad': (150000, 250000),
        'matricula': (300000, 400000),
        'derecho a grado': (100000, 150000)
    }

    try:
        # Obtener el año lectivo activo
        config_activa = get_active_config()
        if not config_activa or 'anio' not in config_activa:
            print("Error: No se pudo obtener el año lectivo de la configuración activa.")
            return False
        
        año_actual = config_activa['anio']
        print(f"Año lectivo activo: {año_actual}")

        # Obtener matrículas y usuarios (admins) activos
        matriculas_activas = Matricula.query.filter_by(año_lectivo=año_actual, estado='activo').all()
        usuarios_admin = User.query.filter_by(estado='activo', rol='admin').all()

        if not matriculas_activas:
            print("Error: No se encontraron matrículas activas para el año lectivo actual.")
            return False
        
        if not usuarios_admin:
            print("Error: No se encontraron usuarios administradores activos.")
            return False

        # Generar pagos
        pagos_creados = 0
        intentos = 0
        max_intentos = NUMERO_DE_PAGOS * 3  # Para evitar bucles infinitos

        print(f"Intentando crear {NUMERO_DE_PAGOS} registros de pago")

        while pagos_creados < NUMERO_DE_PAGOS and intentos < max_intentos:
            matricula = random.choice(matriculas_activas)
            usuario = random.choice(usuarios_admin)
            concepto = random.choice(CONCEPTOS)
            monto_range = MONTOS[concepto]
            monto = random.randint(monto_range[0], monto_range[1])
            metodo_pago = random.choice(METODOS_PAGO)
            estado = random.choice(ESTADOS_PAGO)
            fecha_pago = date.today() - timedelta(days=random.randint(0, 180))


            nuevo_pago = Pago(
                id_matricula=matricula.id,
                id_curso=matricula.id_curso,
                id_usuario=usuario.id,
                concepto=concepto,
                monto=monto,
                metodo_pago=metodo_pago,
                fecha_pago=fecha_pago,
                estado=estado
            )
            db.session.add(nuevo_pago)
            pagos_creados += 1
            print(f"(#{pagos_creados}) Pago de '{concepto}' para {matricula.nombres} preparado.")
            
            intentos += 1

        if pagos_creados > 0:
            db.session.commit()
            print(f"¡{pagos_creados} pagos de prueba creados exitosamente para el año {año_actual}!")
            return True
        else:
            print("No se crearon nuevos pagos.")
            return True

    except Exception as e:
        db.session.rollback()
        print(f"Error al crear los pagos: {str(e)}")
        return False

def main():
    """Función principal que ejecuta todos los procesos en orden"""
    with app.app_context():
        print("INICIANDO PROCESO DE POBLADO DE BASE DE DATOS")
        print("=" * 50)
        
        # Ejecutar en el orden correcto para respetar dependencias
        funciones = [
            crear_usuarios,      # 1. Usuarios (admins y docentes)
            crear_cursos,        # 2. Cursos
            crear_asignaturas,   # 3. Asignaturas
            crear_matriculas,    # 4. Matrículas (requiere cursos)
            crear_asignaciones,  # 5. Asignaciones (requiere usuarios, cursos, asignaturas)
            crear_inclusiones,   # 6. Inclusiones (requiere matrículas y usuarios)
            crear_observaciones, # 7. Observaciones (requiere matrículas y usuarios)
            crear_pagos          # 8. Pagos (requiere matrículas y usuarios)
        ]
        
        for funcion in funciones:
            if not funcion():
                print(f"\nError en {funcion.__name__}. Deteniendo ejecución.")
                return
        
        print("\n" + "=" * 50)
        print("¡PROCESO COMPLETADO EXITOSAMENTE!")
        print("Todos los datos han sido insertados en la base de datos.")
        print("\nResumen de datos creados:")
        print("- 100 usuarios (50 admin + 50 docentes)")
        print("- 15 cursos")
        print("- 11 asignaturas")
        print("- 200 matrículas por curso (3000 estudiantes en total)")
        print("- 28 asignaciones aleatorias")
        print("- 50 registros de inclusión")
        print("- 150 observaciones")
        print("- 250 registros de pago")
        print("\nContraseñas de usuarios: Password123")

if __name__ == "__main__":
    main()