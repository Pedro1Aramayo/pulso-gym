"""Diálogos de PULSO GYM con el mismo lenguaje visual que la ventana principal."""
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout)

from src.camera.camera_manager import buscar_camaras
from src.database import gimnasio as db
from src.domain import presentacion as fmt
from src.ui import iconos, tema
from src.ui.captura_foto import CapturaFotoDialog
from src.ui.componentes import Insignia, boton, etiqueta, redondear, separador, tabla

ANGULOS = (('frontal', 'Frontal', 'Mirando a la cámara'), ('izquierdo', 'Izquierda', 'Giro leve a la izquierda'),
           ('derecho', 'Derecha', 'Giro leve a la derecha'))


def preguntar(padre, titulo, texto, aceptar='Aceptar', detalle=None):
    caja = QMessageBox(QMessageBox.Question, titulo, texto, QMessageBox.Ok | QMessageBox.Cancel, padre)
    caja.button(QMessageBox.Ok).setText(aceptar)
    caja.button(QMessageBox.Ok).setObjectName('primario')
    caja.button(QMessageBox.Cancel).setText('Cancelar')
    caja.setDefaultButton(QMessageBox.Cancel)
    if detalle:
        caja.setInformativeText(detalle)
    return caja.exec() == QMessageBox.Ok


class Dialogo(QDialog):
    def __init__(self, padre, titulo, subtitulo='', icono='info'):
        super().__init__(padre)
        self.setWindowTitle(f'PULSO GYM | {titulo}')
        self.setStyleSheet(tema.ESTILO)
        self.cuerpo = QVBoxLayout(self)
        self.cuerpo.setContentsMargins(28, 24, 28, 24)
        self.cuerpo.setSpacing(16)
        cab = QHBoxLayout()
        cab.setSpacing(14)
        ic = QLabel()
        ic.setFixedSize(44, 44)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet('background: rgba(195,245,60,0.12); border-radius: 22px;')
        ic.setPixmap(iconos.pixmap(icono, tema.LIMA, 22))
        cab.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = etiqueta(titulo, 'tituloTarjeta')
        t.setStyleSheet('font-size: 20px;')
        col.addWidget(t)
        if subtitulo:
            col.addWidget(etiqueta(subtitulo, 'tenue', ajuste=True))
        cab.addLayout(col, 1)
        self.cuerpo.addLayout(cab)
        self.cuerpo.addWidget(separador())

    def botonera(self, texto_ok, al_ok, icono='check'):
        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(boton('Cancelar', al_click=self.reject))
        self.ok = boton(texto_ok, icono, 'primario', al_click=al_ok)
        self.ok.setDefault(True)
        fila.addWidget(self.ok)
        self.cuerpo.addLayout(fila)


class DialogoCamara(Dialogo):
    def __init__(self, padre, actual):
        super().__init__(padre, 'Configuración de cámara',
                         'Elija la webcam de recepción. También acepta la URL de una cámara IP o un archivo de video.', 'videocam')
        self.resize(560, 0)
        fila = QHBoxLayout()
        self.origen = QComboBox()
        self.origen.setEditable(True)
        for i in range(4):
            self.origen.addItem(f'Cámara {i}', i)
        indice = self.origen.findData(actual)
        if indice >= 0:
            self.origen.setCurrentIndex(indice)
        else:
            self.origen.setEditText(str(actual))
        fila.addWidget(self.origen, 1)
        fila.addWidget(boton('Buscar cámaras', 'buscar', al_click=self.buscar))
        self.cuerpo.addWidget(etiqueta('Origen de video', 'datoTitulo'))
        self.cuerpo.addLayout(fila)
        self.info = etiqueta('Si la imagen no aparece, cierre otras aplicaciones que estén usando la webcam.', 'tenue', ajuste=True)
        self.cuerpo.addWidget(self.info)
        self.guardar = QCheckBox('Recordar esta cámara en este equipo')
        self.guardar.setChecked(True)
        self.cuerpo.addWidget(self.guardar)
        self.botonera('Aplicar', self.accept)

    def buscar(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            encontradas = buscar_camaras()
        finally:
            QApplication.restoreOverrideCursor()
        self.origen.clear()
        for i in encontradas:
            self.origen.addItem(f'Cámara {i} · disponible', i)
        self.info.setText(f'Se encontraron {len(encontradas)} cámara(s) disponibles.' if encontradas else
                          'No se encontraron webcams libres. Revise la conexión y los permisos de cámara de Windows.')

    def resultado(self):
        texto = self.origen.currentText()
        dato = self.origen.currentData()
        if dato is not None and texto == self.origen.itemText(self.origen.currentIndex()):
            return dato, self.guardar.isChecked()
        return texto.strip(), self.guardar.isChecked()


class RanuraFoto(QFrame):
    def __init__(self, dialogo, angulo, titulo, ayuda):
        super().__init__()
        self.dialogo, self.angulo = dialogo, angulo
        self.setObjectName('cajaDato')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.vista = QLabel()
        self.vista.setFixedSize(150, 150)
        self.vista.setAlignment(Qt.AlignCenter)
        self.vista.setStyleSheet('background:#0A121C; border:1px dashed #2A3B52; border-radius:12px;')
        lay.addWidget(self.vista, 0, Qt.AlignHCenter)
        cab = QHBoxLayout()
        cab.addWidget(etiqueta(titulo, 'tituloTarjeta'))
        cab.addStretch()
        self.estado = Insignia('Pendiente', 'gris')
        cab.addWidget(self.estado)
        lay.addLayout(cab)
        lay.addWidget(etiqueta(ayuda, 'tenue'))
        fila = QHBoxLayout()
        fila.addWidget(boton('Archivo', 'pdf', al_click=lambda: dialogo.ventana.intentar(self.cargar)))
        fila.addWidget(boton('Cámara', 'camaraFoto', al_click=lambda: dialogo.ventana.intentar(self.capturar)))
        lay.addLayout(fila)
        self.vacia()

    def vacia(self):
        self.vista.setPixmap(iconos.pixmap('usuario', '#334459', 54))

    def mostrar(self, datos, estado='Lista', tono='lima'):
        pix = QPixmap()
        pix.loadFromData(datos)
        self.vista.setPixmap(redondear(pix, 150, 150, 12))
        self.estado.fijar(estado, tono)

    def cargar(self):
        ruta, _ = QFileDialog.getOpenFileName(self.dialogo, 'Fotografía', '', 'Imágenes (*.jpg *.jpeg *.png *.bmp)')
        if ruta:
            if Path(ruta).stat().st_size > 15_000_000:
                raise ValueError('Use una imagen menor a 15 MB.')
            self.dialogo.recibir(self.angulo, Path(ruta).read_bytes())

    def capturar(self):
        captura = CapturaFotoDialog(self.dialogo, self.dialogo.ventana.camera)
        captura.foto_capturada.connect(lambda datos: self.dialogo.ventana.intentar(
            lambda: self.dialogo.recibir(self.angulo, datos)))
        captura.exec()


class DialogoSocio(Dialogo):
    CAMPOS = (('nombre', 'Nombre *'), ('apellido', 'Apellido *'), ('dni', 'DNI *'),
              ('celular', 'Celular'), ('correo_electronico', 'Correo electrónico'))

    def __init__(self, ventana, socio=None):
        editar = socio is not None
        super().__init__(ventana, 'Editar socio' if editar else 'Alta de socio',
                         'Las fotografías se guardan solo en la base local y se usan exclusivamente para el control de acceso.',
                         'editar' if editar else 'socios')
        self.ventana, self.socio, self.fotos = ventana, socio, {}
        self.resize(760, 0)
        grilla = QGridLayout()
        grilla.setHorizontalSpacing(16)
        grilla.setVerticalSpacing(6)
        self.campos = {}
        for n, (clave, texto) in enumerate(self.CAMPOS):
            campo = QLineEdit(str(socio.get(clave) or '') if editar else '')
            campo.setPlaceholderText({'dni': 'Solo números', 'celular': 'Ej.: 381 555 1234',
                                      'correo_electronico': 'nombre@correo.com'}.get(clave, ''))
            self.campos[clave] = campo
            fila, col = divmod(n, 2) if n < 4 else (2, 0)
            grilla.addWidget(etiqueta(texto, 'datoTitulo'), fila * 2, col, 1, 1 if n < 4 else 2)
            grilla.addWidget(campo, fila * 2 + 1, col, 1, 1 if n < 4 else 2)
        self.campos['dni'].setMaxLength(10)
        self.cuerpo.addLayout(grilla)
        self.cuerpo.addWidget(etiqueta('FOTOGRAFÍAS', 'seccion'))
        self.cuerpo.addWidget(etiqueta('Cada imagen debe mostrar exactamente un rostro, con buena iluminación. '
                                       'Para las vistas laterales use un giro leve, no un perfil completo.'
                                       + (' Solo se reemplazan las fotografías que cambie.' if editar else ''),
                                       'tenue', ajuste=True))
        fotos = QHBoxLayout()
        fotos.setSpacing(14)
        self.ranuras = {}
        registradas = {a: db.foto_socio(socio['id'], a) for a, _, _ in ANGULOS} if editar else {}
        for angulo, titulo, ayuda in ANGULOS:
            r = RanuraFoto(self, angulo, titulo, ayuda)
            if registradas.get(angulo):
                r.mostrar(registradas[angulo], 'Registrada', 'azul')
            self.ranuras[angulo] = r
            fotos.addWidget(r)
        self.cuerpo.addLayout(fotos)
        self.botonera('Guardar cambios' if editar else 'Guardar socio', lambda: self.ventana.intentar(self.guardar))

    def recibir(self, angulo, datos):
        img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
        if img is None: raise ValueError('Imagen ilegible.')
        escala = min(1, 1000 / max(img.shape[:2])); img = cv2.resize(img, None, fx=escala, fy=escala)
        caras = self.ventana.detector.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(80, 80))
        if len(caras) != 1: raise ValueError('La foto debe mostrar exactamente un rostro. Use un giro leve, no un perfil completo.')
        ok, png = cv2.imencode('.png', img)
        if not ok: raise ValueError('No se pudo convertir la fotografía.')
        self.fotos[angulo] = png.tobytes()
        self.ranuras[angulo].mostrar(self.fotos[angulo], 'Nueva' if self.socio else 'Lista')

    def datos(self):
        return {k: v.text().strip() for k, v in self.campos.items()}

    def guardar(self):
        if self.socio:
            db.actualizar_socio(self.socio['id'], self.datos(), self.fotos)
            self.socio_id = self.socio['id']
        else:
            self.socio_id = db.registrar_socio(self.datos(), self.fotos)
        if self.fotos or not self.socio:
            self.ventana.fotos_modificadas(self.socio_id)
        self.accept()


class DialogoHistorial(Dialogo):
    def __init__(self, padre, socio):
        super().__init__(padre, f"Historial de pagos · {socio['nombre']} {socio['apellido']}",
                         'Cada renovación cierra el período anterior. La vigencia incluye el inicio y excluye el vencimiento.',
                         'dinero')
        self.resize(860, 480)
        filas = db.historial_membresias(socio['id'])
        t = tabla(['Pagado', 'Plan', 'Importe', 'Inicio', 'Vence', 'Ingresos', 'Estado'])
        t.setRowCount(len(filas))
        from PySide6.QtWidgets import QTableWidgetItem
        from src.ui.componentes import celda_insignia
        for i, m in enumerate(filas):
            valores = [f"{m['pagado_en']:%d/%m/%Y %H:%M}", m['plan'], fmt.moneda(m['importe']),
                       fmt.fecha_numerica(m['inicio']), fmt.fecha_numerica(m['vence']),
                       f"{m['usados']} de {m['cupo']}" if m['cupo'] else str(m['usados'])]
            for j, v in enumerate(valores):
                t.setItem(i, j, QTableWidgetItem(v))
            t.setCellWidget(i, 6, celda_insignia('Reemplazada' if m['cerrada_en'] else 'Actual'))
        if not filas:
            self.cuerpo.addWidget(etiqueta('El socio todavía no registró pagos.', 'vacio'))
        self.cuerpo.addWidget(t, 1)
        fila = QHBoxLayout(); fila.addStretch(); fila.addWidget(boton('Cerrar', al_click=self.accept))
        self.cuerpo.addLayout(fila)
