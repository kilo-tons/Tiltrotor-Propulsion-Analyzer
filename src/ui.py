from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QLabel, QMainWindow, QSlider, QWidget, QHBoxLayout, \
    QVBoxLayout, QGridLayout, QLineEdit, QPushButton, QFormLayout, QFileDialog

import pyqtgraph
import src.comm_mcu as comm_mcu
import src.comm_ni as comm_ni


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("Prop Analysis")

        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        layout = QVBoxLayout()
        layout.setSpacing(50)

        main_layout.addLayout(layout, 0)

        # Hardware init
        self.mcu = comm_mcu.MCUSerialManager()
        self.ni = comm_ni.NiDAQManager()

        # Init and connect external classes
        # Setup Panel
        self.setup_panel = SetupPanel()
        self.setup_panel.connect_button.clicked.connect(self.connect_button_clicked)

        layout.addWidget(self.setup_panel)
        layout.addWidget(ControlPanel())
        layout.addWidget(FileExportPanel())
        layout.addStretch()

        main_layout.addWidget(PlotPanel(), Qt.AlignLeft)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

    def connect_button_clicked(self):
        self.mcu.run(str(self.setup_panel.comport_fill.text()),
                     int(self.setup_panel.baudrate_fill.text()),
                     int(self.setup_panel.pollingrate_fill.text()))


class SetupPanel(QWidget):
    def __init__(self):
        super(SetupPanel, self).__init__()

        main_layout = QVBoxLayout()
        form_layout = QFormLayout()

        main_layout.addLayout(form_layout)

        self.comport_label = QLabel("COM Port")
        self.comport_fill = QLineEdit()
        self.comport_fill.setText("COM1")

        self.baudrate_label = QLabel("Baudrate")
        self.baudrate_fill = QLineEdit()
        self.baudrate_fill.setText("115200")
        self.baudrate_fill.setValidator(QIntValidator())

        self.pollingrate_label = QLabel("Polling rate")
        self.pollingrate_fill = QLineEdit()
        self.pollingrate_fill.setText("100")
        self.pollingrate_fill.setValidator(QIntValidator())

        form_layout.addRow(self.comport_label, self.comport_fill)
        form_layout.addRow(self.baudrate_label, self.baudrate_fill)
        form_layout.addRow(self.pollingrate_label, self.pollingrate_fill)

        self.connect_button = QPushButton("Connect")

        main_layout.addWidget(self.connect_button)
        self.setLayout(main_layout)


class ControlPanel(QWidget):
    def __init__(self):
        super(ControlPanel, self).__init__()

        main_layout = QVBoxLayout()

        self.pwm_label = QLabel("PWM Slider")
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setMinimum(1100)
        self.pwm_slider.setMaximum(1900)
        self.pwm_slider.setSingleStep(1)

        main_layout.addWidget(self.pwm_label)
        main_layout.addWidget(self.pwm_slider)

        self.setLayout(main_layout)


class PlotPanel(QWidget):
    def __init__(self):
        super(PlotPanel, self).__init__()

        main_layout = QVBoxLayout()

        data_layout = QGridLayout()
        data_layout.setVerticalSpacing(5)

        plot_layout = QGridLayout()
        plot_layout.setVerticalSpacing(5)

        main_layout.addLayout(data_layout)

        self.force = ValueLabel()
        self.force.label.setText("FORCE:")
        self.force.value.setText(str(1234.5) + " N")

        self.torque = ValueLabel()
        self.torque.label.setText("TORQUE:")
        self.torque.value.setText(str(0.5443) + " N.m")

        self.rpm = ValueLabel()
        self.rpm.label.setText("RPM:")
        self.rpm.value.setText(str(10000))

        self.windspeed = ValueLabel()
        self.windspeed.label.setText("WINDSPEED:")
        self.windspeed.value.setText(str(15.2) + " m/s")

        data_layout.addWidget(self.force, 0, 0)
        data_layout.addWidget(self.torque, 0, 1)
        data_layout.addWidget(self.rpm, 1, 0)
        data_layout.addWidget(self.windspeed, 1, 1)

        self.graph_force = pyqtgraph.PlotWidget()
        self.graph_force.setTitle("FORCE")
        self.graph_force.setLabel('left', 'Force (N)')
        self.graph_force.setLabel('bottom', 'Time (s)')

        self.graph_torque = pyqtgraph.PlotWidget()
        self.graph_torque.setTitle("TORQUE")
        self.graph_torque.setLabel('left', 'Torque (N.m)')
        self.graph_torque.setLabel('bottom', 'Time (s)')

        self.graph_rpm = pyqtgraph.PlotWidget()
        self.graph_rpm.setTitle("RPM")
        self.graph_rpm.setLabel('left', 'RPM')
        self.graph_rpm.setLabel('bottom', 'Time (s)')

        self.graph_windspeed = pyqtgraph.PlotWidget()
        self.graph_windspeed.setTitle("WIND SPEED")
        self.graph_windspeed.setLabel('left', 'Wind speed (m/s)')
        self.graph_windspeed.setLabel('bottom', 'Time (s)')

        plot_layout.addWidget(self.graph_force, 0, 0)
        plot_layout.addWidget(self.graph_torque, 0, 1)
        plot_layout.addWidget(self.graph_rpm, 1, 0)
        plot_layout.addWidget(self.graph_windspeed, 1, 1)

        main_layout.addLayout(plot_layout)
        self.setLayout(main_layout)


class FileExportPanel(QWidget):
    def __init__(self):
        super(FileExportPanel, self).__init__()

        self.export_dialog = FileExportDialog()

        main_layout = QVBoxLayout()
        fillbox_layout = QFormLayout()

        self.main_label = QLabel("Export")

        self.sample_len_label = QLabel("Sample number")
        self.sample_len_value = QLineEdit()
        self.sample_len_value.setValidator(QIntValidator())

        fillbox_layout.addRow(self.sample_len_label, self.sample_len_value)

        self.record_button = QPushButton("Record and Export")
        self.record_button.clicked.connect(self.export_dialog.export_dialog)

        main_layout.addWidget(self.main_label)
        main_layout.addLayout(fillbox_layout)
        main_layout.addWidget(self.record_button)

        self.setLayout(main_layout)


class FileExportDialog(QWidget):
    def __init__(self):
        super(FileExportDialog, self).__init__()
        self.options = QFileDialog.Options()

    def export_dialog(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Export")
        if fileName:
            print(fileName)


class ValueLabel(QWidget):
    def __init__(self):
        super(ValueLabel, self).__init__()

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.label = QLabel()
        self.value = QLabel()

        layout.addWidget(self.label)
        layout.addWidget(self.value)

        self.setLayout(layout)
