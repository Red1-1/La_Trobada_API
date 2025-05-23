import eventlet  # Importa eventlet antes de cualquier otra cosa
eventlet.monkey_patch()  # Aplica el parcheo

# Importa la funció 'create_app' del mòdul 'app' (normalment de app.py)
from app import create_app, socketio

# Crea la instància de l'aplicació Flask
app = create_app()

# Si s'executa directament (no importat), inicia el servidor
if __name__ == '__main__':
    # Usar socketio.run en lugar de app.run
    socketio.run(app, 
                 debug=True, # Modo desarrollo
                 host='0.0.0.0', # Permite conexiones desde cualquier dispositivo de la red
                 port=5000) #