import os
import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import patch, Mock
from src.domain.reglas import evaluar, un_mes, ZONA, Decision

class ReglasTest(unittest.TestCase):
    def setUp(self):
        self.ahora=datetime(2026,10,20,10,tzinfo=ZONA)
        self.socio={'activo':True}
        self.m={'inicio':date(2026,10,20),'vence':date(2026,11,20), 'cerrada_en':None,'cupo':8,'una_vez_dia':False}
        self.h=[(1,time(7),time(12)),(1,time(16),time(22))]

    def evaluar(self,usados=0,hoy=0,ultimo=None):
        return evaluar(self.socio,self.m,usados,hoy,ultimo,self.h,self.ahora)

    def test_mes_calendario_y_fin_de_mes(self):
        for entrada,salida in [(date(2026,10,20),date(2026,11,20)),(date(2026,1,31),date(2026,2,28)),
                              (date(2028,1,31),date(2028,2,29)),(date(2026,12,30),date(2027,1,30)),
                              (date(2026,3,31),date(2026,4,30))]:
            self.assertEqual(un_mes(entrada),salida)

    def test_limites_vigencia(self):
        self.assertTrue(self.evaluar().permitido)
        self.m['inicio']=date(2026,10,21); self.assertFalse(self.evaluar().permitido)
        self.m['inicio']=date(2026,9,20); self.m['vence']=date(2026,10,20)
        self.assertFalse(self.evaluar().permitido)

    def test_cupos_8_12_20(self):
        for cupo in [8,12,20]:
            self.m['cupo']=cupo
            self.assertEqual(self.evaluar(cupo-1).restantes,1)
            self.assertFalse(self.evaluar(cupo).permitido)

    def test_cupo_no_es_limite_semanal_o_diario(self):
        self.assertTrue(self.evaluar(usados=4,hoy=4).permitido)

    def test_todos_los_dias_y_pase_libre(self):
        self.m.update(cupo=None,una_vez_dia=True)
        self.assertTrue(self.evaluar().permitido)
        self.assertFalse(self.evaluar(hoy=1).permitido)
        self.m['una_vez_dia']=False
        self.assertTrue(self.evaluar(usados=100,hoy=5).permitido)

    def test_antirrebote(self):
        self.assertFalse(self.evaluar(ultimo=self.ahora-timedelta(seconds=29)).permitido)
        self.assertTrue(self.evaluar(ultimo=self.ahora-timedelta(seconds=30)).permitido)

    def test_turnos_y_limites_horarios(self):
        for hora,esperado in [(7,True),(12,False),(15,False),(16,True),(22,False)]:
            self.ahora=self.ahora.replace(hour=hora)
            self.assertEqual(self.evaluar().permitido,esperado)
        self.h=[]; self.assertFalse(self.evaluar().permitido)

    def test_socio_invalido_o_sin_membresia(self):
        self.socio=None; self.assertFalse(self.evaluar().permitido)
        self.socio={'activo':False}; self.assertFalse(self.evaluar().permitido)
        self.socio={'activo':True}; self.m=None; self.assertFalse(self.evaluar().permitido)

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from src.ui.gimnasio import VentanaGimnasio
APP=QApplication.instance() or QApplication([])

class ConfirmacionTest(unittest.TestCase):
    def setUp(self):
        self.v=VentanaGimnasio()
        self.estado={'socio':{'nombre':'Ana','apellido':'Prueba','dni':'12345678'},
                     'membresia':{'id':5,'plan':'2 veces por semana','vence':date(2026,11,20)},
                     'decision':Decision(True,'Ingreso habilitado.',8)}

    def tearDown(self):
        self.v.close(); APP.processEvents()

    def test_cancelar_no_persiste(self):
        with patch('src.ui.gimnasio.db.consultar_acceso',return_value=self.estado), \
             patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar, \
             patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel):
            self.v.proponer(1)
        guardar.assert_not_called(); self.assertFalse(self.v.modal)

    def test_ok_persiste_una_vez_y_pausa_inferencia(self):
        def modal(*args):
            self.assertTrue(self.v.modal)
            self.assertEqual(args[3],QMessageBox.Ok|QMessageBox.Cancel)
            return QMessageBox.Ok
        with patch('src.ui.gimnasio.db.consultar_acceso',return_value=self.estado), \
             patch('src.ui.gimnasio.db.confirmar_ingreso',return_value=(True,'Guardado')) as guardar, \
             patch.object(QMessageBox,'question',side_effect=modal):
            self.v.proponer(1)
        guardar.assert_called_once(); self.assertFalse(self.v.modal)

    def test_modal_no_envia_reconocimientos_y_mantiene_camara(self):
        import numpy as np
        self.v.modal=True; self.v.listo=True
        self.v.camera=Mock(); self.v.camera.leer_frame.return_value=np.zeros((200,200,3),dtype=np.uint8)
        with patch.object(self.v,'enviar') as enviar:
            self.v.frame()
        enviar.assert_not_called(); self.v.camera.cerrar.assert_not_called()

    def test_rechazo_no_muestra_confirmacion(self):
        self.estado['decision']=Decision(False,'Cupo agotado')
        with patch('src.ui.gimnasio.db.consultar_acceso',return_value=self.estado), \
             patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar, \
             patch.object(QMessageBox,'question') as modal:
            self.v.proponer(1)
        guardar.assert_not_called(); modal.assert_not_called()

    def test_respuesta_de_sesion_anterior_se_descarta(self):
        self.v.sesion=2
        with patch.object(self.v,'proponer') as proponer:
            self.v.resultado({'tipo':'reconocer','sesion':1,'resultado':{'estado':'reconocido','socio_id':1}})
        proponer.assert_not_called()

    def test_error_al_guardar_reanuda_reconocimiento(self):
        with patch('src.ui.gimnasio.db.consultar_acceso',return_value=self.estado), \
             patch('src.ui.gimnasio.db.confirmar_ingreso',side_effect=RuntimeError('sin conexión')), \
             patch.object(QMessageBox,'question',return_value=QMessageBox.Ok):
            with self.assertRaises(RuntimeError): self.v.proponer(1)
        self.assertFalse(self.v.modal)

if __name__=='__main__': unittest.main()
