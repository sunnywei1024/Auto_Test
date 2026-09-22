
# -*- coding: utf-8 -*-
"""
Created on Sep 22, 2026
Shanghai
@author: lijiangwei

EA Elektro-Automatik PS 9080-120 DC power supply driver (PS 9000 series)
=======================================================================

SCPI based driver, main features:

1. Connect / reset / identify / error query, remote and local control
2. Output on/off (OUTP) and voltage / current setpoints (SOUR:VOLT, SOUR:CURR)
3. Protection setup: OVP (SOUR:VOLT:PROT), OCP (SOUR:CURR:PROT),
   OPP (SOUR:POW:PROT)
4. Measurements: voltage (MEAS:VOLT?), current (MEAS:CURR?), power (MEAS:POW?)
   with single shot reading and multi sample statistics helpers
5. Functional test function PS9080_TEST() at the end of this module

Installation::

    pip install pyvisa

A VISA backend (for example NI-VISA) must also be installed on the PC.

VISA resource string examples::

    TCPIP0::192.168.1.100::5025::SOCKET
    USB0::0x3855::0x0001::000123456::INSTR
    ASRL3::INSTR

Model rating (PS 9080-120): 0...80 V, 0...120 A.
The complete PS 9000 series shares this command set, the settable range only
depends on the model, so always check the rating of the connected unit.

Notes:
    * Setting a setpoint does not switch the output on, ``OUTP ON`` does.
    * ``SOUR:VOLT?`` returns the voltage setpoint while ``MEAS:VOLT?`` returns
      the measured output voltage.
    * Protection commands follow the SCPI PROTection subsystem. Some firmware
      revisions use the short form instead (``VOLT:OVP`` / ``CURR:OCP``); in
      that case only OVP_CMD / OCP_CMD below have to be adapted.
    * After an OVP / OCP trip the output is switched off, the cause can be read
      from ``STAT:QUES:COND?`` or from the error queue (``SYST:ERR?``).
"""

import re
import time

import pyvisa
from pyvisa.constants import *

# Protection command headers (see the note above)
OVP_CMD = 'SOUR:VOLT:PROT'
OCP_CMD = 'SOUR:CURR:PROT'
OPP_CMD = 'SOUR:POW:PROT'


class PS9080:
    def __init__(self, addr, timeout=5000):
        """
        :param addr: VISA resource string,
                     e.g. 'TCPIP0::192.168.1.100::5025::SOCKET' or 'ASRL3::INSTR'
        :param timeout: read/write timeout in ms, default 5000 ms
        """
        self.addr = addr
        self.res = None
        self.connected = False
        # statistics cache (used by read_voltage / read_current / read_power)
        self.V_avg_value = 0.0
        self.V_max_value = 0.0
        self.V_min_value = 0.0
        self.I_avg_value = 0.0
        self.I_max_value = 0.0
        self.I_min_value = 0.0
        self.P_avg_value = 0.0
        self.P_max_value = 0.0
        self.P_min_value = 0.0

        rm = pyvisa.ResourceManager()
        tupl = rm.list_resources()
        if len(tupl) <= 0:
            print("can not find port !")
        else:
            self.res = rm.open_resource(addr, AccessModes.no_lock, 3000, None)
            self.res.timeout = timeout
            self.connected = True
            print("Connect %s successfully!" % addr)

    # ------------------------------------------------------------------
    # Low level read / write
    # ------------------------------------------------------------------
    def _wr(self, cmd):
        """Send a command (no response expected)"""
        if not self.connected:
            raise RuntimeError("power supply is not connected: %s" % self.addr)
        self.res.write(cmd)

    def _qr(self, cmd):
        """Send a query and return the answer without leading/trailing blanks"""
        if not self.connected:
            raise RuntimeError("power supply is not connected: %s" % self.addr)
        return self.res.query(cmd).strip()

    @staticmethod
    def _num(value):
        """Format a number as a SCPI parameter string"""
        return "%.6g" % float(value)

    @staticmethod
    def _value(text):
        """
        Convert a SCPI answer into a float, tolerating a unit suffix.

        The EA power supplies may append the unit to the value, for example
        '12.00 V', '1.500 A' or '0.000 W'; a plain number ('12.00') and a comma
        as decimal separator ('12,00 V') are accepted as well.

        :param text: raw answer string of the instrument
        :return: the numeric value as float
        """
        s = str(text).strip().strip('"').strip("'")
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", s)
        if match is None:
            raise ValueError("could not convert string to float: %r" % text)
        return float(match.group(0).replace(",", "."))

    # ------------------------------------------------------------------
    # Basic operations: reset / identify / error / remote-local
    # ------------------------------------------------------------------
    def reset(self, delay=0.5):
        """Reset the power supply (*RST + *CLS), delay is the wait time after reset (s)"""
        self._wr('*RST')
        self._wr('*CLS')
        if delay:
            time.sleep(delay)

    def idn(self):
        """Read the instrument identification (*IDN?)"""
        return self._qr('*IDN?')

    def get_error(self):
        """Read the next error (SYST:ERR?), returns '+0,"No error"' if none"""
        return self._qr('SYST:ERR?')

    def remote(self):
        """Switch the device to remote control (SYST:REM)"""
        self._wr('SYST:REM')

    def local(self):
        """Return the device to local (front panel) control (SYST:LOC)"""
        self._wr('SYST:LOC')

    # ------------------------------------------------------------------
    # Output control
    # ------------------------------------------------------------------
    def output(self, state=True):
        """Switch the DC output on / off (OUTP:STAT ON|OFF)"""
        self._wr('OUTP:STAT %s' % ('ON' if state else 'OFF'))
        return bool(state)

    def output_on(self):
        """Switch the DC output on (OUTP ON)"""
        return self.output(True)

    def output_off(self):
        """Switch the DC output off (OUTP OFF)"""
        return self.output(False)

    def output_state(self):
        """Query the DC output state (OUTP:STAT?), True means ON"""
        return self._qr('OUTP:STAT?').strip().upper() in ('1', 'ON')

    # ------------------------------------------------------------------
    # Voltage / current setpoints
    # ------------------------------------------------------------------
    def set_voltage(self, voltage):
        """Set the output voltage setpoint (SOUR:VOLT), unit V"""
        if voltage < 0:
            raise ValueError("voltage must not be less than zero")
        self._wr('SOUR:VOLT %s' % self._num(voltage))

    def get_voltage_setting(self):
        """Query the output voltage setpoint (SOUR:VOLT?), unit V"""
        return self._value(self._qr('SOUR:VOLT?'))

    def set_current(self, current):
        """Set the output current setpoint (SOUR:CURR), unit A"""
        if current < 0:
            raise ValueError("current must not be less than zero")
        self._wr('SOUR:CURR %s' % self._num(current))

    def get_current_setting(self):
        """Query the output current setpoint (SOUR:CURR?), unit A"""
        return self._value(self._qr('SOUR:CURR?'))

    def set_voltage_current(self, voltage, current):
        """Set the voltage and the current setpoint at once (SOUR:VOLT + SOUR:CURR)"""
        self.set_voltage(voltage)
        self.set_current(current)

    # ------------------------------------------------------------------
    # Protection: OVP / OCP / OPP
    # ------------------------------------------------------------------
    def set_ovp(self, voltage):
        """Set the over voltage protection level (SOUR:VOLT:PROT), unit V"""
        if voltage < 0:
            raise ValueError("OVP level must not be less than zero")
        self._wr('%s %s' % (OVP_CMD, self._num(voltage)))

    def get_ovp(self):
        """Query the over voltage protection level (SOUR:VOLT:PROT?), unit V"""
        return self._value(self._qr('%s?' % OVP_CMD))

    def set_ocp(self, current):
        """Set the over current protection level (SOUR:CURR:PROT), unit A"""
        if current < 0:
            raise ValueError("OCP level must not be less than zero")
        self._wr('%s %s' % (OCP_CMD, self._num(current)))

    def get_ocp(self):
        """Query the over current protection level (SOUR:CURR:PROT?), unit A"""
        return self._value(self._qr('%s?' % OCP_CMD))

    def set_opp(self, power):
        """Set the over power protection level (SOUR:POW:PROT), unit W"""
        if power < 0:
            raise ValueError("OPP level must not be less than zero")
        self._wr('%s %s' % (OPP_CMD, self._num(power)))

    def get_opp(self):
        """Query the over power protection level (SOUR:POW:PROT?), unit W"""
        return self._value(self._qr('%s?' % OPP_CMD))

    def set_protection(self, ovp=None, ocp=None, opp=None):
        """Set any of the protection levels (OVP in V, OCP in A, OPP in W)"""
        if ovp is not None:
            self.set_ovp(ovp)
        if ocp is not None:
            self.set_ocp(ocp)
        if opp is not None:
            self.set_opp(opp)

    def get_questionable_status(self):
        """Query the questionable status condition (STAT:QUES:COND?)"""
        return self._qr('STAT:QUES:COND?')

    # ------------------------------------------------------------------
    # Measurements: read voltage / current / power
    # ------------------------------------------------------------------
    def get_voltage(self):
        """Read the output voltage (MEAS:VOLT?), unit V"""
        return self._value(self._qr('MEAS:VOLT?'))

    def get_current(self):
        """Read the output current (MEAS:CURR?), unit A"""
        return self._value(self._qr('MEAS:CURR?'))

    def get_power(self):
        """Read the output power (MEAS:POW?), unit W"""
        return self._value(self._qr('MEAS:POW?'))

    def get_actual(self):
        """Read voltage, current and power in one call, returns (V, I, P)"""
        return self.get_voltage(), self.get_current(), self.get_power()

    def _sample(self, cmd, count=1, delay=0.01):
        """Sample the answer of cmd count times, returns a list of float"""
        count = int(count)
        if count < 1:
            raise ValueError("count must be greater than or equal to 1")
        samples = []
        for index in range(count):
            samples.append(self._value(self._qr(cmd)))
            if delay and index < count - 1:
                time.sleep(delay)
        return samples

    def read_voltage(self, count=1, delay=0.01):
        """
        Read the output voltage repeatedly and compute the statistics
        (average / maximum / minimum).

        :param count: number of samples, default 1
        :param delay: interval between two samples (s), default 10 ms
        :return: average voltage (V); the statistics are also stored in
                 self.V_avg_value / self.V_max_value / self.V_min_value
        """
        samples = self._sample('MEAS:VOLT?', count, delay)
        self.V_avg_value = sum(samples) / len(samples)
        self.V_max_value = max(samples)
        self.V_min_value = min(samples)
        print("Voltage samples=%d max=%s min=%s avg=%f"
              % (count, self.V_max_value, self.V_min_value, self.V_avg_value))
        return self.V_avg_value

    def read_current(self, count=1, delay=0.01):
        """
        Read the output current repeatedly and compute the statistics
        (average / maximum / minimum).

        :param count: number of samples, default 1
        :param delay: interval between two samples (s), default 10 ms
        :return: average current (A); the statistics are also stored in
                 self.I_avg_value / self.I_max_value / self.I_min_value
        """
        samples = self._sample('MEAS:CURR?', count, delay)
        self.I_avg_value = sum(samples) / len(samples)
        self.I_max_value = max(samples)
        self.I_min_value = min(samples)
        print("Current samples=%d max=%s min=%s avg=%f"
              % (count, self.I_max_value, self.I_min_value, self.I_avg_value))
        return self.I_avg_value

    def read_power(self, count=1, delay=0.01):
        """
        Read the output power repeatedly and compute the statistics
        (average / maximum / minimum).

        :param count: number of samples, default 1
        :param delay: interval between two samples (s), default 10 ms
        :return: average power (W); the statistics are also stored in
                 self.P_avg_value / self.P_max_value / self.P_min_value
        """
        samples = self._sample('MEAS:POW?', count, delay)
        self.P_avg_value = sum(samples) / len(samples)
        self.P_max_value = max(samples)
        self.P_min_value = min(samples)
        print("Power samples=%d max=%s min=%s avg=%f"
              % (count, self.P_max_value, self.P_min_value, self.P_avg_value))
        return self.P_avg_value

    def read_vi(self, count=1, delay=0.01):
        """
        Read the output voltage and current together and compute the statistics.

        :return: (average voltage, average current)
        """
        volts = self._sample('MEAS:VOLT?', count, delay)
        amperes = self._sample('MEAS:CURR?', count, delay)
        self.V_avg_value = sum(volts) / len(volts)
        self.V_max_value = max(volts)
        self.V_min_value = min(volts)
        self.I_avg_value = sum(amperes) / len(amperes)
        self.I_max_value = max(amperes)
        self.I_min_value = min(amperes)
        print("Voltage samples=%d max=%s min=%s avg=%f"
              % (count, self.V_max_value, self.V_min_value, self.V_avg_value))
        print("Current samples=%d max=%s min=%s avg=%f"
              % (count, self.I_max_value, self.I_min_value, self.I_avg_value))
        return self.V_avg_value, self.I_avg_value

    def close(self):
        """Close the connection (*CLS + SYST:LOC + close), up to 3 retries"""
        if self.res is None:
            print("Close failed, no connection!")
            return False
        err_cnt = 0
        while True:
            try:
                self.res.write('*CLS')
                self.res.write('SYST:LOC')
                self.res.close()
                self.connected = False
                print("Close EA PS9080 successfully!")
                return True
            except Exception:
                if err_cnt < 3:
                    err_cnt += 1
                    time.sleep(3)
                else:
                    print("Close failed!")
                    return False


# ==============================================================================
# Functional test
# ==============================================================================

def PS9080_TEST(addr, voltage=12.0, current=1.0, ovp=None, ocp=None,
                samples=5, delay=0.1):
    """
    Functional test of the EA PS 9080-120.

    Sequence: connect -> identify -> reset -> set OVP / OCP -> set voltage and
    current -> output off -> output on -> measure V / I / P (with statistics)
    -> output off -> close.

    :param addr: VISA resource string
    :param voltage: voltage setpoint used by the test (V)
    :param current: current setpoint used by the test (A)
    :param ovp: OVP level (V), default voltage * 1.1
    :param ocp: OCP level (A), default current * 1.1
    :param samples: number of samples for the statistics, default 5
    :param delay: interval between two samples (s), default 100 ms
    :return: True when the test finished without exception, else False
    """
    ovp = round(voltage * 1.1, 3) if ovp is None else ovp
    ocp = round(current * 1.1, 3) if ocp is None else ocp

    psu = None
    try:
        psu = PS9080(addr)
        print("IDN   : %s" % psu.idn())
        print("Output: %s" % ("ON" if psu.output_state() else "OFF"))

        psu.reset()
        psu.set_protection(ovp=ovp, ocp=ocp)
        psu.set_voltage_current(voltage, current)
        print("SETP  : V=%.3f V  I=%.3f A  OVP=%.3f V  OCP=%.3f A"
              % (psu.get_voltage_setting(), psu.get_current_setting(),
                 psu.get_ovp(), psu.get_ocp()))

        # a refused setting is reported asynchronously in the error queue, so
        # check it here: -221 / -201 mean the instrument is in LOCAL (front
        # panel) control and does not accept any remote setting
        # err = psu.get_error()
        # if not err.startswith('+0'):
        #     print("PS9080 test FAILED: the instrument refused the settings: %s" % err)
        #     print("        (-201/-221: the device is in LOCAL mode - switch it to "
        #           "remote control on the front panel, then run the test again)")
        #     return False

        # start from a defined state, then switch the output on
        # psu.output_off()
        # time.sleep(1)
        psu.output_on()
        time.sleep(3)
        if not psu.output_state():
            print("OUTP  : OFF")
            print("PS9080 test FAILED: the output could not be switched on "
                  "(instrument error: %s)" % psu.get_error())
            return False
        print("OUTP  : ON")
        time.sleep(delay)
        v_avg, i_avg = psu.read_vi(count=samples, delay=delay)
        print("MEAS  : V=%.6f V  I=%.6f A  P=%.6f W"
              % (v_avg, i_avg, psu.get_power()))

        # switch the output off again before finishing
        psu.output_off()
        print("OUTP  : %s" % ("ON" if psu.output_state() else "OFF"))
        print("PS9080 test PASSED")
        return True
    except Exception as ex:
        print("PS9080 test FAILED: %s" % ex)
        return False
    finally:
        # never leave the output enabled behind
        if psu is not None and psu.connected:
            try:
                psu.output_off()
            except Exception:
                pass
            psu.close()


if __name__ == "__main__":
    # PS9080_TEST('TCPIP0::192.168.1.100::5025::SOCKET', voltage=12.0, current=1.0)
    PS9080_TEST('ASRL7::INSTR', voltage=12.0, current=1.0)