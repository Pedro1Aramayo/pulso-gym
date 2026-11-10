"""Persistencia transaccional. Consultar nunca escribe; confirmar revalida bajo bloqueo."""
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, time, timedelta
from psycopg2.extras import RealDictCursor
from src.database.conexion import conectar_bd
from src.domain.reglas import evaluar, un_mes, ahora_local

@contextmanager
def transaccion():
    con = conectar_bd()
    try:
        with con:
            with con.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
    finally:
        con.close()

def listar_socios():
    with transaccion() as c:
        c.execute('SELECT * FROM socio ORDER BY apellido,nombre,id')
        return c.fetchall()

def planes():
    with transaccion() as c:
        c.execute('SELECT * FROM plan ORDER BY id')
        return c.fetchall()

def registrar_socio(datos, fotos):
    if not datos.get('nombre','').strip() or not datos.get('apellido','').strip():
        raise ValueError('Complete nombre y apellido.')
    if not datos.get('dni','').isdigit() or not 6 <= len(datos['dni']) <= 10:
        raise ValueError('El DNI debe tener entre 6 y 10 dígitos.')
    if set(fotos) != {'frontal','izquierdo','derecho'} or not all(fotos.values()):
        raise ValueError('Se requieren las tres fotografías.')
    with transaccion() as c:
        c.execute("""INSERT INTO socio(nombre,apellido,dni,celular,correo_electronico)
                     VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                  tuple(datos.get(k,'').strip() for k in ('nombre','apellido','dni','celular','correo_electronico')))
        socio_id = c.fetchone()['id']
        for angulo, imagen in fotos.items():
            c.execute('INSERT INTO foto_socio(socio_id,angulo,imagen) VALUES (%s,%s,%s)', (socio_id,angulo,imagen))
        return socio_id

def cambiar_estado(socio_id, activo):
    with transaccion() as c:
        c.execute('UPDATE socio SET activo=%s WHERE id=%s', (activo,socio_id))

def renovar(socio_id, plan_id, importe):
    importe = Decimal(str(importe))
    if not importe.is_finite() or importe < 0:
        raise ValueError('Importe inválido.')
    with transaccion() as c:
        c.execute('SELECT id,activo FROM socio WHERE id=%s FOR UPDATE', (socio_id,))
        socio = c.fetchone()
        if not socio or not socio['activo']:
            raise ValueError('Seleccione un socio activo.')
        ahora = ahora_local()
        c.execute('UPDATE membresia SET cerrada_en=%s WHERE socio_id=%s AND cerrada_en IS NULL', (ahora,socio_id))
        c.execute("""INSERT INTO membresia(socio_id,plan_id,inicio,vence,pagado_en,importe)
                     VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                  (socio_id,plan_id,ahora.date(),un_mes(ahora.date()),ahora,importe))
        return c.fetchone()['id']

def horarios():
    with transaccion() as c:
        c.execute('SELECT * FROM horario ORDER BY dia,abre')
        return c.fetchall()

def agregar_horario(dia, abre, cierra):
    if not 0 <= dia <= 6 or abre >= cierra:
        raise ValueError('El cierre debe ser posterior a la apertura del mismo día.')
    with transaccion() as c:
        c.execute('LOCK TABLE horario IN EXCLUSIVE MODE')
        c.execute('SELECT id FROM horario WHERE dia=%s AND abre < %s AND cierra > %s', (dia,cierra,abre))
        if c.fetchone():
            raise ValueError('La franja se superpone con otra existente.')
        c.execute('INSERT INTO horario(dia,abre,cierra) VALUES (%s,%s,%s)', (dia,abre,cierra))

def quitar_horario(horario_id):
    with transaccion() as c:
        c.execute('DELETE FROM horario WHERE id=%s', (horario_id,))

def _consultar(c, socio_id, ahora):
    c.execute('SELECT * FROM socio WHERE id=%s', (socio_id,))
    socio = c.fetchone()
    c.execute("""SELECT m.*,p.nombre AS plan,p.cupo,p.una_vez_dia
                 FROM membresia m JOIN plan p ON p.id=m.plan_id
                 WHERE m.socio_id=%s AND m.cerrada_en IS NULL""", (socio_id,))
    m = c.fetchone()
    usados = hoy = 0
    ultimo = None
    if m:
        inicio_dia = datetime.combine(ahora.date(), time.min, ahora.tzinfo)
        c.execute('SELECT count(*) AS usados FROM ingreso WHERE membresia_id=%s', (m['id'],))
        usados = c.fetchone()['usados']
        c.execute("""SELECT count(*) AS hoy FROM ingreso i JOIN membresia m ON m.id=i.membresia_id
                     WHERE m.socio_id=%s AND i.instante >= %s AND i.instante < %s""",
                  (socio_id,inicio_dia,inicio_dia+timedelta(days=1)))
        hoy = c.fetchone()['hoy']
    # Antirrebote del socio, incluso si renovó entre dos lecturas.
    c.execute("""SELECT max(i.instante) AS ultimo FROM ingreso i
                 JOIN membresia m ON m.id=i.membresia_id WHERE m.socio_id=%s""", (socio_id,))
    ultimo = c.fetchone()['ultimo']
    c.execute('SELECT dia,abre,cierra FROM horario')
    franjas = [(h['dia'],h['abre'],h['cierra']) for h in c.fetchall()]
    decision = evaluar(socio,m,usados,hoy,ultimo,franjas,ahora)
    return dict(socio=socio,membresia=m,usados=usados,decision=decision)

def consultar_acceso(socio_id):
    with transaccion() as c:
        return _consultar(c,socio_id,ahora_local())

def confirmar_ingreso(socio_id, membresia_id, solicitud):
    with transaccion() as c:
        # Serializa ingresos, renovaciones y cambios de estado para el mismo socio.
        c.execute('SELECT id FROM socio WHERE id=%s FOR UPDATE', (socio_id,))
        if not c.fetchone():
            return False, 'El socio ya no existe.'
        c.execute('LOCK TABLE horario IN SHARE MODE')
        c.execute("""SELECT m.socio_id FROM ingreso i JOIN membresia m ON m.id=i.membresia_id
                     WHERE i.solicitud=%s""", (str(solicitud),))
        anterior = c.fetchone()
        if anterior:
            return (True, 'Este ingreso ya estaba confirmado.') if anterior['socio_id'] == socio_id else (False,'Solicitud inválida.')
        ahora = ahora_local()
        estado = _consultar(c,socio_id,ahora)
        if not estado['decision'].permitido:
            return False, estado['decision'].motivo
        if estado['membresia']['id'] != membresia_id:
            return False, 'La membresía cambió mientras confirmaba. Vuelva a identificarse.'
        c.execute('INSERT INTO ingreso(membresia_id,instante,solicitud) VALUES (%s,%s,%s)',
                  (membresia_id,ahora,str(solicitud)))
        return True, 'Ingreso registrado. ¡Buen entrenamiento!'

def informe(desde, hasta, socio_id=None):
    if desde > hasta:
        raise ValueError('El inicio no puede ser posterior al final.')
    with transaccion() as c:
        c.execute("""SELECT s.id AS socio_id,s.apellido,s.nombre,s.dni,p.nombre AS plan,
                     i.instante,m.inicio,m.vence FROM ingreso i
                     JOIN membresia m ON m.id=i.membresia_id JOIN socio s ON s.id=m.socio_id
                     JOIN plan p ON p.id=m.plan_id
                     WHERE (i.instante AT TIME ZONE 'America/Argentina/Buenos_Aires')::date BETWEEN %s AND %s
                     AND (%s IS NULL OR s.id=%s) ORDER BY i.instante DESC""", (desde,hasta,socio_id,socio_id))
        return c.fetchall()

def estado_membresias():
    with transaccion() as c:
        c.execute("""SELECT s.id,s.apellido,s.nombre,s.dni,s.activo,p.nombre AS plan,
                     m.inicio,m.vence,p.cupo,count(i.id) AS usados,
                     CASE WHEN p.cupo IS NULL THEN NULL ELSE greatest(0,p.cupo-count(i.id)) END AS restantes
                     FROM socio s LEFT JOIN membresia m ON m.socio_id=s.id AND m.cerrada_en IS NULL
                     LEFT JOIN plan p ON p.id=m.plan_id LEFT JOIN ingreso i ON i.membresia_id=m.id
                     GROUP BY s.id,p.id,m.id ORDER BY s.apellido,s.nombre""")
        filas = c.fetchall()
    hoy = ahora_local().date()
    for f in filas:
        f['estado'] = ('Inactivo' if not f['activo'] else 'Sin membresía' if not f['inicio'] else
                       'Vencida' if hoy >= f['vence'] else 'No vigente' if hoy < f['inicio'] else
                       'Cupo agotado' if f['restantes'] == 0 else 'Vigente')
    return filas
