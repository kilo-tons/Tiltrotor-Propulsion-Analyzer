# Primitive Motor Controlling methods to automatically change the RPM of the motor in a pre-defined function.
# Only support for a fixed number of 3 functions: Ramp up, Hold, and Ramp down

from dataclasses import dataclass
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer


@dataclass
class CtrlLinFuncParams:
    time_ms: int = 0  # Duration of the control function
    start_point: float = 0.0  # Initial start point, percentage thrust
    end_point: float = 0.0  # End control point, percentage thrust


class AutoMotCtrlManager(QtCore.QObject):
    # Signals
    updateSampleNum = QtCore.pyqtSignal(int)
    updateMotorSpeed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_update_timer_timeout)

        self.step = 0  # Update step in ms
        self.ramp_up_func = CtrlLinFuncParams()

        self.ramp_down_func = CtrlLinFuncParams()
        self.ramp_down_func.end_point = 0.0

        self.hold_func = CtrlLinFuncParams()
        self.ctrl_func_array = []  # This buffer holds the update values generated from the 3 control functions
        self.ctrl_func_counter = 0

        self.sequence_begin = False
        self.guard_samples = 0

        self.pwm_low = 1100
        self.pwm_high = 1900

    def calculate_sample_num(self, ni_sampling_rate: int):
        time_s = int(round((self.ramp_up_func.time_ms + self.hold_func.time_ms + self.ramp_down_func.time_ms) / 1000.0))
        return (self.guard_samples * 2) + (time_s * ni_sampling_rate)

    def generate(self):
        # Interpolate consts: y = slope * x + intercept, with x = inc_step * step
        slope = (self.pwm_high - self.pwm_low) / 100

        # Ramp up
        intercept = self.ramp_up_func.start_point
        inc_step = (self.ramp_up_func.end_point - self.ramp_up_func.start_point) / (
                self.ramp_up_func.time_ms / self.step)
        ramp_up_update_values = [0] * int(self.ramp_up_func.time_ms / self.step)

        for i in range(len(ramp_up_update_values)):
            ramp_up_update_values[i] = slope * ((i + 1) * inc_step) + intercept

        # Hold/Center
        intercept = self.hold_func.start_point
        inc_step = (self.hold_func.end_point - self.hold_func.start_point) / (self.hold_func.time_ms / self.step)
        hold_update_values = [0] * int(self.hold_func.time_ms / self.step)

        for i in range(len(hold_update_values)):
            hold_update_values[i] = slope * ((i + 1) * inc_step) + intercept

        # Ramp down
        intercept = self.ramp_down_func.start_point
        inc_step = (self.ramp_down_func.end_point - self.ramp_down_func.start_point) \
                   / (self.ramp_down_func.time_ms / self.step)

        ramp_down_update_values = [0] * int(self.ramp_down_func.time_ms / self.step)

        for i in range(len(hold_update_values)):
            hold_update_values[i] = slope * ((i + 1) * inc_step) + intercept

        # Append to control array

        self.ctrl_func_array.extend(ramp_up_update_values)
        self.ctrl_func_array.extend(hold_update_values)
        self.ctrl_func_array.extend(ramp_down_update_values)

    def process(self):
        # Sanity checks
        self.ramp_up_func.start_point = 0.0

        self.hold_func.start_point = self.ramp_up_func.end_point

        self.ramp_down_func.start_point = self.hold_func.end_point

        self.ramp_down_func.end_point = 0.0

        if self.ramp_up_func.time_ms <= 0 or self.ramp_down_func.time_ms <= 0 or self.step <= 0:
            print("Invalid params!")
            return

        sample_num = self.calculate_sample_num()
        if sample_num <= 0:
            print("Invalid number of samples!")
            return

        self.generate()

        self.updateSampleNum.emit(sample_num)

        self.timer.start(self.step)

    def on_update_timer_timeout(self):
        self.updateMotorSpeed.emit(self.ctrl_func_array[self.ctrl_func_counter])
        if self.ctrl_func_counter == (len(self.ctrl_func_array) - 1):
            # Finished, delete array
            self.ctrl_func_array = []
            self.ctrl_func_counter = 0

            self.timer.stop()
