"""TEST_POSTGRES=1 usa un schema temporal en la base configurada; nunca borra tablas existentes."""
import os
import unittest
from uuid import uuid4
from pathlib import Path
from datetime import datetime,timedelta,date,time
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from src.domain.reglas import ZONA
from src.database import gimnasio as db
from src.database.conexion import conectar_bd

@unittest.skipUnless(os.getenv('TEST_POSTGRES')=='1','Requiere PostgreSQL; activar TEST_POSTGRES=1')
class PostgresTest(unittest.TestCase):
    def setUp(self):
        self.schema='prueba_'+uuid4().hex
        con=conectar_bd()
        try:
            with con:
                with con.cursor() as c:
                    c.execute('CREATE SCHEMA '+self.schema)
                    c.execute('SET search_path TO '+self.schema)
                    c.execute((Path(__file__).resolve().parents[1]/'database/initdb/01-schema.sql').read_text(encoding='utf-8'))
        finally: con.close()
        self.original=conectar_bd
        def conectar_prueba():
            con=self.original()
            with con.cursor() as c: c.execute('SET search_path TO '+self.schema)
            return con
        self.parche=patch.object(db,'conectar_bd',side_effect=conectar_prueba); self.parche.start()
        self.clock=patch.object(db,'ahora_local',return_value=datetime(2026,10,20,10,tzinfo=ZONA)); self.reloj=self.clock.start()
        self.sid=db.registrar_socio(dict(nombre='Ana',apellido='Prueba',dni='12345678'),dict(frontal=b'prueba',izquierdo=b'prueba',derecho=b'prueba'))
        self.mid=db.renovar(self.sid,1,100)

    def tearDown(self):
        self.clock.stop(); self.parche.stop()
        con=self.original()
        try:
            with con:
                with con.cursor() as c: c.execute('DROP SCHEMA '+self.schema+' CASCADE')
        finally: con.close()

    def test_consultar_no_escribe_y_confirmar_es_idempotente(self):
        for _ in range(3): self.assertTrue(db.consultar_acceso(self.sid)['decision'].permitido)
        self.assertEqual(len(db.informe(date(2026,10,1),date(2026,10,31))),0)
        clave=uuid4()
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,clave)[0])
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,clave)[0])
        self.assertEqual(len(db.informe(date(2026,10,1),date(2026,10,31))),1)

    def test_renovacion_cierra_periodo_no_acumula_y_revalida(self):
        db.confirmar_ingreso(self.sid,self.mid,uuid4())
        self.reloj.return_value+=timedelta(minutes=1)
        nueva=db.renovar(self.sid,2,200)
        estado=db.consultar_acceso(self.sid)
        self.assertEqual(estado['usados'],0); self.assertEqual(estado['decision'].restantes,12)
        self.assertFalse(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        self.assertTrue(db.confirmar_ingreso(self.sid,nueva,uuid4())[0])
        self.assertEqual(len(db.informe(date(2026,10,1),date(2026,10,31))),2)

    def test_concurrencia_no_duplica_ni_supera_cupo(self):
        with db.transaccion() as c:
            for n in range(7):
                c.execute('INSERT INTO ingreso(membresia_id,instante,solicitud) VALUES (%s,%s,%s)',
                          (self.mid,datetime(2026,10,20,8,tzinfo=ZONA)+timedelta(minutes=n),str(uuid4())))
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(lambda _:db.confirmar_ingreso(self.sid,self.mid,uuid4()),range(2)))
        self.assertEqual(sum(r[0] for r in resultados),1)
        self.assertEqual(db.consultar_acceso(self.sid)['usados'],8)

    def test_cambio_horario_entre_consulta_y_confirmacion(self):
        self.assertTrue(db.consultar_acceso(self.sid)['decision'].permitido)
        for h in db.horarios(): db.quitar_horario(h['id'])
        self.assertFalse(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])

    def test_solapamiento_y_turnos(self):
        with self.assertRaises(ValueError): db.agregar_horario(1,time(8),time(11))
        db.agregar_horario(5,time(8),time(12)); db.agregar_horario(5,time(16),time(20))
        self.assertEqual(sum(h['dia']==5 for h in db.horarios()),2)

    def test_unico_diario_contra_pase_libre(self):
        self.mid=db.renovar(self.sid,4,100)
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        self.reloj.return_value+=timedelta(minutes=1)
        self.assertFalse(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        self.mid=db.renovar(self.sid,5,100)
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        self.reloj.return_value+=timedelta(minutes=1)
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])

    def test_vencimiento_y_socio_inactivo(self):
        db.cambiar_estado(self.sid,False)
        self.assertFalse(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        db.cambiar_estado(self.sid,True)
        self.reloj.return_value=datetime(2026,11,20,10,tzinfo=ZONA)
        self.assertFalse(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        self.assertEqual(db.estado_membresias()[0]['estado'],'Vencida')

    def test_tablero_y_ultimos_accesos_salen_de_la_base(self):
        r=db.resumen_acceso()
        self.assertEqual((r['ingresos_hoy'],r['socios_activos'],r['vencen_hoy']),(0,1,0))
        self.assertTrue(db.confirmar_ingreso(self.sid,self.mid,uuid4())[0])
        with db.transaccion() as c:
            c.execute('INSERT INTO ingreso(membresia_id,instante,solicitud) VALUES (%s,%s,%s)',
                      (self.mid,datetime(2026,10,13,9,tzinfo=ZONA),str(uuid4())))
        r=db.resumen_acceso()
        self.assertEqual((r['ingresos_hoy'],r['ingresos_semana_anterior']),(1,1))
        accesos=db.ultimos_accesos(5)
        self.assertEqual([a['instante'].day for a in accesos],[20,13]); self.assertEqual(accesos[0]['nombre'],'Ana')
        self.reloj.return_value=datetime(2026,11,20,10,tzinfo=ZONA)
        self.assertEqual(db.resumen_acceso()['vencen_hoy'],1)
        self.assertFalse(db.consultar_acceso(self.sid)['decision'].permitido)

    def test_foto_y_edicion_de_socio(self):
        self.assertEqual(db.foto_socio(self.sid),b'prueba')
        db.actualizar_socio(self.sid,dict(nombre='Ana María',apellido='Prueba',dni='12345678',celular='381 555',correo_electronico='ana@correo.com'),{'frontal':b'nueva'})
        self.assertEqual(db.foto_socio(self.sid),b'nueva'); self.assertEqual(db.foto_socio(self.sid,'derecho'),b'prueba')
        self.assertEqual(db.listar_socios()[0]['nombre'],'Ana María')
        otro=db.registrar_socio(dict(nombre='Beto',apellido='Dos',dni='87654321'),dict(frontal=b'b',izquierdo=b'b',derecho=b'b'))
        with self.assertRaisesRegex(ValueError,'Ya existe'): db.actualizar_socio(otro,dict(nombre='Beto',apellido='Dos',dni='12345678'))
        with self.assertRaisesRegex(ValueError,'Ya existe'): db.registrar_socio(dict(nombre='X',apellido='Y',dni='87654321'),dict(frontal=b'b',izquierdo=b'b',derecho=b'b'))
        self.assertEqual(len(db.listar_socios()),2)

    def test_pagos_historial_y_planes(self):
        self.reloj.return_value+=timedelta(minutes=5)
        db.renovar(self.sid,5,300)
        historial=db.historial_membresias(self.sid)
        self.assertEqual([h['plan'] for h in historial],['Pase libre','2 veces por semana'])
        self.assertIsNotNone(historial[1]['cerrada_en'])
        self.assertEqual(float(db.resumen_pagos()['recaudado']),400)
        vigentes={p['nombre']:p['vigentes'] for p in db.socios_por_plan()}
        self.assertEqual((vigentes['Pase libre'],vigentes['2 veces por semana']),(1,0))
        self.assertEqual(db.diagnostico()['socios'],1)

if __name__=='__main__': unittest.main()
