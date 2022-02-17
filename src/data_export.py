import pandas as pd
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import QThread


def force_scale(x):
    # return ((-2069.9692 * x + 2.5339) / 1000) * 9.8067
    # return ((-236.9447)*x*x*x - 552.1514*x*x - 2494.5821*x - 24.7020) / 1000 * 9.8067
    # return x
    return -10.836 * x +0.0009


def torque_scale(x):
    #return x
    return -0.3104 * x + 0.0018


class ExportWorker(QtCore.QObject):

    finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.filename = ""
        self.row_header = []
        self.data = np.array([])

    def run(self):

        file = pd.DataFrame(self.data.transpose(), columns=self.row_header)
        out_path = self.filename

        writer = pd.ExcelWriter(out_path, engine='xlsxwriter')
        file.to_excel(writer, sheet_name='Sheet1')
        # writer.save()
        writer.close()

        self.finished.emit()


class ExportManager(QtCore.QObject):
    # Signal
    saveComplete = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_header = ['Force (V)',
                           'Force (F)',
                           'Torque (V)',
                           'Torque (F)',
                           'Thrust Percentage',
                           'Motor RPM',
                           'Wind speed (m/s)']

        self.filepath = ""
        self.filename = ""

        self.sample_number = 0
        self.sample_counter = 0
        self.data = np.array([])

        self.should_record = False

        self.thread = None
        self.export_worker = None

    def begin_record(self, sample_number: int, filename: str):
        self.should_record = True

        self.filename = filename
        print(filename)

        # Allocate
        self.sample_number = sample_number
        self.sample_counter = 0
        self.data = np.zeros([len(self.row_header), self.sample_number])

        print("Begin data record!")

    def save_data(self, ni_data: object,
                  ni_data_sample_num: int,
                  ni_offset_volt: list,
                  mcu_data: list,
                  thrust_percentage: float):

        if not self.should_record:
            return

        # Update data
        for i in range(ni_data_sample_num):
            # Force
            self.data[0, (i + self.sample_counter)] = np.array(ni_data)[0, i] - ni_offset_volt[0]
            self.data[1, (i + self.sample_counter)] = force_scale(np.array(ni_data)[0, i] - ni_offset_volt[0])  # Interpolate here

            # Torque
            self.data[2, (i + self.sample_counter)] = np.array(ni_data)[1, i] - ni_offset_volt[1]
            self.data[3, (i + self.sample_counter)] = torque_scale(np.array(ni_data)[1, i] - ni_offset_volt[1])  # Interpolate here

            # The remaining data is almost static, update a single, static value per 100ms should probably be fine
            # Thrust Percentage
            self.data[4, (i + self.sample_counter)] = thrust_percentage

            # Motor RPM
            self.data[5, (i + self.sample_counter)] = mcu_data[0]

            # Wind Speed
            self.data[6, (i + self.sample_counter)] = mcu_data[1]

        self.sample_counter += ni_data_sample_num

        # Print progress
        # TODO: Bring the progress bar to main UI
        print("Progress: Number of samples recorded: ", self.sample_counter)

        if self.sample_number <= self.sample_counter:
            # We have enough sample
            self.should_record = False

            # Thread
            self.thread = QThread()

            # Worker
            self.export_worker = ExportWorker()
            self.export_worker.moveToThread(self.thread)

            self.export_worker.filename = self.filename
            self.export_worker.row_header = self.row_header
            self.export_worker.data = self.data

            self.thread.started.connect(self.export_worker.run)

            self.export_worker.finished.connect(self.thread.quit)
            self.export_worker.finished.connect(self.report)
            self.export_worker.finished.connect(self.export_worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)

            self.thread.start()

    def report(self):
        print("File Created")





