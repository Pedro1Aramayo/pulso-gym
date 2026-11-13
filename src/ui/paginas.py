"""Secciones de gestión: socios, membresías y pagos, horarios y cupos, informes."""
from datetime import timedelta

from PySide6.QtCore import QDate, QSize, Qt, QTime
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QCompleter, QDateEdit, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                               QTableWidgetItem, QTimeEdit, QVBoxLayout, QWidget)

from src.database import gimnasio as db
from src.domain import presentacion as fmt
from src.domain.reglas import ahora_local, un_mes
from src.reports.gimnasio import exportar
from src.ui import iconos, tema
from src.ui.componentes import (Avatar, BarraProgreso, Barras, Insignia, Kpi, Tarjeta, boton, celda_insignia,
                                etiqueta, fijar_ancho, separador, tabla)
from src.ui.dialogos import DialogoHistorial, DialogoSocio, preguntar

DIAS = fmt.DIAS


def item(texto, dato=None, alinear=None):
    it = QTableWidgetItem('—' if texto is None else str(texto))
    if dato is not None:
        it.setData(Qt.UserRole, dato)
    if alinear:
        it.setTextAlignment(alinear)
    return it


def buscador(placeholder):
    campo = QLineEdit()
    campo.setPlaceholderText(placeholder)
    campo.addAction(iconos.icono('buscar', tema.TENUE), QLineEdit.LeadingPosition)
    campo.setClearButtonEnabled(True)
    campo.setMinimumWidth(260)
    return campo


def chips(opciones, al_cambiar):
    grupo = QButtonGroup()
    grupo.setExclusive(True)
    fila = QHBoxLayout()
    fila.setSpacing(8)
    for i, texto in enumerate(opciones):
        b = QPushButton(texto)
        b.setObjectName('filtro')
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setChecked(i == 0)
        grupo.addButton(b, i)
        fila.addWidget(b)
    grupo.idClicked.connect(lambda _: al_cambiar())
    return grupo, fila


def fila_kpis(*kpis):
    fila = QHBoxLayout()
    fila.setSpacing(18)
    for k in kpis:
        fila.addWidget(k, 1)
    return fila


def dato(titulo, valor='—'):
    cont = QVBoxLayout()
    cont.setSpacing(2)
    cont.addWidget(etiqueta(titulo, 'datoTitulo'))
    v = etiqueta(valor)
    v.setStyleSheet('font-size: 15px; font-weight: 600;')
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    cont.addWidget(v)
    return cont, v


class Pagina(QWidget):
    def __init__(self, ventana, desplazable=True):
        super().__init__()
        self.v = ventana
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        if desplazable:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            interior = QWidget()
            area.setWidget(interior)
            externo.addWidget(area)
            self.lay = QVBoxLayout(interior)
            self.lay.setContentsMargins(0, 0, 8, 0)
        else:
            self.lay = externo
        self.lay.setSpacing(18)


# ============================================================ SOCIOS
class PaginaSocios(Pagina):
    eyebrow = 'GESTIÓN DE SOCIOS'
    titulo = 'Socios del gimnasio'
    subtitulo = 'Registrá socios con sus tres fotografías, actualizá sus datos y controlá su estado.'

    def __init__(self, ventana):
        super().__init__(ventana)
        self.socios, self.actual = [], None
        self.k_total = Kpi('Socios registrados', 'socios', tema.AZUL)
        self.k_activos = Kpi('Socios activos', 'checkCirculo')
        self.k_vigentes = Kpi('Con membresía vigente', 'tarjeta', tema.LIMA)
        self.k_sin = Kpi('Sin membresía vigente', 'alerta', tema.AMBAR)
        self.lay.addLayout(fila_kpis(self.k_total, self.k_activos, self.k_vigentes, self.k_sin))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        lista = Tarjeta(margen=20)
        barra = QHBoxLayout()
        self.busqueda = buscador('Buscar por nombre, apellido o DNI')
        self.busqueda.textChanged.connect(self.filtrar)
        barra.addWidget(self.busqueda, 1)
        self.filtro, fila = chips(['Todos', 'Activos', 'Inactivos'], self.filtrar)
        barra.addLayout(fila)
        barra.addSpacing(8)
        barra.addWidget(boton('Nuevo socio', 'mas', 'primario', al_click=lambda: self.v.intentar(self.nuevo)))
        lista.cuerpo.addLayout(barra)
        self.tabla = tabla(['', 'Socio', 'N.º', 'DNI', 'Plan', 'Vence', 'Estado'], estirar=1)
        fijar_ancho(self.tabla, 0, 60)
        fijar_ancho(self.tabla, 6, 132)
        self.tabla.itemSelectionChanged.connect(self.seleccionar)
        self.tabla.doubleClicked.connect(lambda _: self.v.intentar(self.editar))
        lista.cuerpo.addWidget(self.tabla, 1)
        self.contador = etiqueta('', 'tenue')
        lista.cuerpo.addWidget(self.contador)
        cuerpo.addWidget(lista, 1)
        cuerpo.addWidget(self._detalle())
        self.lay.addLayout(cuerpo, 1)

    def _detalle(self):
        t = Tarjeta('Ficha del socio', margen=20)
        t.setFixedWidth(380)
        cabecera = QHBoxLayout(); cabecera.setSpacing(16)
        self.foto = Avatar(104, circular=False, radio=12)
        self.foto.setFixedSize(104, 104)
        cabecera.addWidget(self.foto)
        col = QVBoxLayout(); col.setSpacing(8); col.addStretch()
        self.d_nombre = etiqueta('Seleccione un socio', 'nombreSocio', ajuste=True)
        self.d_nombre.setStyleSheet('font-size: 20px;')
        col.addWidget(self.d_nombre)
        fila = QHBoxLayout(); fila.setSpacing(6)
        self.d_estado = Insignia('—', 'gris'); fila.addWidget(self.d_estado)
        self.d_plan = Insignia('', 'ambar'); fila.addWidget(self.d_plan); fila.addStretch()
        col.addLayout(fila); col.addStretch()
        cabecera.addLayout(col, 1)
        t.cuerpo.addLayout(cabecera)
        t.cuerpo.addWidget(separador())
        grilla = QGridLayout(); grilla.setVerticalSpacing(12); grilla.setHorizontalSpacing(16)
        self.d = {}
        for n, (clave, titulo) in enumerate([('numero', 'N.º de socio'), ('dni', 'DNI'), ('celular', 'Celular'),
                                             ('alta', 'Alta'), ('vence', 'Vencimiento'), ('ultimo', 'Último ingreso'),
                                             ('correo', 'Correo electrónico')]):
            caja, self.d[clave] = dato(titulo)
            grilla.addLayout(caja, n // 2, n % 2, 1, 2 if clave == 'correo' else 1)
        t.cuerpo.addLayout(grilla)
        t.cuerpo.addStretch()
        self.b_editar = boton('Editar datos y fotos', 'editar', al_click=lambda: self.v.intentar(self.editar))
        self.b_pago = boton('Registrar pago', 'dinero', 'primario', al_click=self.pagar)
        self.b_historial = boton('Historial de pagos', 'reloj', al_click=lambda: self.v.intentar(
            lambda: DialogoHistorial(self.v, self.actual).exec()))
        self.b_estado = boton('Desactivar socio', 'power', 'peligro', al_click=lambda: self.v.intentar(self.alternar))
        acciones = QGridLayout(); acciones.setSpacing(10)
        acciones.addWidget(self.b_pago, 0, 0, 1, 2)
        acciones.addWidget(self.b_editar, 1, 0); acciones.addWidget(self.b_historial, 1, 1)
        acciones.addWidget(self.b_estado, 2, 0, 1, 2)
        self.b_editar.setText('Editar datos'); self.b_historial.setText('Pagos')
        self.b_editar.setToolTip('Editar datos personales y fotografías'); self.b_historial.setToolTip('Historial de pagos')
        t.cuerpo.addLayout(acciones)
        self.mostrar_detalle(None)
        return t

    def refrescar(self, socio_id=None):
        elegido = socio_id or (self.actual or {}).get('id')
        self.socios = db.estado_membresias()
        activos = [s for s in self.socios if s['activo']]
        vigentes = sum(1 for s in activos if s['estado'] in ('Vigente', 'Cupo agotado'))
        self.k_total.mostrar(len(self.socios))
        self.k_activos.mostrar(len(activos), f"{len(self.socios) - len(activos)} inactivos")
        self.k_vigentes.mostrar(vigentes)
        self.k_sin.mostrar(len(activos) - vigentes, 'Socios activos sin acceso habilitado')
        self.filtrar(elegido)

    def visibles(self):
        texto = self.busqueda.text().strip().lower()
        modo = self.filtro.checkedId()
        return [s for s in self.socios
                if (modo == 0 or s['activo'] == (modo == 1))
                and (not texto or texto in f"{s['nombre']} {s['apellido']} {s['apellido']} {s['nombre']} {s['dni']}".lower())]

    def filtrar(self, elegido=None):
        elegido = elegido if isinstance(elegido, int) else (self.actual or {}).get('id')
        filas = self.visibles()
        t = self.tabla
        t.blockSignals(True)
        t.clearContents()
        t.setRowCount(len(filas))
        fila_elegida = -1
        for i, s in enumerate(filas):
            av = Avatar(36)
            av.mostrar_foto(self.v.foto(s['id']), fmt.iniciales(s['nombre'], s['apellido']))
            cont = QWidget(); l = QHBoxLayout(cont); l.setContentsMargins(10, 0, 0, 0); l.addWidget(av)
            t.setCellWidget(i, 0, cont)
            t.setItem(i, 1, item(f"{s['apellido']}, {s['nombre']}", s['id']))
            t.setItem(i, 2, item(fmt.numero_socio(s['id'])))
            t.setItem(i, 3, item(fmt.dni(s['dni'])))
            t.setItem(i, 4, item(s['plan'] or '—'))
            t.setItem(i, 5, item(fmt.fecha_numerica(s['vence'])))
            t.setCellWidget(i, 6, celda_insignia(s['estado'] if s['activo'] else 'Inactivo'))
            if s['id'] == elegido:
                fila_elegida = i
        t.blockSignals(False)
        self.contador.setText(f'{len(filas)} de {len(self.socios)} socios')
        if fila_elegida >= 0:
            t.selectRow(fila_elegida)
        else:
            t.clearSelection()
            self.mostrar_detalle(None)

    def seleccionar(self):
        fila = self.tabla.currentRow()
        it = self.tabla.item(fila, 1) if fila >= 0 else None
        sid = it.data(Qt.UserRole) if it else None
        self.mostrar_detalle(next((s for s in self.socios if s['id'] == sid), None))

    def mostrar_detalle(self, s):
        self.actual = s
        for b in (self.b_editar, self.b_pago, self.b_historial, self.b_estado):
            b.setEnabled(s is not None)
        if not s:
            self.foto.limpiar()
            self.d_nombre.setText('Seleccione un socio')
            self.d_estado.fijar('Sin selección', 'gris'); self.d_plan.hide()
            for v in self.d.values():
                v.setText('—')
            return
        self.foto.mostrar_foto(self.v.foto(s['id']), fmt.iniciales(s['nombre'], s['apellido']))
        self.d_nombre.setText(f"{s['nombre']} {s['apellido']}")
        estado = s['estado'] if s['activo'] else 'Inactivo'
        self.d_estado.fijar(estado, {'Vigente': 'lima', 'Vencida': 'rojo', 'Cupo agotado': 'ambar'}.get(estado, 'gris'))
        self.d_plan.setText(s['plan'] or ''); self.d_plan.setVisible(bool(s['plan']))
        self.d_plan.fijar(s['plan'] or '', 'ambar')
        self.d['numero'].setText(fmt.numero_socio(s['id']))
        self.d['dni'].setText(fmt.dni(s['dni']))
        self.d['celular'].setText(s['celular'] or '—')
        self.d['correo'].setText(s['correo_electronico'] or '—')
        self.d['alta'].setText(fmt.fecha_numerica(s['creado_en'].date()))
        self.d['vence'].setText(fmt.fecha_numerica(s['vence']))
        self.d['ultimo'].setText(f"{s['ultimo_ingreso']:%d/%m/%Y %H:%M}" if s['ultimo_ingreso'] else '—')
        self.b_estado.setText('Desactivar socio' if s['activo'] else 'Activar socio')
        self.b_estado.setObjectName('peligro' if s['activo'] else '')
        self.b_estado.style().unpolish(self.b_estado); self.b_estado.style().polish(self.b_estado)
        self.b_pago.setEnabled(s['activo'])

    def nuevo(self):
        dialogo = DialogoSocio(self.v)
        if dialogo.exec():
            self.refrescar(dialogo.socio_id)
            QMessageBox.information(self, 'Socio registrado',
                                    'Socio guardado. Registre su pago en Membresías y recargue la cámara para reconocerlo.')

    def editar(self):
        if not self.actual: raise ValueError('Seleccione un socio.')
        dialogo = DialogoSocio(self.v, self.actual)
        if dialogo.exec():
            self.refrescar(self.actual['id'])

    def alternar(self):
        s = self.actual
        if not s: raise ValueError('Seleccione un socio.')
        accion = 'Desactivar' if s['activo'] else 'Activar'
        detalle = ('Un socio inactivo no puede ingresar aunque tenga una membresía vigente.' if s['activo']
                   else 'El socio podrá volver a ingresar si tiene una membresía vigente.')
        if preguntar(self, 'Estado del socio', f"¿{accion} a {s['nombre']} {s['apellido']}?", accion, detalle):
            db.cambiar_estado(s['id'], not s['activo'])
            self.refrescar(s['id'])

    def pagar(self):
        if self.actual:
            self.v.ir(2, socio_id=self.actual['id'])


# ============================================================ MEMBRESÍAS
class PaginaMembresias(Pagina):
    eyebrow = 'MEMBRESÍAS Y PAGOS'
    titulo = 'Membresías y pagos'
    subtitulo = 'Cada pago habilita un mes calendario desde hoy. Renovar antes de tiempo reemplaza el período anterior.'
    FILTROS = ['Todas', 'Vigentes', 'Por vencer', 'Vencidas', 'Sin membresía']

    def __init__(self, ventana):
        super().__init__(ventana)
        self.estado, self.lista_planes = [], []
        self.k_recaudado = Kpi('Recaudado este mes', 'dinero')
        self.k_vigentes = Kpi('Membresías vigentes', 'checkCirculo', tema.AZUL)
        self.k_por_vencer = Kpi('Vencen en 7 días', 'calendario', tema.AMBAR)
        self.k_vencidas = Kpi('Vencidas o sin membresía', 'calendarioX', tema.ROJO)
        self.lay.addLayout(fila_kpis(self.k_recaudado, self.k_vigentes, self.k_por_vencer, self.k_vencidas))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        cuerpo.addWidget(self._formulario())
        lista = Tarjeta('Estado de membresías', margen=20)
        barra = QHBoxLayout()
        self.filtro, fila = chips(self.FILTROS, self.llenar)
        barra.addLayout(fila); barra.addStretch()
        self.busqueda = buscador('Buscar socio o DNI')
        self.busqueda.setMinimumWidth(200)
        self.busqueda.textChanged.connect(self.llenar)
        barra.addWidget(self.busqueda)
        lista.cuerpo.addLayout(barra)
        self.tabla = tabla(['Socio', 'Plan', 'Inicio', 'Vence', 'Uso del mes', 'Estado'], estirar=0)
        fijar_ancho(self.tabla, 4, 170)
        fijar_ancho(self.tabla, 5, 132)
        self.tabla.itemSelectionChanged.connect(self.elegir_de_tabla)
        lista.cuerpo.addWidget(self.tabla, 1)
        pie = QHBoxLayout()
        self.contador = etiqueta('', 'tenue'); pie.addWidget(self.contador); pie.addStretch()
        self.b_historial = boton('Historial de pagos del socio', 'reloj', al_click=lambda: self.v.intentar(self.historial))
        pie.addWidget(self.b_historial)
        lista.cuerpo.addLayout(pie)
        cuerpo.addWidget(lista, 1)
        self.lay.addLayout(cuerpo, 1)

    def _formulario(self):
        t = Tarjeta('Registrar pago', margen=22)
        t.setFixedWidth(410)
        t.cuerpo.setSpacing(8)
        t.cuerpo.addWidget(etiqueta('Socio', 'datoTitulo'))
        self.socio = QComboBox(); self.socio.setEditable(True); self.socio.setInsertPolicy(QComboBox.NoInsert)
        self.socio.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.socio.completer().setFilterMode(Qt.MatchContains)
        self.socio.lineEdit().setPlaceholderText('Escriba nombre o DNI')
        self.socio.currentIndexChanged.connect(self.actualizar_resumen)
        self.socio.editTextChanged.connect(self.actualizar_resumen)
        t.cuerpo.addWidget(self.socio)
        self.actual = etiqueta('', 'tenue', ajuste=True)
        t.cuerpo.addWidget(self.actual)
        t.cuerpo.addWidget(etiqueta('Plan', 'datoTitulo'))
        self.planes_lay = QGridLayout(); self.planes_lay.setSpacing(8)
        self.grupo_planes = QButtonGroup(self); self.grupo_planes.idClicked.connect(lambda _: self.actualizar_resumen())
        t.cuerpo.addLayout(self.planes_lay)
        t.cuerpo.addWidget(etiqueta('Importe abonado', 'datoTitulo'))
        self.importe = QDoubleSpinBox(); self.importe.setRange(0, 999999999); self.importe.setPrefix('$ ')
        self.importe.setDecimals(2); self.importe.setGroupSeparatorShown(True)
        t.cuerpo.addWidget(self.importe)
        self.aviso = QFrame(); self.aviso.setObjectName('aviso')
        av = QHBoxLayout(self.aviso); av.setContentsMargins(12, 10, 12, 10)
        ic = QLabel(); ic.setPixmap(iconos.pixmap('alerta', tema.AMBAR, 18)); av.addWidget(ic, 0, Qt.AlignTop)
        self.aviso_texto = etiqueta('', ajuste=True); self.aviso_texto.setStyleSheet(f'color:{tema.AMBAR}; font-size:13px;')
        av.addWidget(self.aviso_texto, 1)
        t.cuerpo.addWidget(self.aviso)
        self.resumen = etiqueta('', 'tenue', ajuste=True)
        t.cuerpo.addWidget(self.resumen)
        t.cuerpo.addStretch()
        self.b_pagar = boton('Registrar pago', 'check', 'primario', al_click=lambda: self.v.intentar(self.pagar))
        self.b_pagar.setMinimumHeight(48)
        t.cuerpo.addWidget(self.b_pagar)
        return t

    def refrescar(self, socio_id=None):
        elegido = socio_id or self.socio.currentData()
        self.estado = db.estado_membresias()
        self.lista_planes = db.planes()
        cobro = db.resumen_pagos()
        hoy = ahora_local().date()
        activos = [s for s in self.estado if s['activo']]
        for s in self.estado:
            s['por_vencer'] = s['estado'] == 'Vigente' and (s['vence'] - hoy).days <= 7
        self.k_recaudado.mostrar(fmt.moneda(cobro['recaudado']), f"{cobro['pagos']} pagos en {fmt.MESES[hoy.month - 1]}")
        self.k_vigentes.mostrar(sum(1 for s in activos if s['estado'] in ('Vigente', 'Cupo agotado')))
        self.k_por_vencer.mostrar(sum(1 for s in activos if s['por_vencer']), 'Recordar la renovación')
        self.k_vencidas.mostrar(sum(1 for s in activos if s['estado'] in ('Vencida', 'Sin membresía')), 'Socios activos')
        self.socio.blockSignals(True); self.socio.clear()
        for s in activos:
            self.socio.addItem(f"{s['apellido']}, {s['nombre']} · DNI {fmt.dni(s['dni'])}", s['id'])
        self.socio.setCurrentIndex(max(0, self.socio.findData(elegido)) if activos else -1)
        self.socio.blockSignals(False)
        elegido_plan = self.grupo_planes.checkedId()
        for b in self.grupo_planes.buttons():
            self.grupo_planes.removeButton(b); b.deleteLater()
        for i, p in enumerate(self.lista_planes):
            b = QPushButton(p['nombre'])
            b.setToolTip(fmt.regla_plan(p['cupo'], p['una_vez_dia']))
            b.setObjectName('opcion'); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            self.grupo_planes.addButton(b, p['id']); self.planes_lay.addWidget(b, i // 2, i % 2)
        boton_plan = self.grupo_planes.button(elegido_plan) or (self.grupo_planes.buttons() or [None])[0]
        if boton_plan: boton_plan.setChecked(True)
        self.actualizar_resumen()
        self.llenar()

    def socio_elegido(self):
        # Con el texto editado y sin elegir una sugerencia, currentData() sigue apuntando al socio anterior.
        if self.socio.currentIndex() < 0 or self.socio.currentText() != self.socio.itemText(self.socio.currentIndex()):
            return None
        sid = self.socio.currentData()
        return next((s for s in self.estado if s['id'] == sid), None)

    def actualizar_resumen(self):
        s = self.socio_elegido()
        hoy = ahora_local().date()
        vence = un_mes(hoy)
        plan = next((p for p in self.lista_planes if p['id'] == self.grupo_planes.checkedId()), None)
        self.b_pagar.setEnabled(bool(s and plan))
        if not s:
            self.actual.setText('No hay socios activos. Registre o active un socio primero.' if not self.estado else
                                'Elija un socio activo.')
            self.aviso.hide(); self.resumen.clear(); return
        if s['plan']:
            self.actual.setText(f"Membresía actual: {s['plan']} · {s['estado'].lower()} · vence {fmt.fecha_numerica(s['vence'])}")
        else:
            self.actual.setText('El socio no tiene membresía registrada.')
        vigente = s['plan'] and s['estado'] in ('Vigente', 'Cupo agotado', 'No vigente')
        if vigente:
            saldo = f" y se descartan {s['restantes']} entrenamientos sin usar" if s['cupo'] and s['restantes'] else ''
            self.aviso_texto.setText(f"Renovación anticipada: el período actual se cierra hoy{saldo}.")
        self.aviso.setVisible(bool(vigente))
        self.resumen.setText(f"Período: {fmt.fecha_numerica(hoy)} al {fmt.fecha_numerica(vence)} "
                             f"(último día con acceso: {fmt.fecha_numerica(fmt.ultimo_dia(vence))})"
                             + (f" · {fmt.regla_plan(plan['cupo'], plan['una_vez_dia'])}" if plan else ''))

    def visibles(self):
        modo = self.FILTROS[self.filtro.checkedId()]
        texto = self.busqueda.text().strip().lower()
        criterio = {'Todas': lambda s: True, 'Vigentes': lambda s: s['estado'] in ('Vigente', 'Cupo agotado'),
                    'Por vencer': lambda s: s['por_vencer'], 'Vencidas': lambda s: s['estado'] == 'Vencida',
                    'Sin membresía': lambda s: s['estado'] == 'Sin membresía'}[modo]
        return [s for s in self.estado if criterio(s) and (s['activo'] or modo == 'Todas')
                and (not texto or texto in f"{s['nombre']} {s['apellido']} {s['dni']}".lower())]

    def llenar(self):
        filas = self.visibles()
        t = self.tabla
        t.blockSignals(True); t.clearContents(); t.setRowCount(len(filas))
        for i, s in enumerate(filas):
            t.setItem(i, 0, item(f"{s['apellido']}, {s['nombre']}", s['id']))
            t.item(i, 0).setToolTip(f"DNI {fmt.dni(s['dni'])}")
            t.setItem(i, 1, item(s['plan'] or '—'))
            t.setItem(i, 2, item(fmt.fecha_numerica(s['inicio'])))
            t.setItem(i, 3, item(fmt.fecha_numerica(s['vence'])))
            if s['plan'] and s['cupo']:
                cont = QWidget(); l = QHBoxLayout(cont); l.setContentsMargins(10, 0, 10, 0); l.setSpacing(10)
                barra = BarraProgreso(6); barra.setMinimumWidth(80)
                barra.fijar(s['usados'] / s['cupo'], tema.AMBAR if s['restantes'] == 0 else tema.LIMA)
                l.addWidget(barra, 1); l.addWidget(etiqueta(f"{s['usados']}/{s['cupo']}", 'tenue'))
                t.setCellWidget(i, 4, cont)
            else:
                t.setItem(i, 4, item(f"{s['usados']} ingresos · sin cupo" if s['plan'] else '—'))
            t.setCellWidget(i, 5, celda_insignia('Por vencer' if s['por_vencer'] else
                                                 (s['estado'] if s['activo'] else 'Inactivo')))
        t.setColumnWidth(4, 170)
        t.blockSignals(False)
        self.contador.setText(f'{len(filas)} socios')
        self.b_historial.setEnabled(False)

    def elegir_de_tabla(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        sid = self.tabla.item(fila, 0).data(Qt.UserRole)
        self.b_historial.setEnabled(True)
        indice = self.socio.findData(sid)
        if indice >= 0: self.socio.setCurrentIndex(indice)

    def historial(self):
        fila = self.tabla.currentRow()
        if fila < 0: raise ValueError('Seleccione un socio de la tabla.')
        sid = self.tabla.item(fila, 0).data(Qt.UserRole)
        DialogoHistorial(self.v, next(s for s in self.estado if s['id'] == sid)).exec()

    def pagar(self):
        s = self.socio_elegido()
        if s is None: raise ValueError('Elija un socio de la lista.' if self.estado else 'Registre o active un socio primero.')
        plan = next((p for p in self.lista_planes if p['id'] == self.grupo_planes.checkedId()), None)
        if plan is None: raise ValueError('Elija un plan.')
        hoy = ahora_local().date()
        texto = (f"{s['nombre']} {s['apellido']} · {plan['nombre']} · {fmt.moneda(self.importe.value())}\n\n"
                 f"Vigencia: {fmt.fecha_numerica(hoy)} al {fmt.fecha_numerica(fmt.ultimo_dia(un_mes(hoy)))} inclusive.")
        detalle = self.aviso_texto.text() if self.aviso.isVisible() else 'El nuevo período comienza hoy.'
        if preguntar(self, 'Confirmar pago', texto, 'Registrar pago', detalle):
            db.renovar(s['id'], plan['id'], self.importe.value())
            self.importe.setValue(0)
            self.refrescar(s['id'])
            QMessageBox.information(self, 'Pago registrado', 'Nueva membresía registrada por un mes calendario.')


# ============================================================ HORARIOS
class PaginaHorarios(Pagina):
    eyebrow = 'HORARIOS Y CUPOS'
    titulo = 'Horarios de atención y cupos'
    subtitulo = 'Configurá las franjas de apertura. Un día sin franjas está cerrado y el horario de cierre no se incluye.'

    def __init__(self, ventana):
        super().__init__(ventana)
        self.franjas = []
        self.k_estado = Kpi('Estado actual', 'puerta')
        self.k_horas = Kpi('Horas semanales', 'reloj', tema.AZUL)
        self.k_franjas = Kpi('Franjas configuradas', 'horarios', tema.LIMA)
        self.k_dias = Kpi('Días con atención', 'calendario', tema.AMBAR)
        self.lay.addLayout(fila_kpis(self.k_estado, self.k_horas, self.k_franjas, self.k_dias))
        semana = Tarjeta('Semana de atención', margen=20)
        alta = QHBoxLayout(); alta.setSpacing(10)
        self.dia = QComboBox(); self.dia.addItems(DIAS)
        self.desde = QTimeEdit(QTime(7, 0)); self.hasta = QTimeEdit(QTime(22, 0))
        for w in (self.desde, self.hasta):
            w.setDisplayFormat('HH:mm')
        for w in (etiqueta('Día', 'datoTitulo'), self.dia, etiqueta('Desde', 'datoTitulo'), self.desde,
                  etiqueta('Hasta', 'datoTitulo'), self.hasta):
            alta.addWidget(w)
        alta.addWidget(boton('Agregar franja', 'mas', 'primario', al_click=lambda: self.v.intentar(self.agregar)))
        alta.addStretch()
        semana.cuerpo.addLayout(alta)
        self.grilla = QHBoxLayout(); self.grilla.setSpacing(12)
        self.columnas = []
        for d in range(7):
            caja = QFrame(); caja.setObjectName('cajaDato'); caja.setMinimumHeight(220)
            col = QVBoxLayout(caja); col.setContentsMargins(12, 12, 12, 12); col.setSpacing(8)
            titulo = etiqueta(DIAS[d]); titulo.setStyleSheet('font-weight:700; font-size:15px;')
            col.addWidget(titulo)
            resumen = etiqueta('', 'tenue'); col.addWidget(resumen)
            franjas = QVBoxLayout(); franjas.setSpacing(6); col.addLayout(franjas); col.addStretch()
            self.columnas.append((caja, titulo, resumen, franjas))
            self.grilla.addWidget(caja, 1)
        semana.cuerpo.addLayout(self.grilla, 1)
        self.lay.addWidget(semana, 3)
        self.cupos = Tarjeta('Cupos por plan', margen=20)
        self.cupos.cuerpo.addWidget(etiqueta('Los cupos de 8, 12 y 20 son entrenamientos por mes de membresía; no limitan por día ni por semana. '
                                             'Todos los días permite un ingreso diario y Pase libre ingresos ilimitados (con 30 s de antirrebote).',
                                             'tenue', ajuste=True))
        self.cupos_lay = QGridLayout(); self.cupos_lay.setHorizontalSpacing(24); self.cupos_lay.setVerticalSpacing(10)
        self.cupos.cuerpo.addLayout(self.cupos_lay)
        self.lay.addWidget(self.cupos, 2)

    def refrescar(self):
        self.franjas = db.horarios()
        ahora = ahora_local()
        estado, detalle = fmt.estado_horario(self.franjas, ahora)
        self.k_estado.mostrar(estado, detalle)
        self.k_estado.circulo.cambiar('puerta', tema.LIMA if estado == 'Abierto' else tema.ROJO)
        self.k_horas.mostrar(f"{fmt.horas_semanales(self.franjas):g} h")
        self.k_franjas.mostrar(len(self.franjas))
        dias = fmt.franjas_por_dia(self.franjas)
        self.k_dias.mostrar(f"{sum(1 for v in dias.values() if v)} de 7")
        for d, (caja, titulo, resumen, lay) in enumerate(self.columnas):
            while lay.count():
                w = lay.takeAt(0).widget()
                if w: w.deleteLater()
            hoy = d == ahora.weekday()
            caja.setStyleSheet(f'QFrame#cajaDato {{ border: 1px solid {tema.LIMA}; background: rgba(195,245,60,0.05); }}' if hoy else '')
            titulo.setText(DIAS[d] + ('  · hoy' if hoy else ''))
            resumen.setText('Cerrado' if not dias[d] else f"{fmt.horas_semanales(dias[d]):g} h")
            for h in sorted(dias[d], key=lambda h: h['abre']):
                fila = QFrame(); fila.setStyleSheet('QFrame { background:#142133; border-radius:8px; }')
                fl = QHBoxLayout(fila); fl.setContentsMargins(10, 6, 4, 6)
                fl.addWidget(etiqueta(f"{h['abre']:%H:%M} – {h['cierra']:%H:%M}"), 1)
                quitar = QPushButton(); quitar.setObjectName('chipX'); quitar.setCursor(Qt.PointingHandCursor)
                quitar.setIcon(iconos.icono('x', tema.TENUE)); quitar.setToolTip('Quitar franja')
                quitar.clicked.connect(lambda _=False, h=h: self.v.intentar(lambda: self.quitar(h)))
                fl.addWidget(quitar)
                lay.addWidget(fila)
        while self.cupos_lay.count():
            w = self.cupos_lay.takeAt(0).widget()
            if w: w.deleteLater()
        planes = db.socios_por_plan()
        maximo = max([p['vigentes'] for p in planes] + [1])
        for i, p in enumerate(planes):
            nombre = etiqueta(p['nombre']); nombre.setStyleSheet('font-weight:600;')
            barra = BarraProgreso(8); barra.fijar(p['vigentes'] / maximo)
            self.cupos_lay.addWidget(nombre, i, 0)
            self.cupos_lay.addWidget(etiqueta(fmt.regla_plan(p['cupo'], p['una_vez_dia']), 'tenue'), i, 1)
            self.cupos_lay.addWidget(barra, i, 2)
            self.cupos_lay.addWidget(etiqueta(f"{p['vigentes']} {'socio vigente' if p['vigentes'] == 1 else 'socios vigentes'}"), i, 3)
        self.cupos_lay.setColumnStretch(2, 1)

    def agregar(self):
        db.agregar_horario(self.dia.currentIndex(), self.desde.time().toPython(), self.hasta.time().toPython())
        self.refrescar()

    def quitar(self, h):
        if preguntar(self, 'Quitar horario', f"¿Quitar la franja del {DIAS[h['dia']].lower()} "
                                             f"{h['abre']:%H:%M} – {h['cierra']:%H:%M}?", 'Quitar'):
            db.quitar_horario(h['id'])
            self.refrescar()


# ============================================================ INFORMES
class PaginaInformes(Pagina):
    eyebrow = 'INFORMES Y ESTADÍSTICAS'
    titulo = 'Informes y estadísticas'
    subtitulo = 'Analizá los ingresos por período y socio. La exportación incluye el estado actual de las membresías.'

    def __init__(self, ventana):
        super().__init__(ventana)
        self.filas = []
        filtros = Tarjeta(margen=18)
        fila = QHBoxLayout(); fila.setSpacing(10)
        hoy = QDate.currentDate()
        self.desde = QDateEdit(hoy.addDays(-29)); self.hasta = QDateEdit(hoy)
        for w in (self.desde, self.hasta):
            w.setCalendarPopup(True); w.setDisplayFormat('dd/MM/yyyy')
        self.socio = QComboBox(); self.socio.addItem('Todos los socios', None); self.socio.setMinimumWidth(220)
        for w in (etiqueta('Desde', 'datoTitulo'), self.desde, etiqueta('Hasta', 'datoTitulo'), self.hasta):
            fila.addWidget(w)
        fila.addWidget(self.socio, 1)
        fila.addWidget(boton('Consultar', 'buscar', 'primario', al_click=lambda: self.v.intentar(self.refrescar)))
        filtros.cuerpo.addLayout(fila)
        fila2 = QHBoxLayout(); fila2.setSpacing(10)
        self.rangos, chips_lay = chips(['Hoy', '7 días', '30 días', 'Este mes'], self.rango_rapido)
        self.rangos.button(2).setChecked(True)
        fila2.addWidget(etiqueta('Período rápido', 'datoTitulo')); fila2.addLayout(chips_lay); fila2.addStretch()
        fila2.addWidget(etiqueta('Exportar informe', 'datoTitulo'))
        fila2.addWidget(boton('Excel', 'excel', al_click=lambda: self.v.intentar(lambda: self.exportar('xlsx'))))
        fila2.addWidget(boton('PDF', 'pdf', al_click=lambda: self.v.intentar(lambda: self.exportar('pdf'))))
        filtros.cuerpo.addLayout(fila2)
        self.lay.addWidget(filtros)
        self.k_total = Kpi('Ingresos del período', 'puerta')
        self.k_socios = Kpi('Socios distintos', 'socios', tema.AZUL)
        self.k_promedio = Kpi('Promedio diario', 'tendencia', tema.LIMA)
        self.k_pico = Kpi('Día con más ingresos', 'calendario', tema.AMBAR)
        self.lay.addLayout(fila_kpis(self.k_total, self.k_socios, self.k_promedio, self.k_pico))
        graficos = QHBoxLayout(); graficos.setSpacing(18)
        dias = Tarjeta('Ingresos por día', margen=20); self.g_dias = Barras(230); dias.cuerpo.addWidget(self.g_dias, 1)
        graficos.addWidget(dias, 3)
        planes = Tarjeta('Ingresos por plan', margen=20)
        self.planes_lay = QGridLayout(); self.planes_lay.setVerticalSpacing(12)
        planes.cuerpo.addLayout(self.planes_lay); planes.cuerpo.addStretch()
        graficos.addWidget(planes, 2)
        self.lay.addLayout(graficos)
        inferior = QHBoxLayout(); inferior.setSpacing(18)
        horas = Tarjeta('Afluencia por hora', margen=20); self.g_horas = Barras(230); horas.cuerpo.addWidget(self.g_horas, 1)
        inferior.addWidget(horas, 2)
        detalle = Tarjeta('Detalle de ingresos', margen=20)
        self.tabla = tabla(['Fecha', 'Hora', 'Socio', 'DNI', 'Plan'], estirar=2)
        self.tabla.setMinimumHeight(300)
        detalle.cuerpo.addWidget(self.tabla)
        inferior.addWidget(detalle, 3)
        self.lay.addLayout(inferior)

    def rango_rapido(self):
        hoy = QDate.currentDate()
        desde = {0: hoy, 1: hoy.addDays(-6), 2: hoy.addDays(-29), 3: QDate(hoy.year(), hoy.month(), 1)}[self.rangos.checkedId()]
        self.desde.setDate(desde); self.hasta.setDate(hoy)
        self.v.intentar(self.refrescar)

    def refrescar(self):
        elegido = self.socio.currentData()
        self.socio.blockSignals(True); self.socio.clear(); self.socio.addItem('Todos los socios', None)
        for s in db.listar_socios():
            self.socio.addItem(f"{s['apellido']}, {s['nombre']} · {fmt.dni(s['dni'])}", s['id'])
        self.socio.setCurrentIndex(max(0, self.socio.findData(elegido))); self.socio.blockSignals(False)
        desde, hasta = self.desde.date().toPython(), self.hasta.date().toPython()
        self.filas = db.informe(desde, hasta, self.socio.currentData())
        e = fmt.estadisticas_ingresos(self.filas, desde, hasta)
        self.k_total.mostrar(e['total'], f"{(hasta - desde).days + 1} días analizados")
        self.k_socios.mostrar(e['socios'])
        self.k_promedio.mostrar(f"{e['promedio']:.1f}".replace('.', ','), 'ingresos por día')
        self.k_pico.mostrar(f"{e['pico'][0]:%d/%m}" if e['pico'] else '—',
                            f"{e['pico'][1]} ingresos · {DIAS[e['pico'][0].weekday()]}" if e['pico'] else 'Sin ingresos')
        self.g_dias.fijar([(f'{d:%d/%m}', n) for d, n in e['serie']])
        horas = e['por_hora']
        con_datos = [h for h, n in enumerate(horas) if n] or [7, 22]
        rango = range(min(con_datos), max(con_datos) + 1)
        self.g_horas.fijar([(f'{h:02d}h', horas[h]) for h in rango])
        while self.planes_lay.count():
            w = self.planes_lay.takeAt(0).widget()
            if w: w.deleteLater()
        if not e['por_plan']:
            self.planes_lay.addWidget(etiqueta('No hay ingresos en el período elegido.', 'vacio'), 0, 0)
        for i, (plan, n) in enumerate(e['por_plan']):
            barra = BarraProgreso(8); barra.fijar(n / e['total'])
            self.planes_lay.addWidget(etiqueta(plan), i, 0)
            self.planes_lay.addWidget(barra, i, 1)
            self.planes_lay.addWidget(etiqueta(f"{n}  ({round(n * 100 / e['total'])}%)", 'tenue'), i, 2)
        self.planes_lay.setColumnStretch(1, 1)
        t = self.tabla; t.clearContents(); t.setRowCount(len(self.filas))
        for i, r in enumerate(self.filas):
            for j, v in enumerate([f"{r['instante']:%d/%m/%Y}", f"{r['instante']:%H:%M:%S}",
                                   f"{r['apellido']}, {r['nombre']}", fmt.dni(r['dni']), r['plan']]):
                t.setItem(i, j, item(v))

    def exportar(self, extension):
        self.refrescar()
        ruta, _ = QFileDialog.getSaveFileName(self, 'Guardar informe', 'informe_gimnasio.' + extension, 'Archivos (*.' + extension + ')')
        if not ruta: return
        if not ruta.lower().endswith('.' + extension): ruta += '.' + extension
        membresias = db.estado_membresias(); sid = self.socio.currentData()
        if sid is not None: membresias = [m for m in membresias if m['id'] == sid]
        exportar(ruta, self.filas, membresias, self.desde.date().toPython(), self.hasta.date().toPython())
        QMessageBox.information(self, 'Informe guardado', ruta)
