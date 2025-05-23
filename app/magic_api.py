from mtgsdk import Card  # Importa la clase Card de la biblioteca mtgsdk para interactuar con la API de cartas
from routes import databaseconnection  # Importa la función para establecer la conexión a la base de datos
import mysql.connector  # Importa el conector de MySQL
from time import sleep  # Importa la función sleep para pausar la ejecución
import time  # Importa el módulo time para manejar el tiempo
from datetime import timedelta  # Importa timedelta para calcular intervalos de tiempo

def insert_cards_batch(batch):
    cnx = None  # Inicializa la variable de conexión
    try:
        cnx = databaseconnection()  # Establece la conexión a la base de datos
        if cnx and cnx.is_connected():  # Verifica si la conexión es válida
            with cnx.cursor(dictionary=True) as cursor:  # Usa un cursor que devuelve diccionarios
                cont = 0  # Contador de cartas insertadas
                # Preparamos los datos asegurando que todos los campos sean strings
                for card in batch:
                    if card.multiverse_id is not None:  # Verifica que la carta tenga un ID
                        carta = card.multiverse_id
                        print(f"\nInsertando carta: {card.name}")  # Muestra el nombre de la carta que se está insertando
                        print(type(carta))  # Muestra el tipo de la carta
                        cont += 1  # Incrementa el contador
                        # Inserta la carta en la base de datos
                        cursor.execute("INSERT INTO cartes(id_carta) VALUES (%s)", (carta,))
                        cnx.commit()  # Confirma los cambios en la base de datos
                # Devuelve el número de cartas insertadas
                return cont
    except mysql.connector.Error as err:
        print(f"\nError en el batch: {err}")  # Muestra el error si ocurre
        print(f"Última carta procesada: {batch[-1].name if batch else 'N/A'}")  # Muestra la última carta procesada
        return 0  # Retorna 0 en caso de error
    finally:
        if cnx and cnx.is_connected():
            cnx.close()  # Cierra la conexión a la base de datos

def process_all_cards():
    batch_size = 500  # Tamaño del lote para insertar cartas
    current_batch = []  # Inicializa el lote actual
    total_inserted = 0  # Contador total de cartas insertadas
    start_time = time.time()  # Registra el tiempo de inicio
    
    try:
        print("Iniciando proceso de carga de cartas...")
        print(f"Hora de inicio: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Obtenemos el iterador de cartas
        all_cards = Card.all()
        
        for i, card in enumerate(all_cards, 1):  # Itera sobre todas las cartas
            try:
                if card.multiverse_id is not None:  # Verifica que la carta tenga un ID
                    current_batch.append(card)  # Agrega la carta al lote actual
                    
                    # Procesamos el lote cuando alcanza el tamaño
                    if len(current_batch) >= batch_size:
                        inserted = insert_cards_batch(current_batch)  # Inserta el lote en la base de datos
                        total_inserted += inserted  # Actualiza el total de cartas insertadas
                        current_batch = []  # Reinicia el lote actual
                        
                        # Muestra progreso
                        elapsed = time.time() - start_time  # Calcula el tiempo transcurrido
                        avg_speed = total_inserted / elapsed if elapsed > 0 else 0  # Calcula la velocidad promedio
                        print(f"\nProgreso: {total_inserted} cartas insertadas | "
                              f"Tiempo: {timedelta(seconds=int(elapsed))} | "
                              f"Velocidad: {avg_speed:.2f} cartas/segundo")
                        
                        # Pausa para evitar sobrecarga
                        sleep(1.5)  # Pausa de 1.5 segundos
            
                # Mostrar progreso cada 100 cartas
                if i % 100 == 0:
                    elapsed = time.time() - start_time  # Calcula el tiempo transcurrido
                    print(f"\rCartas procesadas: {i} | Tiempo: {timedelta(seconds=int(elapsed))}", end='', flush=True)
            
            except Exception as card_error:
                print(f"\nError procesando carta {i}: {card_error}")  # Muestra el error si ocurre
                continue  # Continúa con la siguiente carta
        
        # Procesar el último lote incom pleto
        if current_batch:
            inserted = insert_cards_batch(current_batch)  # Inserta el último lote en la base de datos
            total_inserted += inserted  # Actualiza el total de cartas insertadas
        
    except Exception as e:
        print(f"\nError general: {e}")  # Muestra el error general si ocurre
    finally:
        end_time = time.time()  # Registra el tiempo de finalización
        total_time = end_time - start_time  # Calcula el tiempo total
        print("\n" + "="*50)
        print("PROCESO COMPLETADO")  # Indica que el proceso ha finalizado
        print(f"Hora de finalización: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Tiempo total: {timedelta(seconds=int(total_time))}")  # Muestra el tiempo total transcurrido
        print(f"Cartas insertadas: {total_inserted}")  # Muestra el total de cartas insertadas
        if total_inserted > 0:
            print(f"Velocidad promedio: {total_inserted/total_time:.2f} cartas/segundo")  # Muestra la velocidad promedio
        print("="*50)

if __name__ == "__main__":
    process_all_cards()  # Llama a la función principal para iniciar el proceso de carga de cartas