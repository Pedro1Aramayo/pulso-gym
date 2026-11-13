import cv2


def normalizar_origen(valor):
    """Índice de webcam (0, 1, …) o, para pruebas y cámaras IP, una ruta o URL de video."""
    texto = str(valor if valor is not None else '0').strip() or '0'
    return int(texto) if texto.lstrip('-').isdigit() else texto


class CameraManager:
    def __init__(self, indice=0):
        self.indice = normalizar_origen(indice)
        self.cap = None

    def cambiar_origen(self, indice):
        """Cambia de cámara; si estaba abierta se reabre con el nuevo origen."""
        estaba_abierta = self.esta_abierta()
        self.cerrar()
        self.indice = normalizar_origen(indice)
        return self.abrir() if estaba_abierta else True

    def abrir(self):
        if self.cap is not None and self.cap.isOpened():
            return True
        self.cap = cv2.VideoCapture(self.indice)
        return self.cap.isOpened()

    def leer_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return None
        ok, frame = self.cap.read()
        if not ok and isinstance(self.indice, str):
            # Los archivos de video se reproducen en bucle.
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def cerrar(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def esta_abierta(self):
        return self.cap is not None and self.cap.isOpened()


def buscar_camaras(maximo=5):
    """Devuelve los índices de webcam que responden con una imagen."""
    encontradas = []
    for indice in range(maximo):
        cap = cv2.VideoCapture(indice)
        try:
            if cap.isOpened() and cap.read()[0]:
                encontradas.append(indice)
        finally:
            cap.release()
    return encontradas
