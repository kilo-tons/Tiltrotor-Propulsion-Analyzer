import nidaqmx
from PyQt5 import QtCore


class NiDAQManager(QtCore.QObject):
    # Signals
    updateData = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        self.force_chan = "Dev1/ai0"
        self.torque_chan = "Dev1/ai1"

        self.task = nidaqmx.Task()

    @QtCore.pyqtSlot(str, str)
    def hw_init(self):
        self.task.ai_channels.add_ai_voltage_chan(self.force_chan)
        self.task.ai_channels.add_ai_voltage_chan(self.torque_chan)

    def read(self):
        buf = list(self.task.read(timeout=0.01))

        self.updateData.emit(buf)






