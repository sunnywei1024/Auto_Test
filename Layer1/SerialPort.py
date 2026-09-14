"""
Created on Sep 11, 2026
Chicago
@author: lijiangwei

Based on pyvisa and pyvisa-py, which are open-source libraries for controlling instruments via 
VISA (Virtual Instrument Software Architecture) interface.
This module provides a SerialPort class that simplifies serial communication with instruments, 
supporting various configurations such as baud rate, data bits, parity, stop bits, flow control, and timeouts.
"""

import pyvisa
import time
from enum import Enum


class Parity(Enum):
    """Checksum parity"""
    NONE = pyvisa.constants.Parity.none
    ODD = pyvisa.constants.Parity.odd
    EVEN = pyvisa.constants.Parity.even
    MARK = pyvisa.constants.Parity.mark
    SPACE = pyvisa.constants.Parity.space


class StopBits(Enum):
    """Stop bits"""
    ONE = pyvisa.constants.StopBits.one
    ONE_AND_A_HALF = pyvisa.constants.StopBits.one_and_a_half
    TWO = pyvisa.constants.StopBits.two


class FlowControl(Enum):
    """Flow control"""
    NONE = pyvisa.constants.VI_ASRL_FLOW_NONE
    XON_XOFF = pyvisa.constants.VI_ASRL_FLOW_XON_XOFF
    RTS_CTS = pyvisa.constants.VI_ASRL_FLOW_RTS_CTS
    DTR_DSR = pyvisa.constants.VI_ASRL_FLOW_DTR_DSR


class SerialPort:
    """Use pyvisa to manage serial port communication with instruments."""

    def __init__(self, port, baud_rate=9600, data_bits=8,
                 parity=Parity.NONE, stop_bits=StopBits.ONE,
                 flow_control=FlowControl.NONE, timeout=2000,
                 read_termination='\n', write_termination='\n'):
        """
        Initialize the serial port.

        :param port: Serial port number or ASRL resource string.
                     Can be an integer (e.g., 3 represents ASRL3) or a string (e.g., "COM3" / "ASRL3::INSTR").
        :param baud_rate: Baud rate
        :param data_bits: Data bits (5/6/7/8)
        :param parity: Checksum parity (Parity enum)
        :param stop_bits: Stop bits (StopBits enum)
        :param flow_control: Flow control (FlowControl enum)
        :param timeout: Read/write timeout, unit ms
        :param read_termination: Read termination character
        :param write_termination: Write termination character
        """
        self.port = port
        self.baud_rate = baud_rate
        self.data_bits = data_bits
        self.parity = parity
        self.stop_bits = stop_bits
        self.flow_control = flow_control
        self.timeout = timeout
        self.read_termination = read_termination
        self.write_termination = write_termination

        self.rm = None
        self.instrument = None

    # ---------- Construction ----------
    @staticmethod
    def _build_resource_name(port):
        """Parse the port input and construct the corresponding ASRL resource string."""
        if isinstance(port, int):
            return f"ASRL{port}::INSTR"
        port = str(port).strip()
        # If the input is "COMx", convert it to "ASRLx::INSTR"
        if port.upper().startswith("COM"):
            return f"ASRL{int(port[3:])}::INSTR"
        # 已经是 "ASRLx::INSTR" 形式
        if "::" in port:
            return port
        return f"ASRL{port}::INSTR"

    # ---------- Connection Management ----------
    def open(self):
        """Open the serial port and apply configuration."""
        resource_name = self._build_resource_name(self.port)
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(resource_name)

        # Serial port property configuration
        self.instrument.baud_rate = self.baud_rate
        self.instrument.data_bits = self.data_bits
        self.instrument.parity = self.parity.value
        self.instrument.stop_bits = self.stop_bits.value
        self.instrument.flow_control = self.flow_control.value

        # Timeout and termination characters
        self.instrument.timeout = self.timeout
        self.instrument.read_termination = self.read_termination
        self.instrument.write_termination = self.write_termination
        return self.instrument

    def close(self):
        """Close the serial port and release resources"""
        if self.instrument is not None:
            try:
                self.instrument.close()
            finally:
                self.instrument = None
        if self.rm is not None:
            try:
                self.rm.close()
            finally:
                self.rm = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ---------- Basic Read/Write ----------#
    def write(self, data, is_hex=True):
        """Send data.

        :param data: Data to send, supports the following types:
            - Hexadecimal string: "AA BB 0D 0A" / "AABB0D0A" / "0xAA,0xBB"
            - Integer list/tuple: [0x01, 0x00, 0x0D, 0x0A]
            - bytes
        :param is_hex: True when sending data in hexadecimal format (default),
                       False when sending data as a regular string.
        """
        if self.instrument is None:
            raise RuntimeError("Serial port not open, please call open() first")
        if not is_hex:
            return self.instrument.write(data)
        if isinstance(data, bytes):
            raw = data
        elif isinstance(data, (list, tuple)):
            raw = bytes(self._to_byte(v) for v in data)
        else:
            clean = str(data).replace(" ", "").replace(",", "").replace("0x", "").replace("0X", "")
            raw = bytes.fromhex(clean)
        return self.instrument.write_raw(raw)

    @staticmethod
    def _to_byte(value):
        """Convert a single element to a byte value (0-255)"""
        if isinstance(value, int):
            return value
        if isinstance(value, bytes):
            return value[0]
        return int(str(value), 16)

    def write_hex(self, data):
        """Send data in hexadecimal format (equivalent to write(data, is_hex=True))"""
        return self.write(data, is_hex=True)

    def write_text(self, data):
        """Send data as a regular string (equivalent to write(data, is_hex=False))"""
        return self.write(data, is_hex=False)

    def read(self):
        """Read a line (ending with read_termination)"""
        if self.instrument is None:
            raise RuntimeError("Serial port not open, please call open() first")
        return self.instrument.read()

    def read_raw(self):
        """Read raw bytes (without termination characters)"""
        if self.instrument is None:
            raise RuntimeError("Serial port not open, please call open() first")
        return self.instrument.read_raw()

    def read_bytes(self, count):
        """Read a specified number of bytes"""
        if self.instrument is None:
            raise RuntimeError("Serial port not open, please call open() first")
        return self.instrument.read_bytes(count)

    def query(self, data, delay=None):
        """Send command and return response"""
        if self.instrument is None:
            raise RuntimeError("Serial port not open, please call open() first")
        return self.instrument.query(data, delay=delay)

    # ---------- Dynamic Parameter Setting   ----------
    def set_baud_rate(self, baud_rate):
        self.baud_rate = baud_rate
        if self.instrument is not None:
            self.instrument.baud_rate = baud_rate

    def set_timeout(self, timeout):
        """Set the timeout value, unit is ms"""
        self.timeout = timeout
        if self.instrument is not None:
            self.instrument.timeout = timeout

    def flush(self):
        """Clear the input and output buffers of the serial port."""
        if self.instrument is not None:
            self.instrument.flush(pyvisa.constants.VI_READ_BUF_DISCARD |
                                 pyvisa.constants.VI_WRITE_BUF_DISCARD)

    # ---------- Normal Methods ----------
    @staticmethod
    def list_serial_resources():
        """List all available ASRL serial port resources in the system"""
        rm = pyvisa.ResourceManager()
        resources = [r for r in rm.list_resources() if r.upper().startswith("ASRL")]
        rm.close()
        return resources


if __name__ == "__main__":
    # Print available serial ports
    # num_list = [0x01, 0x00, 0x0d, 0x0a]
    num_list = "0x01, 0x00, 0x0d, 0x0a"
    serial_port = SerialPort.list_serial_resources()
    print("Available serial port resources:", serial_port)
    print("First available serial port:", serial_port[0])
    # 示例: 打开 COM3 (ASRL3), 9600-8-N-1
    ser = SerialPort(port=serial_port[0] if serial_port else None, baud_rate=256000, timeout=2000)
    ser.open()
    print("Serial port opened:", ser.instrument.resource_name)
    # 十六进制发送
    ser.write(num_list, is_hex=True)  # 等价于 "AT\r\n"
    time.sleep(3)
    # 字符串发送
    # ser.write("AT\r\n", is_hex=False)
    # time.sleep(0.5)
    # reply = ser.read()
    reply = ser.read_raw()
    print("Received:", reply)
    ser.flush()
    ser.close()
    print("Serial port closed")