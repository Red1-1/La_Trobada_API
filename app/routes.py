from flask import Blueprint, jsonify, request, session # Importa las bibliotecas necesarias de Flask
from datetime import datetime 
import mysql.connector  # Importa la biblioteca necesaria para conectarse a una base de datos MySQL
from mysql.connector import errorcode  # Importa el módulo de errores de MySQL
import bcrypt  # Importa la biblioteca para el hashing de contraseñas
from mtgsdk import Card  # Importa la biblioteca para interactuar con la API de cartas
from flask_socketio import emit
from app import socketio # Importa la instancia de SocketIO
from flask_socketio import join_room, leave_room  # Importa funciones para manejar salas de WebSocket

# Crea un Blueprint para la API con un prefijo de URL '/api'
api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/login', methods=['POST'])
def login():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'usuari' y 'contrasenya'
    if not data or 'usuari' not in data or 'contrasenya' not in data:
        return jsonify({'error': 'Falta el usuari o la contrasenya', 'status': 'error'}), 400
    
    username_or_email = data['usuari']
    password = data['contrasenya'].encode('utf-8')  # Convierte la contraseña a bytes para bcrypt
    
    try:
        cnx = databaseconnection()  # Establece la conexión a la base de datos
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:  # Usa un cursor que devuelve diccionarios
                # Consulta para buscar el usuario por nombre o correo
                cursor.execute("SELECT id, nom_usuari, correu, contrasenya FROM usuari WHERE nom_usuari = %s OR correu = %s", 
                              (username_or_email, username_or_email))
                user = cursor.fetchone()  # Obtiene el primer resultado
                
                if not user:
                    return jsonify({'error': 'No es pot trobar a cap usuari amb aquest nom o correu', 'status': 'error'}), 404
                
                # Verifica la contraseña hasheada
                if bcrypt.checkpw(password, user['contrasenya'].encode('utf-8')):
                    # Contraseña correcta - retorna éxito (sin datos sensibles)
                    result = {
                        'status': 'success'
                    }
                    return jsonify(result)
                else:
                    return jsonify({'error': 'Contrasenya incorrecta', 'status': 'error'}), 401
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return jsonify({'error': 'Error de base de datos', 'status': 'error'}), 500
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()  # Cierra la conexión a la base de datos

@api.route('/register', methods=['POST'])
def register():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'nom_usuari', 'correu' y 'contrasenya'
    if not data or 'nom_usuari' not in data or 'correu' not in data or 'contrasenya' not in data:
        return jsonify({'error': 'Falta el nom d\'usuari, el correu o la contrasenya', 'status': 'error'}), 400
    
    usuari = data['nom_usuari']
    correu = data['correu']
    contrasenya = data['contrasenya']
    
    try:
        # Genera un salt y hash de la contraseña
        salt = bcrypt.gensalt()
        contrasenya_hash = bcrypt.hashpw(contrasenya.encode('utf-8'), salt)
        
        cnx = databaseconnection()  # Establece la conexión a la base de datos
        if cnx.is_connected():
            with cnx.cursor() as cursor:
                # Verifica si ya existe un usuario con ese nombre o correo
                cursor.execute("SELECT id FROM usuari WHERE correu = %s", (correu,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    return jsonify({
                        'error': 'Ja existeix un correu electrònic igual',
                        'status': 'error'
                    }), 409  # 409 Conflict es el código adecuado para recursos que ya existen
                
                cursor.execute("SELECT id FROM usuari WHERE nom_usuari = %s", (usuari,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    return jsonify({
                        'error': 'Ja existeix un usuari amb aquest nom',
                        'status': 'error'
                    }), 409  # 409 Conflict es el código adecuado para recursos que ya existen
                
                # Si no existe, procede con el registro
                cursor.execute("INSERT INTO usuari(correu, contrasenya, nom_usuari) VALUES (%s, %s, %s)", 
                             (correu, contrasenya_hash, usuari))
                cnx.commit()  # Confirma los cambios en la base de datos
                return jsonify({'message': 'Usuari creat correctament', 'status': 'success'}), 201
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            return jsonify({'error': 'Incorrect user', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            return jsonify({'error': 'Database does not exist', 'status': 'error'}), 404
        else:
            return jsonify({'error': str(err), 'status': 'error'}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()  # Cierra la conexión a la base de datos

@api.route('/carta/web', methods=['POST'])
def trobar_carta_web():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'nom'
    if not data or 'nom' not in data:
        return jsonify({'error': 'Falta el id de la carta', 'status': 'error'}), 400
    nom = data['nom'].capitalize()
    # Obtiene todas las cartas que coinciden con el nombre
    cards = Card.where(name=nom).all()
    if not cards:
        return jsonify({'error': 'No es pot trobar cap carta amb aquest nom', 'status': 'error'}), 404
    else:
        return jsonify([
            {
                'id': card.multiverse_id,
                'nom': card.name,
                'imatge': card.image_url,
                'expansio': card.set
            } for card in cards if card.name == nom or card.name == data['nom'].lower()
        ]), 200  

@api.route('/coleccio', methods=['POST'])
def crear_coleccio():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'usr' y 'nom_col'
    if not data or 'usr' not in data or 'nom_col' not in data:
        return jsonify({'error': 'Falta el nom d\'usuari o el nom de la col·lecció', 'status': 'error'}), 400
    
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    coleccio = data['nom_col']
    usr = data['usr']
    
    if cnx.is_connected():
        with cnx.cursor(dictionary=True) as cursor:
            # Verifica si el usuario existe
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (usr,))
            id_user = cursor.fetchone()
            
            if id_user:
                # Inserta la nueva colección en la base de datos
                cursor.execute("INSERT INTO coleccio(id_user,nombre) VALUES(%s,%s)", (id_user['id'], coleccio))
                cnx.commit()  # Confirma los cambios
                return jsonify({'message': 'Col·lecció creada correctament', 'status': 'success'}), 201
            else:
                return jsonify({'error': 'el ususari no existeix', 'status': 'error'}), 409

@api.route('/carta/coleccio', methods=['POST'])
def afegir_carta_coleccio():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'id_carta' y 'id_col'
    if not data or 'id_carta' not in data or 'id_col' not in data:
        return jsonify({'error': 'Falta el id de la carta o el nom d\'usuari', 'status': 'error'}), 400
    
    carta = data['id_carta']
    id_col = data['id_col']
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    
    try:
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:
                # Verifica si la carta ya está en la colección
                cursor.execute("SELECT id_carta FROM cartes WHERE id_carta = %s", (carta,))
                existing_card = cursor.fetchone()
                if existing_card:
                    # Inserta la carta en la colección
                    cursor.execute("INSERT INTO coleccio_cartes(id_coleccio, id_carta) VALUES(%s,%s)", (id_col , carta))
                    cnx.commit()  # Confirma los cambios
                    return jsonify({'Success': 'Carta afegida correctament a la col·lecció', 'status': 'success'}), 200
                else:
                    return jsonify({'error': 'La carta no existeix', 'status': 'error'}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Error', 'status': 'error'}), 500

@api.route('/coleccio/mostrar', methods=['POST', 'GET'])
def mostrar_coleccions():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'usr'
    if not data or 'usr' not in data:
        return jsonify({'error': 'Falta el nom d\'usuari', 'status': 'error'}), 400
    
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    usr = data['usr']
    
    try:
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:
                # Busca el ID del usuario
                cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (usr,))
                id_user = cursor.fetchone()
                user_id = id_user['id']
                
                if user_id:
                    # Obtiene las colecciones del usuario
                    cursor.execute("SELECT nombre, id FROM coleccio WHERE id_user=%s", (user_id,))
                    coleccions = cursor.fetchall()
                    if coleccions:
                        return jsonify(coleccions), 200
                    else:
                        return jsonify({'error': 'No hi ha col·leccions per a aquest usuari', 'status': 'error'}), 404
                else:
                    return jsonify({'error': 'el ususari no existeix', 'status': 'error'}), 409
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Error de base de dades', 'status': 'error'}), 500

@api.route('/carta/coleccio/mostrar', methods=['GET'])
def mostrar_coleccio():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'id_col'
    if not data or 'id_col' not in data:
        return jsonify({'error': 'Falta el id de la carta o el nom d\'usuari', 'status': 'error'}), 400
    
    id_col = data['id_col']
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    
    if cnx.is_connected():
        with cnx.cursor(dictionary=True) as cursor:
            # Busca las cartas en la colección
            cursor.execute("SELECT id_carta FROM coleccio_cartes WHERE id_coleccio = %s", (id_col,))
            ids_cartes = cursor.fetchall()

            cartas_encontradas = []
            for id_carta in ids_cartes:
                # Accede al valor del ID
                multiverse_id = id_carta['id_carta'] if isinstance(id_carta, dict) else id_carta[0]
                
                # Busca la carta por su multiverse ID
                cards = Card.where(multiverseid=multiverse_id).all()
                
                # Añade todas las cartas encontradas
                for card in cards:
                    cartas_encontradas.append({
                        'nom': card.name,
                        'imatge': card.image_url,
                        'id_carta': card.multiverse_id  # Añadido ID para referencia
                    })

            if not cartas_encontradas:
                return jsonify({'error': 'No se encontraron cartas para esta colección'}), 404

            return jsonify(cartas_encontradas), 200

@api.route('/coleccio/eliminar', methods=['POST'])
def eliminar_coleccio():
    # Obtiene los datos JSON de la solicitud
    data = request.get_json()
    # Verifica que los datos contengan 'usr' y 'nom_col'
    if not data or 'usr' not in data:
        return jsonify({'error': 'Falta el nom d\'usuari o el nom de la col·lecció', 'status': 'error'}), 400
    
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    usr = data['usr']
    id = data['id']
    print(usr, id)
    if cnx.is_connected():
        with cnx.cursor(dictionary=True) as cursor:
            # Verifica si el usuario existe
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (usr,))
            id_user = cursor.fetchone()
            if id_user:
                # Elimina la colección de la base de datos
                cursor.execute("DELETE FROM coleccio WHERE id= %s", (id,))
                cnx.commit()  # Confirma los cambios
                return jsonify({'message': 'Col·lecció eliminada correctament', 'status': 'success'}), 200
            else:
                return jsonify({'error': 'el ususari no existeix', 'status': 'error'}), 409
            
@api.route('/usuarios/buscar', methods=['GET'])
def buscar_usuarios():
    search_term = request.args.get('q', '').lower()  # Obtiene el término de búsqueda de los parámetros de la URL
    
    if not search_term:
        return jsonify([])  # Si no hay término de búsqueda, retorna lista vacía

    try:
        cnx = databaseconnection()
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:
                # Busca usuarios cuyo nombre comience con el término de búsqueda (insensible a mayúsculas)
                query = """
                    SELECT id, nom_usuari, correu 
                    FROM usuari 
                    WHERE LOWER(nom_usuari) LIKE %s 
                    ORDER BY nom_usuari 
                    LIMIT 10
                """
                cursor.execute(query, (f"{search_term}%",))
                usuarios = cursor.fetchall()
                return jsonify(usuarios), 200
    except mysql.connector.Error as err:
        print(f"Error de base de datos: {err}")
        return jsonify({'error': 'Error al buscar usuarios', 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Error inesperado', 'status': 'error'}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()
  
@api.route('/chat/nuevo', methods=['POST'])
def crear_conversacion():
    data = request.get_json()
    if not data or 'id_usuario1' not in data or 'id_usuario2' not in data:
        return jsonify({'error': 'Se requieren los IDs de ambos usuarios'}), 400
    
    usuari1 = data['id_usuario1']
    usuari2 = data['id_usuario2']
    
    try:
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:  # Usar cursor de diccionario
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (usuari1,))
            id_user = cursor.fetchone()
            if not id_user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
                
            user_id = id_user['id']
            
            # Verificar si ya existe una conversación
            cursor.execute("""
                SELECT id_conversacion FROM conversaciones 
                WHERE (id_usuario1 = %s AND id_usuario2 = %s) 
                OR (id_usuario1 = %s AND id_usuario2 = %s)
            """, (user_id, usuari2, usuari2, user_id))
            
            if cursor.fetchone():
                return jsonify({'error': 'Ya existe una conversación entre estos usuarios'}), 409

            # Crear nueva conversación
            cursor.execute("""
                INSERT INTO conversaciones (id_usuario1, id_usuario2) 
                VALUES (%s, %s)
            """, (user_id, usuari2))
            cnx.commit()
            
            # Obtener el ID de la nueva conversación
            cursor.execute("SELECT LAST_INSERT_ID() AS id_conversacion")
            id_conversacion = cursor.fetchone()['id_conversacion']
            
            return jsonify({
                'id_conversacion': id_conversacion,
                'message': 'Conversación creada exitosamente'
            }), 201

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()
                  
@api.route('/chat/conversaciones/<string:user_id>', methods=['GET'])
def get_conversaciones(user_id):
    """Obtiene todas las conversaciones de un usuario"""
    try:
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (user_id,))
            id_user = cursor.fetchone()
            user_id = id_user['id']
            
            cursor.execute("""
                SELECT c.id_conversacion, 
                       CASE 
                           WHEN c.id_usuario1 = %s THEN u2.nom_usuari
                           ELSE u1.nom_usuari
                       END AS nombre_contacto
                FROM conversaciones c
                JOIN usuari u1 ON c.id_usuario1 = u1.id
                JOIN usuari u2 ON c.id_usuario2 = u2.id
                WHERE c.id_usuario1 = %s OR c.id_usuario2 = %s
            """, (user_id, user_id, user_id))
            return jsonify(cursor.fetchall()),200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()

@api.route('/chat/mensajes/<string:conversacion_id>/<string:user>', methods=['GET'])
def obtener_mensajes(conversacion_id,user):
    """Obtiene todos los mensajes de una conversación específica"""
    try:
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (conversacion_id,))
            id_user_conversacion = cursor.fetchone()
            id_user_conversacion = id_user_conversacion['id']
            if not id_user_conversacion:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (user,))
            id_user = cursor.fetchone()
            id_user = id_user['id']
            
            if not id_user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            # Obtener mensajes y información del remitente
            cursor.execute("""
                SELECT id_conversacion
                FROM conversaciones
                WHERE (id_usuario1 = %s AND id_usuario2 = %s)
                OR (id_usuario1 = %s AND id_usuario2 = %s)
                GROUP BY id_conversacion
            """, (id_user, id_user_conversacion, id_user_conversacion, id_user))
            
            id_conversacion = cursor.fetchone()
            
            cursor.execute("""
                SELECT id_remitente, mensaje, fecha_envio
                from mensajes_privados
                WHERE id_conversacion = %s
                """,(id_conversacion['id_conversacion'],))
            mensajes = cursor.fetchall()
            
            return jsonify(mensajes), 200
            
    except Exception as e:
        print(f"Error al obtener mensajes: {str(e)}")
        return jsonify({'error': 'Error al obtener mensajes'}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()

# Manejo de conexiones WebSocket
@socketio.on('connect')
def handle_connect():
    print(f'Cliente conectado: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Cliente desconectado: {request.sid}')

@socketio.on('unirse_a_conversacion')
def handle_join_conversation(data):
    try:
        user = data.get('usuario') 
        id_user = data.get('id_usuario')# usuario actual
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:
            # Obtener ID del usuario actual
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (user,))
            user_actual = cursor.fetchone()
            if not user_actual:
                emit('error', {'error': 'Usuario actual no encontrado'})
                return
            
            id_user_conversacion = user_actual['id']
              # ID del usuario que se une a 
            cursor.execute("""
                SELECT id_conversacion
                FROM conversaciones
                WHERE (id_usuario1 = %s AND id_usuario2 = %s)
                   OR (id_usuario1 = %s AND id_usuario2 = %s)
                LIMIT 1
            """, (id_user, id_user_conversacion, id_user_conversacion, id_user))

            result = cursor.fetchone()
    
            if result:
                id_conversacion = result['id_conversacion']
                print(f"Usuario {request.sid} unido a la sala {id_conversacion}")
                join_room(id_conversacion)
                emit('unido_a_conversacion', {'id_conversacion': id_conversacion})
            else:
                emit('error', {'error': 'Conversación no encontrada'})

    except Exception as e:
        print(f"Error al unirse a la conversación: {str(e)}")
        emit('error', {'error': str(e)})
    finally:
        if   'cnx' in locals() and cnx.is_connected():
            cnx.close()


@socketio.on('salir_de_conversacion')
def handle_leave_conversation(data):
    id_conversacion = data.get('id_conversacion')
    leave_room(id_conversacion)
    print(f"Usuario {request.sid} salió de la conversación {id_conversacion}")

@socketio.on('enviar_mensaje')
def handle_enviar_mensaje(data):
    try:
        cnx = databaseconnection()
        with cnx.cursor() as cursor:
            cursor.execute("""
                INSERT INTO mensajes_privados (id_conversacion, id_remitente, mensaje)
                VALUES (%s, %s, %s)
            """, (data['id_conversacion'], data['id_remitente'], data['mensaje']))
            cnx.commit()

            emit('nuevo_mensaje', {
                'id_conversacion': data['id_conversacion'],
                'id_remitente': data['id_remitente'],
                'mensaje': data['mensaje'],
                'fecha_envio': datetime.now().isoformat()
            }, room=data['id_conversacion'], skip_sid=request.sid)

    except Exception as e:
        print(e)
        emit('error', {'error': str(e)})
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()


@api.route('/usuario/id/<string:user>', methods=['GET'])
def obtener_id_usuario(user):
    try:
        cnx = databaseconnection()  # Establece la conexión a la base de datos
        with cnx.cursor(dictionary=True) as cursor:
            # Busca el ID del usuario por su nombre
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (user,))
            user = cursor.fetchone()
            
            if user:
                return jsonify({'id': user['id'], 'status': 'success'}), 200
            else:
                return jsonify({'error': 'Usuari no trobat', 'status': 'error'}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500
    finally:
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()

@api.route('/informacion/contrasenya', methods=['POST'])  # Cambiado a POST que es más adecuado
def cambiar_contrasenya():
    data = request.get_json()
    
    # Validación de datos recibidos
    if not data or 'usuari' not in data or 'contrasenya' not in data or 'nova_contrasenya' not in data:
        return jsonify({
            'error': 'Falta el nom d\'usuari, la contrasenya actual o la nova contrasenya',
            'status': 'error'
        }), 400
    
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    usuari = data['usuari']
    password = data['contrasenya'].encode('utf-8')
    nova_contrasenya = data['nova_contrasenya']
        
    try:
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:
                # 1. Verifica si el usuario existe y obtiene su contraseña actual
                cursor.execute("SELECT id, contrasenya FROM usuari WHERE nom_usuari = %s", (usuari,))
                usuari_data = cursor.fetchone()
                
                if not usuari_data:
                    return jsonify({
                        'error': 'Usuari no trobat',
                        'status': 'error'
                    }), 404
                
                # 2. Verifica que la contraseña actual sea correcta
                if not bcrypt.checkpw(password, usuari_data['contrasenya'].encode('utf-8')):
                    return jsonify({
                        'error': 'Contrasenya actual incorrecta',
                        'status': 'error'
                    }), 401
                
                # 3. Hashea la nueva contraseña
                nova_contrasenya_hash = bcrypt.hashpw(nova_contrasenya.encode('utf-8'), bcrypt.gensalt())
                
                # 4. Actualiza la contraseña en la base de datos
                cursor.execute(
                    "UPDATE usuari SET contrasenya = %s WHERE id = %s",
                    (nova_contrasenya_hash.decode('utf-8'), usuari_data['id'])
                )
                cnx.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Contrasenya actualitzada correctament'
                }), 200
                
    except Exception as e:
        print(f"Error: {e}")
        if cnx.is_connected():
            cnx.rollback()  # Revertir cambios en caso de error
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500
    finally:
        if cnx.is_connected():
            cnx.close()

@api.route('/informacion/nom', methods=['POST'])  # Cambiado a POST que es más adecuado
def cambiar_nom():
    data = request.get_json()
    
    # Validación de datos recibidos
    if not data or 'usuari' not in data or 'contrasenya' not in data or 'nou_nom' not in data:
        return jsonify({
            'error': 'Falta el nom d\'usuari, la contrasenya actual o la nova contrasenya',
            'status': 'error'
        }), 400
    
    cnx = databaseconnection()  # Establece la conexión a la base de datos
    usuari = data['usuari']
    password = data['contrasenya'].encode('utf-8')
    nou_nom = data['nou_nom']
        
    try:
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:
                # 1. Verifica si el usuario existe y obtiene su contraseña actual
                cursor.execute("SELECT id, contrasenya FROM usuari WHERE nom_usuari = %s", (usuari,))
                usuari_data = cursor.fetchone()
                
                if not usuari_data:
                    return jsonify({
                        'error': 'Usuari no trobat',
                        'status': 'error'
                    }), 404
                
                # 2. Verifica que la contraseña actual sea correcta
                if not bcrypt.checkpw(password, usuari_data['contrasenya'].encode('utf-8')):
                    return jsonify({
                        'error': 'Contrasenya actual incorrecta',
                        'status': 'error'
                    }), 401
                
                # 3. Hashea la nueva contraseña
                
                # 4. Actualiza la contraseña en la base de datos
                cursor.execute(
                    "UPDATE usuari SET nom_usuari = %s WHERE id = %s",
                    (nou_nom, usuari_data['id'])
                )
                cnx.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Nom actualitzat correctament'
                }), 200
                
    except Exception as e:
        print(f"Error: {e}")
        if cnx.is_connected():
            cnx.rollback()  # Revertir cambios en caso de error
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500
    finally:
        if cnx.is_connected():
            cnx.close()

@api.route('/foro/nou_missatge', methods=['POST'])  
def afegir_nou_missatge():
    data = request.get_json()
    
    # Validación de datos recibidos
    if not data or 'id_user' not in data or 'mensaje' not in data:
        return jsonify({
            'error': 'Falta el nom d\'usuari o el missatge',
            'status': 'error'
        }), 400
    id_user = data['id_user']
    mensaje = data['mensaje']
    cnx = databaseconnection()
    try:
        if cnx.is_connected():
            with cnx.cursor(dictionary=True) as cursor:     
                cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (id_user,))
                id_user = cursor.fetchone()
                id_user = id_user['id']
                cursor.execute("INSERT INTO foro(id_user,mensaje) VALUES(%s,%s)", (id_user, mensaje))
                cnx.commit()
                return jsonify({
                    'message': 'Missatge afegit correctament',
                    'status': 'success'
                }), 201
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            return jsonify({'error': 'Incorrect user', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            return jsonify({'error': 'Database does not exist', 'status': 'error'}), 404
        else:
            print(f"Error: {err}")
            return jsonify({'error': str(err), 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@api.route('/foro/mostrar_missatges', methods=['GET'])
def mostrar_missatges():
    try:
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:
            # Obtiene todos los mensajes del foro
            cursor.execute("SELECT id_user, mensaje FROM foro")
            missatges = cursor.fetchall()
            for missatge in missatges:
                # Obtiene el nombre del usuario
                cursor.execute("SELECT nom_usuari FROM usuari WHERE id = %s", (missatge['id_user'],))
                user = cursor.fetchone()
                if user:
                    missatge['nom_usuari'] = user['nom_usuari']
                else:
                    missatge['nom_usuari'] = 'Desconegut'
            return jsonify(missatges), 200
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(err)
            return jsonify({'error': 'Incorrect user', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(err)
            return jsonify({'error': 'Database does not exist', 'status': 'error'}), 404
        else:
            print(err)
            return jsonify({'error': str(err), 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@api.route('/eventos/crear', methods=['POST'])
def crear_evento():
    try:
        cnx = databaseconnection()
        data = request.get_json()
        # Validar datos requeridos
        if not all(key in data for key in ['creador', 'titulo', 'fecha_evento', 'localizacion']):
            return jsonify({'error': 'Faltan campos obligatorios', 'status': 'error'}), 400
        
        with cnx.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (data['creador'],))
            id_user = cursor.fetchone()
            query = """
                INSERT INTO eventos 
                (id_creador, titulo, descripcion, fecha_evento, localizacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                id_user['id'],
                data['titulo'],
                data.get('descripcion'),
                data['fecha_evento'],
                data['localizacion']
            ))
            cnx.commit()
            return jsonify({'message': 'Evento creado correctamente', 'status': 'success'}), 201
            
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(err)
            return jsonify({'error': 'Acceso denegado', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(err)
            return jsonify({'error': 'Base de datos no existe', 'status': 'error'}), 404
        else:
            print(err)
            return jsonify({'error': str(err), 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@api.route('/eventos/mostrar', methods=['GET'])
def mostrar_eventos():
    try:
        cnx = databaseconnection()
        with cnx.cursor(dictionary=True) as cursor:
            # Obtiene todos los eventos
            cursor.execute("""
                SELECT e.*, u.nom_usuari as creador_nombre 
                FROM eventos e
                JOIN usuari u ON e.id_creador = u.id
            """)
            eventos = cursor.fetchall()
            
            # Para cada evento, obtener participantes
            for evento in eventos:
                cursor.execute("""
                    SELECT u.id, u.nom_usuari 
                    FROM evento_participantes ep
                    JOIN usuari u ON ep.id_usuario = u.id
                    WHERE ep.id_evento = %s
                """, (evento['id_evento'],))
                participantes = cursor.fetchall()
                evento['participantes'] = participantes
                evento['fecha_evento'] = evento['fecha_evento'].strftime('%Y-%m-%d %H:%M:%S')  # Formatear la fecha
            return jsonify(eventos), 200
            
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(err)
            return jsonify({'error': 'Acceso denegado', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(err)
            return jsonify({'error': 'Base de datos no existe', 'status': 'error'}), 404
        else:
            print(err)
            return jsonify({'error': str(err), 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@api.route('/eventos/unirse', methods=['POST'])
def unirse_evento():
    try:
        cnx = databaseconnection()
        data = request.get_json()
        print(data)
        # Validar datos requeridos
        if not all(key in data for key in ['id_evento', 'usuario']):
            return jsonify({'error': 'Faltan campos obligatorios', 'status': 'error'}), 400
            
        with cnx.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM usuari WHERE nom_usuari= %s", (data['usuario'],))
            id_user = cursor.fetchone()
            
            # Verificar si el usuario ya está registrado
            cursor.execute("""
                SELECT 1 FROM evento_participantes 
                WHERE id_evento = %s AND id_usuario = %s
            """, (data['id_evento'], id_user['id']))
            if cursor.fetchone():
                
                return jsonify({'error': 'Ya estás registrado en este evento', 'status': 'error'}), 400
            
            # Unirse al evento
            cursor.execute("""
                INSERT INTO evento_participantes 
                (id_evento, id_usuario)
                VALUES (%s, %s)
            """, (data['id_evento'], id_user['id']))
            cnx.commit()
            return jsonify({'message': 'Te has unido al evento correctamente', 'status': 'success'}), 201
            
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(err)
            return jsonify({'error': 'Acceso denegado', 'status': 'error'}), 403
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(err)
            return jsonify({'error': 'Base de datos no existe', 'status': 'error'}), 404
        else:
            print(err)
            return jsonify({'error': str(err), 'status': 'error'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

    
def databaseconnection():  # Función para conectarse a la base de datosx
    try:
        # Establece la conexión con la base de datos
        cnx = mysql.connector.connect(user='root', password='', database='la_trobada')
        return cnx  # Retorna la conexión establecida
    except mysql.connector.Error as err:  # Captura errores de conexión
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:  # Verifica si el error es de acceso denegado
            print("Incorrect user")
            cnx.close()  # Cierra la conexión
        elif err.errno == errorcode.ER_BAD_DB_ERROR:  # Verifica si el error es que la base de datos no existe
            print("database doesn't exist")
            cnx.close()  # Cierra la conexión
        else:
            print(err)  # Imprime cualquier otro error
            cnx.close()  # Cierra la conexión

