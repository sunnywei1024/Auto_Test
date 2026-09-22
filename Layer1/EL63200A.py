# -*- coding: utf-8 -*-
"""
Created on Sep 22, 2026
Shanghai
@author: lijiangwei

Chroma 63200A Series Programmable DC Electronic Load driver
===========================================================

SCPI based driver, main features:

1. Connect / reset / identify / error query
2. Operating mode setup: CC (constant current) / CV (constant voltage) /
   CR (constant resistance) / CP (constant power) / CCD (constant current
   dynamic) / CCFS (constant current fast slew) / CRCC (CR + CC combined);
   every mode can be set to the high or the low range
3. Input (LOAD) on/off, short circuit (SHORT) simulation, Von / Voff setting
4. Protection setup: OCP / OVP / OPP
5. Measurements: voltage (MEAS:VOLT?) / current (MEAS:CURR?) / power (MEAS:POW?)

Installation::

    pip install pyvisa

A VISA backend (for example NI-VISA) must also be installed on the PC.

VISA resource string examples::

    USB0::0x0A69::0x0879::63210AL01706::INSTR
    TCPIP0::192.168.1.100::5025::SOCKET
    GPIB0::1::INSTR

Notes:
    * Chroma merges the mode and the range into one ``MODE`` command,
      for example ``MODE CCH`` = constant current high range,
      ``MODE CCDL`` = constant current dynamic low range.
    * The load is switched on with ``LOAD ON|OFF``, not with ``INP ON|OFF``.
    * Static levels use L1 / L2, L1 is the default setpoint.
    * ``CURR:DYN:REP`` = 0 means infinite repeat (continuous).
"""

import time
from enum import Enum

import pyvisa
from pyvisa.constants import *


# ==============================================================================
# Enumerations (one to one mapping with the 63200A SCPI parameters)
# ==============================================================================

class LoadMode(Enum):
    """Operating mode + range ``MODE``"""

    CC_LOW = "CCL"          # constant current, low range
    CC_HIGH = "CCH"         # constant current, high range
    CV_LOW = "CVL"          # constant voltage, low range
    CV_HIGH = "CVH"         # constant voltage, high range
    CR_LOW = "CRL"          # constant resistance, low range
    CR_HIGH = "CRH"         # constant resistance, high range
    CP_LOW = "CPL"          # constant power, low range
    CP_HIGH = "CPH"         # constant power, high range
    CCD_LOW = "CCDL"        # constant current dynamic, low range
    CCD_HIGH = "CCDH"       # constant current dynamic, high range
    CCFS_LOW = "CCFSL"      # constant current fast slew, low range
    CCFS_HIGH = "CCFSH"     # constant current fast slew, high range
    CRCC = "CRCC"           # constant resistance + constant current


class LoadRange(Enum):
    """Range ``HIGH`` / ``LOW``"""

    LOW = "LOW"
    HIGH = "HIGH"


# supported base modes (without the range suffix)
_MODES = ("CC", "CV", "CR", "CP", "CCD", "CCFS")


class EL63200A:
    def __init__(self, addr, timeout=5000):
        """
        :param addr: VISA resource string,
                     e.g. 'USB0::0x0A69::0x0879::63210AL01706::INSTR'
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
            raise RuntimeError("electronic load is not connected: %s" % self.addr)
        self.res.write(cmd)

    def _qr(self, cmd):
        """Send a query and return the answer without leading/trailing blanks"""
        if not self.connected:
            raise RuntimeError("electronic load is not connected: %s" % self.addr)
        return self.res.query(cmd).strip()

    @staticmethod
    def _num(value):
        """Format a number as a SCPI parameter string"""
        return "%.6g" % float(value)

    # ------------------------------------------------------------------
    # Basic operations: reset / identify / error / mode
    # ------------------------------------------------------------------
    def reset(self, delay=0.5):
        """Reset the load (*RST + *CLS), delay is the wait time after reset (s)"""
        self._wr('*RST')
        self._wr('*CLS')
        if delay:
            time.sleep(delay)

    def idn(self):
        """Read the instrument identification (*IDN?), e.g. 'Chroma,63210A,...'"""
        return self._qr('*IDN?')

    def get_error(self):
        """Read the next error (SYST:ERR?), returns '+0,"No error"' if none"""
        return self._qr('SYST:ERR?')

    def set_mode(self, mode, high_range=True):
        """
        Set the operating mode (MODE); mode and range are sent as one code.

        :param mode: 'CC' / 'CV' / 'CR' / 'CP' / 'CCD' / 'CCFS' / 'CRCC',
                     a LoadMode member is accepted too (high_range is ignored)
        :param high_range: True for the high range, False for the low range
        :return: the mode code actually sent, e.g. 'CCH'
        """
        if isinstance(mode, LoadMode):
            code = mode.value
            self._wr('MODE %s' % code)
            return code

        code = str(mode).strip().upper()
        if code == 'CRCC':
            self._wr('MODE CRCC')
            return code
        # a mode code carrying a range suffix is accepted as well, e.g. 'CCH' / 'CCDL'
        base = code[:-1] if len(code) > 2 and code[:-1] in _MODES and code[-1] in ('H', 'L') else code
        if base not in _MODES:
            raise ValueError("unsupported mode: %s (use CC/CV/CR/CP/CCD/CCFS/CRCC)" % mode)
        code = base + ('H' if high_range else 'L')
        self._wr('MODE %s' % code)
        return code

    def get_mode(self):
        """Query the current mode (MODE?), e.g. 'CCH'"""
        return self._qr('MODE?')

    def set_range(self, high_range=True):
        """Set the range of the current mode, i.e. send MODE once again"""
        return self.set_mode(self.get_mode(), high_range)

    # ------------------------------------------------------------------
    # Input control (LOAD) / short circuit / Von / Voff
    # ------------------------------------------------------------------
    def load(self, state=True):
        """Turn the load input on / off (LOAD ON|OFF)"""
        self._wr('LOAD %s' % ('ON' if state else 'OFF'))
        return bool(state)

    def load_on(self):
        """Turn the load input on (LOAD ON)"""
        return self.load(True)

    def load_off(self):
        """Turn the load input off (LOAD OFF)"""
        return self.load(False)

    def load_state(self):
        """Query the load input state (LOAD?), True means ON"""
        return self._qr('LOAD?').strip().upper() in ('1', 'ON')

    def set_short(self, state=True):
        """Short circuit simulation on / off (LOAD:SHOR ON|OFF)"""
        self._wr('LOAD:SHOR %s' % ('ON' if state else 'OFF'))

    def set_von(self, voltage):
        """Set the Von turn on voltage (VOLT:ON), unit V"""
        self._wr('VOLT:ON %s' % self._num(voltage))

    def get_von(self):
        """Query the Von turn on voltage (VOLT:ON?), unit V"""
        return float(self._qr('VOLT:ON?'))

    def set_voff(self, voltage):
        """Set the Voff turn off voltage (VOLT:OFF), unit V"""
        self._wr('VOLT:OFF %s' % self._num(voltage))

    def get_voff(self):
        """Query the Voff turn off voltage (VOLT:OFF?), unit V"""
        return float(self._qr('VOLT:OFF?'))

    # ------------------------------------------------------------------
    # Protection setup: OCP / OVP / OPP
    # ------------------------------------------------------------------
    def set_ocp(self, current, state=True):
        """Over current protection (CURR:PROT), current is the threshold (A)"""
        self._wr('CURR:PROT %s' % self._num(current))
        self._wr('CURR:PROT:STAT %s' % ('ON' if state else 'OFF'))

    def set_ovp(self, voltage, state=True):
        """Over voltage protection (VOLT:PROT), voltage is the threshold (V)"""
        self._wr('VOLT:PROT %s' % self._num(voltage))
        self._wr('VOLT:PROT:STAT %s' % ('ON' if state else 'OFF'))

    def set_opp(self, power, state=True):
        """Over power protection (POW:PROT), power is the threshold (W)"""
        self._wr('POW:PROT %s' % self._num(power))
        self._wr('POW:PROT:STAT %s' % ('ON' if state else 'OFF'))

    def clear_protection(self):
        """Clear the protection trip state (PROT:CLE)"""
        self._wr('PROT:CLE')

    # ------------------------------------------------------------------
    # CC constant current mode
    # ------------------------------------------------------------------
    def CC_MODE(self, current=None, high_range=True, slew=None, rise=None, fall=None):
        """
        Set the CC constant current mode and the current level
        (MODE CCH/CCL + CURR:STAT:L1).

        :param current: current setpoint (A), None keeps the old value
        :param high_range: True = high range (CCH), False = low range (CCL)
        :param slew: current slew rate (A/us), optional
        :param rise: current rise time (s), optional
        :param fall: current fall time (s), optional
        :return: the mode code actually sent, e.g. 'CCH'
        """
        code = self.set_mode('CC', high_range)
        if current is not None:
            self.set_current(current)
        if slew is not None:
            self.set_current_slew(slew)
        if rise is not None:
            self.set_current_rise(rise)
        if fall is not None:
            self.set_current_fall(fall)
        return code

    def set_current(self, current, level=1):
        """Set the CC static current (CURR:STAT:L1|L2), unit A"""
        if current < 0:
            raise ValueError("current must not be less than zero")
        self._wr('CURR:STAT:L%d %s' % (level, self._num(current)))
  
    def get_current_setting(self, level=1):
        """Query the CC static current setpoint (CURR:STAT:L1?), unit A"""
        return float(self._qr('CURR:STAT:L%d?' % level))

    def set_current_slew(self, slew):
        """Set the CC current slew rate (CURR:STAT:SLEW), unit A/us"""
        self._wr('CURR:STAT:SLEW %s' % self._num(slew))

    def set_current_rise(self, rise):
        """Set the CC current rise time (CURR:STAT:RISE), unit s"""
        self._wr('CURR:STAT:RISE %s' % self._num(rise))

    def set_current_fall(self, fall):
        """Set the CC current fall time (CURR:STAT:FALL), unit s"""
        self._wr('CURR:STAT:FALL %s' % self._num(fall))

    def set_current_range(self, high_range=True):
        """Set the current range (CURR:RANG HIGH|LOW)"""
        self._wr('CURR:RANG %s' % ('HIGH' if high_range else 'LOW'))

    # ------------------------------------------------------------------
    # CV constant voltage mode
    # ------------------------------------------------------------------
    def CV_MODE(self, voltage=None, current_limit=None, high_range=True):
        """
        Set the CV constant voltage mode
        (MODE CVH/CVL + VOLT:STAT:L1).

        :param voltage: voltage setpoint (V), None keeps the old value
        :param current_limit: current limit in CV mode (A), optional
        :param high_range: True = high range (CVH), False = low range (CVL)
        :return: the mode code actually sent, e.g. 'CVH'
        """
        code = self.set_mode('CV', high_range)
        if voltage is not None:
            self.set_voltage(voltage)
        if current_limit is not None:
            self.set_current_limit(current_limit)
        return code

    def set_voltage(self, voltage, level=1):
        """Set the CV static voltage (VOLT:STAT:L1|L2), unit V"""
        if voltage < 0:
            raise ValueError("voltage must not be less than zero")
        self._wr('VOLT:STAT:L%d %s' % (level, self._num(voltage)))

    def get_voltage_setting(self, level=1):
        """Query the CV static voltage setpoint (VOLT:STAT:L1?), unit V"""
        return float(self._qr('VOLT:STAT:L%d?' % level))

    def set_voltage_range(self, high_range=True):
        """Set the voltage range (VOLT:RANG HIGH|LOW)"""
        self._wr('VOLT:RANG %s' % ('HIGH' if high_range else 'LOW'))

    def set_current_limit(self, current):
        """Set the current limit used in CV mode (CURR:LIM), unit A"""
        self._wr('CURR:LIM %s' % self._num(current))

    def get_current_limit(self):
        """Query the current limit used in CV mode (CURR:LIM?), unit A"""
        return float(self._qr('CURR:LIM?'))

    # ------------------------------------------------------------------
    # CR constant resistance mode
    # ------------------------------------------------------------------
    def CR_MODE(self, resistance=None, high_range=True):
        """
        Set the CR constant resistance mode (MODE CRH/CRL + RES:STAT:L1).

        :param resistance: resistance setpoint (ohm), None keeps the old value
        :param high_range: True = high range (CRH), False = low range (CRL)
        :return: the mode code actually sent, e.g. 'CRH'
        """
        code = self.set_mode('CR', high_range)
        if resistance is not None:
            self.set_resistance(resistance)
        return code

    def set_resistance(self, resistance, level=1):
        """Set the CR static resistance (RES:STAT:L1|L2), unit ohm"""
        if resistance <= 0:
            raise ValueError("resistance must be greater than zero")
        self._wr('RES:STAT:L%d %s' % (level, self._num(resistance)))

    def get_resistance(self, level=1):
        """Query the CR static resistance setpoint (RES:STAT:L1?), unit ohm"""
        return float(self._qr('RES:STAT:L%d?' % level))

    def set_resistance_range(self, high_range=True):
        """Set the resistance range (RES:RANG HIGH|LOW)"""
        self._wr('RES:RANG %s' % ('HIGH' if high_range else 'LOW'))
     

    # ------------------------------------------------------------------
    # CP constant power mode
    # ------------------------------------------------------------------
    def CP_MODE(self, power=None, high_range=True):
        """
        Set the CP constant power mode (MODE CPH/CPL + POW:STAT:L1).

        :param power: power setpoint (W), None keeps the old value
        :param high_range: True = high range (CPH), False = low range (CPL)
        :return: the mode code actually sent, e.g. 'CPH'
        """
        code = self.set_mode('CP', high_range)
        if power is not None:
            self.set_power(power)
        return code

    def set_power(self, power, level=1):
        """Set the CP static power (POW:STAT:L1|L2), unit W"""
        self._wr('POW:STAT:L%d %s' % (level, self._num(power)))

    def get_power_setting(self, level=1):
        """Query the CP static power setpoint (POW:STAT:L1?), unit W"""
        return float(self._qr('POW:STAT:L%d?' % level))

    # ------------------------------------------------------------------
    # CCD constant current dynamic mode
    # ------------------------------------------------------------------
    def CCD_MODE(self, level_low=None, level_high=None, time_low=None,
                 time_high=None, rise=None, fall=None, repeat=None,
                 high_range=True):
        """
        Set the CCD constant current dynamic mode (MODE CCDH/CCDL) and
        configure the dynamic parameters.

        :param level_low: low level current L1 (A), CURR:DYN:L1
        :param level_high: high level current L2 (A), CURR:DYN:L2
        :param time_low: time at the low level T1 (s), CURR:DYN:T1
        :param time_high: time at the high level T2 (s), CURR:DYN:T2
        :param rise: rise time (s), CURR:DYN:RISE
        :param fall: fall time (s), CURR:DYN:FALL
        :param repeat: repeat count, 0 means infinite, CURR:DYN:REP
        :param high_range: True = high range (CCDH), False = low range (CCDL)
        :return: the mode code actually sent, e.g. 'CCDH'
        """
        code = self.set_mode('CCD', high_range)
        if level_low is not None or level_high is not None:
            self.set_dynamic_levels(level_low, level_high)
        if time_low is not None or time_high is not None:
            self.set_dynamic_timing(time_low, time_high)
        if rise is not None or fall is not None:
            self.set_dynamic_slew(rise, fall)
        if repeat is not None:
            self.set_dynamic_repeat(repeat)
        return code

    def set_dynamic_levels(self, level_low=None, level_high=None):
        """Set the two dynamic current levels (CURR:DYN:L1 / CURR:DYN:L2), unit A"""
        if level_low is not None:
            self._wr('CURR:DYN:L1 %s' % self._num(level_low))
        if level_high is not None:
            self._wr('CURR:DYN:L2 %s' % self._num(level_high))

    def get_dynamic_level(self, level=1):
        """Query a dynamic current level (CURR:DYN:L1? / CURR:DYN:L2?), unit A"""
        return float(self._qr('CURR:DYN:L%d?' % level))

    def set_dynamic_timing(self, time_low=None, time_high=None):
        """Set the dynamic times (CURR:DYN:T1 / CURR:DYN:T2), unit s"""
        if time_low is not None:
            self._wr('CURR:DYN:T1 %s' % self._num(time_low))
        if time_high is not None:
            self._wr('CURR:DYN:T2 %s' % self._num(time_high))

    def get_dynamic_time(self, level=1):
        """Query a dynamic time (CURR:DYN:T1? / CURR:DYN:T2?), unit s"""
        return float(self._qr('CURR:DYN:T%d?' % level))

    def set_dynamic_slew(self, rise=None, fall=None):
        """Set the dynamic rise/fall time (CURR:DYN:RISE / CURR:DYN:FALL), unit s"""
        if rise is not None:
            self._wr('CURR:DYN:RISE %s' % self._num(rise))
        if fall is not None:
            self._wr('CURR:DYN:FALL %s' % self._num(fall))

    def set_dynamic_repeat(self, repeat):
        """Set the dynamic repeat count (CURR:DYN:REP), 0 means infinite"""
        self._wr('CURR:DYN:REP %d' % int(repeat))

    # ------------------------------------------------------------------
    # CCFS constant current fast slew mode
    # ------------------------------------------------------------------
    def CCFS_MODE(self, level_low=None, level_high=None, rise=None, fall=None,
                  high_range=True):
        """
        Set the CCFS constant current fast slew mode (MODE CCFSH/CCFSL).

        Note: this mode reuses the static level and slew commands
        (CURR:STAT:L1/L2 + RISE/FALL); the exact behaviour may differ between
        firmware versions, always check the instrument manual.

        :param level_low: level L1 (A)
        :param level_high: level L2 (A)
        :param rise: rise time (s)
        :param fall: fall time (s)
        :param high_range: True = high range (CCFSH), False = low range (CCFSL)
        :return: the mode code actually sent, e.g. 'CCFSH'
        """
        code = self.set_mode('CCFS', high_range)
        if level_low is not None:
            self.set_current(level_low, 1)
        if level_high is not None:
            self.set_current(level_high, 2)
        if rise is not None:
            self.set_current_rise(rise)
        if fall is not None:
            self.set_current_fall(fall)
        return code

    # ------------------------------------------------------------------
    # CRCC constant resistance + constant current mode
    # ------------------------------------------------------------------
    def CRCC_MODE(self, resistance=None, current_limit=None):
        """
        Set the CR + CC combined mode (MODE CRCC).

        :param resistance: resistance setpoint (ohm), RES:CRCC
        :param current_limit: current limit (A), CURR:CRCC
        :return: always 'CRCC'
        """
        self._wr('MODE CRCC')
        if resistance is not None:
            self._wr('RES:CRCC %s' % self._num(resistance))
        if current_limit is not None:
            self._wr('CURR:CRCC %s' % self._num(current_limit))
        return 'CRCC'
    

    # ------------------------------------------------------------------
    # Measurements: read voltage / current / power
    # ------------------------------------------------------------------
    def get_voltage(self):
        """Read the load input voltage (MEAS:VOLT?), unit V"""
        return float(self._qr('MEAS:VOLT?'))

    def get_current(self):
        """Read the load current (MEAS:CURR?), unit A"""
        return float(self._qr('MEAS:CURR?'))

    def get_power(self):
        """Read the load power (MEAS:POW?), unit W"""
        return float(self._qr('MEAS:POW?'))

    def fetch_voltage(self):
        """Read the voltage of the previous measurement (FETC:VOLT?), unit V"""
        return float(self._qr('FETC:VOLT?'))

    def fetch_current(self):
        """Read the current of the previous measurement (FETC:CURR?), unit A"""
        return float(self._qr('FETC:CURR?'))

    def _sample(self, cmd, count=1, delay=0.01):
        """Sample the answer of cmd count times, returns a list of float"""
        count = int(count)
        if count < 1:
            raise ValueError("count must be greater than or equal to 1")
        samples = []
        for index in range(count):
            samples.append(float(self._qr(cmd)))
            if delay and index < count - 1:
                time.sleep(delay)
        return samples

    def read_voltage(self, count=1, delay=0.01):
        """
        Read the voltage repeatedly and compute the statistics
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
        Read the current repeatedly and compute the statistics
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
        Read the power repeatedly and compute the statistics
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
        Read the voltage and the current together and compute the statistics.

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
                print("Close Chroma 63200A successfully!")
                return True
            except Exception:
                if err_cnt < 3:
                    err_cnt += 1
                    time.sleep(3)
                else:
                    print("Close failed!")
                    return False


if __name__ == "__main__":
    ELOAD = EL63200A('USB0::0x0A69::0x0879::63210AL01706::INSTR')
    print(ELOAD.idn())

    # --- CC constant current: 2A, high range, slew 1A/us ---
    ELOAD.reset()
    ELOAD.CC_MODE(2.0, high_range=True, slew=1.0)
    ELOAD.load_on()
    print("CC  V=%.6f V  I=%.6f A  P=%.6f W"
          % (ELOAD.get_voltage(), ELOAD.get_current(), ELOAD.get_power()))
    ELOAD.read_voltage(count=5, delay=0.05)
    ELOAD.read_current(count=5, delay=0.05)

    # --- CV constant voltage: 12V, current limit 5A ---
    ELOAD.CV_MODE(12.0, current_limit=5.0)

    # --- CR constant resistance: 10 ohm ---
    ELOAD.CR_MODE(10.0)

    # --- CP constant power: 100W ---
    ELOAD.CP_MODE(100.0)

    # --- CCD constant current dynamic: 1A / 5A for 1ms each, infinite loop ---
    ELOAD.CCD_MODE(level_low=1.0, level_high=5.0,
                   time_low=0.001, time_high=0.001,
                   rise=1e-5, fall=1e-5, repeat=0)

    ELOAD.load_off()
    ELOAD.close()


