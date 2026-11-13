"""Textos y cálculos de presentación sin Qt ni base de datos."""
from collections import Counter
from datetime import timedelta

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
MESES_CORTOS = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']


def fecha_larga(d):
    return f'{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}'


def fecha_corta(d):
    return '—' if d is None else f'{d.day} {MESES_CORTOS[d.month - 1]} {d.year}'


def fecha_numerica(d):
    return '—' if d is None else d.strftime('%d/%m/%Y')


def numero_socio(socio_id):
    return f'{int(socio_id):04d}'


def moneda(valor):
    entero, _, dec = f'{float(valor or 0):,.2f}'.partition('.')
    return f"$ {entero.replace(',', '.')},{dec}"


def dni(valor):
    texto = str(valor or '')
    return f'{int(texto):,}'.replace(',', '.') if texto.isdigit() else texto


def iniciales(nombre, apellido):
    return ((nombre or ' ')[0] + (apellido or ' ')[0]).strip().upper() or '?'


def variacion(actual, anterior):
    """Porcentaje entero respecto del valor anterior; None cuando no hay base de comparación."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior)


def regla_plan(cupo, una_vez_dia):
    if cupo:
        return f'{cupo} entrenamientos por mes'
    return '1 ingreso por día' if una_vez_dia else 'Ingresos ilimitados'


def texto_restantes(membresia, restantes):
    if not membresia:
        return '—'
    if membresia.get('cupo'):
        return '—' if restantes is None else f"{restantes} de {membresia['cupo']}"
    return '1 por día' if membresia.get('una_vez_dia') else 'Ilimitados'


def ultimo_dia(vence):
    """La vigencia es [inicio, vence): el último día con acceso es el anterior al vencimiento."""
    return None if vence is None else vence - timedelta(days=1)


def estadisticas_ingresos(filas, desde, hasta):
    """Resumen del período a partir de las filas del informe (ya filtradas en la base)."""
    dias = (hasta - desde).days + 1
    por_dia = Counter(f['instante'].date() for f in filas)
    serie = [(desde + timedelta(days=i), por_dia.get(desde + timedelta(days=i), 0)) for i in range(max(dias, 0))]
    por_plan = Counter(f['plan'] for f in filas).most_common()
    por_hora = Counter(f['instante'].hour for f in filas)
    pico = max(serie, key=lambda x: (x[1], x[0])) if serie and filas else None
    return dict(total=len(filas), socios=len({f['socio_id'] for f in filas}),
                promedio=len(filas) / dias if dias > 0 else 0, pico=pico, serie=serie,
                por_plan=por_plan, por_hora=[por_hora.get(h, 0) for h in range(24)])


def franjas_por_dia(horarios):
    dias = {d: [] for d in range(7)}
    for h in horarios:
        dias[h['dia']].append(h)
    return dias


def horas_semanales(horarios):
    total = 0
    for h in horarios:
        total += (h['cierra'].hour * 60 + h['cierra'].minute) - (h['abre'].hour * 60 + h['abre'].minute)
    return total / 60


def estado_horario(horarios, ahora):
    """('Abierto', 'hasta 22:00') o ('Cerrado', 'abre lunes 07:00') según las franjas configuradas."""
    hora = ahora.time().replace(tzinfo=None)
    for h in sorted(horarios, key=lambda h: h['abre']):
        if h['dia'] == ahora.weekday() and h['abre'] <= hora < h['cierra']:
            return 'Abierto', f"hasta las {h['cierra']:%H:%M}"
    for salto in range(8):
        dia = (ahora.weekday() + salto) % 7
        for h in sorted((h for h in horarios if h['dia'] == dia), key=lambda h: h['abre']):
            if salto or h['abre'] > hora:
                cuando = 'hoy' if salto == 0 else 'mañana' if salto == 1 else DIAS[dia].lower()
                return 'Cerrado', f"abre {cuando} {h['abre']:%H:%M}"
    return 'Cerrado', 'sin horarios configurados'

