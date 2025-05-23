class Config:
    # Dirección del servidor MySQL (puede ser una IP o un nombre de dominio)
    MYSQL_HOST = '10.100.3.25'  # O la dirección de tu servidor PHPMyAdmin
    
    # Nombre de usuario para conectarse a la base de datos MySQL
    MYSQL_USER = 'root'
    
    # Contraseña del usuario de la base de datos MySQL
    MYSQL_PASSWORD = ''  # Dejar vacío si no hay contraseña, pero no es recomendable en producción
    
    # Nombre de la base de datos a la que se desea conectar
    MYSQL_DB = 'la_trobada'
    
    # Clase de cursor que se utilizará para las consultas (en este caso, un cursor que devuelve diccionarios)
    MYSQL_CURSORCLASS = 'DictCursor'