from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import eventlet  # Asegúrate de importar eventlet

app = Flask(__name__)
cors = CORS()
socketio = SocketIO()  # Aquí sigue inicializando el SocketIO

def create_app():
    app.config.from_object('app.config.Config')
    
    # Inicializar extensiones
    cors.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")  # Configuración de CORS para el socket
    
    from app import routes
    app.register_blueprint(routes.api)
    
    app.config['SECRET_KEY'] = 'x'  
    return app
