import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLibraryInfo
from src.ui.gimnasio import VentanaGimnasio

if __name__ == '__main__':
    app=QApplication(sys.argv)
    traduccion=QTranslator(app)
    if traduccion.load('qtbase_es', QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(traduccion)
    ventana=VentanaGimnasio()
    ventana.show()
    sys.exit(app.exec())
