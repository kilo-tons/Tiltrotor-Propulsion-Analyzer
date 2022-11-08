import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QLabel, QMainWindow, QSlider, QWidget, QHBoxLayout, \
    QVBoxLayout, QGridLayout, QLineEdit, QPushButton, QFormLayout, QFileDialog, QGroupBox, \
    QMessageBox

import pyqtgraph
import src.comm_mcu as comm_mcu
import src.comm_ni as comm_ni
import src.data_export as data_export


def force_scale(x):
    # return ((-2069.9692 * x + 2.5339) / 1000) * 9.8067
    # return ((-236.9447)*x*x*x - 552.1514*x*x - 2494.5821*x - 24.7020) / 1000 * 9.8067
    # return x
    # return -10.836 * x +0.0009 % Old loadcell, DEAD
    # return -30.41 * x + 0.1676
    return -29.833 * x + 0.1644
    # return x


def torque_scale(x):
    # return x
    # return -0.3104 * x + 0.0018 % Old loadcell, DEAD
    return -0.5985*x - 0.0006


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("Prop Analysis")

        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        layout = QVBoxLayout()
        layout.setSpacing(50)

        main_layout.addLayout(layout, 0)

        # Backend init
        self.mcu = comm_mcu.MCUSerialManager()
        self.ni = comm_ni.NiDAQManager()
        self.data_export = data_export.ExportManager()

        # Init and connect external classes
        # Setup Panel
        self.setup_panel = SetupPanel()
        self.setup_panel.connect_button.clicked.connect(self.connect_button_clicked)
        self.mcu.portStatus.connect(self.port_status_changed)

        # Control Panel
        self.control_panel = ControlPanel()
        self.control_panel.pwm_slider.valueChanged.connect(self.pwm_value_changed)
        self.control_panel.offset_button.clicked.connect(self.offset_button_clicked)

        # Export Panel
        self.file_export_panel = FileExportPanel()
        self.file_export_panel.record_button.clicked.connect(self.record_button_clicked)

        # Internal
        self.data_export.saveComplete.connect(self.save_completed_dialog)
        self.ni.updateData.connect(self.update_record_data)

        layout.addWidget(self.setup_panel)
        layout.addWidget(self.control_panel)
        layout.addWidget(self.file_export_panel)
        layout.addStretch()

        self.plot_panel = PlotPanel()

        # Plotter
        self.mcu.updateData.connect(self.plot_panel.plot_data_mcu_update)
        self.ni.updateData.connect(self.plot_panel.plot_data_ni_update)

        main_layout.addWidget(self.plot_panel, Qt.AlignLeft)

        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

    @QtCore.pyqtSlot()
    def connect_button_clicked(self):
        self.plot_panel.data_range_init(int(self.setup_panel.pollingrate_fill.text()),
                                        int(self.setup_panel.ni_samples_per_second_fill.text()))

        self.mcu.run(str(self.setup_panel.comport_fill.text()),
                     int(self.setup_panel.baudrate_fill.text()),
                     int(self.setup_panel.pollingrate_fill.text()))

        self.ni.hw_init(str(self.setup_panel.ni_dev1_fill.text()),
                        str(self.setup_panel.ni_dev2_fill.text()),
                        int(self.setup_panel.ni_samples_per_second_fill.text()))

    @QtCore.pyqtSlot()
    def disconnect_button_clicked(self):
        self.mcu.close()
        self.ni.close()

    @QtCore.pyqtSlot(bool)
    def port_status_changed(self, status: bool):
        if status:
            # Port opened, change "Connect" to "Disconnect" status
            self.setup_panel.connect_to_disconnect_function()
            self.setup_panel.connect_button.clicked.disconnect(self.connect_button_clicked)
            self.setup_panel.connect_button.clicked.connect(self.disconnect_button_clicked)

        else:
            # Port closed, change "Disconnect" to "Connect" status
            self.setup_panel.disconnect_to_connect_function()
            self.setup_panel.connect_button.clicked.disconnect(self.disconnect_button_clicked)
            self.setup_panel.connect_button.clicked.connect(self.connect_button_clicked)

    @QtCore.pyqtSlot()
    def pwm_value_changed(self):
        self.mcu.on_pwm_changed(self.control_panel.pwm_slider.value())

    @QtCore.pyqtSlot()
    def offset_button_clicked(self):
        # Use average as offset value
        offset_data_volt = self.ni.get_average()
        self.plot_panel.force_data_offset_volt = offset_data_volt[0]
        self.plot_panel.torque_data_offset_volt = offset_data_volt[1]

        self.plot_panel.plot_ni_set_offset_real()

    @QtCore.pyqtSlot()
    def record_button_clicked(self):
        if self.file_export_panel.sample_len_value.text() == "" \
                or self.file_export_panel.sample_len_value.text() == 0:
            # Invalid
            print("Sample length is invalid!")
            return

        if self.file_export_panel.filepath_path.text() == "":
            # Invalid
            print("Filepath is invalid!")
            return

        self.data_export.begin_record(int(self.file_export_panel.sample_len_value.text()),
                                      self.file_export_panel.filepath_path.text())

    @QtCore.pyqtSlot()
    def save_completed_dialog(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Notice")
        dialog.setText("File Export Complete")

        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()

    @QtCore.pyqtSlot(object, int)
    def update_record_data(self, ni_data: object, sps: int):
        # Use NI polling timer as the main data record timer
        mcu_data = self.mcu.return_data()

        ni_force_offset = self.plot_panel.force_data_offset_volt
        ni_torque_offset = self.plot_panel.torque_data_offset_volt

        # Interpolate thrust percentage
        thrust_percentage = float((self.control_panel.pwm_slider.value() - 1100) / 8)

        # list_test = [ni_data[0], -0.0004 * ni_data[0] + 0.1205, ni_data[1], 0, 0, 0, mcu_data[0], mcu_data[1]]
        # print(-2337.2 * ni_data[0] + 288.85)
        self.data_export.save_data(ni_data,
                                   sps,
                                   [ni_force_offset, ni_torque_offset],
                                   mcu_data,
                                   thrust_percentage)


class SetupPanel(QWidget):
    def __init__(self):
        super(SetupPanel, self).__init__()

        main_layout = QVBoxLayout()
        form_layout = QFormLayout()

        main_layout.addLayout(form_layout)

        self.comport_label = QLabel("COM Port")
        self.comport_fill = QLineEdit()
        self.comport_fill.setText("COM5")

        self.baudrate_label = QLabel("Baudrate")
        self.baudrate_fill = QLineEdit()
        self.baudrate_fill.setText("115200")
        self.baudrate_fill.setValidator(QIntValidator())

        self.pollingrate_label = QLabel("MCU Polling rate")
        self.pollingrate_fill = QLineEdit()
        self.pollingrate_fill.setText("100")
        self.pollingrate_fill.setValidator(QIntValidator())

        self.ni_dev1_label = QLabel("Force sensor Port:")
        self.ni_dev1_fill = QLineEdit()
        self.ni_dev1_fill.setText("Dev1/ai0")

        self.ni_dev2_label = QLabel("Torque sensor Port:")
        self.ni_dev2_fill = QLineEdit()
        self.ni_dev2_fill.setText("Dev1/ai1")

        self.ni_samples_per_second_label = QLabel("Number of Samples per Second")
        self.ni_samples_per_second_fill = QLineEdit()
        self.ni_samples_per_second_fill.setText("1000")
        self.ni_samples_per_second_fill.setValidator(QIntValidator())

        form_layout.addRow(self.comport_label, self.comport_fill)
        form_layout.addRow(self.baudrate_label, self.baudrate_fill)
        form_layout.addRow(self.pollingrate_label, self.pollingrate_fill)
        form_layout.addRow(self.ni_dev1_label, self.ni_dev1_fill)
        form_layout.addRow(self.ni_dev2_label, self.ni_dev2_fill)
        form_layout.addRow(self.ni_samples_per_second_label, self.ni_samples_per_second_fill)

        self.connect_button = QPushButton("Connect")
        main_layout.addWidget(self.connect_button)

        groupbox = QGroupBox("Setup")
        groupbox.setLayout(main_layout)

        # QHBoxLayout or QVBoxLayout wrapper layout should works
        layout = QHBoxLayout()
        layout.addWidget(groupbox)

        self.setLayout(layout)

    def connect_to_disconnect_function(self):
        # Disable any input
        self.comport_fill.setReadOnly(True)
        self.baudrate_fill.setReadOnly(True)
        self.pollingrate_fill.setReadOnly(True)

        self.ni_dev1_fill.setReadOnly(True)
        self.ni_dev2_fill.setReadOnly(True)
        self.ni_samples_per_second_fill.setReadOnly(True)

        self.connect_button.setText("Disconnect")

    # Reversed
    def disconnect_to_connect_function(self):
        # Re-enable
        self.comport_fill.setReadOnly(False)
        self.baudrate_fill.setReadOnly(False)
        self.pollingrate_fill.setReadOnly(False)

        self.ni_dev1_fill.setReadOnly(False)
        self.ni_dev2_fill.setReadOnly(False)
        self.ni_samples_per_second_fill.setReadOnly(False)

        self.connect_button.setText("Connect")


class ControlPanel(QWidget):
    def __init__(self):
        super(ControlPanel, self).__init__()

        main_layout = QVBoxLayout()

        self.pwm_label = QLabel("RPM Control Slider")
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setMinimum(1100)
        self.pwm_slider.setMaximum(1900)
        self.pwm_slider.setSingleStep(1)

        self.thrust_percentage_display = QLabel(str((self.pwm_slider.value() - 1100)/8))
        self.pwm_slider.valueChanged.connect(self.pwm_value_changed)

        self.offset_button = QPushButton("Offset the torque and force channel")

        main_layout.addWidget(self.pwm_label)
        main_layout.addWidget(self.pwm_slider)
        main_layout.addWidget(self.thrust_percentage_display)
        main_layout.addWidget(self.offset_button)

        groupbox = QGroupBox("Control")
        groupbox.setLayout(main_layout)

        # QHBoxLayout or QVBoxLayout wrapper layout should works
        layout = QHBoxLayout()
        layout.addWidget(groupbox)

        self.setLayout(layout)

    def pwm_value_changed(self):
        self.thrust_percentage_display.setText(str((self.pwm_slider.value() - 1100)/8))


class PlotPanel(QWidget):
    def __init__(self):
        super(PlotPanel, self).__init__()
        main_layout = QVBoxLayout()

        data_layout = QGridLayout()
        data_layout.setVerticalSpacing(5)

        plot_layout = QGridLayout()
        plot_layout.setVerticalSpacing(5)

        main_layout.addLayout(data_layout)

        # Data holder
        self.force_data = []
        self.force_data_average_raw = 0
        self.force_data_offset_volt = 0
        self.force_data_average_newt = 0.0
        self.force_data_offset_newt = 0

        self.torque_data = []
        self.torque_data_average_raw = 0
        self.torque_data_average_nm = 0
        self.torque_data_offset_volt = 0
        self.torque_data_offset_nm = 0

        self.ni_time_axis = []
        self.ni_data_counter = 0

        self.windspeed_data = []
        self.rpm_data = []
        self.mcu_time_axis = []
        self.mcu_data_counter = 0

        self.force = ValueLabel()
        self.force.label.setText("FORCE:")
        self.force.label.setFont(QFont('Arial', 12))
        self.force.value.setText(str(0) + " N")
        self.force.value.setFont(QFont('Arial', 20))

        self.torque = ValueLabel()
        self.torque.label.setText("TORQUE:")
        self.torque.label.setFont(QFont('Arial', 12))
        self.torque.value.setText(str(0) + " N.m")
        self.torque.value.setFont(QFont('Arial', 20))

        self.rpm = ValueLabel()
        self.rpm.label.setText("RPM:")
        self.rpm.label.setFont(QFont('Arial', 12))
        self.rpm.value.setText(str(0))
        self.rpm.value.setFont(QFont('Arial', 20))

        self.windspeed = ValueLabel()
        self.windspeed.label.setText("WINDSPEED:")
        self.windspeed.label.setFont(QFont('Arial', 12))
        self.windspeed.value.setText(str(0) + " m/s")
        self.windspeed.value.setFont(QFont('Arial', 20))

        data_layout.addWidget(self.force, 0, 0)
        data_layout.addWidget(self.torque, 0, 1)
        data_layout.addWidget(self.rpm, 1, 0)
        data_layout.addWidget(self.windspeed, 1, 1)

        self.graph_force = pyqtgraph.PlotWidget()
        self.graph_force.setTitle("FORCE")
        self.graph_force.setLabel('left', 'Force (N)')
        self.graph_force.setLabel('bottom', 'Time (ms)')
        self.graph_force.setMouseEnabled(x=False, y=False)

        self.graph_torque = pyqtgraph.PlotWidget()
        self.graph_torque.setTitle("TORQUE")
        self.graph_torque.setLabel('left', 'Torque (N.m)')
        self.graph_torque.setLabel('bottom', 'Time (ms)')
        self.graph_torque.setMouseEnabled(x=False, y=False)

        self.graph_rpm = pyqtgraph.PlotWidget()
        self.graph_rpm.setTitle("RPM")
        self.graph_rpm.setLabel('left', 'RPM')
        self.graph_rpm.setLabel('bottom', 'Time (ms)')
        self.graph_rpm.setMouseEnabled(x=False, y=False)

        self.graph_windspeed = pyqtgraph.PlotWidget()
        self.graph_windspeed.setTitle("WIND SPEED")
        self.graph_windspeed.setLabel('left', 'Wind speed (m/s)')
        self.graph_windspeed.setLabel('bottom', 'Time (ms)')
        self.graph_windspeed.setMouseEnabled(x=False, y=False)

        plot_layout.addWidget(self.graph_force, 0, 0)
        plot_layout.addWidget(self.graph_torque, 0, 1)
        plot_layout.addWidget(self.graph_rpm, 1, 0)
        plot_layout.addWidget(self.graph_windspeed, 1, 1)

        main_layout.addLayout(plot_layout)
        self.setLayout(main_layout)

    def data_range_init(self, mcu_polling_rate: int, ni_sample_per_second: int):
        # Init the arrays
        self.force_data = [0] * ni_sample_per_second
        self.torque_data = [0] * ni_sample_per_second
        self.ni_time_axis = list(range(0, ni_sample_per_second, int(ni_sample_per_second / 1000)))
        self.ni_data_counter = 0

        self.windspeed_data = [0] * int(1000 / mcu_polling_rate)
        self.rpm_data = [0] * int(1000 / mcu_polling_rate)
        self.mcu_time_axis = list(range(0, 1000, mcu_polling_rate))
        self.mcu_data_counter = 0

    def plot_data_mcu_update(self, rpm: int, windspeed: float):
        i = self.mcu_data_counter

        self.windspeed.value.setText(str(round(windspeed, 2)) + " m/s")
        self.windspeed_data[i] = windspeed

        self.rpm.value.setText(str(rpm))
        self.rpm_data[i] = rpm

        self.mcu_data_counter += 1

        if self.mcu_data_counter == len(self.mcu_time_axis):
            self.plot_mcu_ui_update()
            self.mcu_data_counter = 0

    def plot_mcu_ui_update(self):
        self.graph_windspeed.clear()
        self.graph_windspeed.plot(self.mcu_time_axis, self.windspeed_data)

        self.graph_rpm.clear()
        self.graph_rpm.plot(self.mcu_time_axis, self.rpm_data)

    def plot_data_ni_update(self, data, samples_per_scan: int):

        # Interpolate the function here
        force_average_volt = float(np.average(data[0]))
        torque_average_volt = float(np.average(data[1]))

        self.force_data_average_raw = force_scale(force_average_volt - self.force_data_offset_volt)
        self.torque_data_average_raw = torque_scale(torque_average_volt - self.torque_data_offset_volt)

        self.force.value.setText(str(round(self.force_data_average_raw, 4)) + " N")
        self.torque.value.setText(str(round(self.torque_data_average_raw, 4)) + " N.m")

        # Push to plot array
        for i in range(samples_per_scan):
            self.force_data[i + self.ni_data_counter] = force_scale(np.array(data)[0, i] - self.force_data_offset_volt)
            self.torque_data[i + self.ni_data_counter] = torque_scale(np.array(data)[1, i] - self.torque_data_offset_volt)

        self.ni_data_counter += samples_per_scan

        if self.ni_data_counter == len(self.ni_time_axis):
            self.plot_ni_ui_update()
            self.ni_data_counter = 0

    def plot_ni_ui_update(self):
        self.graph_force.clear()
        self.graph_force.plot(self.ni_time_axis, self.force_data)

        self.graph_torque.clear()
        self.graph_torque.plot(self.ni_time_axis, self.torque_data)

    def plot_ni_set_offset_real(self):
        self.force_data_offset_newt = self.force_data_average_raw
        self.torque_data_offset_nm = self.torque_data_average_raw


class FileExportPanel(QWidget):
    def __init__(self):
        super(FileExportPanel, self).__init__()

        main_layout = QVBoxLayout()
        fillbox_layout = QFormLayout()

        self.file_dialog = QFileDialog()
        self.file_dialog.setDefaultSuffix("xlsx")
        self.file_dialog.setWindowTitle("Export Path")
        self.file_dialog.setWindowModality(Qt.ApplicationModal)
        self.file_dialog.setNameFilter("Microsoft Excel Worksheet (*.xlsx)")
        self.file_dialog.fileSelected.connect(self.filename_received)

        self.sample_len_label = QLabel("Sample number")
        self.sample_len_value = QLineEdit()
        self.sample_len_value.setValidator(QIntValidator())

        self.filepath_label = QLabel("File Path")
        self.filepath_path = QLineEdit()

        # Avoid random file path edit
        # TODO: Implement filepath validator
        # self.filepath_path.setReadOnly(True)

        fillbox_layout.addRow(self.sample_len_label, self.sample_len_value)
        fillbox_layout.addRow(self.filepath_label, self.filepath_path)

        self.filepath_browse_button = QPushButton("Browse")
        self.filepath_browse_button.clicked.connect(self.browse_button_clicked)

        self.record_button = QPushButton("Record and Export")

        main_layout.addLayout(fillbox_layout)
        main_layout.addWidget(self.filepath_browse_button)
        main_layout.addWidget(self.record_button)

        groupbox = QGroupBox("Export")
        groupbox.setLayout(main_layout)

        # QHBoxLayout or QVBoxLayout wrapper layout should works
        layout = QHBoxLayout()
        layout.addWidget(groupbox)

        self.setLayout(layout)

    def browse_button_clicked(self):
        # fileName, _ = self.file_dialog.getSaveFileName(self, "Export", "", "Microsoft Excel Worksheet (*.xlsx)")
        self.file_dialog.show()
        # if fileName:
        #     self.filepath_path.setText(fileName)

    def filename_received(self, file_name: str):
        if file_name:
            self.filepath_path.setText(file_name)


class AdvancedFunction(QWidget):
    def __init__(self):
        super(ValueLabel, self).__init__()


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
