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

if __name__=='__main__': unittest.main()
