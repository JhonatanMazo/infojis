from app import create_app
from app.models.user import User  

app = create_app()

def listar_usuarios():
    usuarios = User.query.all()
    for u in usuarios:
        print(f"ID: {u.id}, Nombre: {u.nombre}, Email: {u.email}, Contraseña (hash): {u.contraseña}")

if __name__ == "__main__":
    with app.app_context():
        listar_usuarios()
