"""Persistencia transaccional. Consultar nunca escribe; confirmar revalida bajo bloqueo."""
import re
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, time, timedelta
from psycopg2 import errors
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

ANGULOS = ('frontal', 'izquierdo', 'derecho')
CORREO = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validar_datos(datos):
    datos = {k: (datos.get(k) or '').strip() for k in ('nombre', 'apellido', 'dni', 'celular', 'correo_electronico')}
    if not datos['nombre'] or not datos['apellido']:
        raise ValueError('Complete nombre y apellido.')
    if len(datos['nombre']) > 100 or len(datos['apellido']) > 100:
        raise ValueError('Nombre y apellido admiten hasta 100 caracteres.')
    if not datos['dni'].isdigit() or not 6 <= len(datos['dni']) <= 10:
        raise ValueError('El DNI debe tener entre 6 y 10 dígitos.')
    if datos['celular'] and not re.fullmatch(r'[0-9 +()\-]{6,40}', datos['celular']):
        raise ValueError('El celular solo admite números, espacios, +, paréntesis y guiones.')
    if datos['correo_electronico'] and (len(datos['correo_electronico']) > 200 or not CORREO.match(datos['correo_electronico'])):
        raise ValueError('Revise el correo electrónico.')
    return datos


@contextmanager
def _dni_unico(dni):
    try:
        yield
    except errors.UniqueViolation:
        raise ValueError(f'Ya existe un socio con el DNI {dni}.') from None


def registrar_socio(datos, fotos):
    datos = _validar_datos(datos)
    if set(fotos) != set(ANGULOS) or not all(fotos.values()):
        raise ValueError('Se requieren las tres fotografías.')
    with _dni_unico(datos['dni']), transaccion() as c:
        c.execute("""INSERT INTO socio(nombre,apellido,dni,celular,correo_electronico)
                     VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                  tuple(datos[k] for k in ('nombre','apellido','dni','celular','correo_electronico')))
        socio_id = c.fetchone()['id']
        for angulo, imagen in fotos.items():
            c.execute('INSERT INTO foto_socio(socio_id,angulo,imagen) VALUES (%s,%s,%s)', (socio_id,angulo,imagen))
        return socio_id


def actualizar_socio(socio_id, datos, fotos=None):
    """Modifica datos de contacto y reemplaza solo las fotografías indicadas."""
    datos = _validar_datos(datos)
    fotos = {a: f for a, f in (fotos or {}).items() if f}
    if not set(fotos) <= set(ANGULOS):
        raise ValueError('Ángulo de fotografía inválido.')
    with _dni_unico(datos['dni']), transaccion() as c:
        c.execute("""UPDATE socio SET nombre=%s,apellido=%s,dni=%s,celular=%s,correo_electronico=%s
                     WHERE id=%s""", tuple(datos[k] for k in ('nombre','apellido','dni','celular','correo_electronico')) + (socio_id,))
        if not c.rowcount:
            raise ValueError('El socio ya no existe.')
        for angulo, imagen in fotos.items():
            c.execute("""INSERT INTO foto_socio(socio_id,angulo,imagen) VALUES (%s,%s,%s)
                         ON CONFLICT (socio_id,angulo) DO UPDATE SET imagen=EXCLUDED.imagen""", (socio_id,angulo,imagen))


def foto_socio(socio_id, angulo='frontal'):
    with transaccion() as c:
        c.execute('SELECT imagen FROM foto_socio WHERE socio_id=%s AND angulo=%s', (socio_id, angulo))
        fila = c.fetchone()
        return bytes(fila['imagen']) if fila else None


def angulos_registrados(socio_id):
    with transaccion() as c:
        c.execute('SELECT angulo FROM foto_socio WHERE socio_id=%s', (socio_id,))
        return {f['angulo'] for f in c.fetchall()}

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
        c.execute("""SELECT s.id,s.apellido,s.nombre,s.dni,s.celular,s.correo_electronico,s.activo,s.creado_en,
                     m.id AS membresia_id,p.nombre AS plan,p.una_vez_dia,m.inicio,m.vence,m.importe,m.pagado_en,
                     p.cupo,count(i.id) AS usados,
                     CASE WHEN p.cupo IS NULL THEN NULL ELSE greatest(0,p.cupo-count(i.id)) END AS restantes,
                     (SELECT max(u.instante) FROM ingreso u JOIN membresia um ON um.id=u.membresia_id
                      WHERE um.socio_id=s.id) AS ultimo_ingreso
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


def _rango_dia(ahora):
    inicio = datetime.combine(ahora.date(), time.min, ahora.tzinfo)
    return inicio, inicio + timedelta(days=1)


def resumen_acceso():
    """Indicadores de recepción. La comparación usa el mismo día de la semana anterior hasta la misma hora."""
    ahora = ahora_local()
    inicio, fin = _rango_dia(ahora)
    with transaccion() as c:
        c.execute("""SELECT
            (SELECT count(*) FROM ingreso WHERE instante >= %s AND instante < %s) AS ingresos_hoy,
            (SELECT count(*) FROM ingreso WHERE instante >= %s AND instante < %s) AS ingresos_semana_anterior,
            (SELECT count(*) FROM socio WHERE activo) AS socios_activos,
            (SELECT count(*) FROM membresia m JOIN socio s ON s.id=m.socio_id
             WHERE m.cerrada_en IS NULL AND s.activo AND m.vence = %s) AS vencen_hoy""",
                  (inicio, fin, inicio - timedelta(days=7), ahora - timedelta(days=7), ahora.date()))
        return c.fetchone()


def ultimos_accesos(limite=8):
    with transaccion() as c:
        c.execute("""SELECT i.id,i.instante,s.id AS socio_id,s.nombre,s.apellido,p.nombre AS plan
                     FROM ingreso i JOIN membresia m ON m.id=i.membresia_id
                     JOIN socio s ON s.id=m.socio_id JOIN plan p ON p.id=m.plan_id
                     ORDER BY i.instante DESC, i.id DESC LIMIT %s""", (limite,))
        return c.fetchall()


def historial_membresias(socio_id):
    with transaccion() as c:
        c.execute("""SELECT m.id,m.inicio,m.vence,m.cerrada_en,m.pagado_en,m.importe,p.nombre AS plan,
                     p.cupo,count(i.id) AS usados
                     FROM membresia m JOIN plan p ON p.id=m.plan_id LEFT JOIN ingreso i ON i.membresia_id=m.id
                     WHERE m.socio_id=%s GROUP BY m.id,p.id ORDER BY m.pagado_en DESC, m.id DESC""", (socio_id,))
        return c.fetchall()


def resumen_pagos():
    ahora = ahora_local()
    inicio_mes = datetime.combine(ahora.date().replace(day=1), time.min, ahora.tzinfo)
    with transaccion() as c:
        c.execute("""SELECT coalesce(sum(importe),0) AS recaudado, count(*) AS pagos FROM membresia
                     WHERE pagado_en >= %s AND pagado_en < %s""", (inicio_mes, inicio_mes.replace(
                         year=inicio_mes.year + (inicio_mes.month == 12), month=inicio_mes.month % 12 + 1)))
        return c.fetchone()


def socios_por_plan():
    """Socios activos con membresía vigente hoy, agrupados por plan."""
    hoy = ahora_local().date()
    with transaccion() as c:
        c.execute("""SELECT p.id,p.nombre,p.cupo,p.una_vez_dia,count(m.id) FILTER (
                         WHERE m.inicio <= %s AND %s < m.vence AND s.activo) AS vigentes
                     FROM plan p LEFT JOIN membresia m ON m.plan_id=p.id AND m.cerrada_en IS NULL
                     LEFT JOIN socio s ON s.id=m.socio_id GROUP BY p.id ORDER BY p.id""", (hoy, hoy))
        return c.fetchall()


def afluencia_por_hora(dias=30):
    desde = ahora_local() - timedelta(days=dias)
    with transaccion() as c:
        c.execute("""SELECT extract(hour FROM instante AT TIME ZONE 'America/Argentina/Buenos_Aires')::int AS hora,
                     count(*) AS ingresos FROM ingreso WHERE instante >= %s GROUP BY 1""", (desde,))
        filas = {f['hora']: f['ingresos'] for f in c.fetchall()}
    return [filas.get(h, 0) for h in range(24)]


def diagnostico():
    with transaccion() as c:
        c.execute("""SELECT current_database() AS base, current_setting('server_version') AS version,
                     (SELECT count(*) FROM socio) AS socios, (SELECT count(*) FROM membresia) AS membresias,
                     (SELECT count(*) FROM ingreso) AS ingresos""")
        return c.fetchone()
