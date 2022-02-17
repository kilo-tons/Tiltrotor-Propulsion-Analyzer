import sys
from PyQt5.QtWidgets import QApplication
import src.ui


app = QApplication(sys.argv)

window = src.ui.MainWindow()
window.show()

app.exec()
