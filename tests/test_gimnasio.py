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
        self.estado={'socio':{'id':1,'nombre':'Ana','apellido':'Prueba','dni':'12345678','activo':True},
                     'membresia':{'id':5,'plan':'2 veces por semana','vence':date(2026,11,20),'cupo':8,'una_vez_dia':False},
                     'decision':Decision(True,'Ingreso habilitado.',8)}
        self.foto=patch.object(self.v,'foto',return_value=None); self.foto.start()

    def tearDown(self):
        self.foto.stop(); self.v.close(); APP.processEvents()

    def proponer(self):
        with patch('src.ui.gimnasio.db.consultar_acceso',return_value=self.estado):
            self.v.proponer(1)

    def test_reconocer_solo_muestra_panel_sin_persistir(self):
        with patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar:
            self.proponer()
        guardar.assert_not_called(); self.assertTrue(self.v.modal)
        self.assertTrue(self.v.acceso.confirmar.isEnabled()); self.assertTrue(self.v.acceso.cancelar.isEnabled())
        self.assertEqual(self.v.acceso.nombre.text(),'Ana Prueba')
        self.assertEqual(self.v.acceso.restantes.text(),'8 de 8')
        self.assertEqual(self.v.acceso.vence.text(),'20 nov. 2026')

    def test_cancelar_no_persiste(self):
        self.proponer()
        with patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar:
            self.v.acceso.cancelar.click()
        guardar.assert_not_called(); self.assertFalse(self.v.modal)
        self.assertFalse(self.v.acceso.confirmar.isEnabled())

    def test_confirmar_persiste_una_vez_con_la_misma_solicitud(self):
        self.proponer()
        solicitud=self.v.pendiente['solicitud']
        with patch('src.ui.gimnasio.db.confirmar_ingreso',return_value=(True,'Guardado')) as guardar, \
             patch.object(self.v.acceso,'refrescar'):
            self.v.confirmar(); self.v.confirmar(); self.v.acceso.confirmar.click()
        guardar.assert_called_once_with(1,5,solicitud); self.assertFalse(self.v.modal)
        self.assertEqual(self.v.acceso.restantes.text(),'7 de 8')

    def test_expiracion_cancela_sin_persistir(self):
        self.proponer()
        with patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar:
            self.v.expira.timeout.emit()
        guardar.assert_not_called(); self.assertFalse(self.v.modal)

    def test_cambiar_de_seccion_cancela_la_confirmacion(self):
        self.proponer()
        with patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar, \
             patch.object(self.v.paginas.widget(1),'refrescar'):
            self.v.ir(1)
        guardar.assert_not_called(); self.assertFalse(self.v.modal)

    def test_modal_no_envia_reconocimientos_y_mantiene_camara(self):
        import numpy as np
        self.v.modal=True; self.v.listo=True
        self.v.camera=Mock(); self.v.camera.leer_frame.return_value=np.zeros((200,200,3),dtype=np.uint8)
        with patch.object(self.v,'enviar') as enviar:
            self.v.frame()
        enviar.assert_not_called(); self.v.camera.cerrar.assert_not_called()

    def test_rechazo_no_habilita_confirmacion(self):
        self.estado['decision']=Decision(False,'Cupo agotado')
        with patch('src.ui.gimnasio.db.confirmar_ingreso') as guardar:
            self.proponer()
        guardar.assert_not_called(); self.assertFalse(self.v.modal)
        self.assertFalse(self.v.acceso.confirmar.isEnabled())
        self.assertEqual(self.v.acceso.mensaje.text(),'Cupo agotado')

    def test_respuesta_de_sesion_anterior_se_descarta(self):
        self.v.sesion=2
        with patch.object(self.v,'proponer') as proponer:
            self.v.resultado({'tipo':'reconocer','sesion':1,'resultado':{'estado':'reconocido','socio_id':1}})
        proponer.assert_not_called()

    def test_error_al_guardar_reanuda_reconocimiento(self):
        self.proponer()
        with patch('src.ui.gimnasio.db.confirmar_ingreso',side_effect=RuntimeError('sin conexión')):
            with self.assertRaises(RuntimeError): self.v.confirmar()
        self.assertFalse(self.v.modal)

    def test_todas_las_secciones_cargan_con_la_base(self):
        from src.domain.reglas import ahora_local
        socio={'id':3,'nombre':'Ana','apellido':'Prueba','dni':'12345678','celular':'','correo_electronico':'',
               'activo':True,'creado_en':ahora_local(),'membresia_id':1,'plan':'Pase libre','una_vez_dia':False,
               'inicio':date(2026,10,1),'vence':date(2026,11,1),'importe':1000,'pagado_en':ahora_local(),
               'cupo':None,'usados':2,'restantes':None,'ultimo_ingreso':None,'estado':'Vigente'}
        with patch.multiple('src.ui.paginas.db',estado_membresias=Mock(return_value=[socio]),
                            planes=Mock(return_value=[{'id':1,'nombre':'Pase libre','cupo':None,'una_vez_dia':False}]),
                            resumen_pagos=Mock(return_value={'recaudado':1000,'pagos':1}),
                            horarios=Mock(return_value=[{'id':1,'dia':0,'abre':time(7),'cierra':time(12)}]),
                            socios_por_plan=Mock(return_value=[{'id':1,'nombre':'Pase libre','cupo':None,'una_vez_dia':False,'vigentes':1}]),
                            listar_socios=Mock(return_value=[socio]),informe=Mock(return_value=[])):
            for i in range(1,5):
                with patch.object(QMessageBox,'warning') as aviso:
                    self.v.ir(i)
                aviso.assert_not_called()
        self.assertEqual(self.v.paginas.widget(1).tabla.rowCount(),1)
        self.assertEqual(self.v.paginas.widget(3).k_franjas.valor.text(),'1')
        pagina=self.v.paginas.widget(2)
        self.assertEqual(pagina.socio_elegido()['id'],3)
        pagina.socio.setEditText('Otro socio')
        self.assertIsNone(pagina.socio_elegido()); self.assertFalse(pagina.b_pagar.isEnabled())
        with patch('src.ui.paginas.db.renovar') as renovar, self.assertRaises(ValueError):
            pagina.pagar()
        renovar.assert_not_called()


class PresentacionTest(unittest.TestCase):
    def test_formatos(self):
        from src.domain import presentacion as f
        self.assertEqual(f.fecha_larga(date(2025,1,27)),'Lunes, 27 de enero de 2025')
        self.assertEqual(f.fecha_corta(date(2025,2,28)),'28 feb. 2025')
        self.assertEqual(f.moneda(25000.5),'$ 25.000,50')
        self.assertEqual(f.dni('12345678'),'12.345.678')
        self.assertEqual(f.numero_socio(37),'0037')
        self.assertEqual(f.ultimo_dia(date(2026,11,20)),date(2026,11,19))

    def test_variacion_solo_con_base_real(self):
        from src.domain.presentacion import variacion
        self.assertIsNone(variacion(5,0)); self.assertEqual(variacion(112,100),12); self.assertEqual(variacion(50,100),-50)

    def test_restantes_por_tipo_de_plan(self):
        from src.domain.presentacion import texto_restantes
        self.assertEqual(texto_restantes({'cupo':12,'una_vez_dia':False},3),'3 de 12')
        self.assertEqual(texto_restantes({'cupo':None,'una_vez_dia':True},None),'1 por día')
        self.assertEqual(texto_restantes({'cupo':None,'una_vez_dia':False},None),'Ilimitados')

    def test_estado_horario(self):
        from src.domain.presentacion import estado_horario
        h=[{'dia':0,'abre':time(7),'cierra':time(12)},{'dia':0,'abre':time(16),'cierra':time(22)}]
        lunes=datetime(2026,11,16,10,tzinfo=ZONA)
        self.assertEqual(estado_horario(h,lunes),('Abierto','hasta las 12:00'))
        self.assertEqual(estado_horario(h,lunes.replace(hour=13)),('Cerrado','abre hoy 16:00'))
        self.assertEqual(estado_horario(h,lunes.replace(hour=22)),('Cerrado','abre lunes 07:00'))
        self.assertEqual(estado_horario([],lunes),('Cerrado','sin horarios configurados'))

    def test_estadisticas_del_periodo(self):
        from src.domain.presentacion import estadisticas_ingresos
        filas=[{'instante':datetime(2026,11,2,9,tzinfo=ZONA),'socio_id':1,'plan':'A'},
               {'instante':datetime(2026,11,2,18,tzinfo=ZONA),'socio_id':2,'plan':'B'},
               {'instante':datetime(2026,11,3,9,tzinfo=ZONA),'socio_id':1,'plan':'A'}]
        e=estadisticas_ingresos(filas,date(2026,11,1),date(2026,11,3))
        self.assertEqual((e['total'],e['socios'],e['pico']),(3,2,(date(2026,11,2),2)))
        self.assertEqual([n for _,n in e['serie']],[0,2,1]); self.assertEqual(e['por_plan'][0],('A',2))
        self.assertEqual(e['por_hora'][9],2)


class CamaraTest(unittest.TestCase):
    def test_origen_indice_o_ruta(self):
        from src.camera.camera_manager import normalizar_origen
        self.assertEqual(normalizar_origen('1'),1); self.assertEqual(normalizar_origen(''),0)
        self.assertEqual(normalizar_origen('rtsp://camara/1'),'rtsp://camara/1')


class ValidacionSocioTest(unittest.TestCase):
    def test_datos_invalidos_no_llegan_a_la_base(self):
        from src.database import gimnasio as db
        base={'nombre':'Ana','apellido':'Prueba','dni':'12345678','celular':'','correo_electronico':''}
        fotos={a:b'x' for a in ('frontal','izquierdo','derecho')}
        with patch('src.database.gimnasio.transaccion') as t:
            for cambio in [{'nombre':' '},{'dni':'12a45'},{'dni':'123'},{'correo_electronico':'sin-arroba'},{'celular':'abc'}]:
                with self.assertRaises(ValueError): db.registrar_socio({**base,**cambio},fotos)
            with self.assertRaises(ValueError): db.registrar_socio(base,{'frontal':b'x'})
            with self.assertRaises(ValueError): db.actualizar_socio(1,base,{'perfil':b'x'})
        t.assert_not_called()

if __name__=='__main__': unittest.main()
