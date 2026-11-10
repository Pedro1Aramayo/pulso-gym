"""Puente Qt: FaceNet vive fuera del proceso de la interfaz."""
import base64
import json
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal, Slot


class TrabajadorReconocimiento(QObject):
    terminado = Signal(object)
    progreso = Signal(str)
    detenido = Signal()
    TIEMPO_CARGA_MS = 180000
    TIEMPO_ROSTRO_MS = 15000

    def __init__(self):
        super().__init__()
        self.proceso = None
        self.reloj = None
        self.trabajo = None
        self.pendiente = None
        self.buffer = bytearray()
        self.fallo = None
        self.cerrando = False

    def iniciar_proceso(self):
        # Se crean en el hilo al que pertenece este trabajador, no en __init__.
        if self.proceso is None:
            self.proceso = QProcess(self)
            self.proceso.started.connect(self.enviar_pendiente)
            self.proceso.readyReadStandardOutput.connect(self.leer_respuesta)
            self.proceso.readyReadStandardError.connect(self.leer_error)
            self.proceso.finished.connect(self.proceso_finalizado)
            self.proceso.errorOccurred.connect(self.error_proceso)
            self.reloj = QTimer(self)
            self.reloj.setSingleShot(True)
            self.reloj.timeout.connect(self.agotar_tiempo)
        env = QProcessEnvironment.systemEnvironment()
        for clave, valor in {
            "TF_NUM_INTRAOP_THREADS": "2", "TF_NUM_INTEROP_THREADS": "1",
            "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1",
            "TF_CPP_MIN_LOG_LEVEL": "2", "PYTHONUTF8": "1",
        }.items():
            env.insert(clave, valor)
        self.proceso.setProcessEnvironment(env)
        self.proceso.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        self.proceso.setProgram(sys.executable)
        self.proceso.setArguments(["-u", "-B", "-m", "src.recognition.proceso_reconocimiento"])
        self.buffer.clear()
        self.proceso.start()

    @Slot(object)
    def ejecutar(self, trabajo):
        if self.cerrando or self.trabajo is not None:
            return
        self.trabajo = trabajo
        self.fallo = None
        try:
            if trabajo["cancelacion"].is_set() and trabajo["tipo"] != "preparar":
                self.completar({"error": True, "mensaje": "Operación cancelada."})
                return
            solicitud = {"tipo": trabajo["tipo"]}
            if trabajo["tipo"] == "reconocer":
                if self.proceso is None or self.proceso.state() != QProcess.Running:
                    self.completar({"error": True, "reiniciar": True,
                                    "mensaje": "El motor está detenido. Cierre y vuelva a abrir la cámara."})
                    return
                if len(trabajo["rostros"]) != 1:
                    self.completar({"resultado": {"estado": "multiples_rostros"}})
                    return
                x, y, w, h = map(int, trabajo["rostros"][0])
                rostro = trabajo["frame"][y:y+h, x:x+w]
                ok, png = cv2.imencode('.png', rostro)
                if not ok:
                    raise ValueError('No se pudo codificar el rostro')
                solicitud["imagen"] = base64.b64encode(png).decode('ascii')
            self.pendiente = (json.dumps(solicitud) + '\n').encode('utf-8')
            if self.proceso is None or self.proceso.state() == QProcess.NotRunning:
                self.iniciar_proceso()
            elif self.proceso.state() == QProcess.Running:
                self.enviar_pendiente()
            self.reloj.start(self.TIEMPO_CARGA_MS if trabajo["tipo"] == "preparar" else self.TIEMPO_ROSTRO_MS)
        except Exception as error:
            print('Error enviando trabajo facial:', error, flush=True)
            self.completar({"error": True, "mensaje": "No se pudo procesar el rostro. Vuelva a intentarlo."})

    @Slot()
    def enviar_pendiente(self):
        if self.pendiente is not None and not self.cerrando:
            self.proceso.write(self.pendiente)
            self.pendiente = None

    @Slot()
    def leer_respuesta(self):
        self.buffer.extend(bytes(self.proceso.readAllStandardOutput()))
        while b'\n' in self.buffer:
            linea, _, resto = self.buffer.partition(b'\n')
            self.buffer = bytearray(resto)
            try:
                respuesta = json.loads(linea)
            except (ValueError, UnicodeError):
                continue
            if self.cerrando or self.fallo:
                continue
            if 'progreso' in respuesta:
                self.progreso.emit(respuesta['progreso'])
            elif self.trabajo is not None:
                self.completar(respuesta)

    @Slot()
    def leer_error(self):
        texto = bytes(self.proceso.readAllStandardError()).decode('utf-8', errors='replace')
        if texto.strip():
            # Algunas terminales Windows no admiten los caracteres de TensorFlow.
            codificacion = getattr(sys.stdout, 'encoding', None) or 'utf-8'
            texto = texto.encode(codificacion, errors='replace').decode(codificacion)
            print(texto, end='', flush=True)

    def completar(self, datos):
        if self.reloj is not None:
            self.reloj.stop()
        trabajo, self.trabajo = self.trabajo, None
        self.pendiente = None
        if trabajo is not None:
            self.terminado.emit({
                "tipo": trabajo["tipo"], "sesion": trabajo["sesion"],
                **datos,
            })

    @Slot()
    def agotar_tiempo(self):
        self.fallo = "El reconocimiento superó el tiempo de espera. Cierre y vuelva a abrir la cámara."
        self.proceso.kill()

    def error_proceso(self, error):
        if error == QProcess.FailedToStart:
            self.completar({"error": True, "reiniciar": True,
                            "mensaje": "No se pudo iniciar el motor facial. Revise la terminal."})
            if self.cerrando:
                self.detenido.emit()

    def proceso_finalizado(self, *args):
        if self.trabajo is not None:
            self.completar({"error": True, "reiniciar": True,
                            "mensaje": self.fallo or "El motor facial se cerró. Cierre y vuelva a abrir la cámara."})
        if self.cerrando:
            self.detenido.emit()

    @Slot()
    def detener(self):
        self.cerrando = True
        if self.reloj is not None:
            self.reloj.stop()
        if self.proceso is not None and self.proceso.state() != QProcess.NotRunning:
            # Es un proceso propio, sin escrituras a la base: se puede detener con seguridad.
            self.proceso.kill()
        else:
            self.detenido.emit()
