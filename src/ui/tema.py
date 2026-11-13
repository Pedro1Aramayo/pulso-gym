"""Paleta, tipografías y hoja de estilos de PULSO GYM."""
from pathlib import Path
from PySide6.QtGui import QFontDatabase

LIMA = '#C3F53C'
LIMA_HOVER = '#D3FB63'
FONDO = '#0A1320'
LATERAL = '#08111C'
TARJETA = '#0F1925'
BORDE = '#1B2838'
TEXTO = '#E8EEF6'
TENUE = '#8C9CB1'
AZUL = '#6CB2FF'
AMBAR = '#F5B83D'
ROJO = '#FF6B6B'
FUENTES = Path(__file__).resolve().parent / 'recursos' / 'fuentes'
_cargadas = False


def cargar_fuentes():
    global _cargadas
    if not _cargadas:
        for ruta in sorted(FUENTES.glob('*.ttf')):
            QFontDatabase.addApplicationFont(str(ruta))
        _cargadas = True


ESTILO = f"""
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
QWidget {{ color: {TEXTO}; font-size: 14px; }}
QMainWindow, QWidget#raiz, QDialog, QMessageBox {{ background: {FONDO}; }}
QWidget#lateral {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A1420, stop:1 #070E17);
    border-right: 1px solid #142030; }}
QLabel {{ background: transparent; }}
QLabel#eyebrow {{ color: {LIMA}; font-size: 12px; font-weight: 600; letter-spacing: 2px; }}
QLabel#titulo {{ font-family: 'Montserrat'; font-size: 32px; font-weight: 800; color: #F4F7FB; }}
QLabel#subtitulo, QLabel#tenue {{ color: {TENUE}; }}
QLabel#subtitulo {{ font-size: 15px; }}
QLabel#lema {{ color: #AFBCCB; font-size: 10px; font-weight: 600; letter-spacing: 1.6px; }}
QLabel#tituloTarjeta {{ font-size: 17px; font-weight: 700; color: #F4F7FB; }}
QLabel#kpiTitulo {{ color: #C9D3DF; font-size: 14px; }}
QLabel#kpiValor {{ font-family: 'Montserrat'; font-size: 26px; font-weight: 800; color: #F6F8FB; }}
QLabel#fecha {{ font-size: 15px; color: #DCE4EE; }}
QLabel#vacio {{ color: {TENUE}; font-size: 14px; }}
QLabel#nombreSocio {{ font-family: 'Montserrat'; font-size: 25px; font-weight: 800; color: #F6F8FB; }}
QLabel#datoTitulo {{ color: {TENUE}; font-size: 13px; }}
QLabel#datoValor {{ font-size: 19px; font-weight: 700; color: #F4F7FB; }}
QLabel#datoLima {{ font-size: 19px; font-weight: 700; color: {LIMA}; }}
QLabel#mensajeOk {{ color: {LIMA}; font-weight: 600; }}
QLabel#mensajeError {{ color: {ROJO}; font-weight: 600; }}
QLabel#seccion {{ color: {TENUE}; font-size: 12px; font-weight: 600; letter-spacing: 1.2px; }}
QFrame#tarjeta {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #111C29, stop:1 #0D1622);
    border: 1px solid {BORDE}; border-radius: 14px; }}
QFrame#tarjeta[tono="lima"] {{ border: 2px solid {LIMA};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #13251C, stop:1 #0D1A1C); }}
QFrame#tarjeta[tono="rojo"] {{ border: 2px solid {ROJO};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2A1519, stop:1 #13141D); }}
QFrame#tarjeta[tono="ambar"] {{ border: 2px solid {AMBAR};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2A2214, stop:1 #13161D); }}
QFrame#kpiCamara {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10201B, stop:1 #0E1824);
    border: 1px solid #1E3529; border-radius: 14px; }}
QFrame#separador {{ background: #1B2838; max-height: 1px; min-height: 1px; border: none; }}
QFrame#separadorV {{ background: #1B2838; max-width: 1px; min-width: 1px; border: none; }}
QFrame#cajaDato {{ background: rgba(255,255,255,0.025); border: 1px solid #1D2A3A; border-radius: 10px; }}
QFrame#aviso {{ background: rgba(245,184,61,0.10); border: 1px solid rgba(245,184,61,0.45); border-radius: 10px; }}
QFrame#avisoError {{ background: rgba(255,107,107,0.10); border: 1px solid rgba(255,107,107,0.45); border-radius: 10px; }}
QFrame#filaAcceso {{ border-bottom: 1px solid #172333; background: transparent; }}
QPushButton {{ background: #152132; border: 1px solid #22324A; border-radius: 10px; padding: 10px 18px;
    color: {TEXTO}; font-size: 14px; font-weight: 500; }}
QPushButton:hover {{ background: #1B2B41; border-color: #2D4160; }}
QPushButton:pressed {{ background: #12202F; }}
QPushButton:disabled {{ color: #5B6B80; background: #111A27; border-color: #18243A; }}
QPushButton#primario {{ background: {LIMA}; color: #0A1404; border: none; font-weight: 700; font-size: 15px; }}
QPushButton#primario:hover {{ background: {LIMA_HOVER}; }}
QPushButton#primario:disabled {{ background: #3B4A24; color: #6E7B5A; }}
QPushButton#peligro {{ color: #FFB4B4; border-color: #4A2530; background: #1E1520; }}
QPushButton#peligro:hover {{ background: #2A1822; }}
QPushButton#enlace {{ background: transparent; border: none; color: {LIMA}; padding: 4px; font-size: 13px; font-weight: 600; }}
QPushButton#enlace:hover {{ color: {LIMA_HOVER}; }}
QPushButton#nav {{ text-align: left; padding: 0 18px; background: #0F1926; border: 1px solid #172334;
    border-radius: 10px; color: #DCE4EE; font-size: 16px; font-weight: 500; min-height: 50px; }}
QPushButton#nav:hover {{ background: #142133; border-color: #20314A; }}
QPushButton#nav:checked {{ background: {LIMA}; color: #0A1404; border: none; font-weight: 700; }}
QPushButton#filtro {{ padding: 7px 14px; border-radius: 16px; font-size: 13px; background: #121D2C; }}
QPushButton#filtro:checked {{ background: rgba(195,245,60,0.14); color: {LIMA}; border-color: rgba(195,245,60,0.55); }}
QPushButton#opcion {{ text-align: left; padding: 11px 12px; background: #0C1520; border: 1px solid #22324A; border-radius: 12px; }}
QPushButton#opcion:checked {{ background: rgba(195,245,60,0.10); border: 2px solid {LIMA}; }}
QPushButton#chipX {{ background: transparent; border: none; padding: 0; color: {TENUE}; }}
QPushButton#chipX:hover {{ color: {ROJO}; }}
QToolButton#usuario {{ background: transparent; border: none; padding: 8px; color: {TEXTO}; font-size: 15px; font-weight: 500; }}
QToolButton#usuario:hover {{ background: #111C2A; border-radius: 10px; }}
QToolButton#usuario::menu-indicator {{ image: none; }}
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QDoubleSpinBox, QSpinBox {{ background: #0C1520; border: 1px solid #22324A;
    border-radius: 9px; padding: 9px 12px; color: {TEXTO}; selection-background-color: {LIMA}; selection-color: #0A1404; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {LIMA}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: #0F1A27; border: 1px solid #22324A; selection-background-color: #1C2C40;
    selection-color: {LIMA}; outline: none; padding: 4px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
QCheckBox {{ spacing: 8px; }}
QTableWidget {{ background: transparent; border: none; gridline-color: transparent; outline: none;
    selection-background-color: rgba(195,245,60,0.10); selection-color: {TEXTO}; alternate-background-color: rgba(255,255,255,0.018); }}
QTableWidget::item {{ border-bottom: 1px solid #162232; padding: 0 10px; }}
QTableWidget::item:selected {{ background: rgba(195,245,60,0.10); }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {TENUE}; border: none; border-bottom: 1px solid #1F2D40;
    padding: 10px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #22324A; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #22324A; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QMenu {{ background: #0F1A27; border: 1px solid #22324A; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 9px 22px 9px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: #1C2C40; color: {LIMA}; }}
QMenu::separator {{ height: 1px; background: #22324A; margin: 6px 8px; }}
QToolTip {{ background: #0F1A27; color: {TEXTO}; border: 1px solid #2D4160; padding: 6px 8px; border-radius: 6px; }}
QMessageBox QLabel {{ font-size: 14px; }}
QMessageBox QPushButton {{ min-width: 96px; }}
QCalendarWidget QWidget {{ alternate-background-color: #111C2A; }}
QCalendarWidget QAbstractItemView {{ background: #0F1A27; selection-background-color: {LIMA}; selection-color: #0A1404; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; color: {TEXTO}; padding: 6px; font-weight: 600; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: #0C1520; }}
"""
