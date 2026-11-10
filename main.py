import sys
from PySide6.QtWidgets import QApplication
from src.ui.gimnasio import VentanaGimnasio

if __name__ == '__main__':
    app=QApplication(sys.argv)
    ventana=VentanaGimnasio()
    ventana.show()
    sys.exit(app.exec())
