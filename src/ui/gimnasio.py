"""Recepción de PULSO GYM. Reconocimiento sin escrituras hasta confirmar."""
import os
from threading import Event
from time import monotonic
from pathlib import Path
from uuid import uuid4

import cv2
from PySide6.QtCore import QEvent, QProcess, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
                               QPushButton, QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from src.camera.camera_manager import CameraManager
from src.database import gimnasio as db
from src.domain import presentacion as fmt
from src.domain.reglas import ahora_local
from src.recognition.trabajador_reconocimiento import TrabajadorReconocimiento
from src.ui import iconos, tema
from src.ui.componentes import Avatar, Insignia, Kpi, Tarjeta, boton, etiqueta, separador

ESPERA_CONFIRMACION_MS = 45000
DESCANSO_RESULTADO_MS = 9000


def origen_camara():
    guardado = QSettings('PULSO GYM', 'Recepcion').value('camara/origen')
    return guardado if guardado not in (None, '') else os.getenv('CAMERA_INDEX', '0')


class TextoEstado(QLabel):
    """Mensaje de recepción; cada cambio se refleja sobre el video."""
    cambio = Signal(str)

    def setText(self, texto):
        super().setText(texto)
        self.cambio.emit(texto)


class Logo(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(10)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        pulso = QLabel()
        pulso.setPixmap(iconos.pixmap('pulso', tema.LIMA, 54))
        fila.addWidget(pulso, 0, Qt.AlignVCenter)
        texto = QLabel(f"<div style='line-height:86%'><span style='color:#F4F7FB'>PULSO</span><br>"
                       f"<span style='color:{tema.LIMA}'>GYM</span></div>")
        texto.setStyleSheet("font-family:'Montserrat'; font-size:30px; font-weight:800;")
        fila.addWidget(texto)
        fila.addStretch()
        lay.addLayout(fila)
        lay.addWidget(etiqueta('GESTIÓN INTEGRAL DEL GIMNASIO', 'lema'))


class VistaCamara(QWidget):
    """Video de la webcam con esquinas redondeadas, marco de rostro y estado superpuesto."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(560, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.imagen = None
        self.rostros = []
        self.titulo, self.detalle, self.tono = 'Cámara apagada', 'Presione «Abrir / recargar cámara».', 'gris'

    def mostrar(self, imagen, rostros):
        self.imagen, self.rostros = imagen, rostros
        self.update()

    def limpiar(self):
        self.imagen, self.rostros = None, []
        self.update()

    def estado(self, titulo, detalle='', tono='lima'):
        self.titulo, self.detalle, self.tono = titulo, detalle, tono
        self.update()

    def _area_imagen(self):
        if self.imagen is None:
            return QRectF(self.rect())
        w, h = self.imagen.width(), self.imagen.height()
        escala = max(self.width() / w, self.height() / h)
        return QRectF((self.width() - w * escala) / 2, (self.height() - h * escala) / 2, w * escala, h * escala)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        camino = QPainterPath()
        camino.addRoundedRect(QRectF(self.rect()), 14, 14)
        p.setClipPath(camino)
        p.fillRect(self.rect(), QColor('#060C14'))
        if self.imagen is not None:
            area = self._area_imagen()
            p.drawImage(area, self.imagen)
            escala = area.width() / self.imagen.width()
            p.setPen(QPen(QColor(tema.LIMA), 4, Qt.SolidLine, Qt.RoundCap))
            for x, y, w, h in self.rostros:
                r = QRectF(area.x() + x * escala, area.y() + y * escala, w * escala, h * escala).adjusted(-14, -18, 14, 14)
                largo = min(r.width(), r.height()) * 0.22
                for cx, cy, dx, dy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                                       (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
                    p.drawLine(int(cx), int(cy), int(cx + dx * largo), int(cy))
                    p.drawLine(int(cx), int(cy), int(cx), int(cy + dy * largo))
        else:
            ic = iconos.pixmap('videocamOff', '#3A4B60', 64)
            p.drawPixmap(int(self.width() / 2 - 32), int(self.height() / 2 - 70), ic)
        p.setClipping(False)
        p.setPen(QPen(QColor('#1E2C3E'), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        self._pintar_estado(p)

    def _pintar_estado(self, p):
        color = QColor({'lima': tema.LIMA, 'rojo': tema.ROJO, 'ambar': tema.AMBAR, 'gris': '#7D8DA3'}[self.tono])
        f1, f2 = QFont('Inter', 11), QFont('Inter', 10)
        f1.setWeight(QFont.DemiBold)
        ancho = min(self.width() - 40, max(330, 90 + 8 * max(len(self.titulo), len(self.detalle) * 0.9)))
        r = QRectF((self.width() - ancho) / 2, self.height() - 86, ancho, 62)
        fondo = QColor(10, 22, 18, 225) if self.tono == 'lima' else QColor(12, 18, 28, 230)
        p.setPen(QPen(color, 1.4))
        p.setBrush(fondo)
        p.drawRoundedRect(r, 12, 12)
        nombre = {'lima': 'checkCirculo', 'rojo': 'xCirculo', 'ambar': 'alerta', 'gris': 'info'}[self.tono]
        p.drawPixmap(int(r.left() + 18), int(r.center().y() - 15), iconos.pixmap(nombre, color.name(), 30))
        p.setPen(QColor('#F4F7FB'))
        p.setFont(f1)
        p.drawText(QRectF(r.left() + 62, r.top() + 10, r.width() - 76, 22), Qt.AlignLeft | Qt.AlignVCenter, self.titulo)
        p.setPen(QColor('#B9C5D3'))
        p.setFont(f2)
        p.drawText(QRectF(r.left() + 62, r.top() + 31, r.width() - 76, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.detalle, Qt.ElideRight, int(r.width() - 80)))


class FilaAcceso(QFrame):
    ALTO = 56

    def __init__(self, acceso, foto):
        super().__init__()
        self.setObjectName('filaAcceso')
        self.setFixedHeight(self.ALTO)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(12)
        avatar = Avatar(38, circular=False, radio=8)
        avatar.mostrar_foto(foto, fmt.iniciales(acceso['nombre'], acceso['apellido']))
        lay.addWidget(avatar)
        col = QVBoxLayout()
        col.setSpacing(0)
        nombre = etiqueta(f"{acceso['nombre']} {acceso['apellido']}")
        nombre.setStyleSheet('font-weight:600; font-size:14px;')
        col.addWidget(nombre)
        col.addWidget(etiqueta(f"N.º {fmt.numero_socio(acceso['socio_id'])}", 'tenue'))
        lay.addLayout(col, 1)
        lay.addWidget(Insignia(acceso['plan'], '#AFC0D3'))
        instante = acceso['instante']
        hora = etiqueta(f'{instante:%H:%M}' if instante.date() == ahora_local().date() else f'{instante:%d/%m %H:%M}')
        hora.setMinimumWidth(76)
        hora.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(hora)
        lay.addWidget(Insignia('✓ Ingreso', 'lima'))


class PaginaAcceso(QWidget):
    eyebrow = 'CONTROL DE ACCESO'
    titulo = 'Acceso facial de socios'
    subtitulo = 'Validá la identidad del socio con la cámara y registrá su ingreso al gimnasio.'

    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self._accesos, self._mostrados = [], None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        kpis = QHBoxLayout()
        kpis.setSpacing(18)
        self.kpi_ingresos = Kpi('Ingresos hoy', 'puerta')
        self.variacion = Insignia()
        self.variacion.hide()
        self.kpi_ingresos.layout().addWidget(self.variacion, 0, Qt.AlignBottom)
        self.kpi_activos = Kpi('Socios activos', 'socios', tema.AZUL)
        self.kpi_vencen = Kpi('Vencen hoy', 'calendario', tema.AMBAR)
        self.kpi_camara = Kpi('Cámara', 'videocam', tema.LIMA, 'kpiCamara')
        self.estado_camara = Insignia()
        self.kpi_camara.valor.hide()
        self.kpi_camara.layout().itemAt(1).layout().insertWidget(2, self.estado_camara)
        for k in (self.kpi_ingresos, self.kpi_activos, self.kpi_vencen, self.kpi_camara):
            kpis.addWidget(k, 1)
        lay.addLayout(kpis)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        self.en_vivo = Insignia()
        camara = Tarjeta('Cámara de acceso', self.en_vivo, margen=18)
        self._icono_titulo(camara, 'videocam')
        self.video = VistaCamara()
        camara.cuerpo.addWidget(self.video, 1)
        botones = QHBoxLayout()
        botones.setSpacing(12)
        self.abrir = boton('Abrir / recargar cámara', 'camaraFoto', al_click=self.v.iniciar,
                           tooltip='Abre la webcam y vuelve a cargar las fotografías registradas de los socios.')
        self.detener = boton('Detener', 'videocamOff', al_click=self.v.cerrar_camara)
        botones.addWidget(self.abrir, 1)
        botones.addWidget(boton('Configuración de cámara', 'ajustes', al_click=self.v.configurar_camara), 1)
        botones.addWidget(self.detener)
        camara.cuerpo.addLayout(botones)
        cuerpo.addWidget(camara, 62)

        derecha = QVBoxLayout()
        derecha.setSpacing(18)
        derecha.addWidget(self._panel_socio())
        accion = boton('Ver informe completo', None, 'enlace', al_click=lambda: self.v.ir(4))
        accion.setIcon(iconos.icono('chevron', tema.LIMA))
        accion.setLayoutDirection(Qt.RightToLeft)
        self.accesos = Tarjeta('Últimos accesos', accion, margen=18)
        self.accesos.installEventFilter(self)
        self._icono_titulo(self.accesos, 'reloj')
        self.lista_accesos = QVBoxLayout()
        self.lista_accesos.setSpacing(0)
        self.accesos.cuerpo.addLayout(self.lista_accesos)
        self.accesos.cuerpo.addStretch()
        derecha.addWidget(self.accesos, 1)
        cuerpo.addLayout(derecha, 38)
        lay.addLayout(cuerpo, 1)

    def _icono_titulo(self, tarjeta, nombre, color=tema.TEXTO):
        fila = tarjeta.cuerpo.itemAt(0).layout()
        ic = QLabel()
        ic.setPixmap(iconos.pixmap(nombre, color, 22))
        fila.insertWidget(0, ic)
        fila.insertSpacing(1, 6)
        return ic

    def _panel_socio(self):
        self.panel = Tarjeta('Socio reconocido', margen=20)
        self.panel_icono = self._icono_titulo(self.panel, 'checkCirculo', tema.LIMA)
        fila = QHBoxLayout()
        fila.setSpacing(20)
        self.foto = Avatar(116, circular=False, radio=12)
        self.foto.setFixedSize(116, 116)
        fila.addWidget(self.foto)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addStretch()
        self.nombre = etiqueta('Esperando socio', 'nombreSocio')
        self.numero = etiqueta('Ubíquese frente a la cámara.', 'tenue')
        self.plan = Insignia()
        self.plan.hide()
        for w in (self.nombre, self.numero):
            col.addWidget(w)
        col.addSpacing(6)
        col.addWidget(self.plan)
        col.addStretch()
        fila.addLayout(col, 1)
        self.panel.cuerpo.addLayout(fila)
        self.panel.cuerpo.addWidget(separador())
        datos = QHBoxLayout()
        datos.setSpacing(14)
        self.restantes = self._dato(datos, 'puerta', 'Ingresos restantes', 'datoLima')
        datos.addWidget(separador(True))
        self.vence = self._dato(datos, 'calendario', 'Vencimiento', 'datoValor')
        self.panel.cuerpo.addLayout(datos)
        self.mensaje = etiqueta('', 'tenue', ajuste=True)
        self.mensaje.hide()
        self.panel.cuerpo.addWidget(self.mensaje)
        botones = QHBoxLayout()
        botones.setSpacing(12)
        self.confirmar = boton('Confirmar ingreso', 'check', 'primario',
                               al_click=lambda: self.v.intentar(self.v.confirmar), tooltip='Registrar el ingreso (Enter)')
        self.cancelar = boton('Cancelar', 'x', al_click=lambda: self.v.cancelar(), tooltip='No registrar el ingreso (Esc)')
        for b in (self.confirmar, self.cancelar):
            b.setMinimumHeight(50)
        botones.addWidget(self.confirmar, 3)
        botones.addWidget(self.cancelar, 2)
        self.panel.cuerpo.addLayout(botones)
        self.panel_espera()
        return self.panel

    def _dato(self, fila, icono, titulo, estilo):
        caja = QHBoxLayout()
        caja.setSpacing(12)
        circulo = QLabel()
        circulo.setFixedSize(42, 42)
        circulo.setAlignment(Qt.AlignCenter)
        circulo.setStyleSheet('background:#16212F; border:1px solid #223146; border-radius:10px;')
        circulo.setPixmap(iconos.pixmap(icono, '#C9D3DF', 20))
        caja.addWidget(circulo)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(etiqueta(titulo, 'datoTitulo'))
        valor = etiqueta('—', estilo)
        col.addWidget(valor)
        caja.addLayout(col, 1)
        fila.addLayout(caja, 1)
        return valor

    def _panel(self, tono, titulo, icono, color):
        self.panel.tono(tono)
        self.panel.titulo.setText(titulo)
        self.panel.titulo.setStyleSheet(f'color:{color};' if tono else '')
        self.panel_icono.setPixmap(iconos.pixmap(icono, color, 22))

    def panel_espera(self):
        self._panel(None, 'Socio reconocido', 'usuario', tema.TENUE)
        self.foto.limpiar()
        self.nombre.setText('Esperando socio')
        self.numero.setText('Ubíquese frente a la cámara.')
        self.plan.hide()
        self.restantes.setText('—')
        self.vence.setText('—')
        self.mensaje.hide()
        self.confirmar.setEnabled(False)
        self.cancelar.setEnabled(False)

    def panel_socio(self, estado, foto, tono, mensaje=''):
        socio, m = estado['socio'], estado['membresia']
        titulos = {'lima': ('Socio reconocido', 'checkCirculo', tema.LIMA),
                   'rojo': ('Acceso no habilitado', 'xCirculo', tema.ROJO),
                   'ambar': ('Revisar ingreso', 'alerta', tema.AMBAR)}
        self._panel(tono, *titulos[tono])
        if socio:
            self.foto.mostrar_foto(foto, fmt.iniciales(socio['nombre'], socio['apellido']))
            self.nombre.setText(f"{socio['nombre']} {socio['apellido']}")
            self.numero.setText(f"N.º de socio: {fmt.numero_socio(socio['id'])} · DNI {fmt.dni(socio['dni'])}")
        if m:
            self.plan.fijar(f"★  {m['plan']}", 'ambar')
            self.plan.show()
            self.restantes.setText(fmt.texto_restantes(m, estado['decision'].restantes))
            self.vence.setText(fmt.fecha_corta(m['vence']))
            self.vence.setToolTip(f"Último día con acceso: {fmt.fecha_numerica(fmt.ultimo_dia(m['vence']))}")
        else:
            self.plan.hide()
            self.restantes.setText('—')
            self.vence.setText('—')
        self.mensaje.setObjectName('mensajeOk' if tono == 'lima' else 'mensajeError')
        self.mensaje.setStyleSheet(f"color:{ {'lima': tema.LIMA, 'rojo': tema.ROJO, 'ambar': tema.AMBAR}[tono] }; font-weight:600;")
        self.mensaje.setText(mensaje)
        self.mensaje.setVisible(bool(mensaje))

    def refrescar(self, silencioso=False):
        try:
            r = db.resumen_acceso()
            self._accesos = db.ultimos_accesos(8)
        except Exception as e:
            if not silencioso:
                raise
            print(type(e).__name__, str(e))
            return
        self.kpi_ingresos.mostrar(r['ingresos_hoy'])
        var = fmt.variacion(r['ingresos_hoy'], r['ingresos_semana_anterior'])
        if var is None:
            self.variacion.hide()
        else:
            self.variacion.fijar(f"↑ +{var}%" if var >= 0 else f"↓ {abs(var)}%", 'lima' if var >= 0 else 'rojo')
            self.variacion.setToolTip(f"Comparado con el mismo día de la semana pasada hasta esta hora "
                                      f"({r['ingresos_semana_anterior']} ingresos).")
            self.variacion.show()
        self.kpi_activos.mostrar(r['socios_activos'])
        self.kpi_vencen.mostrar(r['vencen_hoy'])
        self.kpi_vencen.setToolTip('Membresías cuyo período termina hoy: desde hoy ya no habilitan el ingreso.')
        self._mostrados = None
        self._pintar_accesos()
        self.estado_camara_ui()

    def _filas_que_entran(self):
        return max(1, (self.accesos.height() - 84) // FilaAcceso.ALTO)

    def _pintar_accesos(self):
        accesos = self._accesos[:self._filas_que_entran()]
        clave = [a['id'] for a in accesos]
        if clave == self._mostrados:
            return
        self._mostrados = clave
        while self.lista_accesos.count():
            w = self.lista_accesos.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not accesos:
            vacio = etiqueta('Todavía no hay ingresos registrados.', 'vacio')
            vacio.setAlignment(Qt.AlignCenter)
            vacio.setMinimumHeight(80)
            self.lista_accesos.addWidget(vacio)
        for a in accesos:
            self.lista_accesos.addWidget(FilaAcceso(a, self.v.foto(a['socio_id'])))

    def eventFilter(self, objeto, evento):
        if objeto is self.accesos and evento.type() == QEvent.Resize and self._accesos:
            QTimer.singleShot(0, self._pintar_accesos)
        return super().eventFilter(objeto, evento)

    def estado_camara_ui(self):
        abierta = bool(self.v.camera.esta_abierta())
        self.estado_camara.fijar('●  Activa' if abierta else '●  Inactiva', 'lima' if abierta else 'gris')
        self.kpi_camara.circulo.cambiar('videocam' if abierta else 'videocamOff', tema.LIMA if abierta else tema.TENUE)
        origen = self.v.camera.indice
        texto = f'Webcam {origen}' if isinstance(origen, int) else f'Origen: {Path(str(origen)).name or origen}'
        self.kpi_camara.detalle.setText(texto)
        self.kpi_camara.detalle.setToolTip(str(origen))
        self.kpi_camara.detalle.show()
        if abierta and self.v.listo:
            self.en_vivo.fijar('●  Transmisión en vivo', 'lima')
        elif abierta:
            self.en_vivo.fijar('●  Preparando', 'ambar')
        else:
            self.en_vivo.fijar('●  Sin transmisión', 'gris')
        self.detener.setEnabled(abierta)


class VentanaGimnasio(QMainWindow):
    def __init__(self):
        super().__init__()
        tema.cargar_fuentes()
        self.setWindowTitle('PULSO GYM | Acceso facial')
        self.setWindowIcon(iconos.icono('pulso', tema.LIMA))
        self.resize(1480, 900)
        self.setMinimumSize(1280, 780)
        self.setStyleSheet(tema.ESTILO)
        self.camera = CameraManager(origen_camara())
        self.motor = TrabajadorReconocimiento()
        self.motor.terminado.connect(self.resultado)
        self.motor.progreso.connect(lambda s: self.estado.setText(s))
        self.motor.detenido.connect(self.finalizar_cierre)
        self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.ocupado = False; self.listo = False; self.modal = False; self.cerrando = False
        self.sesion = 0; self.cancelacion = Event(); self.proximo = 0; self.ultimo_socio = {}
        self.pendiente = None
        self.fotos = {}
        self._construir()
        self.timer = QTimer(self); self.timer.timeout.connect(self.frame); self.timer.start(40)
        self.reloj = QTimer(self); self.reloj.timeout.connect(self.tic); self.reloj.start(1000)
        self.tablero = QTimer(self); self.tablero.timeout.connect(self.refrescar_tablero); self.tablero.start(30000)
        self.expira = QTimer(self); self.expira.setSingleShot(True)
        self.expira.timeout.connect(lambda: self.cancelar('Tiempo de confirmación agotado. No se registró el ingreso.'))
        self.descanso = QTimer(self); self.descanso.setSingleShot(True)
        self.descanso.timeout.connect(lambda: None if self.modal else self.acceso.panel_espera())
        QShortcut(QKeySequence(Qt.Key_Return), self, lambda: self.intentar(self.confirmar) if self.modal else None)
        QShortcut(QKeySequence(Qt.Key_Enter), self, lambda: self.intentar(self.confirmar) if self.modal else None)
        QShortcut(QKeySequence(Qt.Key_Escape), self, lambda: self.cancelar() if self.modal else None)
        self.tic()
        QTimer.singleShot(0, self.refrescar_tablero)

    # ---------- estructura ----------
    def _construir(self):
        from src.ui.paginas import PaginaHorarios, PaginaInformes, PaginaMembresias, PaginaSocios
        raiz = QWidget(); raiz.setObjectName('raiz'); self.setCentralWidget(raiz)
        base = QHBoxLayout(raiz); base.setContentsMargins(0, 0, 0, 0); base.setSpacing(0)
        lateral = QWidget(); lateral.setObjectName('lateral'); lateral.setFixedWidth(268)
        lat = QVBoxLayout(lateral); lat.setContentsMargins(16, 30, 16, 20); lat.setSpacing(10)
        lat.addWidget(Logo()); lat.addSpacing(34)
        self.navegacion = []
        for i, (texto, icono) in enumerate([('Acceso facial', 'acceso'), ('Socios', 'socios'),
                                            ('Membresías y pagos', 'membresias'), ('Horarios y cupos', 'horarios'),
                                            ('Informes', 'informes')]):
            b = QPushButton('   ' + texto); b.setObjectName('nav'); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.setIcon(iconos.icono(icono, '#C9D3DF', '#0A1404')); b.setIconSize(QSize(22, 22))
            b.clicked.connect(lambda _=False, idx=i: self.ir(idx))
            lat.addWidget(b); self.navegacion.append(b)
        lat.addStretch()
        lat.addWidget(separador()); lat.addSpacing(6)
        usuario = QToolButton(); usuario.setObjectName('usuario'); usuario.setText('  Recepción')
        usuario.setIcon(iconos.icono('usuario', tema.TEXTO)); usuario.setIconSize(QSize(26, 26))
        usuario.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); usuario.setPopupMode(QToolButton.InstantPopup)
        usuario.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); usuario.setCursor(Qt.PointingHandCursor)
        menu = QMenu(usuario)
        menu.addAction(iconos.icono('ajustes'), 'Configuración de cámara', self.configurar_camara)
        menu.addAction(iconos.icono('actualizar'), 'Recargar fotografías de socios', self.iniciar)
        menu.addAction(iconos.icono('base'), 'Estado de la base de datos', lambda: self.intentar(self.diagnostico))
        menu.addAction(iconos.icono('info'), 'Acerca de PULSO GYM', self.acerca)
        menu.addSeparator()
        menu.addAction(iconos.icono('salir'), 'Salir', self.close)
        usuario.setMenu(menu)
        lat.addWidget(usuario)
        base.addWidget(lateral)

        contenido = QWidget(); col = QVBoxLayout(contenido); col.setContentsMargins(34, 26, 34, 26); col.setSpacing(20)
        cabecera = QHBoxLayout(); textos = QVBoxLayout(); textos.setSpacing(4)
        eyebrow = QHBoxLayout(); barra = QFrame(); barra.setFixedSize(26, 4)
        barra.setStyleSheet(f'background:{tema.LIMA}; border-radius:2px;')
        self.eyebrow = etiqueta('', 'eyebrow'); eyebrow.addWidget(barra, 0, Qt.AlignVCenter); eyebrow.addSpacing(8)
        eyebrow.addWidget(self.eyebrow); eyebrow.addStretch(); textos.addLayout(eyebrow)
        self.titulo = etiqueta('', 'titulo'); self.subtitulo = etiqueta('', 'subtitulo')
        textos.addWidget(self.titulo); textos.addWidget(self.subtitulo)
        cabecera.addLayout(textos, 1)
        fecha_ic = QLabel(); fecha_ic.setPixmap(iconos.pixmap('calendario', '#C9D3DF', 20))
        reloj_ic = QLabel(); reloj_ic.setPixmap(iconos.pixmap('reloj', '#C9D3DF', 20))
        self.fecha = etiqueta('', 'fecha'); self.hora = etiqueta('', 'fecha')
        for w in (fecha_ic, self.fecha):
            cabecera.addWidget(w, 0, Qt.AlignTop)
        cabecera.addSpacing(18); sep = separador(True); sep.setFixedHeight(26); cabecera.addWidget(sep, 0, Qt.AlignTop)
        cabecera.addSpacing(18)
        for w in (reloj_ic, self.hora):
            cabecera.addWidget(w, 0, Qt.AlignTop)
        col.addLayout(cabecera)
        self.estado = TextoEstado('Abrí la cámara para comenzar.')
        self.estado.hide()
        self.paginas = QStackedWidget()
        self.acceso = PaginaAcceso(self)
        for pagina in (self.acceso, PaginaSocios(self), PaginaMembresias(self), PaginaHorarios(self), PaginaInformes(self)):
            self.paginas.addWidget(pagina)
        col.addWidget(self.paginas, 1)
        base.addWidget(contenido, 1)
        self.estado.cambio.connect(self._estado_en_video)
        self._mostrar_cabecera(0)

    def _mostrar_cabecera(self, indice):
        p = self.paginas.widget(indice)
        self.eyebrow.setText(p.eyebrow); self.titulo.setText(p.titulo); self.subtitulo.setText(p.subtitulo)
        for i, b in enumerate(self.navegacion):
            b.setChecked(i == indice)
        self.setWindowTitle(f"PULSO GYM | {self.navegacion[indice].text().strip()}")

    def _estado_en_video(self, texto):
        tono = 'gris'
        if any(t in texto for t in ('No se pudo', 'Error', 'no confirmada', 'No hay fotos', 'agotado', 'Ubique')):
            tono = 'ambar'
        elif self.listo:
            tono = 'lima'
        titulo = ('Cámara apagada' if not self.camera.esta_abierta() else
                  'Rostro detectado' if self.ocupado and self.listo else 'Reconocimiento activo' if self.listo else 'Preparando')
        if self.ocupado and self.listo:
            texto = 'Analizando identidad…'
        self.acceso.video.estado(titulo, texto, tono)

    def tic(self):
        ahora = ahora_local()
        self.fecha.setText(fmt.fecha_larga(ahora.date()))
        self.hora.setText(f'{ahora:%H:%M}')

    def intentar(self, funcion):
        try:
            return funcion()
        except Exception as e:
            print(type(e).__name__, str(e))
            mensaje = str(e) if isinstance(e, ValueError) else 'No se pudo completar la operación. Revise la conexión con la base de datos y los datos ingresados. Detalle en la terminal.'
            QMessageBox.warning(self, 'Operación no completada', mensaje)
            return None

    def ir(self, indice, **opciones):
        if self.modal and indice != 0:
            self.cancelar('Ingreso cancelado al cambiar de sección.')
        self.sesion += 1; self.cancelacion.set()
        self.paginas.setCurrentIndex(indice); self._mostrar_cabecera(indice)
        pagina = self.paginas.widget(indice)
        if indice == 0:
            self.acceso.refrescar(silencioso=True)
        else:
            self.intentar(lambda: pagina.refrescar(**opciones))

    def refrescar_tablero(self):
        if self.paginas.currentIndex() == 0:
            self.acceso.refrescar(silencioso=True)

    def foto(self, socio_id):
        if socio_id not in self.fotos:
            try:
                self.fotos[socio_id] = db.foto_socio(socio_id)
            except Exception as e:
                print(type(e).__name__, str(e))
                return None
        return self.fotos[socio_id]

    def fotos_modificadas(self, socio_id=None):
        """Tras un alta o un cambio de fotografías hay que recargar las referencias faciales."""
        self.fotos.pop(socio_id, None)
        if self.listo:
            self.listo = False
            self.estado.setText('Hay fotografías nuevas: presione «Abrir / recargar cámara» para reconocerlas.')

    # ---------- cámara y reconocimiento ----------
    def iniciar(self):
        if self.ocupado: return
        if self.modal: self.cancelar()
        if self.paginas.currentIndex() != 0: self.ir(0)
        if not self.camera.abrir():
            self.camera.cerrar(); self.estado.setText('No se pudo abrir la webcam. Revise permisos o elija otra en Configuración de cámara.')
            self.acceso.estado_camara_ui(); return
        self.sesion += 1; self.listo = False; self.ultimo_socio.clear()
        self.estado.setText('Preparando FaceNet512 y fotografías de socios…')
        self.acceso.estado_camara_ui()
        self.enviar('preparar')

    def enviar(self, tipo, frame=None, rostros=None):
        self.ocupado = True; self.acceso.abrir.setEnabled(False); self.cancelacion = Event()
        self.motor.ejecutar(dict(tipo=tipo, sesion=self.sesion, cancelacion=self.cancelacion,
                                 frame=frame, rostros=rostros))
        if tipo == 'reconocer':
            self._estado_en_video('Analizando identidad…')

    def cerrar_camara(self):
        if self.modal: self.cancelar()
        self.sesion += 1; self.cancelacion.set(); self.listo = False
        self.camera.cerrar(); self.acceso.video.limpiar()
        self.estado.setText('Reconocimiento detenido.')
        self.acceso.estado_camara_ui()

    def configurar_camara(self):
        from src.ui.dialogos import DialogoCamara
        dialogo = DialogoCamara(self, self.camera.indice)
        if dialogo.exec():
            origen, guardar = dialogo.resultado()
            if guardar:
                QSettings('PULSO GYM', 'Recepcion').setValue('camara/origen', str(origen))
            estaba = self.camera.esta_abierta()
            self.cerrar_camara()
            self.camera.indice = CameraManager(origen).indice
            self.estado.setText(f'Cámara configurada: {self.camera.indice}.')
            if estaba: self.iniciar()
            self.acceso.estado_camara_ui()

    def frame(self):
        if self.cerrando or not self.camera.esta_abierta() or self.paginas.currentIndex() != 0: return
        imagen = self.camera.leer_frame()
        if imagen is None:
            self.sesion += 1; self.cancelacion.set()
            if not self.modal: self.estado.setText('No se pudo leer la cámara.')
            return
        imagen = cv2.flip(imagen, 1)
        escala = min(1, 640 / max(imagen.shape[:2]))
        pequena = cv2.resize(imagen, None, fx=escala, fy=escala)
        caras = self.detector.detectMultiScale(cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(60, 60))
        if len(caras): caras = (caras / escala).round().astype(int)
        # Mientras se espera la confirmación solo se dibuja el marco; no se lanzan nuevas inferencias.
        if not self.modal:
            if len(caras) != 1:
                self.sesion += 1; self.cancelacion.set()
                if self.listo: self.estado.setText('Ubique un solo rostro.' if len(caras) > 1 else 'Mirá a la cámara.')
            elif self.listo and not self.ocupado and monotonic() >= self.proximo:
                self.enviar('reconocer', imagen.copy(), caras.copy())
        rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB); h, w = rgb.shape[:2]
        q = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888).copy()
        self.acceso.video.mostrar(q, [tuple(c) for c in caras])

    def resultado(self, r):
        self.ocupado = False; self.acceso.abrir.setEnabled(True); self.proximo = monotonic() + 2
        if self.cerrando: return
        if r['tipo'] == 'preparar':
            self.listo = not r.get('error') and r.get('cantidad', 0) > 0 and self.camera.esta_abierta()
            self.estado.setText('Listo: mirá a la cámara.' if self.listo else r.get('mensaje', 'No hay fotos válidas. Registre un socio y recargue la cámara.'))
            self.acceso.estado_camara_ui()
            return
        if r['sesion'] != self.sesion or not self.camera.esta_abierta() or self.paginas.currentIndex() != 0: return
        if r.get('error'):
            if r.get('reiniciar'): self.listo = False
            self.estado.setText(r.get('mensaje', 'Error facial. Vuelva a abrir la cámara.')); return
        identidad = r['resultado']
        if identidad['estado'] != 'reconocido':
            self.estado.setText('Identidad no confirmada. No se registró ningún ingreso.'); return
        sid = identidad['socio_id']
        if monotonic() < self.ultimo_socio.get(sid, 0): return
        self.ultimo_socio[sid] = monotonic() + 10
        self.intentar(lambda: self.proponer(sid))

    def proponer(self, sid):
        # Sin escrituras en este tramo: Cancelar conserva la base intacta.
        estado = db.consultar_acceso(sid); d = estado['decision']; socio = estado['socio']
        nombre = f"{socio['nombre']} {socio['apellido']}" if socio else 'Socio no válido'
        self.descanso.stop()
        foto = self.foto(sid) if socio else None
        if not d.permitido:
            self.acceso.panel_socio(estado, foto, 'rojo', d.motivo)
            self.estado.setText(f'{nombre}: {d.motivo}')
            self.descanso.start(DESCANSO_RESULTADO_MS)
            return
        m = estado['membresia']
        self.modal = True
        self.pendiente = dict(socio_id=sid, membresia_id=m['id'], solicitud=uuid4(), nombre=nombre)
        self.acceso.panel_socio(estado, foto, 'lima', 'Verifique la identidad y confirme el ingreso.')
        self.acceso.confirmar.setEnabled(True); self.acceso.cancelar.setEnabled(True)
        self.acceso.confirmar.setFocus()
        self.estado.setText(f'{nombre}: esperando confirmación.')
        self.expira.start(ESPERA_CONFIRMACION_MS)

    def _liberar(self, sid):
        self.modal = False; self.pendiente = None; self.expira.stop()
        self.proximo = monotonic() + 3; self.ultimo_socio[sid] = monotonic() + 10
        self.acceso.confirmar.setEnabled(False); self.acceso.cancelar.setEnabled(False)
        self.descanso.start(DESCANSO_RESULTADO_MS)

    def confirmar(self):
        if not self.modal or not self.pendiente: return
        p = self.pendiente
        self.acceso.confirmar.setEnabled(False)
        try:
            ok, mensaje = db.confirmar_ingreso(p['socio_id'], p['membresia_id'], p['solicitud'])
        finally:
            self._liberar(p['socio_id'])
        self.estado.setText(f"{p['nombre']}: {mensaje}")
        self.acceso.mensaje.setText(f'{mensaje} · {ahora_local():%H:%M}' if ok else mensaje)
        self.acceso.mensaje.setStyleSheet(f"color:{tema.LIMA if ok else tema.ROJO}; font-weight:600;")
        self.acceso.mensaje.show()
        if not ok:
            self.acceso._panel('rojo', 'Acceso no habilitado', 'xCirculo', tema.ROJO)
        self.acceso.refrescar(silencioso=True)

    def cancelar(self, motivo='Cancelado. No se registró el ingreso.'):
        if not self.modal or not self.pendiente: return
        p = self.pendiente
        self._liberar(p['socio_id'])
        self.estado.setText(f"{p['nombre']}: {motivo}")
        self.acceso.mensaje.setText(motivo)
        self.acceso.mensaje.setStyleSheet(f'color:{tema.TENUE}; font-weight:600;')
        self.acceso.mensaje.show()
        self.acceso._panel(None, 'Ingreso cancelado', 'xCirculo', tema.TENUE)

    # ---------- menú ----------
    def diagnostico(self):
        d = db.diagnostico()
        QMessageBox.information(self, 'Estado de la base de datos',
                                f"Conexión correcta con «{d['base']}» (PostgreSQL {d['version']}).\n\n"
                                f"Socios: {d['socios']}\nMembresías registradas: {d['membresias']}\nIngresos registrados: {d['ingresos']}")

    def acerca(self):
        QMessageBox.about(self, 'Acerca de PULSO GYM',
                          '<b>PULSO GYM</b> · Gestión integral del gimnasio<br><br>'
                          'Python · PySide6 · PostgreSQL · FaceNet512 (DeepFace) · OpenCV<br><br>'
                          'Las fotografías y los datos personales se guardan solo en la base local. '
                          'El reconocimiento nunca registra un ingreso sin la confirmación de recepción.')

    def closeEvent(self, event):
        if not self.cerrando:
            self.cerrando = True; self.timer.stop(); self.cerrar_camara()
            self.motor.detener()
        if self.motor.proceso is not None and self.motor.proceso.state() != QProcess.ProcessState.NotRunning:
            event.ignore()
        else: event.accept()

    def finalizar_cierre(self):
        if self.cerrando: QTimer.singleShot(0, self.close)
