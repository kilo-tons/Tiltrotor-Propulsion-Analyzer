from PyQt5 import QtCore, QtSerialPort
from enum import Enum
import time


# Underlying APIs to encode/decode frames
from PyQt5.QtCore import QTimer


class Function(Enum):
    READ = 0x01
    WRITE = 0x02
    RESPOND = 0x03
    STOP = 0x04
    HEARTBEAT = 0x05


# Copied
def crc16_ccitt(buf: bytes, length: int):
    table = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
        0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
        0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
        0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
        0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
        0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
        0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
        0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
        0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
        0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
        0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
        0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
        0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
        0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
        0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
        0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
        0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
        0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
        0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
        0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
        0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
        0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
        0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
    ]

    # Fixed poly for this implementation
    crc = 0xFFFF

    for i in range(length):
        crc = (crc << 8) ^ table[(crc >> 8) ^ buf[i]]
        crc &= 0xFFFF

    return crc


def mcu_packet_encode(function: Enum, params: int):
    # Function switch
    if function.value == Function.READ:
        # params is polling rate (1 - 10000ms)
        # Sanity check, constraining
        if params > 10000:
            params = 10000

        elif params < 1:
            params = 1

    # elif function.value == Function.WRITE:
    #     # params is PWM high time (1100 - 1900ms)
    #     # Sanity check, constraining
    #     if params > 1900:
    #         params = 1900
    #
    #     elif params < 1100:
    #         params = 1100

    elif function.value == Function.STOP or function.value == Function.HEARTBEAT:
        # Ignore params
        params = 0

    # After constraining, the ms value has the uint16 data type
    # Split to 2 bytes
    params_msb = (params >> 8) & 0xFF
    params_lsb = params & 0xFF

    # Prepare package
    # Format: "BK x xx xx xx CRC16 K"
    buf = bytearray([0x42, 0x4B, function.value, params_msb, params_lsb, 0x00, 0x00, 0x00, 0x00])

    crc16 = crc16_ccitt(buf, len(buf))

    # Split
    crc16_msb = (crc16 >> 8) & 0xFF
    crc16_lsb = crc16 & 0xFF

    buf.extend([crc16_msb, crc16_lsb])

    # Add tail byte
    buf.append(0x4B)

    return buf


def mcu_packet_decode(buf: bytes):
    # Checking
    if not len(buf) == 12:
        return [0, 0.0, False]

    if not (buf[0] == b'B' and buf[1] == b'K' and buf[11] == b'K' and buf[2] == b'\x03'):
        return [0, 0.0, False]

    # Python are storing the buffer in bytes, required to convert to "uint8" variables
    int_buf = list(range(len(buf)))
    for i in int_buf:
        int_buf[i] = int.from_bytes(buf[i], "big")

    crc16 = int_buf[9] << 8 | int_buf[10]

    if not (crc16 == crc16_ccitt(int_buf, 9)):
        return [0, 0.0, False]

    # Begin decoding
    rpm = int_buf[3] << 8 | int_buf[4]
    wind_speed = float((int_buf[5] << 8 | int_buf[6]) / 1000)  # In m/s

    return [rpm, wind_speed, True]


# MCU Serial backend
class MCUSerialManager(QtCore.QObject):
    # Signals
    updateData = QtCore.pyqtSignal(int, float)
    portStatus = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial = QtSerialPort.QSerialPort(self)
        self.timer = QTimer(self)

        # Data holder
        self.data = [0, 0.0]

        self.updateData.connect(self.update_data)

    @QtCore.pyqtSlot(str, int, int)
    def run(self, portname: str, baudrate: int, polling_rate: int):
        self.serial.setBaudRate(baudrate)
        self.serial.setPortName(portname)

        if self.serial.isOpen:
            if not self.serial.open(QtCore.QIODevice.ReadWrite):
                print("Port cannot be opened!")
                return
        else:
            print("Port is in use!")
            return

        # Begin listening
        self.serial.readyRead.connect(self.receive)

        # Write READ command
        buf = mcu_packet_encode(Function.READ, polling_rate)
        self.serial.write(buf)
        self.serial.flush()

        # Send heartbeat
        self.send_heartbeat()

        # Set heartbeat timer
        self.timer.start(1000) # 1s heartbeat
        self.timer.timeout.connect(self.send_heartbeat)

        # Update UI
        self.portStatus.emit(True)

    @QtCore.pyqtSlot(int)
    def on_pwm_changed(self, pwm: int):
        if not self.serial.isOpen:
            return

        buf = mcu_packet_encode(Function.WRITE, pwm)
        self.serial.write(buf)
        self.serial.flush()

    @QtCore.pyqtSlot()
    def receive(self):
        while self.serial.bytesAvailable():
            # This should avoid any delay problem from any major task execution
            if (self.serial.bytesAvailable() % 12) != 0:
                return

            buf = self.serial.readAll()
            [rpm, wind_speed, valid] = mcu_packet_decode(buf)

            if valid:
                # Emit changes
                self.updateData.emit(rpm, wind_speed)

    def return_data(self):
        return self.data

    def update_data(self, rpm: int, wind_speed: float):
        self.data = [rpm, wind_speed]

    @QtCore.pyqtSlot()
    def send_heartbeat(self):
        buf = mcu_packet_encode(Function.HEARTBEAT, 0x00)
        self.serial.write(buf)
        self.serial.flush()

    @QtCore.pyqtSlot()
    def close(self):
        if not self.serial.isOpen:
            print("Port is not open")
            return

        buf = mcu_packet_encode(Function.STOP, 0x00)
        self.serial.write(buf)
        self.serial.flush()

        self.serial.close()

        # Turn off heartbeat timer
        self.timer.stop()

        # Update UI
        self.portStatus.emit(False)

