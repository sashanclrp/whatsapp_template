import hashlib
import json
import os
from openai import OpenAI, AsyncOpenAI
from pathlib import Path
from config.env import OPENAI_API_KEY
from utils.logger import logger


class VectorStoreHelper:
    FILE_HASHES_DB = "src/services/agents/db/file_hashes.json"
    
    @staticmethod
    async def create_and_populate_vector_store(file_paths: list[str], vector_store_name: str = "My Vector Store"):
        """
        Crea un vector store y sube los archivos dados, realizando polling 
        hasta que se completen de procesar.
        
        Returns:
            str: El ID del vector store recién creado.
        """
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        logger.debug(f"[VectorStoreHelper] Iniciando creación del vector store: {vector_store_name}")
        # Paso 1: Crear un vector store
        try:
            vector_store = await client.beta.vector_stores.create(
                name=vector_store_name
            )
            logger.debug(f"[VectorStoreHelper] Respuesta de creación del vector store: {vector_store}")
        except Exception as e:
            logger.error(f"[VectorStoreHelper] Error al crear vector store: {e}")
            raise e

        # Extraer el ID del vector store (ya sea como atributo o como clave del diccionario)
        vector_store_id = getattr(vector_store, "id", None)
        if not vector_store_id and hasattr(vector_store, "get"):
            vector_store_id = vector_store.get("id")
        logger.debug(f"[VectorStoreHelper] ID obtenido del vector store: {vector_store_id}")

        if not vector_store_id:
            logger.error(f"[VectorStoreHelper] No se pudo obtener el ID del vector store, vector_store: {vector_store}")
            raise ValueError("No se pudo obtener el ID del vector store creado.")

        # Paso 2: Abrir los archivos como streams
        logger.debug(f"[VectorStoreHelper] Creando streams para archivos: {file_paths}")
        file_streams = []
        for path in file_paths:
            try:
                f = open(path, "rb")
                file_streams.append(f)
                logger.debug(f"[VectorStoreHelper] Archivo abierto: {path}")
            except Exception as e:
                logger.error(f"[VectorStoreHelper] Error abriendo archivo {path}: {e}")

        # Paso 3: Subir archivos y hacer polling hasta que hayan sido procesados
        try:
            logger.debug(f"[VectorStoreHelper] Subiendo archivos al vector store ID: {vector_store_id}")
            await client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=file_streams
            )
            logger.debug(f"[VectorStoreHelper] Archivos subidos y procesados correctamente para vector store ID: {vector_store_id}")
        except Exception as e:
            logger.error(f"[VectorStoreHelper] Error al subir archivos al vector store: {e}")
            raise e
        finally:
            for f in file_streams:
                f.close()
                logger.debug(f"[VectorStoreHelper] Archivo stream cerrado")

        logger.debug(f"[VectorStoreHelper] Vector store creado exitosamente con ID: {vector_store_id}")
        return vector_store_id

    @staticmethod
    async def load_file_hashes():
        """
        Carga el JSON que lleva el registro de hashes para directorios.
        Se utiliza una estructura plana (diccionario vacío por defecto).
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(VectorStoreHelper.FILE_HASHES_DB), exist_ok=True)
        
        try:
            if os.path.exists(VectorStoreHelper.FILE_HASHES_DB):
                with open(VectorStoreHelper.FILE_HASHES_DB, "r") as f:
                    content = f.read()
                    if content.strip():  # Check if file is not empty
                        return json.loads(content)
            return {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    async def save_file_hashes(data):
        """
        Guarda en disco el JSON de hashes de directorios.
        """
        with open(VectorStoreHelper.FILE_HASHES_DB, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    async def compute_directory_hash(directory_path: str) -> str:
        """
        Calcula un hash único para todos los archivos de un directorio 
        (ordenados por nombre para evitar resultados inconsistentes).

        :param directory_path: Ruta del directorio a procesar.
        :return: Hash (SHA256) en representación hexadecimal.
        """
        dir_path = Path(directory_path)
        # Puedes filtrar archivos según una extensión en particular. Aquí se toman todos.
        file_list = sorted(dir_path.glob("*.*"))

        hasher = hashlib.sha256()

        for file_path in file_list:
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)

        return hasher.hexdigest()

    @staticmethod
    async def get_or_create_vector_store_for_directory(directory_path: str, vector_store_name: str):
        """
        Dado un directorio, calcula su hash. Si el vector store asociado ya existe y el hash coincide,
        lo reutiliza. Si el hash ha cambiado, se realizan los siguientes pasos:
        
           1. Se listan todos los archivos asociados al vector store anterior.
           2. Se borran esos archivos.
           3. Se elimina el vector store.
           4. Se crea un nuevo vector store subiendo nuevamente todos los archivos.
           5. Se actualiza el registro en file_hashes.json usando como clave el nombre del directorio
              (p.ej., "memory_dir_hashes") manteniendo siempre únicamente el hash más reciente.
        
        Returns:
            str: El ID del vector store (ya sea reutilizado o recién creado).
        """
        data = await VectorStoreHelper.load_file_hashes()
        # Utilizar el nombre del directorio para la clave, por ejemplo "memory_dir_hash"
        directory_key = f"{Path(directory_path).name}_dir_hash"
        
        # Obtener el registro antiguo, si existe
        old_record = data.get(directory_key)
        
        # Calcular el hash actual del directorio
        logger.debug(f"[VectorStoreHelper] Registro previo ({directory_key}): {old_record}")

        current_hash = await VectorStoreHelper.compute_directory_hash(directory_path)
        
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.debug(f"[VectorStoreHelper] Hash actual para {directory_path}: {current_hash}")

        if old_record is not None:
            old_hash = old_record.get("hash")
            old_vector_store_id = old_record.get("vector_store_id")
            logger.debug(f"[VectorStoreHelper] Comparando old_hash: {old_hash} con current_hash: {current_hash}")
            
            if old_hash == current_hash:
                logger.info(f"[VectorStoreHelper] Reutilizando vector store (ID={old_vector_store_id}) por directorio sin cambios.")
                return old_vector_store_id
            else:
                logger.info(f"[VectorStoreHelper] Contenido ha cambiado. Se borrará el vector store antiguo (ID={old_vector_store_id}).")
                # Realizar la eliminación del vector store y sus archivos según el código existente.
                try:
                    files_list = await client.beta.vector_stores.files.list(vector_store_id=old_vector_store_id)
                    # 2. Borrar cada archivo
                    for file_obj in files_list:
                        try:
                            await client.files.delete(file_obj.id)
                        except Exception as e:
                            logger.warning(f"[VectorStoreHelper] Error al borrar archivo {file_obj.id}: {e}")
                except Exception as e:
                    logger.warning(f"[VectorStoreHelper] Error al listar archivos: {e}")

                try:
                    await client.beta.vector_stores.delete(vector_store_id=old_vector_store_id)
                except Exception as e:
                    logger.warning(f"[VectorStoreHelper] Error al borrar vector store {old_vector_store_id}: {e}")

                # Se crea un nuevo vector store
                dir_path = Path(directory_path)
                file_list = sorted(dir_path.glob("*.*"))
                file_paths = [str(p) for p in file_list if p.is_file()]

                logger.debug(f"[VectorStoreHelper] Archivos encontrados para subir: {file_paths}")
                
                new_vector_store_id = await VectorStoreHelper.create_and_populate_vector_store(
                    file_paths,
                    vector_store_name=vector_store_name
                )
                data[directory_key] = {"hash": current_hash, "vector_store_id": new_vector_store_id}
                await VectorStoreHelper.save_file_hashes(data)
                return new_vector_store_id

        else:
            logger.info(f"[VectorStoreHelper] No se encontró registro previo. Se creará un vector store nuevo.")
            dir_path = Path(directory_path)
            file_list = sorted(dir_path.glob("*.*"))
            file_paths = [str(p) for p in file_list if p.is_file()]
            logger.debug(f"[VectorStoreHelper] Archivos encontrados para subir: {file_paths}")
            new_vector_store_id = await VectorStoreHelper.create_and_populate_vector_store(
                file_paths,
                vector_store_name=vector_store_name
            )
            data[directory_key] = {"hash": current_hash, "vector_store_id": new_vector_store_id}
            await VectorStoreHelper.save_file_hashes(data)
            return new_vector_store_id


##############################################################################
# NEW CLASS: UserContextFile
##############################################################################
class UserContextFile:
    """
    Manages the (re)creation of a user context file (in .md format)
    on OpenAI. This file_id is then stored in Airtable + Redis as
    user_context_file_id.
    """

    @staticmethod
    async def sync_user_context_file(user_data: dict) -> str:
        """
        1) Si user_data contiene 'user_context_file_id', elimina ese archivo de OpenAI.
        2) Genera un archivo .md en español basándose en el objeto user_data creado desde Airtable:
        
             # {Nombre} - {waid}
             
             - waid: {waid}
             - Nombre de usuario: {Nombre}
             - Fecha de Nacimiento: {Fecha de Nacimiento}
             - Signo Zodiacal: {Signo Zodiacal}       (vacío si no está definido)
             - Género: {Género}                       (vacío si no está definido)
             - Ubicación: {Ubicación}                 (se construye a partir de Ciudad y País)
             - Preferencias del Usuario: {Preferencias} (vacío si no está definido)
             
        3) Sube el archivo .md a OpenAI y obtiene el nuevo file_id.
        4) Retorna el nuevo file_id (para almacenar en Redis y Airtable).
        """
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        old_file_id = user_data.get("user_context_file_id")
        if old_file_id:
            try:
                await client.files.delete(old_file_id)
            except Exception as e:
                print(f"[UserContextFile] No se pudo eliminar el archivo antiguo {old_file_id}: {str(e)}")

        # Recuperar valores desde el objeto user_data basado en la estructura de Airtable
        waid = user_data.get("waid", "")
        user_name = user_data.get("Nombre", "")
        fecha_nacimiento = user_data.get("Fecha de Nacimiento", "")
        signo_zodiacal = user_data.get("Signo Zodiacal", "")
        edad = user_data.get("Edad", "")
        genero = user_data.get("Género", "")
        ciudad = user_data.get("Ciudad", "")
        pais = user_data.get("País", "")
        ubicacion = f"{ciudad}, {pais}" if ciudad and pais else (ciudad or pais)
        preferencias = user_data.get("Preferencias", "") or user_data.get("Notas", "")

        # Construir el contenido Markdown en español
        md_content = (
            f"# {user_name} - {waid}\n\n"
            f"- waid: {waid}\n"
            f"- Nombre de usuario: {user_name}\n"
            f"- Fecha de Nacimiento: {fecha_nacimiento}\n"
            f"- Edad: {edad}\n"
            f"- Signo Zodiacal: {signo_zodiacal}\n"
            f"- Género: {genero}\n"
            f"- Ubicación: {ubicacion}\n"
            f"- Preferencias del Usuario: {preferencias}\n"
        )
        md_bytes = md_content.encode("utf-8")

        # El nombre del archivo sigue el formato: user:{waid}_context.md
        filename = f"user:{waid}_context.md"

        try:
            upload_resp = await client.files.create(
                file=(filename, md_bytes, "text/markdown"),
                purpose="assistants",  # Puedes cambiar a "context" si se requiere
            )
        except Exception as e:
            print(f"[UserContextFile] Error al subir el archivo de contexto del usuario: {str(e)}")
            return ""

        new_file_id = upload_resp.id  # Se retorna el ID del nuevo archivo.
        return new_file_id