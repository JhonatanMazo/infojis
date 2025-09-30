from app import create_app
from app.extensions import db
from app.models.user import User

# Crear aplicación primero
app = create_app()

# Importar modelos DENTRO del contexto de aplicación
with app.app_context():

    # Verificar si ya existe un usuario administrador
    if db.session.query(User).filter_by(email="admin@infojis.com").first():
        print("El usuario administrador ya existe.")
    else:
        # Usuario administrador
        admin = User(
            nombre="Administrador",
            apellidos="Sistema",
            documento="00000001", 
            email="admin@infojis.com",
            rol="admin",
            estado="activo",
            genero="sin_especificar"
        )
        admin.set_password("Admin1234")
        db.session.add(admin)
        print("Usuario administrador creado.")
   
    try:
        db.session.commit()
        print("\n¡Usuario creado exitosamente!")
        print("=================================")
        print("Rol: Administrador")
        print(f"Email: admin@infojis.com")
        print(f"Contraseña: Admin1234")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear usuarios: {str(e)}")