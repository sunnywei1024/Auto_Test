# -*- coding: UTF-8 -*-
"""
Created on Sep 30, 2026
Shanghai
@author: lijiangwei

Keysight DAQ973A data acquisition system driver.

The DAQ973A is a 3-slot mainframe with a 6.5 digit DMM (up to 120 channels once
multiplexer modules are fitted).  Its measurement commands belong to the Keysight
Truevolt DMM family (the same command set as the Keysight 34461A already used in
this project), extended by the ROUTe subsystem which switches channels and runs
a channel scan.

Implemented features
--------------------
Measurement functions (MEASure / CONFigure / SENSe)

    name  token      command          measured quantity
    DCV   'VOLT:DC'  MEAS:VOLT:DC?    DC voltage
    ACV   'VOLT:AC'  MEAS:VOLT:AC?    AC voltage (true RMS)
    DCI   'CURR:DC'  MEAS:CURR:DC?    DC current
    ACI   'CURR:AC'  MEAS:CURR:AC?    AC current
    RES   'RES'      MEAS:RES?        2-wire resistance
    FRES  'FRES'     MEAS:FRES?       4-wire resistance
    FREQ  'FREQ'     MEAS:FREQ?       frequency
    PER   'PER'      MEAS:PER?        period
    TEMP  'TEMP'     MEAS:TEMP?       temperature (RTD / thermistor / thermocouple)  
    CAP   'CAP'      MEAS:CAP?        capacitance
    CONT  'CONT'     MEAS:CONT?       continuity
    DIOD  'DIOD'     MEAS:DIO?        diode

Channel and scan (ROUTe)

    ROUT:OPEN / ROUT:CLOS (@ch)      open / close the relays of a channel
    ROUT:SCAN (@ch_list)             scan list
    ROUT:SCAN:INT <s>                interval between two scan sweeps
    ROUT:MON:CHAN / ROUT:MON:STAT    monitor one channel
    ROUT:CHAN:LAB <text>,(@ch)       channel label

Trigger and sample (TRIGger / SAMPle)

    TRIG:SOUR / TRIG:COUN / TRIG:DEL / TRIG:SLOP / TRIG:TIM
    SAMP:COUN / SAMP:SOUR / SAMP:TIM

Data (READ? / FETCh? / DATA)

    READ? / FETC? / DATA:LAST? / DATA:POIN? / DATA:REMove? / INIT / ABOR

Math and limits (CALCulate)

    CALC:AVER:STAT / CALC:AVER:COUN     statistics (min / max / average / sdev)
    CALC:NULL:STAT / CALC:NULL:VAL      offset (null)
    CALC:LIM:UPPer / LOWer / STATe      alarm limits per channel

Digital I/O and totalizer (DAQM907A module)

    SENS:DIG:DATA:BYTE? / SOUR:DIG:DATA:BYTE / SOUR:DIG:ENAB
    SENS:TOT (totalizer reading / reset)

System and format

    *IDN? / *RST / *CLS / *OPC? / SYST:ERR? / SYST:BEEP / SYST:LOC|REM
    SYST:DATE / SYST:TIME / FORM:DATA (ASC|REAL) / UNIT:TEMP (C|F|K)

Notes
-----
* The channel argument is always a channel number (101), a channel list
  ([101, 102]) or a ready made SCPI list ('(@101,102)').
* Measurement and configuration commands accept the channel list as their last
  parameter, so a channel can carry its own function and range.
* The DAQM907A digital I/O and totalizer tokens depend on the fitted module;
  validate them once on the bench with check_error().
"""

import time
from enum import Enum

import pyvisa
from pyvisa.constants import *


class MeasurementFunction(str, Enum):
    """Measurement functions of the DAQ973A (MEASure / CONFigure / SENSe token)."""
    DC_VOLTAGE = 'VOLT:DC'
    AC_VOLTAGE = 'VOLT:AC'
    DC_CURRENT = 'CURR:DC'
    AC_CURRENT = 'CURR:AC'
    RESISTANCE = 'RES'
    RESISTANCE_4W = 'FRES'
    FREQUENCY = 'FREQ'
    PERIOD = 'PER'
    TEMPERATURE = 'TEMP'
    CAPACITANCE = 'CAP'
    CONTINUITY = 'CONT'
    DIODE = 'DIOD'


class TriggerSource(str, Enum):
    """TRIGger:SOURce values."""
    IMMEDIATE = 'IMM'
    BUS = 'BUS'
    EXTERNAL = 'EXT'
    TIMER = 'TIM'
    CHANNEL = 'CHAN'
    ALARM1 = 'ALAR1'
    ALARM2 = 'ALAR2'
    ALARM3 = 'ALAR3'
    ALARM4 = 'ALAR4'


class SampleSource(str, Enum):
    """SAMPle:SOURce values."""
    IMMEDIATE = 'IMM'
    TIMER = 'TIM'


class TriggerSlope(str, Enum):
    """TRIGger:SLOPe values (external trigger edge)."""
    POSITIVE = 'POS'
    NEGATIVE = 'NEG'


class AutoZero(str, Enum):
    """SENSe:<function>:ZERO:AUTO values."""
    ON = 'ON'
    OFF = 'OFF'
    ONCE = 'ONCE'


class TemperatureTransducer(str, Enum):
    """SENSe:TEMPerature:TRANsducer values."""
    RTD = 'RTD'                  # 2-wire RTD
    FRTD = 'FTH'                 # 4-wire RTD
    THERMISTOR = 'THER'          # 2.2 kOhm / 5 kOhm / 10 kOhm thermistor
    THERMOCOUPLE = 'TC'          # thermocouple


class ThermocoupleType(str, Enum):
    """SENSe:TEMPerature:TCouple:TYPE values."""
    B = 'B'
    E = 'E'
    J = 'J'
    K = 'K'
    N = 'N'
    R = 'R'
    S = 'S'
    T = 'T'


class RTDType(str, Enum):
    """SENSe:TEMPerature:RTD:TYPE values (alpha = 0.00385 / 0.00391)."""
    ALPHA_385 = '85'
    ALPHA_391 = '91'


class ThermistorType(str, Enum):
    """SENSe:TEMPerature:THERMistor:TYPE values (nominal resistance in Ohm)."""
    OHM_2252 = '2252'
    OHM_5000 = '5000'
    OHM_10000 = '10000'


class TemperatureUnit(str, Enum):
    """UNIT:TEMPerature values."""
    CELSIUS = 'C'
    FAHRENHEIT = 'F'
    KELVIN = 'K'


class DataFormat(str, Enum):
    """FORMat:DATA values."""
    ASCII = 'ASC'
    REAL = 'REAL'


class ByteOrder(str, Enum):
    """FORMat:BORDer values."""
    NORMAL = 'NORM'
    SWAPPED = 'SWAP'


class DAQ973A:
    """Keysight DAQ973A data acquisition system (3-slot mainframe, 6.5 digit DMM)."""

    # ------------------------------------------------------------------ connect

    def __init__(self, addr, timeout=5000, reset=False):
        """Open the connection.

        :param addr:    VISA resource string, e.g.
                        'USB0::0x2A8D::0x0301::MY12345678::INSTR'
        :param timeout: I/O timeout in milliseconds
        :param reset:   send *RST when True
        """
        self.res = None
        self.connected = False
        rm = pyvisa.ResourceManager()
        tupl = rm.list_resources()
        if len(tupl) <= 0:
            print("can not find port !")
            return
        self.res = rm.open_resource(addr, AccessModes.no_lock, 3000, None)
        self.res.timeout = timeout
        self.connected = True
        print("Connect %s successfully!" % addr)
        if reset:
            self.reset()

    def close(self):
        """Close the connection (*CLS + SYST:LOC + close), up to 3 retries."""
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
                print("Close Keysight DAQ973A successfully!")
                return True
            except Exception:
                if err_cnt < 3:
                    err_cnt += 1
                    time.sleep(3)
                else:
                    print("Close failed!")
                    return False

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _func(function):
        """Reduce a MeasurementFunction (or a plain string) to a SCPI token."""
        if isinstance(function, Enum):
            return function.value
        return str(function).upper()

    @staticmethod
    def _token(value, enum_class, label='value'):
        """Validate an Enum member / member name / SCPI token and return the token.

        'THERMOCOUPLE', 'thermocouple', 'TC' and
        TemperatureTransducer.THERMOCOUPLE all give 'TC'.  An unknown token
        raises ValueError, so a typo is caught before it reaches the instrument
        (there it would only end up in the error queue).
        """
        if isinstance(value, enum_class):
            return value.value
        text = str(value).strip().upper()
        for member in enum_class:
            if text == member.value.upper() or text == member.name.upper():
                return member.value
        allowed = ', '.join('%s=%s' % (m.name, m.value) for m in enum_class)
        raise ValueError("DAQ973A: unknown %s '%s' (allowed: %s)"
                         % (label, value, allowed))

    @staticmethod
    def _number(value):
        """Format a numeric / keyword parameter (AUTO, MIN, MAX, DEF pass through)."""
        if value is None:
            return None
        if isinstance(value, str):
            return value.upper()
        return '%.12g' % float(value)

    @staticmethod
    def _channel_text(channel):
        """Return a SCPI channel list, e.g. '(@101,102)', for int / list / text."""
        if channel is None:
            return None
        if isinstance(channel, (list, tuple, set)):
            return '(@%s)' % ','.join(str(c) for c in channel)
        text = str(channel).strip()
        if text.startswith('('):
            return text 
        return '(@%s)' % text

    def _build(self, header, args=(), channel=None):
        """Build '<header> <arg>,<arg>,(@<ch_list>)' omitting the trailing gaps."""
        parts = [self._number(a) for a in args]
        while parts and parts[-1] is None:
            parts.pop()
        tail = ','.join('' if p is None else p for p in parts)
        ch = self._channel_text(channel)
        if ch:
            tail = (tail + ',') if tail else ''
            tail += ch
        return header + (' ' + tail if tail else '')

    @staticmethod
    def _parse_values(text):
        """Split a comma separated answer into floats (scalar when there is one)."""
        if text is None:
            return None
        items = [t.strip().strip('"') for t in str(text).split(',') if t.strip() != '']
        values = []
        for item in items:
            try:
                values.append(float(item))
            except ValueError:
                values.append(item)
        if len(values) == 1:
            return values[0]
        return values

    def _write(self, cmd):
        self.res.write(cmd)
        return cmd

    def _read(self, cmd):
        """Write a command which produces an answer, then read that answer."""
        self.res.write(cmd)
        return self.res.read().strip()

    def _query(self, cmd):
        return self.res.query(cmd).strip()

    def _query_try(self, cmd):
        """Query which may not be offered by the firmware -> None instead of a timeout."""
        try:
            return self._query(cmd)
        except Exception:
            return None

    def _query_num(self, cmd):
        """Query a numeric answer, tolerating a unit suffix ('5.00000000E+00')."""
        text = self._query_try(cmd)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            value = self._parse_values(text)
            return value if isinstance(value, float) else None

    # ------------------------------------------------------------- error queue

    def check_error(self, label=''):
        """Read the error queue once; print and return the error, None when clean."""
        answer = self._query('SYST:ERR?')
        if answer.startswith('+0') or answer.startswith('0'):
            return None
        print("DAQ973A error%s: %s"
              % ((' (%s)' % label) if label else '', answer))
        return answer

    def read_all_errors(self, limit=20):
        """Drain the error queue and return the list of error strings."""
        errors = []
        for _ in range(limit):
            answer = self._query('SYST:ERR?')
            if answer.startswith('+0') or answer.startswith('0'):
                break
            errors.append(answer)
        for item in errors:
            print("DAQ973A error: %s" % item)
        return errors

    # ------------------------------------------------------------------- system

    def idn(self):
        """*IDN? -> identification string."""
        return self._query('*IDN?')

    def reset(self):
        """*RST + *CLS, then wait until the instrument is ready (*OPC?)."""
        self._write('*RST')
        self._write('*CLS')
        try:
            self._query('*OPC?')
        except Exception:
            pass
        return True

    def clear(self):
        """*CLS - clear the status registers and the error queue."""
        return self._write('*CLS')

    def wait_ready(self, timeout=None):
        """*OPC? - block until all pending operations are finished."""
        old = self.res.timeout
        if timeout is not None:
            self.res.timeout = timeout
        try:
            self._query('*OPC?')
            return True
        finally:
            self.res.timeout = old

    def self_test(self):
        """*TST? - run the internal self test ('+0' means passed)."""
        return self._query('*TST?')

    def set_local(self):
        """SYST:LOC - return the front panel control to the operator."""
        return self._write('SYST:LOC')

    def set_remote(self):
        """SYST:REM - lock the front panel (remote control)."""
        return self._write('SYST:REM')

    def beep(self, seconds=None):
        """SYST:BEEP - beep once (or for the given number of seconds)."""
        if seconds is None:
            return self._write('SYST:BEEP')
        return self._write('SYST:BEEP %s' % self._number(seconds))

    def get_date(self):
        """SYST:DATE? -> (year, month, day)."""
        return self._parse_values(self._query('SYST:DATE?'))

    def set_date(self, year, month, day):
        """SYST:DATE <year>,<month>,<day>."""
        return self._write('SYST:DATE %d,%d,%d' % (int(year), int(month), int(day)))

    def get_time(self):
        """SYST:TIME? -> (hour, minute, second)."""
        return self._parse_values(self._query('SYST:TIME?'))

    def set_time(self, hour, minute, second):
        """SYST:TIME <hour>,<minute>,<second>."""
        return self._write('SYST:TIME %d,%d,%d' % (int(hour), int(minute), int(second)))

    # -------------------------------------------------------------- measurement

    def configure(self, function, range=None, resolution=None, channel=None):
        """CONFigure:<function> [<range>][,<resolution>][,(@<ch_list>)].

        :param function:   MeasurementFunction member or SCPI token
        :param range:      numeric value or 'AUTO' / 'MIN' / 'MAX' / 'DEF'
        :param resolution: numeric value or 'MIN' / 'MAX' / 'DEF'
        :param channel:    channel number, channel list or '(@..)' text
        """
        return self._write(self._build('CONF:%s' % self._func(function),
                                       (range, resolution), channel))

    def get_configuration(self):
        """CONF? -> the function which was configured last."""
        return self._query_try('CONF?')

    def measure(self, function, range=None, resolution=None, channel=None):
        """MEASure:<function>? - configure, measure once and return the reading(s).

        Returns a float for a single channel, a list of floats for a channel list
        and None when the instrument reports an invalid reading.
        """
        answer = self._read(self._build('MEAS:%s?' % self._func(function),
                                        (range, resolution), channel))
        return self._parse_values(answer)

    # single shot convenience wrappers -----------------------------------------

    def measure_dc_voltage(self, range=None, resolution=None, channel=None):
        """DC voltage (VOLT:DC) - up to 300 V on the module inputs."""
        return self.measure(MeasurementFunction.DC_VOLTAGE, range, resolution, channel)

    def measure_ac_voltage(self, range=None, resolution=None, channel=None):
        """AC voltage (VOLT:AC), true RMS."""
        return self.measure(MeasurementFunction.AC_VOLTAGE, range, resolution, channel)

    def measure_dc_current(self, range=None, resolution=None, channel=None):
        """DC current (CURR:DC)."""
        return self.measure(MeasurementFunction.DC_CURRENT, range, resolution, channel)

    def measure_ac_current(self, range=None, resolution=None, channel=None):
        """AC current (CURR:AC)."""
        return self.measure(MeasurementFunction.AC_CURRENT, range, resolution, channel)

    def measure_resistance(self, range=None, resolution=None, channel=None):
        """2-wire resistance (RES) - the channel HI/LO pair carries the excitation."""
        return self.measure(MeasurementFunction.RESISTANCE, range, resolution, channel)

    def measure_4wire_resistance(self, range=None, resolution=None, channel=None):
        """4-wire resistance (FRES) - uses the channel pair and its sense pair."""
        return self.measure(MeasurementFunction.RESISTANCE_4W, range, resolution, channel)

    def measure_frequency(self, range=None, resolution=None, channel=None):
        """Frequency (FREQ) of the signal on the channel."""
        return self.measure(MeasurementFunction.FREQUENCY, range, resolution, channel)

    def measure_period(self, range=None, resolution=None, channel=None):
        """Period (PER) of the signal on the channel."""
        return self.measure(MeasurementFunction.PERIOD, range, resolution, channel)

    def measure_temperature(self, transducer=None, range=None, resolution=None,
                            channel=None):
        """Temperature (TEMP) - RTD / thermistor / thermocouple.

        The transducer is normally configured per channel with
        set_temperature_transducer() and set_thermocouple_type(); it can also be
        given here as the first parameter of the measurement command
        (MEAS:TEMP? <type>,<range>,<resolution>,(@<ch_list>)).
        """
        token = self._func(transducer) if transducer is not None else None
        answer = self._read(self._build('MEAS:TEMP?', (token, range, resolution),
                                        channel))
        return self._parse_values(answer)

    def measure_capacitance(self, range=None, resolution=None, channel=None):
        """Capacitance (CAP)."""
        return self.measure(MeasurementFunction.CAPACITANCE, range, resolution, channel)

    def measure_continuity(self, channel=None):
        """Continuity (CONT) - 1 means the circuit is closed."""
        return self.measure(MeasurementFunction.CONTINUITY, None, None, channel)

    def measure_diode(self, channel=None):
        """Diode test (DIO) - forward voltage in volts."""
        return self.measure(MeasurementFunction.DIODE, None, None, channel)

    # sample / trigger / data --------------------------------------------------

    def set_sample_count(self, count):
        """SAMP:COUN <count> - readings taken per trigger."""
        return self._write('SAMP:COUN %d' % int(count))

    def get_sample_count(self):
        """SAMP:COUN? -> readings per trigger."""
        return self._query_num('SAMP:COUN?')

    def set_sample_source(self, source):
        """SAMP:SOUR {IMM|TIM} - immediate or interval sampling."""
        return self._write('SAMP:SOUR %s' % (source.value if isinstance(source, Enum) else source))

    def set_sample_timer(self, seconds):
        """SAMP:TIM <seconds> - interval used when SAMP:SOUR is TIMer."""
        return self._write('SAMP:TIM %s' % self._number(seconds))

    def set_trigger_source(self, source):
        """TRIG:SOUR {IMM|BUS|EXT|TIM|CHAN|ALAR1..4}."""
        return self._write('TRIG:SOUR %s' % (source.value if isinstance(source, Enum) else source))

    def get_trigger_source(self):
        """TRIG:SOUR? -> the configured trigger source."""
        return self._query('TRIG:SOUR?')

    def set_trigger_count(self, count):
        """TRIG:COUN <count> - number of triggers accepted per INITiate."""
        return self._write('TRIG:COUN %d' % int(count))

    def get_trigger_count(self):
        """TRIG:COUN? -> number of triggers per INITiate."""
        return self._query_num('TRIG:COUN?')

    def set_trigger_delay(self, seconds):
        """TRIG:DEL <seconds> - delay between the trigger and the first sample."""
        return self._write('TRIG:DEL %s' % self._number(seconds))

    def set_trigger_slope(self, slope):
        """TRIG:SLOP {POS|NEG} - active edge of the external trigger input."""
        return self._write('TRIG:SLOP %s' % (slope.value if isinstance(slope, Enum) else slope))

    def set_trigger_timer(self, seconds):
        """TRIG:TIM <seconds> - trigger period used when TRIG:SOUR is TIMer."""
        return self._write('TRIG:TIM %s' % self._number(seconds))

    def initiate(self):
        """INIT - start a measurement on the configured trigger."""
        return self._write('INIT')

    def abort(self):
        """ABOR - stop a running measurement."""
        return self._write('ABOR')

    def fetch(self):
        """FETC? - return the readings of the measurement which is already running."""
        return self._parse_values(self._read('FETC?'))

    def read(self):
        """READ? - INITiate + FETCh, i.e. a complete measurement, return the data."""
        return self._parse_values(self._read('READ?'))

    def get_data_points(self):
        """DATA:POIN? -> number of readings stored in the instrument memory."""
        return self._query_num('DATA:POIN?')

    def get_last_data(self, sample_count=None):
        """DATA:LAST? [<count>] -> the most recent reading(s)."""
        cmd = 'DATA:LAST?' if sample_count is None else 'DATA:LAST? %d' % int(sample_count)
        return self._parse_values(self._read(cmd))

    def remove_data(self, count='ALL'):
        """DATA:REMove? <count>|ALL - read and remove readings from the memory."""
        return self._parse_values(self._read('DATA:REM? %s' % count))

    def clear_data(self):
        """DATA:REMove? ALL with the answer discarded - free the reading memory."""
        self._read('DATA:REM? ALL')
        return True

    def set_reading_channel(self, on=True, timestamp=False):
        """FORM:READ:CHAN {ON|OFF} - append the channel number to every reading."""
        state = 'ON' if on else 'OFF'
        self._write('FORM:READ:CHAN %s' % state)
        if timestamp:
            self._write('FORM:READ:TIME ON')
            self._write('FORM:READ:TIME:SOUR TIM')
        return state

    # ------------------------------------------------------------ channel / scan

    def open_channels(self, channels):
        """ROUT:OPEN (@<ch_list>) - open the relays (disconnect the channels)."""
        self._write('ROUT:OPEN %s' % self._channel_text(channels))
        self.check_error('ROUT:OPEN')

    def close_channels(self, channels):
        """ROUT:CLOS (@<ch_list>) - close the relays (connect the channels)."""
        self._write('ROUT:CLOS %s' % self._channel_text(channels))
        self.check_error('ROUT:CLOS')

    def open_all_channels(self):
        """ROUT:OPEN (@100:199) - open every channel of the module slots."""
        return self.open_channels('(@100:199)')

    def set_scan_list(self, channels):
        """ROUT:SCAN (@<ch_list>) - define the scan list (measurement order)."""
        self._write('ROUT:SCAN %s' % self._channel_text(channels))
        return self.check_error('ROUT:SCAN')

    def get_scan_list(self):
        """ROUT:SCAN? -> the current scan list, e.g. '@101,102,103'."""
        return self._query_try('ROUT:SCAN?')

    def get_scan_size(self):
        """ROUT:SCAN:SIZE? -> number of channels in the scan list."""
        return self._query_num('ROUT:SCAN:SIZE?')

    def clear_scan_list(self):
        """ROUT:SCAN (@) - empty the scan list."""
        return self._write('ROUT:SCAN (@)')

    def set_scan_interval(self, seconds):
        """ROUT:SCAN:INT <seconds> - pause between two scan sweeps."""
        return self._write('ROUT:SCAN:INT %s' % self._number(seconds))

    def get_scan_interval(self):
        """ROUT:SCAN:INT? -> scan interval in seconds."""
        return self._query_num('ROUT:SCAN:INT?')

    def set_monitor_channel(self, channel):
        """ROUT:MON:CHAN (@<ch>) - channel shown on the front panel display."""
        return self._write('ROUT:MON:CHAN %s' % self._channel_text(channel))

    def set_monitor_state(self, on=True):
        """ROUT:MON:STAT {ON|OFF} - switch the channel monitor on or off."""
        return self._write('ROUT:MON:STAT %s' % ('ON' if on else 'OFF'))

    def get_monitor_data(self):
        """ROUT:MON:DATA? -> the reading of the monitored channel."""
        return self._parse_values(self._query_try('ROUT:MON:DATA?'))

    def set_channel_label(self, channel, label):
        """ROUT:CHAN:LAB '<text>',(@<ch>) - name a channel."""
        return self._write("ROUT:CHAN:LAB '%s',%s" % (label, self._channel_text(channel)))

    def get_channel_label(self, channel):
        """ROUT:CHAN:LAB? (@<ch>) -> the label of a channel."""
        return self._query_try('ROUT:CHAN:LAB? %s' % self._channel_text(channel))

    def clear_channel_labels(self):
        """ROUT:CHAN:LAB:REMove ALL - drop every channel label."""
        return self._write('ROUT:CHAN:LAB:REM ALL')

    def scan(self, channels=None, interval=None, timeout=None):
        """Scan the scan list (or the given channels) once and return the readings.

        :param channels: scan list programmed before the sweep when given
        :param interval: pause between two sweeps (ROUT:SCAN:INT)
        :param timeout:  I/O timeout for this sweep only, in ms
        """
        old = self.res.timeout
        if timeout is not None:
            self.res.timeout = timeout
        try:
            if channels is not None:
                self.set_scan_list(channels)
            if interval is not None:
                self.set_scan_interval(interval)
            self.set_trigger_source(TriggerSource.IMMEDIATE)
            self._write('SAMP:COUN 1')
            self._write('TRIG:COUN 1')
            answer = self._read('READ?')
        finally:
            self.res.timeout = old
        return self._parse_values(answer)

    # ------------------------------------------------------- channel parameters

    def set_function(self, function, channel=None):
        """SENS:FUNC '<function>'[,(@<ch_list>)] - select the function of a channel."""
        cmd = "SENS:FUNC '%s'" % self._func(function)
        ch = self._channel_text(channel)
        if ch:
            cmd += ',%s' % ch
        return self._write(cmd)

    def get_function(self, channel=None):
        """SENS:FUNC? [(@<ch_list>)] -> the function selected for a channel."""
        return self._query_try(self._build('SENS:FUNC?', (), channel))

    def set_range(self, function, range, channel=None):
        """SENS:<function>:RANG <value|AUTO|MIN|MAX> - measurement range."""
        return self._write(self._build('SENS:%s:RANG' % self._func(function),
                                       (range,), channel))

    def get_range(self, function, channel=None):
        """SENS:<function>:RANG? -> the measurement range in use."""
        return self._query_num(self._build('SENS:%s:RANG?' % self._func(function),
                                           (), channel))

    def set_resolution(self, function, resolution, channel=None):
        """SENS:<function>:RES <value|MIN|MAX> - reading resolution."""
        return self._write(self._build('SENS:%s:RES' % self._func(function),
                                       (resolution,), channel))

    def set_nplc(self, function, nplc, channel=None):
        """SENS:<function>:NPLC <0.02..100> - integration time in power line cycles."""
        return self._write(self._build('SENS:%s:NPLC' % self._func(function),
                                       (nplc,), channel))

    def get_nplc(self, function, channel=None):
        """SENS:<function>:NPLC? -> integration time in power line cycles."""
        return self._query_num(self._build('SENS:%s:NPLC?' % self._func(function),
                                           (), channel))

    def set_autozero(self, function, mode, channel=None):
        """SENS:<function>:ZERO:AUTO {ON|OFF|ONCE} - offset compensation."""
        return self._write(self._build('SENS:%s:ZERO:AUTO' % self._func(function),
                                       (mode.value if isinstance(mode, Enum) else mode,),
                                       channel))

    def set_dc_voltage_impedance(self, auto=True):
        """SENS:VOLT:DC:IMP:AUTO {ON|OFF} - high (>10 GOhm) input impedance."""
        return self._write('SENS:VOLT:DC:IMP:AUTO %s' % ('ON' if auto else 'OFF'))

    def set_ac_bandwidth(self, bandwidth, function=MeasurementFunction.AC_VOLTAGE,
                         channel=None):
        """SENS:<function>:BAND <Hz> - AC low frequency limit (3 / 20 / 200 Hz)."""
        return self._write(self._build('SENS:%s:BAND' % self._func(function),
                                       (bandwidth,), channel))

    # -------------------------------------------------------------- temperature

    def set_temperature_transducer(self, transducer, channel=None):
        """SENS:TEMP:TRAN {RTD|FTH|THER|TC}[,(@<ch_list>)] - temperature sensor type."""
        return self._write(self._build('SENS:TEMP:TRAN',
                                       (self._token(transducer, TemperatureTransducer,
                                                    'temperature transducer'),),
                                       channel))

    def set_thermocouple_type(self, tc_type, channel=None):
        """SENS:TEMP:TC:TYPE {B|E|J|K|N|R|S|T}[,(@<ch_list>)] - thermocouple type."""
        return self._write(self._build('SENS:TEMP:TC:TYPE',
                                       (self._token(tc_type, ThermocoupleType,
                                                    'thermocouple type'),), channel))

    def set_thermocouple_junction(self, source='INT', value=None, channel=None):
        """SENS:TEMP:TC:RJUN:RSEL {INT|EXT|FIX} [+ SENS:TEMP:TC:RJUN:EXT <value>].

        :param source: 'INT' internal sensor, 'EXT' external reference,
                       'FIX' fixed value written with the value parameter
        """
        args = (source,)
        self._write(self._build('SENS:TEMP:TC:RJUN:RSEL', args, channel))
        if value is not None:
            self._write(self._build('SENS:TEMP:TC:RJUN:EXT', (value,), channel))
        return source

    def set_rtd_type(self, rtd_type, channel=None):
        """SENS:TEMP:RTD:TYPE {85|91}[,(@<ch_list>)] - RTD alpha (0.00385 / 0.00391)."""
        return self._write(self._build('SENS:TEMP:RTD:TYPE',
                                       (self._token(rtd_type, RTDType, 'RTD type'),),
                                       channel))

    def set_thermistor_type(self, thermistor, channel=None):
        """SENS:TEMP:THER:TYPE {2252|5000|10000}[,(@<ch_list>)] - thermistor nominal
        resistance in Ohm; only used when the transducer of the channel is THER."""
        return self._write(self._build('SENS:TEMP:THER:TYPE',
                                       (self._token(thermistor, ThermistorType,
                                                    'thermistor type'),), channel))

    def set_temperature_unit(self, unit):
        """UNIT:TEMP {C|F|K} - unit used for every temperature reading (global)."""
        return self._write('UNIT:TEMP %s'
                           % self._token(unit, TemperatureUnit, 'temperature unit'))

    def get_temperature_unit(self):
        """UNIT:TEMP? -> the temperature unit in use."""
        return self._query_try('UNIT:TEMP?')

    def get_temperature_configuration(self, channel=None):
        """Read the temperature setup of a channel back as a dict.

        Keys: transducer / rtd_type / thermistor / tc_type / tc_junction / unit;
        an entry is None when the firmware does not answer that query.
        """
        return {
            'transducer': self._query_try(self._build('TEMP:TRAN?', (), channel)),
            'rtd_type': self._query_try(self._build('TEMP:RTD:TYPE?', (), channel)),
            'thermistor': self._query_try(self._build('TEMP:THER:TYPE?', (),
                                                      channel)),
            'tc_type': self._query_try(self._build('TEMP:TC:TYPE?', (), channel)),
            'tc_junction': self._query_try(self._build('TEMP:TC:RJUN:RSEL?', (),
                                                       channel)),
            'unit': self._query_try('UNIT:TEMP?'),
        }

    def configure_temperature(self, transducer, channel=None, tc_type=None,
                              rtd_type=None, thermistor=None, junction=None,
                              unit=None, range=None, resolution=None):
        """Configure one channel for a temperature measurement in a single call.

        :param transducer: 'RTD' (2-wire) / 'FTH' (4-wire) / 'THER' / 'TC'
        :param tc_type:    thermocouple type - only with transducer TC
        :param rtd_type:   RTD alpha - only with transducer RTD / FTH
        :param thermistor: nominal resistance 2252 / 5000 / 10000 - only with THER
        :param junction:   cold junction - only with TC; a string ('INT'), or a
                           tuple when a value belongs to it, e.g. ('FIX', 25.0)
        :param unit:       'C' / 'F' / 'K' (a global setting of the instrument)
        :param range:      optional range written with CONF:TEMP
        :param resolution: optional resolution written with CONF:TEMP

        Contradictory parameters (e.g. a thermocouple type together with
        transducer RTD) raise ValueError before anything is written.

        :return: the transducer token which was written
        """
        # every value is validated BEFORE the first write, so a typo cannot
        # leave half a temperature setup in the instrument
        token = self._token(transducer, TemperatureTransducer, 'temperature transducer')
        tc_token = (self._token(tc_type, ThermocoupleType, 'thermocouple type')
                    if tc_type is not None else None)
        rtd_token = (self._token(rtd_type, RTDType, 'RTD type')
                     if rtd_type is not None else None)
        thermistor_token = (self._token(thermistor, ThermistorType, 'thermistor type')
                            if thermistor is not None else None)
        unit_token = (self._token(unit, TemperatureUnit, 'temperature unit')
                      if unit is not None else None)

        if tc_token is not None and token != TemperatureTransducer.THERMOCOUPLE.value:
            raise ValueError("DAQ973A: a thermocouple type needs transducer TC "
                             "(got '%s')" % token)
        if rtd_token is not None and token not in (TemperatureTransducer.RTD.value,
                                                   TemperatureTransducer.FRTD.value):
            raise ValueError("DAQ973A: an RTD type needs transducer RTD or FTH "
                             "(got '%s')" % token)
        if thermistor_token is not None \
                and token != TemperatureTransducer.THERMISTOR.value:
            raise ValueError("DAQ973A: a thermistor type needs transducer THER "
                             "(got '%s')" % token)
        if junction is not None and token != TemperatureTransducer.THERMOCOUPLE.value:
            raise ValueError("DAQ973A: a cold junction needs transducer TC "
                             "(got '%s')" % token)

        if unit_token is not None:
            self.set_temperature_unit(unit_token)
        self.set_temperature_transducer(token, channel)
        if tc_token is not None:
            self.set_thermocouple_type(tc_token, channel)
        if rtd_token is not None:
            self.set_rtd_type(rtd_token, channel)
        if thermistor_token is not None:
            self.set_thermistor_type(thermistor_token, channel)
        if junction is not None:
            if isinstance(junction, (list, tuple)):
                source = junction[0]
                value = junction[1] if len(junction) > 1 else None
                self.set_thermocouple_junction(source, value, channel)
            else:
                self.set_thermocouple_junction(junction, channel=channel)
        if range is not None or resolution is not None:
            self.configure(MeasurementFunction.TEMPERATURE, range, resolution, channel)
        self.check_error('configure_temperature')
        return token

    # ------------------------------------------------------------- math / limits

    def enable_statistics(self, on=True):
        """CALC:AVER:STAT {ON|OFF} - min / max / average / sdev over the readings."""
        return self._write('CALC:AVER:STAT %s' % ('ON' if on else 'OFF'))

    def set_statistics_count(self, count):
        """CALC:AVER:COUN <count> - readings used for the statistics."""
        return self._write('CALC:AVER:COUN %d' % int(count))

    def get_statistics(self):
        """CALC:AVER:*? -> dict with minimum / maximum / average / sdev / pkpk."""
        return {
            'minimum': self._query_num('CALC:AVER:MIN?'),
            'maximum': self._query_num('CALC:AVER:MAX?'),
            'average': self._query_num('CALC:AVER:AVER?'),
            'sdev': self._query_num('CALC:AVER:SDEV?'),
            'pkpk': self._query_num('CALC:AVER:PKPK?'),
        }

    def clear_statistics(self):
        """CALC:AVER:CLE - restart the statistics."""
        return self._write('CALC:AVER:CLE')

    def set_null(self, offset, on=True):
        """CALC:NULL:VAL <offset> + CALC:NULL:STAT {ON|OFF} - offset a reading."""
        self._write('CALC:NULL:VAL %s' % self._number(offset))
        self._write('CALC:NULL:STAT %s' % ('ON' if on else 'OFF'))
        return offset

    def set_null_auto(self, on=True):
        """CALC:NULL:VAL:AUTO {ON|OFF} - take the next reading as the null value."""
        return self._write('CALC:NULL:VAL:AUTO %s' % ('ON' if on else 'OFF'))

    def set_limit(self, channel, upper=None, lower=None):
        """CALC:LIM:UPPER / LOWer <value>,(@<ch>) - alarm limits of a channel."""
        if upper is not None:
            self._write(self._build('CALC:LIM:UPP', (upper,), channel))
        if lower is not None:
            self._write(self._build('CALC:LIM:LOW', (lower,), channel))
        return self.check_error('CALC:LIM')

    def enable_limit(self, on=True, channel=None):
        """CALC:LIM:STAT {ON|OFF}[,(@<ch_list>)] - enable the alarm limits."""
        return self._write(self._build('CALC:LIM:STAT',
                                       ('ON' if on else 'OFF',), channel))

    def clear_limit(self, channel=None):
        """CALC:LIM:CLE [(@<ch_list>)] - clear the limit violations."""
        return self._write(self._build('CALC:LIM:CLE', (), channel))

    def get_limit_state(self, channel=None):
        """CALC:LIM:UPPER:STAT? / LOWer:STAT? -> which limits are violated."""
        return {
            'upper': self._query_try(self._build('CALC:LIM:UPP:STAT?', (), channel)),
            'lower': self._query_try(self._build('CALC:LIM:LOW:STAT?', (), channel)),
        }

    # ------------------------------------------------------- digital I/O / total

    def read_digital(self, channel=None):
        """SENS:DIG:DATA:BYTE? [(@<ch>)] - read the digital input byte (DAQM907A)."""
        return self._parse_values(self._query_try(self._build('SENS:DIG:DATA:BYTE?',
                                                              (), channel)))

    def write_digital(self, value, channel=None):
        """SOUR:DIG:DATA:BYTE <value>[,(@<ch>)] - drive the digital output byte."""
        return self._write(self._build('SOUR:DIG:DATA:BYTE', (value,), channel))

    def set_digital_enable(self, mask, channel=None):
        """SOUR:DIG:ENAB <mask>[,(@<ch>)] - mask of the digital output lines."""
        return self._write(self._build('SOUR:DIG:ENAB', (mask,), channel))

    def read_totalizer(self, channel=None):
        """SENS:TOT:DATA? [(@<ch>)] - totalizer count (DAQM907A)."""
        return self._parse_values(self._query_try(self._build('SENS:TOT:DATA?',
                                                              (), channel)))

    def reset_totalizer(self, channel=None):
        """SENS:TOT:RES [(@<ch>)] - reset the totalizer count."""
        return self._write(self._build('SENS:TOT:RES', (), channel))

    # ------------------------------------------------------------ format / data

    def set_data_format(self, fmt=DataFormat.ASCII, byte_order=None):
        """FORM:DATA {ASC|REAL} - answer format ('REAL' = binary block)."""
        self._write('FORM:DATA %s' % (fmt.value if isinstance(fmt, Enum) else fmt))
        if byte_order is not None:
            self._write('FORM:BORD %s'
                        % (byte_order.value if isinstance(byte_order, Enum) else byte_order))
        return fmt

    def get_data_format(self):
        """FORM:DATA? -> the answer format in use."""
        return self._query_try('FORM:DATA?')

    # ---------------------------------------------------------------- functional

    def channel_sweep(self, channels, function=MeasurementFunction.DC_VOLTAGE,
                      range=None, resolution=None, delay=0.05):
        """Measure every channel of a list one after the other.

        :return: list of (channel, value) tuples
        """
        result = []
        for channel in channels:
            if delay:
                time.sleep(delay)
            value = self.measure(function, range, resolution, channel)
            print("DAQ973A channel %s : %s" % (channel, value))
            result.append((channel, value))
        return result


# ---------------------------------------------------------------------- helpers

def DAQ973A_INIT(addr, reset=False, verbose=True):
    """Open the DAQ973A and return the driver object (None when it is not reachable)."""
    try:
        meter = DAQ973A(addr, reset=reset)
    except Exception as exc:
        print("DAQ973A: connect %s failed - %s" % (addr, exc))
        return None
    if not meter.connected:
        return None
    if verbose:
        print("IDN : %s" % meter.idn())
    return meter


def DAQ973A_MEASURE_TEST(meter, channel=101, verbose=False):
    """Measure all twelve functions on one channel, print one line each.

    :param meter: a DAQ973A object prepared by DAQ973A_INIT()
    :return: dict {function name: value} (None for a failed item)
    """
    meter.set_temperature_transducer(TemperatureTransducer.THERMOCOUPLE, channel)
    meter.set_thermocouple_type(ThermocoupleType.J, channel)
    meter.set_temperature_unit(TemperatureUnit.CELSIUS)
    # print(meter.get_temperature_configuration(channel))
    # print(meter.get_temperature_unit())
    items = [
        # ('DCV', meter.measure_dc_voltage, {'channel': channel}),
        # ('ACV', meter.measure_ac_voltage, {'channel': channel}),
        # ('DCI', meter.measure_dc_current, {'channel': channel}),
        # ('ACI', meter.measure_ac_current, {'channel': channel}),
        # ('RES', meter.measure_resistance, {'channel': channel}),
        # ('FRES', meter.measure_4wire_resistance, {'channel': channel}),
        # ('FREQ', meter.measure_frequency, {'channel': channel}),
        # ('PER', meter.measure_period, {'channel': channel}),
        ('TEMP', meter.measure_temperature, {'channel': channel}),
        # ('CAP', meter.measure_capacitance, {'channel': channel}),
        # ('CONT', meter.measure_continuity, {'channel': channel}),
        # ('DIOD', meter.measure_diode, {'channel': channel}),
    ]
    result = {}
    for name, func, kwargs in items:
        try:
            value = func(**kwargs)
        except Exception as exc:
            value = None
            if verbose:
                print("DAQ973A %s failed - %s" % (name, exc))
        result[name] = value
        print("%-5s : %s" % (name, value))
    return result


def DAQ973A_SCAN_TEST(meter, channels, interval=0.1, verbose=True):
    """Scan a channel list once and print the readings paired with the channels."""
    values = meter.scan(channels, interval=interval)
    if values is None:
        print("DAQ973A scan : no answer (check the scan list and the trigger source)")
        return None
    if not isinstance(values, list):
        values = [values]
    pairs = list(zip(list(channels) if isinstance(channels, (list, tuple)) else [channels],
                     values))
    if verbose:
        for channel, value in pairs:
            print("DAQ973A scan channel %s : %s" % (channel, value))
    return pairs


def DAQ973A_TEST(addr, channel=101, reset=False):
    """Complete functional check: connect, measure all functions, disconnect."""
    meter = DAQ973A_INIT(addr, reset=reset)
    if meter is None:
        print("DAQ973A test FAILED - no connection to %s" % addr)
        return False
    try:
        for i in range(0,100):
            result = DAQ973A_MEASURE_TEST(meter, channel) 
        failed = [name for name, value in result.items() if value is None]
        if failed:
            print("DAQ973A test FAILED for: %s" % ', '.join(failed))
            return False
        print("DAQ973A test is done")
        return True
    finally:
        meter.close()


if __name__ == "__main__":
    # m = DAQ973A('USB0::0x2A8D::0x8601::MY59008008::INSTR', reset=False)
    # print("IDN   : %s" % m.idn())
    # print("DCV   : %s" % m.measure_dc_voltage(channel=101))
    # print("error : %s" % m.check_error())
    # DAQ973A_TEST('USB0::0x2A8D::0x8601::MY59008008::INSTR',channel=101, reset=False)
    meter = DAQ973A('USB0::0x2A8D::0x8601::MY59008008::INSTR', reset=False)
    meter.set_temperature_transducer(TemperatureTransducer.THERMOCOUPLE, 102)
    meter.set_thermocouple_type(ThermocoupleType.J, 102)
    meter.set_temperature_unit(TemperatureUnit.CELSIUS)
    for i in range(0,100):
        result = meter.measure_temperature(channel =102)
        print(result)
        time.sleep(0.1)
    print("Temp test is done!!!")
    meter.close()
    