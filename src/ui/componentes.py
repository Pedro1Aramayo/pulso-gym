"""Widgets reutilizables del diseño PULSO GYM."""
from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSizePolicy, QTableWidget, QVBoxLayout, QWidget)

from src.ui import iconos, tema


def etiqueta(texto='', nombre=None, ajuste=False):
    lb = QLabel(texto)
    if nombre:
        lb.setObjectName(nombre)
    lb.setWordWrap(ajuste)
    return lb


def refrescar_estilo(w):
    w.style().unpolish(w)
    w.style().polish(w)


def boton(texto, icono=None, nombre=None, color=None, al_click=None, tooltip=None):
    b = QPushButton(texto)
    if nombre:
        b.setObjectName(nombre)
    if icono:
        b.setIcon(iconos.icono(icono, color or ('#0A1404' if nombre == 'primario' else tema.TEXTO)))
        b.setIconSize(QSize(18, 18))
    b.setCursor(Qt.PointingHandCursor)
    if al_click:
        b.clicked.connect(al_click)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def separador(vertical=False):
    f = QFrame()
    f.setObjectName('separadorV' if vertical else 'separador')
    return f


class Tarjeta(QFrame):
    def __init__(self, titulo=None, accion=None, margen=22, sombra=True):
        super().__init__()
        self.setObjectName('tarjeta')
        self.cuerpo = QVBoxLayout(self)
        self.cuerpo.setContentsMargins(margen, margen - 2, margen, margen)
        self.cuerpo.setSpacing(14)
        if titulo:
            fila = QHBoxLayout()
            self.titulo = etiqueta(titulo, 'tituloTarjeta')
            fila.addWidget(self.titulo)
            fila.addStretch()
            if accion:
                fila.addWidget(accion)
            self.cuerpo.addLayout(fila)
        if sombra:
            s = QGraphicsDropShadowEffect(self)
            s.setBlurRadius(28)
            s.setOffset(0, 8)
            s.setColor(QColor(0, 0, 0, 90))
            self.setGraphicsEffect(s)

    def tono(self, valor):
        self.setProperty('tono', valor or '')
        refrescar_estilo(self)


class IconoCirculo(QLabel):
    """Icono dentro de un círculo translúcido como en la referencia."""

    def __init__(self, icono, color=tema.LIMA, tam=52):
        super().__init__()
        self.setFixedSize(tam, tam)
        self._tam = tam
        self.cambiar(icono, color)

    def cambiar(self, icono, color):
        self._icono, self._color = icono, QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fondo = QColor(self._color)
        fondo.setAlpha(34)
        p.setPen(Qt.NoPen)
        p.setBrush(fondo)
        p.drawEllipse(self.rect())
        ic = iconos.pixmap(self._icono, self._color.name(), int(self._tam * 0.46))
        lado = ic.width() / ic.devicePixelRatio()
        p.drawPixmap(int((self._tam - lado) / 2), int((self._tam - lado) / 2), ic)


class Kpi(QFrame):
    def __init__(self, titulo, icono, color=tema.LIMA, nombre='tarjeta'):
        super().__init__()
        self.setObjectName(nombre)
        self.setMinimumHeight(120)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(18)
        self.circulo = IconoCirculo(icono, color, 58)
        lay.addWidget(self.circulo, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addStretch()
        self.titulo = etiqueta(titulo, 'kpiTitulo')
        self.valor = etiqueta('—', 'kpiValor')
        self.detalle = etiqueta('', 'tenue')
        self.detalle.setTextFormat(Qt.RichText)
        self.titulo.setWordWrap(True); self.detalle.setWordWrap(True)
        for w in (self.titulo, self.valor, self.detalle):
            col.addWidget(w)
        col.addStretch()
        lay.addLayout(col, 1)

    def mostrar(self, valor, detalle=''):
        self.valor.setText(str(valor))
        self.detalle.setText(detalle)
        self.detalle.setVisible(bool(detalle))


def redondear(pix, ancho, alto, radio=14):
    """Recorta una imagen centrada con esquinas redondeadas."""
    escala = pix.scaled(ancho * 2, alto * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    salida = QPixmap(ancho * 2, alto * 2)
    salida.fill(Qt.transparent)
    p = QPainter(salida)
    p.setRenderHint(QPainter.Antialiasing)
    camino = QPainterPath()
    camino.addRoundedRect(QRectF(0, 0, ancho * 2, alto * 2), radio * 2, radio * 2)
    p.setClipPath(camino)
    p.drawPixmap((ancho * 2 - escala.width()) // 2, (alto * 2 - escala.height()) // 2, escala)
    p.end()
    salida.setDevicePixelRatio(2)
    return salida


class Avatar(QLabel):
    """Foto real del socio o, si no está disponible, sus iniciales."""

    def __init__(self, tam=44, circular=True, radio=14):
        super().__init__()
        self.tam, self.circular, self.radio = tam, circular, radio
        self.setFixedSize(tam, tam if circular else int(tam * 1.2))
        self.limpiar()

    def limpiar(self, texto=''):
        self._pix, self._texto = None, texto
        self.update()

    def mostrar_foto(self, datos, iniciales=''):
        pix = QPixmap()
        if datos and pix.loadFromData(datos):
            self._pix = pix
        else:
            self._pix = None
        self._texto = iniciales
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        camino = QPainterPath()
        if self.circular:
            camino.addEllipse(r)
        else:
            camino.addRoundedRect(r, self.radio, self.radio)
        p.setClipPath(camino)
        if self._pix:
            esc = self._pix.scaled(self.size() * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            esc.setDevicePixelRatio(2)
            w, h = esc.width() / 2, esc.height() / 2
            p.drawPixmap(int((self.width() - w) / 2), int((self.height() - h) / 2), esc)
        else:
            fondo = QColor('#18273A')
            p.fillRect(self.rect(), fondo)
            if self._texto:
                p.setPen(QColor(tema.LIMA))
                f = QFont('Montserrat', max(9, int(self.width() * 0.3)))
                f.setWeight(QFont.Bold)
                p.setFont(f)
                p.drawText(self.rect(), Qt.AlignCenter, self._texto)
            else:
                ic = iconos.pixmap('usuario', '#4A5C73', int(self.width() * 0.5))
                lado = ic.width() / ic.devicePixelRatio()
                p.drawPixmap(int((self.width() - lado) / 2), int((self.height() - lado) / 2), ic)
        p.setClipping(False)
        p.setPen(QPen(QColor('#24364C'), 1.2))
        p.setBrush(Qt.NoBrush)
        if self.circular:
            p.drawEllipse(r)
        else:
            p.drawRoundedRect(r, self.radio, self.radio)


class Insignia(QLabel):
    COLORES = {'lima': tema.LIMA, 'rojo': tema.ROJO, 'ambar': tema.AMBAR, 'azul': tema.AZUL, 'gris': tema.TENUE}

    def __init__(self, texto='', tono='lima'):
        super().__init__()
        self.fijar(texto, tono)

    def fijar(self, texto, tono='lima'):
        c = QColor(self.COLORES.get(tono, tono))
        self.setText(texto)
        self.setStyleSheet(f'color:{c.name()}; background: rgba({c.red()},{c.green()},{c.blue()},0.13);'
                           f'border:1px solid rgba({c.red()},{c.green()},{c.blue()},0.40); border-radius: 11px;'
                           'padding: 3px 11px; font-size: 12px; font-weight: 600;')
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)


TONO_ESTADO = {'Vigente': 'lima', 'Vencida': 'rojo', 'Cupo agotado': 'ambar', 'Sin membresía': 'gris',
               'No vigente': 'azul', 'Inactivo': 'gris', 'Activo': 'lima', 'Actual': 'lima',
               'Reemplazada': 'gris', 'Por vencer': 'ambar'}


def celda_insignia(texto):
    cont = QWidget()
    lay = QHBoxLayout(cont)
    lay.setContentsMargins(10, 0, 0, 0)
    lay.addWidget(Insignia(texto, TONO_ESTADO.get(texto, 'gris')))
    lay.addStretch()
    return cont


def tabla(columnas, estirar=None):
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(52)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setSelectionMode(QTableWidget.SingleSelection)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setFocusPolicy(Qt.NoFocus)
    t.setWordWrap(False)
    h = t.horizontalHeader()
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(estirar if estirar is not None else len(columnas) - 1, QHeaderView.Stretch)
    return t


class ColumnasOpcionales(QObject):
    """Oculta columnas secundarias cuando la tabla es angosta, para no truncar los nombres."""
    def __init__(self, tabla, columnas, ancho_minimo):
        super().__init__(tabla)
        self.tabla, self.columnas, self.ancho = tabla, columnas, ancho_minimo
        tabla.installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Resize:
            for c in self.columnas:
                self.tabla.setColumnHidden(c, self.tabla.width() < self.ancho)
        return False


def fijar_ancho(t, columna, ancho):
    """Las columnas con widgets (insignias, avatares) no se miden con ResizeToContents."""
    t.horizontalHeader().setSectionResizeMode(columna, QHeaderView.Fixed)
    t.setColumnWidth(columna, ancho)


class Barras(QWidget):
    """Gráfico de barras liviano pintado con QPainter (sin dependencias extra)."""

    def __init__(self, alto=220):
        super().__init__()
        self.setMinimumHeight(alto)
        self.datos = []
        self.resaltar = None

    def fijar(self, datos, resaltar=None):
        self.datos, self.resaltar = list(datos), resaltar
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.datos:
            return
        maximo = max(v for _, v in self.datos) or 1
        izq, inf, sup = 34, 26, 12
        ancho = (self.width() - izq - 6) / len(self.datos)
        alto = self.height() - inf - sup
        f = p.font()
        f.setPointSize(8)
        p.setFont(f)
        for k in range(5):
            y = sup + alto * k / 4
            p.setPen(QPen(QColor('#18263A'), 1, Qt.DashLine))
            p.drawLine(izq, int(y), self.width() - 6, int(y))
            p.setPen(QColor(tema.TENUE))
            p.drawText(QRectF(0, y - 8, izq - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f'{round(maximo * (4 - k) / 4)}')
        paso = max(1, round(len(self.datos) / 12))
        for i, (etiq, v) in enumerate(self.datos):
            h = alto * v / maximo
            x = izq + i * ancho + ancho * 0.18
            color = QColor(tema.LIMA if (self.resaltar is None or i == self.resaltar) else '#4E6A2A')
            if v:
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(x, sup + alto - h, ancho * 0.64, h), 3, 3)
            if i % paso == 0:
                p.setPen(QColor(tema.TENUE))
                p.drawText(QRectF(x - ancho, self.height() - inf + 6, ancho * 2.64, 16), Qt.AlignCenter, etiq)


class BarraProgreso(QWidget):
    def __init__(self, alto=8):
        super().__init__()
        self.setFixedHeight(alto)
        self.valor = 0.0
        self.color = tema.LIMA

    def fijar(self, valor, color=tema.LIMA):
        self.valor, self.color = max(0.0, min(1.0, valor)), color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.height() / 2
        p.setBrush(QColor('#1A283A'))
        p.drawRoundedRect(QRectF(self.rect()), r, r)
        if self.valor:
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(QRectF(0, 0, self.width() * self.valor, self.height()), r, r)
