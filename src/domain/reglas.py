"""Reglas puras: mes calendario, fin exclusivo, cupos y horario local."""
import calendar
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA = ZoneInfo('America/Argentina/Buenos_Aires')
REPETICION_SEGUNDOS = 30

def ahora_local():
    return datetime.now(ZONA)

def un_mes(fecha):
    anio, mes = fecha.year + (fecha.month == 12), fecha.month % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))

@dataclass(frozen=True)
class Decision:
    permitido: bool
    motivo: str
    restantes: int | None = None

def evaluar(socio, membresia, usados, ingresos_hoy, ultimo, horarios, ahora):
    if not socio or not socio['activo']:
        return Decision(False, 'Socio inexistente o inactivo.')
    if not membresia:
        return Decision(False, 'El socio no tiene una membresía activa.')
    hoy = ahora.date()
    if membresia['cerrada_en'] is not None or not membresia['inicio'] <= hoy < membresia['vence']:
        return Decision(False, 'Membresía vencida o todavía no vigente.')
    if not any(d == ahora.weekday() and a <= ahora.time().replace(tzinfo=None) < c for d,a,c in horarios):
        return Decision(False, 'El gimnasio está cerrado en este horario.')
    if ultimo and (ahora - ultimo).total_seconds() < REPETICION_SEGUNDOS:
        return Decision(False, 'Intento repetido: espere 30 segundos desde el último ingreso.')
    cupo = membresia['cupo']
    restantes = None if cupo is None else max(0, cupo - usados)
    if cupo is not None and usados >= cupo:
        return Decision(False, 'Se agotaron los entrenamientos de la membresía.', 0)
    if membresia['una_vez_dia'] and ingresos_hoy:
        return Decision(False, 'El plan Todos los días permite un solo ingreso por día.')
    return Decision(True, 'Ingreso habilitado.', restantes)
