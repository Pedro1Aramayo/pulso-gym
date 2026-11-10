import hashlib
import json
from pathlib import Path
from importlib.metadata import version

import cv2
import numpy as np

# Evitar que TensorFlow ocupe todos los núcleos mientras la UI muestra video.
import os
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "2")
os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "2")

from deepface import DeepFace

from src.database.conexion import conectar_bd


class ReconocedorFacial:

    UMBRAL = 0.40

    def __init__(self):

        # ====================================================
        # HAAR CASCADE
        # ====================================================

        ruta_haar = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        self.detector = cv2.CascadeClassifier(
            ruta_haar
        )

        if self.detector.empty():

            raise RuntimeError(
                "No se pudo cargar Haar Cascade."
            )

        # ====================================================
        # MODELO FACENET512
        # ====================================================

        print(
            "Cargando modelo FaceNet512..."
        )

        DeepFace.build_model(
            "Facenet512"
        )

        print(
            "FaceNet512 cargado."
        )

        # ====================================================
        # EMBEDDINGS DE REFERENCIA
        # ====================================================

        self.referencias = []

    # ========================================================
    # DETECTAR ROSTROS
    # ========================================================

    def detectar_rostros(
        self,
        imagen
    ):

        gris = cv2.cvtColor(
            imagen,
            cv2.COLOR_BGR2GRAY
        )

        rostros = self.detector.detectMultiScale(
            gris,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )

        return rostros

    # ========================================================
    # GENERAR EMBEDDING
    # ========================================================

    def generar_embedding(
        self,
        rostro
    ):

        try:

            representaciones = DeepFace.represent(
                img_path=rostro,
                model_name="Facenet512",
                detector_backend="skip",
                enforce_detection=False,
                align=False
            )

            if not representaciones:
                return None

            embedding = representaciones[0][
                "embedding"
            ]

            return np.array(
                embedding,
                dtype=np.float32
            )

        except Exception as error:

            print(
                "Error generando embedding:"
            )

            print(error)

            return None

    # ========================================================
    # CARGAR REFERENCIAS DESDE POSTGRESQL
    # ========================================================

    def cargar_referencias(self):
        # Caché local derivada: nunca se guarda en Git ni reemplaza a PostgreSQL.
        ruta = Path(__file__).resolve().parents[2] / ".cache" / "facial" / "referencias.json"
        firma = f"haar80-skip-v1:{version('deepface')}:{cv2.__version__}:Facenet512"
        cache = {}
        try:
            almacen = json.loads(ruta.read_text(encoding="utf-8"))
            if almacen.get("firma") == firma:
                cache = almacen.get("embeddings", {})
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        nuevos = {}
        referencias = []
        conexion = None
        reutilizadas = 0
        try:
            conexion = conectar_bd()
            # Una foto por vez: no cargar todas las imágenes en RAM con fetchall.
            with conexion.cursor(name="referencias_faciales") as cursor:
                cursor.itersize = 1
                cursor.execute("""
                    SELECT f.id, f.socio_id, a.nombre, a.apellido, f.angulo, f.imagen
                    FROM foto_socio f INNER JOIN socio a ON a.id=f.socio_id
                    ORDER BY f.socio_id, f.id
                """)
                for foto_id, socio_id, nombre, apellido, angulo, datos in cursor:
                    clave = hashlib.sha256(bytes(datos)).hexdigest()
                    embedding = None
                    if clave in cache:
                        if cache[clave] is None:
                            nuevos[clave] = None
                            continue
                        try:
                            candidato = np.asarray(cache[clave], dtype=np.float32)
                            if candidato.shape == (512,) and np.isfinite(candidato).all():
                                embedding = candidato
                                reutilizadas += 1
                        except (ValueError, TypeError):
                            pass
                    if embedding is None:
                        imagen = cv2.imdecode(np.frombuffer(bytes(datos), dtype=np.uint8), cv2.IMREAD_COLOR)
                        if imagen is None:
                            nuevos[clave] = None
                            continue
                        rostros = self.detectar_rostros(imagen)
                        if len(rostros) != 1:
                            nuevos[clave] = None
                            continue
                        x, y, w, h = rostros[0]
                        embedding = self.generar_embedding(imagen[y:y+h, x:x+w])
                        del imagen
                        if embedding is None:
                            continue
                    nuevos[clave] = embedding.tolist()
                    referencias.append({
                        "foto_id": foto_id, "socio_id": socio_id,
                        "nombre": nombre, "apellido": apellido, "angulo": angulo,
                        "embedding": embedding,
                    })
            self.referencias = referencias
        except Exception:
            self.referencias = []
            raise
        finally:
            if conexion is not None:
                conexion.close()
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = ruta.with_name(f"referencias.{os.getpid()}.tmp")
            temporal.write_text(json.dumps({"firma": firma, "embeddings": nuevos}), encoding="utf-8")
            temporal.replace(ruta)
        except OSError as error:
            print("No se pudo guardar la caché de referencias:", error)
        print(f"Referencias válidas: {len(referencias)}; reutilizadas: {reutilizadas}")
        return len(referencias)

    # ========================================================
    # DISTANCIA COSENO
    # ========================================================

    def distancia_coseno(
        self,
        embedding_a,
        embedding_b
    ):

        producto = np.dot(
            embedding_a,
            embedding_b
        )

        norma_a = np.linalg.norm(
            embedding_a
        )

        norma_b = np.linalg.norm(
            embedding_b
        )

        if norma_a == 0 or norma_b == 0:
            return 1.0

        similitud = (
            producto
            / (norma_a * norma_b)
        )

        distancia = (
            1.0 - similitud
        )

        return float(
            distancia
        )

    # ========================================================
    # RECONOCER ROSTRO
    # ========================================================

    def reconocer(
        self,
        imagen,
        rostros=None
    ):

        # La UI puede reutilizar la detección del mismo frame sin repetir Haar.
        # Se conserva reconocer(imagen) para las pruebas y otros consumidores.
        if rostros is None:
            rostros = self.detectar_rostros(
                imagen
            )

        # ----------------------------------------------------
        # SIN ROSTROS
        # ----------------------------------------------------

        if len(rostros) == 0:

            return {
                "estado": "sin_rostro",
                "rostros": []
            }

        # ----------------------------------------------------
        # MÁS DE UN ROSTRO
        # ----------------------------------------------------

        if len(rostros) > 1:

            return {
                "estado": "multiples_rostros",
                "rostros": rostros
            }

        # ----------------------------------------------------
        # EXACTAMENTE UN ROSTRO
        # ----------------------------------------------------

        x, y, w, h = rostros[0]

        rostro = imagen[
            y:y + h,
            x:x + w
        ]

        embedding_actual = (
            self.generar_embedding(
                rostro
            )
        )

        if embedding_actual is None:

            return {
                "estado": "error_embedding",
                "rostros": rostros
            }

        # ----------------------------------------------------
        # COMPARAR CON TODAS LAS REFERENCIAS
        # ----------------------------------------------------

        mejor_referencia = None
        menor_distancia = None

        for referencia in self.referencias:

            distancia = self.distancia_coseno(
                embedding_actual,
                referencia["embedding"]
            )

            if (
                menor_distancia is None
                or distancia < menor_distancia
            ):

                menor_distancia = distancia
                mejor_referencia = referencia

        # ----------------------------------------------------
        # SIN REFERENCIAS
        # ----------------------------------------------------

        if mejor_referencia is None:

            return {
                "estado": "sin_referencias",
                "rostros": rostros
            }

        # ----------------------------------------------------
        # BEST MATCH + THRESHOLD 0.40
        # ----------------------------------------------------

        if menor_distancia <= self.UMBRAL:

            return {
                "estado": "reconocido",
                "socio_id":
                    mejor_referencia["socio_id"],
                "nombre":
                    mejor_referencia["nombre"],
                "apellido":
                    mejor_referencia["apellido"],
                "angulo":
                    mejor_referencia["angulo"],
                "distancia":
                    menor_distancia,
                "rostros":
                    rostros
            }

        return {
            "estado": "no_reconocido",
            "distancia": menor_distancia,
            "rostros": rostros
        }