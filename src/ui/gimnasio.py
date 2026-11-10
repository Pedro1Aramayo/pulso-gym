"""Recepción de PULSO GYM. Reconocimiento sin escrituras hasta confirmar."""
import os
from time import monotonic
from threading import Event
from uuid import uuid4
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QDate, QTime
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QMainWindow,QWidget,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,
    QFormLayout,QLineEdit,QComboBox,QStackedWidget,QMessageBox,QFileDialog,QTableWidget,
    QTableWidgetItem,QHeaderView,QDateEdit,QTimeEdit,QDoubleSpinBox,QDialog,QDialogButtonBox)
from src.database import gimnasio as db
from src.domain.reglas import ahora_local
from src.camera.camera_manager import CameraManager
from src.ui.captura_foto import CapturaFotoDialog
from src.recognition.trabajador_reconocimiento import TrabajadorReconocimiento
from src.reports.gimnasio import exportar

DIAS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
ESTILO = """
QWidget {background:#111c29; color:#e8eef5; font-family:'Segoe UI'; font-size:14px;}
QLabel#marca {color:#b8f34a; font-size:27px; font-weight:800;}
QLabel#titulo {font-size:25px; font-weight:700;}
QLabel#ayuda {color:#aebfd2;}
QPushButton {background:#263a50; border:0; border-radius:6px; padding:11px 18px;}
QPushButton:hover {background:#36536e;}
QPushButton:disabled {color:#718096; background:#1b2939;}
QPushButton#primario {background:#b8f34a; color:#13200a; font-weight:700;}
QLineEdit,QComboBox,QDateEdit,QTimeEdit,QDoubleSpinBox {background:#1b2b3e; padding:8px; border:1px solid #3b5169; border-radius:4px;}
QTableWidget {background:#162437; gridline-color:#30455d; alternate-background-color:#203248;}
QHeaderView::section {background:#263a50; padding:8px; border:0; color:#b8f34a;}
"""

def boton(texto, funcion, primario=False):
    b=QPushButton(texto)
    if primario: b.setObjectName('primario')
    b.clicked.connect(funcion)
    return b

def tabla(cabeceras):
    t=QTableWidget(0,len(cabeceras)); t.setHorizontalHeaderLabels(cabeceras)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setSelectionMode(QTableWidget.SingleSelection)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t

def llenar(t, filas):
    t.setRowCount(len(filas))
    for i,f in enumerate(filas):
        for j,v in enumerate(f):
            t.setItem(i,j,QTableWidgetItem('—' if v is None else str(v)))

class VentanaGimnasio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PULSO GYM | Acceso facial')
        self.resize(1200,800); self.setMinimumSize(1000,700)
        self.setStyleSheet(ESTILO)
        self.camera=CameraManager(int(os.getenv('CAMERA_INDEX','0')))
        self.motor=TrabajadorReconocimiento()
        self.motor.terminado.connect(self.resultado)
        self.motor.progreso.connect(lambda s:self.estado.setText(s))
        self.motor.detenido.connect(self.finalizar_cierre)
        self.detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
        self.ocupado=False; self.listo=False; self.modal=False; self.cerrando=False
        self.sesion=0; self.cancelacion=Event(); self.proximo=0; self.ultimo_socio={}
        contenedor=QWidget(); self.setCentralWidget(contenedor); base=QHBoxLayout(contenedor)
        lateral=QVBoxLayout(); marca=QLabel('PULSO\nGYM'); marca.setObjectName('marca')
        lateral.addWidget(marca); lateral.addWidget(QLabel('RECEPCIÓN · ACCESO FACIAL'))
        self.paginas=QStackedWidget()
        for i,n in enumerate(['01  Acceso facial','02  Socios','03  Membresías y pagos','04  Horarios','05  Informes']):
            lateral.addWidget(boton(n,lambda checked=False,idx=i:self.ir(idx)))
        lateral.addStretch(); lateral.addWidget(QLabel('Trabajo final · Contexto B'))
        base.addLayout(lateral,1); base.addWidget(self.paginas,5)
        self.pagina_acceso(); self.pagina_socios(); self.pagina_membresias(); self.pagina_horarios(); self.pagina_informes()
        self.timer=QTimer(self); self.timer.timeout.connect(self.frame); self.timer.start(40)

    def pagina(self,titulo,ayuda):
        w=QWidget(); l=QVBoxLayout(w)
        h=QLabel(titulo); h.setObjectName('titulo'); l.addWidget(h)
        a=QLabel(ayuda); a.setWordWrap(True); a.setObjectName('ayuda'); l.addWidget(a)
        self.paginas.addWidget(w)
        return l

    def intentar(self,funcion):
        try: return funcion()
        except Exception as e:
            print(type(e).__name__,str(e))
            mensaje=str(e) if isinstance(e,ValueError) else 'No se pudo completar la operación. Revise la conexión y los datos (DNI único). Detalle en la terminal.'
            QMessageBox.warning(self,'Operación no completada',mensaje)
            return None

    def ir(self,indice):
        self.sesion+=1; self.cancelacion.set(); self.paginas.setCurrentIndex(indice)
        if indice==1: self.intentar(self.refrescar_socios)
        if indice==2: self.intentar(self.refrescar_membresias)
        if indice==3: self.intentar(self.refrescar_horarios)
        if indice==4: self.intentar(self.consultar_informes)

    def pagina_acceso(self):
        l=self.pagina('Tu entrenamiento empieza acá','Mirá a la cámara. Revisá tu nombre y confirmá el ingreso con OK.')
        self.video=QLabel('Cámara apagada'); self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(620,390); self.video.setStyleSheet('background:#080f19; border:2px solid #36536e; border-radius:12px;')
        l.addWidget(self.video,1)
        self.estado=QLabel('Abrí la cámara para comenzar.'); self.estado.setWordWrap(True); l.addWidget(self.estado)
        fila=QHBoxLayout(); self.abrir=boton('Abrir / recargar cámara',self.iniciar,True)
        fila.addWidget(self.abrir); fila.addWidget(boton('Cerrar cámara',self.cerrar_camara)); l.addLayout(fila)

    def iniciar(self):
        if self.ocupado: return
        if not self.camera.abrir():
            self.camera.cerrar(); self.estado.setText('No se pudo abrir la webcam. Revise permisos y CAMERA_INDEX.'); return
        self.sesion+=1; self.listo=False; self.ultimo_socio.clear()
        self.estado.setText('Preparando FaceNet512 y fotografías de socios…')
        self.enviar('preparar')

    def enviar(self,tipo,frame=None,rostros=None):
        self.ocupado=True; self.abrir.setEnabled(False); self.cancelacion=Event()
        self.motor.ejecutar(dict(tipo=tipo,sesion=self.sesion,cancelacion=self.cancelacion,
                                frame=frame,rostros=rostros))

    def cerrar_camara(self):
        self.sesion+=1; self.cancelacion.set(); self.listo=False
        self.camera.cerrar(); self.video.clear(); self.video.setText('Cámara apagada')
        self.estado.setText('Reconocimiento detenido.')

    def frame(self):
        if self.cerrando or not self.camera.esta_abierta() or self.paginas.currentIndex()!=0: return
        imagen=self.camera.leer_frame()
        if imagen is None:
            self.sesion+=1; self.cancelacion.set()
            if not self.modal: self.estado.setText('No se pudo leer la cámara.')
            return
        imagen=cv2.flip(imagen,1)
        # Durante el modal sólo se actualiza el video; no se lanzan nuevas inferencias.
        if not self.modal:
            escala=min(1,640/max(imagen.shape[:2]))
            pequena=cv2.resize(imagen,None,fx=escala,fy=escala)
            caras=self.detector.detectMultiScale(cv2.cvtColor(pequena,cv2.COLOR_BGR2GRAY),1.1,5,minSize=(60,60))
            if len(caras): caras=(caras/escala).round().astype(int)
            if len(caras)!=1:
                self.sesion+=1; self.cancelacion.set()
                if self.listo: self.estado.setText('Ubique un solo rostro.' if len(caras)>1 else 'Mirá a la cámara.')
            elif self.listo and not self.ocupado and monotonic()>=self.proximo:
                self.enviar('reconocer',imagen.copy(),caras.copy())
            for x,y,w,h in caras: cv2.rectangle(imagen,(x,y),(x+w,y+h),(74,243,184),2)
        rgb=cv2.cvtColor(imagen,cv2.COLOR_BGR2RGB); h,w=rgb.shape[:2]
        q=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format_RGB888).copy()
        self.video.setPixmap(QPixmap.fromImage(q).scaled(self.video.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def resultado(self,r):
        self.ocupado=False; self.abrir.setEnabled(True); self.proximo=monotonic()+2
        if self.cerrando: return
        if r['tipo']=='preparar':
            self.listo=not r.get('error') and r.get('cantidad',0)>0 and self.camera.esta_abierta()
            self.estado.setText('Listo: mirá a la cámara.' if self.listo else r.get('mensaje','No hay fotos válidas. Registre un socio y recargue la cámara.'))
            return
        if r['sesion']!=self.sesion or not self.camera.esta_abierta() or self.paginas.currentIndex()!=0: return
        if r.get('error'):
            if r.get('reiniciar'): self.listo=False
            self.estado.setText(r.get('mensaje','Error facial. Vuelva a abrir la cámara.')); return
        identidad=r['resultado']
        if identidad['estado']!='reconocido':
            self.estado.setText('Identidad no confirmada. No se registró ningún ingreso.'); return
        sid=identidad['socio_id']
        if monotonic()<self.ultimo_socio.get(sid,0): return
        self.ultimo_socio[sid]=monotonic()+10
        self.intentar(lambda:self.proponer(sid))

    def proponer(self,sid):
        # Sin escrituras en este tramo: Cancelar conserva la base intacta.
        estado=db.consultar_acceso(sid); d=estado['decision']; socio=estado['socio']
        nombre=f"{socio['nombre']} {socio['apellido']}" if socio else 'Socio no válido'
        if not d.permitido:
            self.estado.setText(f'{nombre}: {d.motivo}'); return
        m=estado['membresia']; self.modal=True
        try:
            texto=(f"{nombre} · DNI {socio['dni']}\n\nRegistrar INGRESO al gimnasio\n"
                   f"Plan: {m['plan']}\nVence: {m['vence'].strftime('%d/%m/%Y')} (día no incluido)\n")
            if d.restantes is not None: texto+=f'Entrenamientos disponibles antes de ingresar: {d.restantes}\n'
            respuesta=QMessageBox.question(self,'Confirmar ingreso',texto,QMessageBox.Ok|QMessageBox.Cancel,QMessageBox.Cancel)
            if respuesta==QMessageBox.Ok:
                ok,mensaje=db.confirmar_ingreso(sid,m['id'],uuid4())
                self.estado.setText(f'{nombre}: {mensaje}')
            else:
                self.estado.setText(f'{nombre}: cancelado. No se registró el ingreso.')
        finally:
            self.modal=False; self.proximo=monotonic()+3; self.ultimo_socio[sid]=monotonic()+10

    def pagina_socios(self):
        l=self.pagina('Socios','Alta con tres fotografías. Use una sola persona, buena iluminación y un giro leve para las vistas laterales.')
        l.addWidget(boton('Registrar nuevo socio',lambda:self.intentar(self.nuevo_socio),True))
        self.socios_tabla=tabla(['ID','Apellido','Nombre','DNI','Estado']); l.addWidget(self.socios_tabla)
        l.addWidget(boton('Activar / desactivar seleccionado',lambda:self.intentar(self.alternar_socio)))

    def refrescar_socios(self):
        self.socios=db.listar_socios()
        llenar(self.socios_tabla,[(s['id'],s['apellido'],s['nombre'],s['dni'],'Activo' if s['activo'] else 'Inactivo') for s in self.socios])

    def alternar_socio(self):
        i=self.socios_tabla.currentRow()
        if i<0: raise ValueError('Seleccione un socio.')
        s=self.socios[i]
        if QMessageBox.question(self,'Estado del socio',f"¿Cambiar el estado de {s['nombre']} {s['apellido']}?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            db.cambiar_estado(s['id'],not s['activo']); self.refrescar_socios()

    def nuevo_socio(self):
        dialogo=QDialog(self); dialogo.setWindowTitle('Alta de socio'); dialogo.resize(620,560)
        l=QVBoxLayout(dialogo); f=QFormLayout(); campos={}; fotos={}
        for clave,etiqueta in [('nombre','Nombre *'),('apellido','Apellido *'),('dni','DNI *'),('celular','Celular'),('correo_electronico','Correo')]:
            campos[clave]=QLineEdit(); f.addRow(etiqueta,campos[clave])
        l.addLayout(f)
        ayuda=QLabel('Fotografías: se verificará que cada imagen contenga exactamente un rostro.'); ayuda.setWordWrap(True); l.addWidget(ayuda)
        def recibir(angulo,datos,label):
            img=cv2.imdecode(np.frombuffer(datos,np.uint8),cv2.IMREAD_COLOR)
            if img is None: raise ValueError('Imagen ilegible.')
            escala=min(1,1000/max(img.shape[:2])); img=cv2.resize(img,None,fx=escala,fy=escala)
            caras=self.detector.detectMultiScale(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),1.1,5,minSize=(80,80))
            if len(caras)!=1: raise ValueError('La foto debe mostrar exactamente un rostro. Use un giro leve, no un perfil completo.')
            ok,png=cv2.imencode('.png',img)
            if not ok: raise ValueError('No se pudo convertir la fotografía.')
            fotos[angulo]=png.tobytes(); label.setText(angulo.capitalize()+' · lista')
        def cargar(a,label):
            ruta,_=QFileDialog.getOpenFileName(dialogo,'Fotografía','','Imágenes (*.jpg *.jpeg *.png *.bmp)')
            if ruta:
                from pathlib import Path
                if Path(ruta).stat().st_size>15_000_000: raise ValueError('Use una imagen menor a 15 MB.')
                recibir(a,Path(ruta).read_bytes(),label)
        def capturar(a,label):
            captura=CapturaFotoDialog(dialogo,self.camera)
            captura.foto_capturada.connect(lambda datos:self.intentar(lambda:recibir(a,datos,label)))
            captura.exec()
        for angulo in ['frontal','izquierdo','derecho']:
            fila=QHBoxLayout(); etiqueta=QLabel(angulo.capitalize()+' · pendiente'); fila.addWidget(etiqueta)
            fila.addWidget(boton('Archivo',lambda checked=False,a=angulo,e=etiqueta:self.intentar(lambda:cargar(a,e))))
            fila.addWidget(boton('Cámara',lambda checked=False,a=angulo,e=etiqueta:self.intentar(lambda:capturar(a,e))))
            l.addLayout(fila)
        botones=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Save).setText('Guardar socio'); botones.button(QDialogButtonBox.Cancel).setText('Cancelar')
        def guardar():
            db.registrar_socio({k:v.text().strip() for k,v in campos.items()},fotos)
            self.listo=False; dialogo.accept(); self.refrescar_socios()
            QMessageBox.information(self,'Socio registrado','Socio guardado. Registre su pago en Membresías y recargue la cámara para reconocerlo.')
        botones.accepted.connect(lambda:self.intentar(guardar)); botones.rejected.connect(dialogo.reject)
        l.addWidget(botones); dialogo.exec()

    def pagina_membresias(self):
        l=self.pagina('Membresías y pagos','Cada pago inicia un mes desde hoy. Renovar anticipadamente reemplaza el período anterior y descarta el saldo sin usar.')
        f=QFormLayout(); self.socio_pago=QComboBox(); self.plan_pago=QComboBox()
        self.importe=QDoubleSpinBox(); self.importe.setRange(0,999999999); self.importe.setPrefix('$ ')
        f.addRow('Socio',self.socio_pago); f.addRow('Plan',self.plan_pago); f.addRow('Importe abonado',self.importe)
        l.addLayout(f); l.addWidget(boton('Registrar pago / renovar',lambda:self.intentar(self.pagar),True))
        self.membresias_tabla=tabla(['Socio','DNI','Plan','Inicio','Vence','Usados','Restantes','Estado']); l.addWidget(self.membresias_tabla)

    def refrescar_membresias(self):
        self.socio_pago.clear(); self.plan_pago.clear()
        for s in db.listar_socios():
            if s['activo']: self.socio_pago.addItem(f"{s['apellido']}, {s['nombre']} · {s['dni']}",s['id'])
        for p in db.planes(): self.plan_pago.addItem(p['nombre'],p['id'])
        llenar(self.membresias_tabla,[(f"{s['apellido']}, {s['nombre']}",s['dni'],s['plan'],s['inicio'],s['vence'],s['usados'],
                                     s['restantes'] if s['cupo'] else ('Sin cupo' if s['plan'] else '—'),s['estado']) for s in db.estado_membresias()])

    def pagar(self):
        sid=self.socio_pago.currentData()
        if sid is None: raise ValueError('Registre o active un socio primero.')
        if QMessageBox.question(self,'Confirmar pago',f"{self.socio_pago.currentText()}\n{self.plan_pago.currentText()} · $ {self.importe.value():.2f}\n\nEl nuevo período comienza hoy. Se pierde cualquier saldo anterior. ¿Continuar?",QMessageBox.Ok|QMessageBox.Cancel,QMessageBox.Cancel)==QMessageBox.Ok:
            db.renovar(sid,self.plan_pago.currentData(),self.importe.value()); self.refrescar_membresias()
            QMessageBox.information(self,'Pago registrado','Nueva membresía registrada por un mes calendario.')

    def pagina_horarios(self):
        l=self.pagina('Horarios de atención','Agregue varias franjas por día para turnos separados. Un día sin franjas se considera cerrado. El cierre no está incluido.')
        fila=QHBoxLayout(); self.dia=QComboBox(); self.dia.addItems(DIAS)
        self.desde_hora=QTimeEdit(QTime(7,0)); self.hasta_hora=QTimeEdit(QTime(22,0))
        self.desde_hora.setDisplayFormat('HH:mm'); self.hasta_hora.setDisplayFormat('HH:mm')
        for w in [self.dia,QLabel('Desde'),self.desde_hora,QLabel('Hasta'),self.hasta_hora]: fila.addWidget(w)
        fila.addWidget(boton('Agregar',lambda:self.intentar(self.agregar_franja),True)); l.addLayout(fila)
        self.horarios_tabla=tabla(['ID','Día','Apertura','Cierre']); l.addWidget(self.horarios_tabla)
        l.addWidget(boton('Quitar franja seleccionada',lambda:self.intentar(self.quitar_franja)))

    def refrescar_horarios(self):
        self.franjas=db.horarios()
        llenar(self.horarios_tabla,[(h['id'],DIAS[h['dia']],h['abre'],h['cierra']) for h in self.franjas])

    def agregar_franja(self):
        db.agregar_horario(self.dia.currentIndex(),self.desde_hora.time().toPython(),self.hasta_hora.time().toPython()); self.refrescar_horarios()

    def quitar_franja(self):
        i=self.horarios_tabla.currentRow()
        if i<0: raise ValueError('Seleccione una franja.')
        if QMessageBox.question(self,'Quitar horario','¿Quitar la franja seleccionada?',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            db.quitar_horario(self.franjas[i]['id']); self.refrescar_horarios()

    def pagina_informes(self):
        l=self.pagina('Ingresos e informes','Consulte ingresos por fecha y socio. La exportación incluye el estado actual de las membresías.')
        fila=QHBoxLayout(); self.desde_fecha=QDateEdit(QDate.currentDate().addDays(-30)); self.hasta_fecha=QDateEdit(QDate.currentDate())
        for w in [self.desde_fecha,self.hasta_fecha]: w.setCalendarPopup(True); w.setDisplayFormat('dd/MM/yyyy')
        self.filtro_socio=QComboBox(); self.filtro_socio.addItem('Todos los socios',None)
        for w in [self.desde_fecha,self.hasta_fecha,self.filtro_socio]: fila.addWidget(w)
        fila.addWidget(boton('Consultar',lambda:self.intentar(self.consultar_informes),True)); l.addLayout(fila)
        self.informes_tabla=tabla(['Fecha / hora','Socio','DNI','Plan']); l.addWidget(self.informes_tabla)
        l.addWidget(boton('Exportar Excel',lambda:self.intentar(lambda:self.exportar_informes('xlsx'))))
        l.addWidget(boton('Exportar PDF',lambda:self.intentar(lambda:self.exportar_informes('pdf'))))

    def consultar_informes(self):
        elegido=self.filtro_socio.currentData(); self.filtro_socio.clear(); self.filtro_socio.addItem('Todos los socios',None)
        for s in db.listar_socios(): self.filtro_socio.addItem(f"{s['apellido']}, {s['nombre']} · {s['dni']}",s['id'])
        indice=self.filtro_socio.findData(elegido); self.filtro_socio.setCurrentIndex(max(0,indice))
        self.filas_informe=db.informe(self.desde_fecha.date().toPython(),self.hasta_fecha.date().toPython(),self.filtro_socio.currentData())
        llenar(self.informes_tabla,[(r['instante'].strftime('%d/%m/%Y %H:%M:%S'),f"{r['apellido']}, {r['nombre']}",r['dni'],r['plan']) for r in self.filas_informe])

    def exportar_informes(self,extension):
        self.consultar_informes()
        ruta,_=QFileDialog.getSaveFileName(self,'Guardar informe','informe_gimnasio.'+extension,'Archivos (*.'+extension+')')
        if not ruta: return
        if not ruta.lower().endswith('.'+extension): ruta+='.'+extension
        membresias=db.estado_membresias(); sid=self.filtro_socio.currentData()
        if sid is not None: membresias=[m for m in membresias if m['id']==sid]
        exportar(ruta,self.filas_informe,membresias,self.desde_fecha.date().toPython(),self.hasta_fecha.date().toPython())
        QMessageBox.information(self,'Informe guardado',ruta)

    def closeEvent(self,event):
        if not self.cerrando:
            self.cerrando=True; self.timer.stop(); self.cerrar_camara()
            self.motor.detener()
        if self.motor.proceso is not None and self.motor.proceso.state()!=self.motor.proceso.NotRunning:
            event.ignore()
        else: event.accept()

    def finalizar_cierre(self):
        if self.cerrando: QTimer.singleShot(0,self.close)
