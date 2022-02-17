import nidaqmx
from nidaqmx.constants import TerminalConfiguration
from nidaqmx import system
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
import numpy as np


class NiDAQManager(QtCore.QObject):
    # Signals
    updateData = QtCore.pyqtSignal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.force_chan = ""
        self.torque_chan = ""

        self.task = None
        self.timer = QTimer(self)
        self.samples_per_scan = 0
        self.data = np.array([])
        self.torque_average = 0
        self.force_average = 0

    @QtCore.pyqtSlot(str, str)
    def hw_init(self, force_chan: str, torque_chan: str, samples_per_second: int):
        self.task = nidaqmx.Task()
        self.force_chan = force_chan
        self.torque_chan = torque_chan

        self.task.ai_channels.add_ai_voltage_chan(self.force_chan,
                                                  terminal_config=TerminalConfiguration.RSE)
        self.task.ai_channels.add_ai_voltage_chan(self.torque_chan,
                                                  terminal_config=TerminalConfiguration.RSE)

        self.samples_per_scan = int(samples_per_second / 10)

        self.timer.timeout.connect(self.read)

        self.data = np.zeros([2, self.samples_per_scan])

        # Poll at 100ms interval to reduce CPU load
        self.timer.start(100)

    def get_average(self):
        return [self.force_average, self.torque_average]

    @QtCore.pyqtSlot()
    def read(self):
        self.data = self.task.read(number_of_samples_per_channel=self.samples_per_scan,
                                   timeout=0.1)

        # Use average value per scan as offset value when required
        self.force_average = float(np.average(self.data[0]))
        self.torque_average = float(np.average(self.data[1]))

        self.updateData.emit(self.data, self.samples_per_scan)

    @QtCore.pyqtSlot()
    def close(self):
        self.timer.stop()
        # nidaqmx.system.storage.persisted_task.PersistedTask.delete()
        self.task.close()
