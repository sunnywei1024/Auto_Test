# -*- coding: UTF-8 -*-
"""
Created on Sep 28, 2026
Shanghai
@author: lijiangwei

Keysight 53230A universal frequency counter / timer driver
==========================================================

SCPI driver for the Keysight 53230A (350 MHz, 12 digits/s) universal frequency
counter / timer; the command set is shared with the 53220A.

Content:

1. the class FREQ53230A - connection, input settings (INPut subsystem),
   reference clock (SENSe:ROSCillator), measurement functions, trigger
   (TRIGger subsystem), gate (SENSe:<function>:GATE) and the triggered / gated
   measurement measure_gated()
2. FREQ53230A_INIT() - prepares a counter for the test functions
3. one function per measurement item - FREQ53230A_FREQ_TEST, FREQ53230A_PER_TEST,
   FREQ53230A_PWID_TEST, FREQ53230A_TINT_TEST, FREQ53230A_NWID_TEST,
   FREQ53230A_PDUT_TEST, FREQ53230A_FTIM_TEST, FREQ53230A_RTIM_TEST,
   FREQ53230A_PHAS_TEST, FREQ53230A_SPER_TEST - every one of them prints one
   result line and returns the measured value
4. FREQ53230A_TEST() - every item over one connection, with the cross checks
   FREQ x PER = 1, PWID + NWID = SPER and TINT = PWID

Installation::

    pip install pyvisa

A VISA backend (NI-VISA, Keysight IO Libraries) is required as well.

VISA resource string examples::

    USB0::0x0957::0x1907::MY64200013::INSTR
    TCPIP0::192.168.1.100::inst0::INSTR
    GPIB0::10::INSTR

Usage::

    from Layer1.KEYSIGHT53230A import FREQ53230A_INIT, FREQ53230A_FREQ_TEST

    counter = FREQ53230A_INIT('USB0::0x0957::0x1907::MY64200013::INSTR')
    if counter is not None:
        print(FREQ53230A_FREQ_TEST(counter, gate_time=0.1, channel=1))
        counter.close()

Notes:

* The SCPI keywords are sent in their short form, the instrument accepts the
  long form as well.  Enum members are converted into the matching SCPI
  parameter, a plain string is passed through unchanged, so a token which is not
  listed in an enum can still be used - set_slope(1, 'POS') for example.
* The unit of a reading depends on the function: Hz for frequency, s for period,
  pulse width, rise time, fall time, time interval and single period, degrees for
  phase and the RATIO (0.5 = 50 %) for the duty cycle - the tested 53230A does
  not answer the duty cycle in percent, use measure_duty_cycle_percent().
* The measurement channel is part of the function: 'SENS:FUNC "FREQ 2"' or
  'SENS:FUNC "TINT 1,2"'.  The counter omits the DEFAULT channel from its
  answers ('"FREQ 1"' is echoed as 'FREQ', '"TINT 1,2"' as 'TINT'), which the
  check in set_measurement_function() takes into account.
* Frequency, period and single period measurements share the gate settings
  (SENSe:FREQ:GATE...), a time interval or phase measurement is gated by the
  input edges and has no gate timer.
* On the tested 53230A the rise / fall time measurement and the single input
  time interval ('TINT 1') share the two levels INPut<ch>:LEV1 / LEV2 and the
  two edges INPut<ch>:SLOP1 / SLOP2.  The counter validates the PAIR of levels
  on every write and replaces both with its defaults when the low reference is
  written first, so the HIGH reference is written first (see
  set_transition_levels()) and the automatic level has to be off while a
  transition time is measured.
* A timebase which does not match its setting scales EVERY reading of the
  counter - an external reference of 5 MHz where 10 MHz is configured doubles
  every frequency and halves every period.  FREQ53230A_INIT() therefore switches
  the automatic reference selection off and selects the internal oscillator.
* A command which not every firmware revision offers (ABORt, INITiate:CONTinuous)
  is sent once and left out when the counter refuses it, see _write_once() and
  _write_first().
"""

import re
import time
from enum import Enum

import pyvisa
from pyvisa.constants import *


class InputCoupling(Enum):
    """Input coupling INPut{1|2}:COUPling"""
    AC = 'AC'
    DC = 'DC'


class InputImpedance(Enum):
    """Input impedance INPut{1|2}:IMPedance"""
    OHM_50 = '50'      # 50 ohm
    OHM_1M = '1E6'     # 1 Mohm


class InputSlope(Enum):
    """Trigger (threshold) slope INPut{1|2}:SLOPe{1|2}"""
    POSITIVE = 'POS'   # rising edge
    NEGATIVE = 'NEG'   # falling edge


class LevelAuto(Enum):
    """Automatic trigger level INPut{1|2}:LEVel:AUTO"""
    ON = 'ON'
    OFF = 'OFF'
    ONCE = 'ONCE'


class ReferenceClock(Enum):
    """Timebase / reference oscillator SENSe:ROSCillator:SOURce"""
    INTERNAL = 'INT'   # internal oscillator
    EXTERNAL = 'EXT'   # external reference at the rear input


class TriggerSource(Enum):
    """Trigger source TRIGger:SOURce"""
    IMMEDIATE = 'IMM'
    EXTERNAL = 'EXT'
    BUS = 'BUS'
    INTERNAL = 'INT'


class TriggerSlope(Enum):
    """Slope of the external trigger input TRIGger:SLOPe"""
    POSITIVE = 'POS'
    NEGATIVE = 'NEG'


class GateSource(Enum):
    """Gate source SENSe:<function>:GATE:SOURce"""
    TIMER = 'TIM'      # internal gate timer
    EXTERNAL = 'EXT'   # gate signal at the rear gate input


class GatePolarity(Enum):
    """Gate signal polarity SENSe:<function>:GATE:POLarity"""
    POSITIVE = 'POS'
    NEGATIVE = 'NEG'


class MeasurementFunction(Enum):
    """Measurement function CONF:<function> / MEAS:<function>?"""
    FREQUENCY = 'FREQ'       # unit Hz
    PERIOD = 'PER'           # unit s
    PULSE_WIDTH = 'PWID'     # unit s, rising -> falling edges of one input
    NEGATIVE_PULSE_WIDTH = 'NWID'   # unit s, falling -> rising edges
    DUTY_CYCLE = 'PDUT'      # ratio on the tested 53230A (0.5 = 50 %)
    RISE_TIME = 'RTIM'       # unit s
    FALL_TIME = 'FTIM'       # unit s
    TIME_INTERVAL = 'TINT'   # unit s
    PHASE = 'PHAS'           # unit deg
    SINGLE_PERIOD = 'SPER'   # unit s


# Function / channel string of SENSe:FUNCtion.  The first template is used by
# default; a firmware which expects another form answers an error, then the next
# template can be selected by hand in self.func_channel_format.
FUNC_CHANNEL_FORMATS = (
    '"%s %s"',      # SENS:FUNC "FREQ 2"     / "TINT 1,2"
    '"%s",%s',      # SENS:FUNC "FREQ",2     / "TINT",1,2
    '"%s",(@%s)',   # SENS:FUNC "FREQ",(@2)  / "TINT",(@1,2)
    '"%s,%s"',      # SENS:FUNC "FREQ,2"     / "TINT,1,2"
    '"%s%s"',       # SENS:FUNC "FREQ2"
)

# Value which the counter answers when no valid measurement could be made
# (overflow, missing edges, ...), see is_valid_reading()
INVALID_READING = 9.91e+37

# Number of times a transition time row is prepared and measured again with the
# same recipe before the next recipe is tried.  The tested 53230A answers an edge
# to edge interval instead of the transition time in single runs although every
# setting is the one which was written; three attempts cover two failures in a
# row, which was observed on hardware.
TRANSITION_REPEATS = 3

# Spellings of "leave the free running mode" (INITiate:CONTinuous OFF), tried
# once each by _write_first().  The tested 53230A answers -113,"Undefined header"
# for the first one, so the spelling which the connected unit accepts is looked
# for instead of reporting an error on every run.
FREE_RUNNING_COMMANDS = (
    'INIT:CONT OFF',
    'INIT:CONTINUOUS OFF',
    ':INITIATE:CONTINUOUS OFF',
    'INIT:CONT 0',
    'INIT:CONTINUOUS 0',
)


class FREQ53230A:
    def __init__(self, addr, timeout=5000):
        """
        :param addr: VISA resource string,
                     e.g. 'USB0::0x0957::0x1907::MY64200013::INSTR'
        :param timeout: read/write timeout in ms, default 5000 ms
        """
        self.addr = addr
        self.res = None
        self.connected = False
        self.timeout = timeout
        self.gate_time = 1.0        # gate time (s) used by measure_gated()
        self.function = None        # last function, 'FREQ', 'TINT', ...
        self.measurement_channel = None   # last channel, '1', '1,2', ...
        self.func_channel_format = FUNC_CHANNEL_FORMATS[0]   # see below
        self.func_channel_cmd = 'SENS:FUNC'   # ':FUNC' when the legacy form
                                              # is the one this unit accepts
        self.strict_channel_check = False   # True -> RuntimeError when the
                                            # channel cannot be read back
        self._verified_channels = set()   # checked function / channel keys
        self._channel_warned = False      # 'channel not reported' printed once
        self.plain_edge_ok = True         # False when the counter refuses
                                          # INP<ch>:SLOP (without a line number)
        self.settle_time = 0.1            # s - pause after a setting write, see
                                          # settle(); 0 disables it
        self.quiet = False                # True -> no notices, see _say()
        self.optional_commands = {}       # result of the commands which not
                                          # every unit offers, see _write_once()

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
    # Low level read / write helpers
    # ------------------------------------------------------------------
    def _wr(self, cmd):
        """Send a command (no response expected)"""
        if not self.connected:
            raise RuntimeError("counter is not connected: %s" % self.addr)
        self.res.write(cmd)

    def _qr(self, cmd):
        """Send a query and return the answer without leading/trailing blanks"""
        if not self.connected:
            raise RuntimeError("counter is not connected: %s" % self.addr)
        return self.res.query(cmd).strip()

    @staticmethod
    def _num(value):
        """Format a number as a SCPI parameter string"""
        return "%.6g" % float(value)

    @classmethod
    def _token(cls, value):
        """
        Convert a setting into a SCPI parameter string: an Enum member with its
        value (InputCoupling.DC -> 'DC'), a bool into 'ON' / 'OFF', a number
        with _num() and a string unchanged.
        """
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, bool):
            return 'ON' if value else 'OFF'
        if isinstance(value, (int, float)):
            return cls._num(value)
        return str(value)

    @staticmethod
    def _value(text):
        """
        Convert a single SCPI answer into a float, tolerating a unit suffix
        ('+1.00000000E+006' and '1.00000000E+006 HZ').
        """
        txt = str(text).strip().strip('"\'')
        match = re.match(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?', txt)
        if not match:
            raise ValueError("cannot convert %r into a number" % text)
        return float(match.group(0))

    @classmethod
    def _values(cls, text):
        """Convert a comma separated SCPI answer into a list of floats"""
        return [cls._value(item) for item in str(text).split(',')
                if str(item).strip()]

    @staticmethod
    def is_valid_reading(value):
        """
        True when value is a normal reading.

        The counter answers 9.91E+37 (INVALID_READING) when no valid measurement
        could be made - an overflow, or missing edges of a time interval
        measurement.  Such an answer is a number, so it is not caught by an
        exception.
        """
        return abs(float(value)) < INVALID_READING / 2.0

    @staticmethod
    def _ch(channel):
        """Normalize a channel number (1 or 2) used by the INPut node"""
        ch = int(channel)
        if ch not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        return ch

    def _gate_node(self, function, node):
        """
        Build the gate command of a measurement function: frequency / period and
        the functions without a dedicated gate node use SENSe:FREQ:GATE...,
        time interval and phase SENSe:TINT:GATE..., totalize SENSe:TOT:GATE....
        """
        func = self._token(function).upper()
        if func.startswith('TOT'):
            return 'SENS:TOT:GATE:%s' % node
        if func.startswith('TINT') or func.startswith('PHAS'):
            return 'SENS:TINT:GATE:%s' % node
        return 'SENS:FREQ:GATE:%s' % node

    def _has_gate_timer(self, function):
        """True when the measurement function is gated by the gate timer"""
        return not self._token(function).upper().startswith(('TINT', 'PHAS'))

    def _is_pair_function(self, function):
        """True for the measurements which use two channels (start / stop)"""
        return self._token(function).upper().startswith(('TINT', 'PHAS'))

    @classmethod
    def _channel_text(cls, channel, stop_channel=None, pair=False):
        """
        Build the channel part of a function string ('1', '2' or '1,2').

        :param channel: measurement channel 1 or 2; a channel pair can also be
                        given as a tuple or list (1, 2), any other text (for
                        example '1,2') is passed through unchanged
        :param stop_channel: stop channel of a time interval / phase measurement
        :param pair: True when the function needs a channel pair - the other
                     channel is then used as stop channel when stop_channel is
                     not given
        """
        if isinstance(channel, (tuple, list)):
            if not pair:
                raise ValueError("only a time interval / phase measurement "
                                 "uses a channel pair")
            return ','.join(str(cls._ch(ch)) for ch in channel)
        text = str(channel).strip()
        if text not in ('1', '2'):      # raw channel list, pass it through
            return text
        if stop_channel is not None and not pair:
            raise ValueError("only a time interval / phase measurement "
                             "uses a stop channel")
        start = int(text)
        if stop_channel is not None:
            return '%d,%d' % (start, cls._ch(stop_channel))
        if pair:
            return '%d,%d' % (start, 2 if start == 1 else 1)
        return text

    # ------------------------------------------------------------------
    # Connection / status
    # ------------------------------------------------------------------
    def idn(self):
        """Query the identification string (*IDN?)"""
        return self._qr('*IDN?')

    def reset(self, wait=True):
        """
        Reset the counter to the power-on state (*RST) and clear the error queue.

        :param wait: True (default) -> wait for the reset to finish (*OPC?)
                     before the next command is sent.  A setting which is written
                     while the reset is still running is lost, which made a
                     transition time row fail in some runs and not in others.
        """
        self._wr('*RST')
        if wait:
            self.wait_opc()
        self._wr('*CLS')

    def clear(self):
        """Clear the status registers and the error queue (*CLS)"""
        self._wr('*CLS')

    def settle(self, seconds=None):
        """
        Wait a moment so the counter can process the settings just written.

        The commands of a recipe follow each other within milliseconds and a
        setting which is not applied yet gives a reading which does not belong to
        that setup - the tested 53230A answered a frequency of 1956.8 Hz for a
        1 kHz signal without the pause.  Set self.settle_time = 0 to switch the
        pause off.

        :param seconds: pause in s, self.settle_time by default
        """
        pause = self.settle_time if seconds is None else float(seconds)
        if pause > 0:
            time.sleep(pause)

    def _say(self, text):
        """
        Print a notice unless the counter runs in quiet mode.

        FREQ53230A_INIT() sets self.quiet for a run which reports the measurement
        results only; everything which is not a result (a setting which the
        counter adjusted on its own, a state which is worth a warning) is dropped
        then.  An instrument ERROR is printed in every case (see
        _write_once() / drain_notices()).

        :param text: the notice
        """
        if not self.quiet:
            print(text)

    @staticmethod
    def answer_is_ok(err, notice_ok=True):
        """
        True when an answer of SYST:ERR? does not stop the measurement.

        '+0,"No error"' is the clean answer.  A -2xx answer is an execution
        error: the counter understood the command and adjusted a setting on its
        own (the tested 53230A answers -221 'Settings conflict; low reference >=
        high reference' while the two reference levels of a transition time are
        written).  Such a notice does not stop the measurement, so it is not a
        refusal when notice_ok is True; -1xx (command error) and the other
        classes are real errors in every case.

        :param err: answer of SYST:ERR?
        :param notice_ok: True (default) -> a -2xx answer is accepted
        """
        text = str(err).strip().lstrip('+')
        if text.startswith('0,'):
            return True
        return bool(notice_ok) and text.lstrip('+-').startswith('2')

    def _write_once(self, cmd, label=''):
        """
        Send a command which not every firmware revision offers, once.

        The transition time recipe uses ABORt to keep the counter free of
        leftovers (a result which belongs to the previous settings can otherwise
        come back as the new one), but the connected unit may answer an error for
        it.  Such a command is sent once only: the result is remembered in
        self.optional_commands, a refusal is reported and the command is not sent
        again, so the error queue stays clean and the measurement continues.

        :param cmd: the command to send
        :param label: text printed with the notice when it is refused
        :return: True when the counter accepted the command
        """
        if cmd in self.optional_commands:
            return self.optional_commands[cmd]
        self.clear()
        self._wr(cmd)
        messages = self.read_messages()
        accepted = self.first_problem(messages) is None
        self.optional_commands[cmd] = accepted
        if not accepted:
            print("53230A: the counter answers %s for '%s' - the command is not"
                  " sent again%s"
                  % ('; '.join(messages), cmd,
                     (' (%s)' % label) if label else ''))
        return accepted

    def _write_first(self, candidates, label=''):
        """
        Send the first spelling of a command which the counter accepts.

        A firmware revision may use a different mnemonic for the same setting:
        the tested 53230A answers -113,"Undefined header" for 'INIT:CONT OFF'
        (see FREE_RUNNING_COMMANDS).  Every candidate is sent once with a cleared
        error queue; the accepted spelling is remembered under the tuple of the
        candidates, so the search runs once per counter.

        :param candidates: the spellings of one command, best first
        :param label: text printed when none of them is accepted
        :return: True when one of the candidates was accepted
        """
        key = tuple(candidates)
        if key in self.optional_commands:
            return self.optional_commands[key]
        answers = []
        accepted = False
        for cmd in candidates:
            self.clear()
            self._wr(cmd)
            messages = self.read_messages()
            answers.append('%s -> %s' % (cmd, '; '.join(messages) or '+0'))
            if self.first_problem(messages) is None:
                accepted = True
                if cmd != candidates[0]:
                    self._say("53230A: '%s' is the spelling of %s which the"
                              " connected unit accepts"
                              % (cmd, label or 'this command'))
                break
        if not accepted:
            self._say("53230A: %s is not offered by the connected unit (tried"
                      " once: %s) - the command is left out and the measurement"
                      " continues without it"
                      % (label or 'a command', '; '.join(answers)))
        self.optional_commands[key] = accepted
        return accepted

    def get_error(self):
        """Query the error queue (SYST:ERR?), '+0,"No error"' when it is empty"""
        return self._qr('SYST:ERR?')

    def read_messages(self, limit=8):
        """
        Read the error queue until it is empty.

        One command can leave more than one message behind (the two reference
        levels of a transition time are a pair), so the queue is read up to
        `limit` times.

        :param limit: highest number of messages which is read
        :return: list of the answers which are not '+0,"No error"'
        """
        messages = []
        for _ in range(max(1, int(limit))):
            err = self.get_error()
            if err.lstrip('+').startswith('0,'):
                break
            messages.append(err)
        return messages

    def first_problem(self, messages, notice_ok=True):
        """
        The first answer of a list which stops the measurement.

        :param messages: list of answers of SYST:ERR?
        :param notice_ok: True (default) -> a -2xx notice is not a problem
        :return: the first answer which answer_is_ok() rejects, else None
        """
        for err in messages:
            if not self.answer_is_ok(err, notice_ok):
                return err
        return None

    def drain_notices(self, label=''):
        """
        Read the error queue and report what a group of setting writes left in it.

        The counter reports -221 'Settings conflict; low reference >= high
        reference' while the pair of reference levels of a transition time is
        written (it builds a valid pair afterwards).  That message is a notice,
        but it would be read at the next query of the error queue, which belongs
        to another step and would make it look as if THAT step failed.  So the
        queue is read here and only a real error is printed.

        :param label: text printed with the messages
        :return: list of the answers which are real errors
        """
        messages = self.read_messages()
        problem = self.first_problem(messages)
        if problem is not None:
            print("53230A error %s%s"
                  % (('(%s) ' % label) if label else '', problem))
        elif messages:
            self._say("53230A: the counter reports %s - it adjusted its"
                      " settings, the measurement continues%s"
                      % ('; '.join(messages),
                         (' (%s)' % label) if label else ''))
        return [err for err in messages if not self.answer_is_ok(err)]

    def check_error(self, label=''):
        """
        Query the error queue and print the answer when an error is pending.

        :param label: optional text printed with the error message
        :return: True when the error queue is empty, else False
        """
        err = self.get_error()
        clean = err.lstrip('+').startswith('0,')
        if not clean:
            print("53230A error %s%s" % (('(%s) ' % label) if label else '', err))
        return clean

    def wait_opc(self, timeout=None):
        """Wait until all pending operations are finished (*OPC?)"""
        old = self.res.timeout
        if timeout is not None:
            self.res.timeout = timeout
        try:
            self._qr('*OPC?')
        finally:
            self.res.timeout = old

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
                print("Close Keysight 53230A successfully!")
                return True
            except Exception:
                if err_cnt < 3:
                    err_cnt += 1
                    time.sleep(3)
                else:
                    print("Close failed!")
                    return False

    # ------------------------------------------------------------------
    # Input settings: coupling / impedance / voltage range / trigger level /
    # slope / bandwidth limiting (low pass) filter
    # ------------------------------------------------------------------
    def set_coupling(self, channel=1, coupling=InputCoupling.DC):
        """Set the input coupling of a channel (INP{ch}:COUP)"""
        self._wr('INP%d:COUP %s' % (self._ch(channel), self._token(coupling)))

    def get_coupling(self, channel=1):
        """Query the input coupling of a channel (INP{ch}:COUP?)"""
        return self._qr('INP%d:COUP?' % self._ch(channel))

    def set_impedance(self, channel=1, impedance=InputImpedance.OHM_1M):
        """Set the input impedance of a channel (INP{ch}:IMP)"""
        self._wr('INP%d:IMP %s' % (self._ch(channel), self._token(impedance)))

    def get_impedance(self, channel=1):
        """Query the input impedance of a channel (INP{ch}:IMP?), unit ohm"""
        return self._value(self._qr('INP%d:IMP?' % self._ch(channel)))

    def set_voltage_range(self, channel=1, volts=None, auto=False):
        """
        Set the input voltage range of a channel (INP{ch}:RANG).

        :param volts: range in volt, for example 5.0 for the 5 V range
        :param auto: True -> the counter selects the range automatically
                     (INP{ch}:RANG AUTO), volts is then not used
        """
        ch = self._ch(channel)
        if auto:
            self._wr('INP%d:RANG AUTO' % ch)
        elif volts is not None:
            self._wr('INP%d:RANG %s' % (ch, self._num(volts)))
        else:
            raise ValueError("volts is required when auto is False")

    def get_voltage_range(self, channel=1):
        """Query the input voltage range of a channel (INP{ch}:RANG?), unit V"""
        return self._value(self._qr('INP%d:RANG?' % self._ch(channel)))

    def set_trigger_level(self, channel=1, volts=None, auto=None, relative=None,
                          line=1):
        """
        Set the trigger (threshold) level of a channel.

        :param volts: absolute level in volt (INP{ch}:LEV[line])
        :param auto: True / False / LevelAuto.ONCE -> automatic trigger level
                     (INP{ch}:LEV:AUTO), None leaves the setting untouched
        :param relative: level in percent of the input signal
                         (INP{ch}:LEV[line]:REL)
        :param line: 1 (default) or 2 - the start / stop level used by time
                     interval and phase measurements (INP{ch}:LEV1 / LEV2)

        With an automatic level the counter sets the level, a level given with
        volts or relative is then ignored by the instrument.
        """
        ch = self._ch(channel)
        line = 1 if int(line) == 1 else 2
        if auto is not None:
            self._wr('INP%d:LEV:AUTO %s' % (ch, self._token(auto)))
        if volts is not None:
            self._wr('INP%d:LEV%d %s' % (ch, line, self._num(volts)))
        if relative is not None:
            self._wr('INP%d:LEV%d:REL %s' % (ch, line, self._num(relative)))

    def get_trigger_level(self, channel=1, line=1):
        """Query the absolute trigger level (INP{ch}:LEV[line]?), unit V"""
        ch = self._ch(channel)
        line = 1 if int(line) == 1 else 2
        return self._value(self._qr('INP%d:LEV%d?' % (ch, line)))

    def get_trigger_level_auto(self, channel=1):
        """
        Query the automatic trigger level setting (INP{ch}:LEV:AUTO?) - the
        counter reports the state as a number (1 = on, 0 = off).
        """
        return self._value(self._qr('INP%d:LEV:AUTO?' % self._ch(channel)))

    def get_trigger_level_range(self, channel=1):
        """
        Query the trigger level limits of a channel, unit V.

        :return: (minimum, peak to peak, maximum) - INP{ch}:LEV:MIN?,
                 INP{ch}:LEV:PTP? and INP{ch}:LEV:MAX?
        """
        ch = self._ch(channel)
        minimum = self._value(self._qr('INP%d:LEV:MIN?' % ch))
        ptp = self._value(self._qr('INP%d:LEV:PTP?' % ch))
        maximum = self._value(self._qr('INP%d:LEV:MAX?' % ch))
        return minimum, ptp, maximum

    def set_slope(self, channel=1, slope=InputSlope.POSITIVE, line=1):
        """
        Set the trigger (threshold) slope of a channel (INP{ch}:SLOP[line]).

        :param slope: InputSlope.POSITIVE (rising edge, default) or
                      InputSlope.NEGATIVE (falling edge)
        :param line: 1 (default) or 2 - the start / stop edge used by time
                     interval and phase measurements (INP{ch}:SLOP1 / SLOP2)
        """
        ch = self._ch(channel)
        line = 1 if int(line) == 1 else 2
        self._wr('INP%d:SLOP%d %s' % (ch, line, self._token(slope)))

    def get_slope(self, channel=1, line=1):
        """Query the trigger slope of a channel (INP{ch}:SLOP[line]?)"""
        ch = self._ch(channel)
        line = 1 if int(line) == 1 else 2
        return self._qr('INP%d:SLOP%d?' % (ch, line))

    @staticmethod
    def _slope_text(value):
        """
        A slope answer reduced to POS / NEG (a firmware may add the number of the
        line or the long form).
        """
        return str(value).strip().upper()[:3]

    def set_bandwidth(self, channel=1, value=False):
        """
        Set the bandwidth limiting (low pass) filter of a channel (INP{ch}:FILT).

        :param value: False (filter off, default), True (filter on) or the filter
                      setting accepted by the instrument; the value is passed
                      through, so a firmware specific token can be used as well
        """
        self._wr('INP%d:FILT %s' % (self._ch(channel), self._token(value)))

    def get_bandwidth(self, channel=1):
        """Query the bandwidth limiting (low pass) filter (INP{ch}:FILT?)"""
        return self._qr('INP%d:FILT?' % self._ch(channel))

    def configure_input(self, channel=1, coupling=None, impedance=None,
                        volts_range=None, range_auto=None, level=None,
                        auto_level=None, relative_level=None, slope=None,
                        bandwidth=None):
        """
        Configure several input channel parameters with one call.

        All parameters are optional, only the ones which are not None are sent;
        the meaning is the same as in the individual set_* methods.
        """
        ch = self._ch(channel)
        if coupling is not None:
            self.set_coupling(ch, coupling)
        if impedance is not None:
            self.set_impedance(ch, impedance)
        if volts_range is not None or range_auto is not None:
            self.set_voltage_range(ch, volts=volts_range, auto=bool(range_auto))
        if level is not None or auto_level is not None \
                or relative_level is not None:
            self.set_trigger_level(ch, volts=level, auto=auto_level,
                                   relative=relative_level)
        if slope is not None:
            self.set_slope(ch, slope)
        if bandwidth is not None:
            self.set_bandwidth(ch, bandwidth)

    # ------------------------------------------------------------------
    # Reference clock (timebase)
    # ------------------------------------------------------------------
    def set_reference_clock(self, source=ReferenceClock.INTERNAL,
                            external_frequency=None, auto=None, verify=True):
        """
        Select the timebase of the counter (SENS:ROSC:SOUR).

        :param source: ReferenceClock.INTERNAL (internal oscillator, default) or
                       ReferenceClock.EXTERNAL (external reference at the rear
                       reference input)
        :param external_frequency: frequency of the external reference in Hz,
                                   normally 1000000, 5000000 or 10000000
                                   (SENS:ROSC:EXT:FREQ)
        :param auto: True / False -> automatic switch over to the external
                     reference when a signal is detected (SENS:ROSC:SOUR:AUTO)
        :param verify: True (default) -> read the source back and print a notice
                       when the counter keeps another one
        """
        if external_frequency is not None:
            self._wr('SENS:ROSC:EXT:FREQ %s' % self._num(external_frequency))
        if auto is not None:
            self._wr('SENS:ROSC:SOUR:AUTO %s' % self._token(auto))
        self._wr('SENS:ROSC:SOUR %s' % self._token(source))
        if verify:
            # A counter which is locked to an external reference keeps it even
            # after SOURce INT was written while the automatic switch over is on,
            # and a reference which does not match the setting scales EVERY
            # reading: a 5 MHz reference where 10 MHz is configured doubles every
            # frequency and halves every period.
            try:
                stored = self.get_reference_clock()
            except Exception:
                stored = None
            if stored is not None and \
                    self._token(source).upper() not in str(stored).upper():
                self._say("53230A: the counter reports the reference clock '%s'"
                          " although '%s' was written - every reading is scaled"
                          " by the timebase which is really used"
                          % (stored, self._token(source)))

    def get_reference_clock(self):
        """Query the timebase source (SENS:ROSC:SOUR?), 'INT' or 'EXT'"""
        return self._qr('SENS:ROSC:SOUR?')

    def get_reference_clock_auto(self):
        """Query the automatic reference selection (SENS:ROSC:SOUR:AUTO?)"""
        return self._value(self._qr('SENS:ROSC:SOUR:AUTO?'))

    def get_external_reference_frequency(self):
        """Query the external reference frequency (SENS:ROSC:EXT:FREQ?), unit Hz"""
        return self._value(self._qr('SENS:ROSC:EXT:FREQ?'))

    def check_external_reference(self):
        """
        Query whether a valid external reference is connected
        (SENS:ROSC:EXT:CHECK?) - the raw answer is returned, normally '1' when
        the external reference is valid and '0' when it is missing.
        """
        return self._qr('SENS:ROSC:EXT:CHECK?')

    # ------------------------------------------------------------------
    # Measurement functions
    # ------------------------------------------------------------------
    def configure(self, function=MeasurementFunction.FREQUENCY,
                  expected=None, resolution=None,
                  channel=None, stop_channel=None):
        """
        Select the measurement function (CONF:<function>).

        :param function: MeasurementFunction member or a plain string
        :param expected: expected value, used by the counter to choose its
                         internal settings (optional)
        :param resolution: wanted resolution (optional)
        :param channel: measurement channel, 1 or 2 (optional); when given, the
                        function and the channel are selected with SENS:FUNC
                        after the CONF command
        :param stop_channel: stop channel of a time interval / phase measurement

        The two parameters are passed through as CONF:<function> <a>,<b> and
        their meaning depends on the function: for a frequency measurement the
        expected value and the resolution, for a rise or fall time measurement
        the low and the high reference in percent.
        """
        cmd = 'CONF:%s' % self._token(function)
        if expected is not None:
            params = [self._num(expected)]
            if resolution is not None:
                params.append(self._num(resolution))
            cmd += ' ' + ','.join(params)
        self._wr(cmd)
        self.function = self._token(function)
        if channel is not None:
            self.set_measurement_function(function, channel, stop_channel)

    def set_rise_fall_references(self, low=10.0, high=90.0,
                                 function=MeasurementFunction.RISE_TIME):
        """
        Set the low and high reference of a rise or fall time measurement
        (CONF:<function> <low>,<high>), unit %.

        :param low: low reference in percent
        :param high: high reference in percent
        :param function: MeasurementFunction.RISE_TIME (default) or FALL_TIME
        """
        if float(low) >= float(high):
            raise ValueError("the low reference must be smaller than the high"
                             " reference")
        self.configure(function, expected=low, resolution=high)

    def get_configuration(self):
        """
        Query the configuration of the current function (CONFigure?), for example
        '"RTIM +1.00000000000000E+001,+9.00000000000000E+001"' (rise time with
        the references 10 % / 90 %).

        :return: the answer, or '' when the firmware does not answer it
        """
        old = self.res.timeout
        self.res.timeout = min(old, 2000)
        try:
            return self._qr('CONF?').strip()
        except Exception:
            return ''
        finally:
            self.res.timeout = old

    def set_measurement_function(self, function=MeasurementFunction.FREQUENCY,
                                 channel=None, stop_channel=None, verify=True):
        """
        Select the measurement function and its measurement channel
        (SENS:FUNC "<function> <channel>").

        A time interval or phase measurement uses a channel pair (start, stop);
        the counter confirms the channel ('SENS:FUNC "FREQ 2"' is echoed as
        'FREQ 2'), the default channel is omitted ('"FREQ 1"' answers 'FREQ').

        :param function: MeasurementFunction member or a plain string
        :param channel: measurement channel 1 or 2; None keeps the channel
                        selected by the instrument
        :param stop_channel: stop channel of a time interval / phase measurement
        :param verify: True (default) -> read the error queue and the answer of
                       SENSe:FUNCtion? after the write.  A command error (-1xx)
                       raises a RuntimeError, an execution error (-2xx, for
                       example -221 'Settings conflict' of a rise time
                       measurement) prints a notice when the function is
                       selected anyway; an error which left another function
                       selected raises as well.  A channel which does not appear
                       in the answer only warns (self.strict_channel_check = True
                       raises in that case too).  The check is done once per
                       function / channel combination.
        """
        func = self._token(function)
        channels = self._channel_text(channel, stop_channel,
                                      pair=self._is_pair_function(func))
        check = bool(verify) and channels is not None and \
            self._verify_key(func, channels) not in self._verified_channels
        if check:
            self.clear()        # empty the queue so an error belongs to this write
        if channels is None:
            cmd = 'SENS:FUNC "%s"' % func
        else:
            cmd = '%s ' % self.func_channel_cmd + \
                (self.func_channel_format % (func, channels))
        self._wr(cmd)
        self.function = func
        self.measurement_channel = channels
        if check:
            self._verify_measurement_channel(func, channels, cmd)

    @staticmethod
    def _verify_key(function, channels):
        """Key of a function / channel combination (verification cache)"""
        return ('%s %s' % (function, channels)).upper()

    def _default_channel_text(self, function):
        """
        The channel which the counter does not report: 'FREQ 1' is echoed as
        'FREQ' and 'TINT 1,2' as 'TINT', only a different channel appears.
        """
        return '1,2' if self._is_pair_function(function) else '1'

    def _verify_measurement_channel(self, function, channels, cmd):
        """
        Check that the counter accepted the function / channel selection.

            -1xx (command error)    the command itself was not accepted -> raise
            -22x (parameter value)  the value is not valid, for example
                                    'TINT 1,1' -> raise
            other -2xx (execution)  the counter understood the command but had to
                                    adjust settings -> notice, the measurement
                                    continues

        Whether the channel can be read back differs between firmware revisions,
        so a channel which does not appear in the answer of SENSe:FUNCtion? only
        warns as well.  self.strict_channel_check = True raises in both cases.

        :param cmd: the command which was sent (used in the message)
        """
        err = self.get_error()
        err_code = err.split(',')[0].strip().lstrip('+')
        answer = self._qr('SENS:FUNC?').strip()
        key = self._verify_key(function, channels)
        if err_code != '0':
            # -221 'Settings conflict; low reference >= high reference' is
            # reported while a rise time function is selected (the counter keeps
            # the function and only changes its references), -224 'Illegal
            # parameter value' for 'TINT 1,1' means nothing was selected.
            if err_code.startswith('-1') or self.strict_channel_check or \
                    not self._selection_is_active(function, channels, answer):
                raise RuntimeError(
                    "the counter refused %s: %s - the function / channel was "
                    "not selected; check the channel on the display of the "
                    "counter" % (cmd, err))
            self._say("53230A: the counter reports %s for %s - it adjusted its"
                      " settings (execution error); %s %s is selected and the"
                      " measurement continues"
                      % (err, cmd, function, channels))
            self._verified_channels.add(key)
            return
        if self._selection_is_active(function, channels, answer):
            self._verified_channels.add(key)
            return
        message = ("the counter accepted %s but reports '%s' only - the"
                   " measurement channel %s may not have been selected"
                   % (cmd, answer, channels))
        if self.strict_channel_check:
            raise RuntimeError(message + " - check the channel on the display"
                                         " of the counter")
        if not self._channel_warned:
            # whether the channel is echoed is a property of the firmware, not of
            # a single function: one notice per counter is enough
            self._channel_warned = True
            self._say("53230A: %s (notice printed once)" % message)
        self._verified_channels.add(key)

    def _selection_is_active(self, function, channels, answer=None):
        """
        True when SENSe:FUNCtion? reports the requested function / channel.

        :param answer: answer of SENSe:FUNCtion? which was read already
                       (optional, the query is sent when it is not given)
        """
        if answer is None:
            answer = self._qr('SENS:FUNC?')
        reported = str(answer).replace(' ', '').upper()
        wanted = str(channels).replace(' ', '')
        return wanted in reported or \
            (wanted == self._default_channel_text(function) and
             self._token(function).upper() in reported)

    def get_measurement_function(self):
        """Query the measurement function and its channel (SENS:FUNC?)"""
        return self._qr('SENS:FUNC?')

    def check_measurement_function_string(self,
                                          function=MeasurementFunction.FREQUENCY,
                                          channels=None):
        """
        Write one function string and report the reaction of the counter.

        The error queue is the reliable test for a function / channel form:
        'SENS:FUNC "TINT 1,2"' is accepted while 'SENS:FUNC "TINT 1,1"' answers
        -224 Illegal parameter value on the tested 53230A.

        :param function: function used for the test
        :param channels: the channel text behind the function, for example '1',
                         '2', '1,2' or '1,1'; None sends the function alone
        :return: (accepted, answer of SENSe:FUNCtion?, error queue answer)
        """
        cmd = 'SENS:FUNC "%s"' % self._token(function)
        if channels is not None:
            cmd = '%s "%s %s"' % (self.func_channel_cmd, self._token(function),
                                  channels)
        self.clear()
        self._wr(cmd)
        err = self.get_error()
        answer = self._qr('SENS:FUNC?').strip()
        accepted = err.lstrip('+').startswith('0,')
        self._say("%-28s %-8s SENS:FUNC? = %s%s"
                  % (cmd, 'accepted' if accepted else 'refused', answer,
                     '' if accepted else '   error: %s' % err))
        return accepted, answer, err

    # ------------------------------------------------------------------
    # Transition time / single input interval preparation
    # ------------------------------------------------------------------
    def set_plain_edge(self, channel=1, edge=InputSlope.NEGATIVE):
        """
        Write the trigger edge of the channel without a line number
        (INP<ch>:SLOP).

        Not every firmware revision offers this form, so the command is sent once
        only: a refusal is remembered in self.plain_edge_ok and reported.

        :param channel: input channel which is used
        :param edge: InputSlope.POSITIVE (rising) or InputSlope.NEGATIVE
        :return: True when the counter accepted the command
        """
        if not self.plain_edge_ok:
            return False
        ch = self._ch(channel)
        token = self._token(edge)
        self._wr('INP%d:SLOP %s' % (ch, token))
        err = self.get_error()
        if not self.answer_is_ok(err):
            self.plain_edge_ok = False
            self._say("53230A: the counter refused 'INP%d:SLOP %s' (%s) - the"
                      " single trigger edge of the channel is left as it is"
                      % (ch, token, err))
            return False
        return True

    def set_transition_edges(self, channel=1, edge=InputSlope.POSITIVE,
                             tries=3):
        """
        Write the two edges of a transition time / interval and read them back.

        INP<ch>:SLOP1 (start) and INP<ch>:SLOP2 (stop) are shared by the time
        interval and the rise / fall time measurement, and a leftover pair makes
        a transition time answer an edge to edge interval instead.  The two
        answers are read back and the write is repeated (up to `tries` times),
        which makes the measurement reproducible.

        :param channel: input channel which is used
        :param edge: both lines get the same edge - a rise time is measured
                     between two rising edges, a fall time between two falling
                     edges
        :param tries: number of write / read back cycles, 3 by default
        :return: (edge of line 1, edge of line 2, True when both match)
        """
        ch = self._ch(channel)
        wanted = self._slope_text(self._token(edge))

        def write_edges():
            """Write both edges and wait until the counter processed them"""
            self.set_slope(ch, edge, line=1)
            self.set_slope(ch, edge, line=2)
            self.wait_opc()
            self.settle()

        edge1 = edge2 = None
        for _ in range(max(1, int(tries))):
            write_edges()
            edge1 = self._slope_text(self.get_slope(ch, line=1))
            edge2 = self._slope_text(self.get_slope(ch, line=2))
            if edge1 == wanted and edge2 == wanted:
                return edge1, edge2, True
        return edge1, edge2, False

    def set_transition_levels(self, channel=1, low=10.0, high=90.0, tries=3,
                              tolerance=0.5, relative=True):
        """
        Write the two reference levels of a transition time / interval.

        INP<ch>:LEV1 gets the low reference and INP<ch>:LEV2 the high reference,
        both computed from the signal (INP<ch>:LEV:MIN and INP<ch>:LEV:PTP).  The
        two levels are read back because the counter sometimes keeps the level of
        its automatic level instead of the value which was written - the write is
        then repeated, which makes the transition time reproducible.

        :param channel: input channel which is used
        :param low: low reference in percent (line 1)
        :param high: high reference in percent (line 2); the same value for both
                     is used by a single input interval (the pulse width at that
                     level)
        :param tries: number of write / read back cycles, 3 by default
        :param tolerance: allowed difference in percent of the peak to peak
                          voltage, 0.5 % by default
        :param relative: True (default) -> the levels are written in percent of
                         the input signal (INP<ch>:LEV1:REL / LEV2:REL), which is
                         the native form of a transition time reference and
                         follows the signal; False -> the voltage is computed from
                         INP<ch>:LEV:MIN / LEV:PTP and written directly
        :return: (level of line 1, level of line 2, automatic level state, True
                 when the levels match and the automatic level is off)
        :raise RuntimeError: when the counter reports no signal on the channel
        """
        ch = self._ch(channel)
        minimum, ptp, _ = self.get_trigger_level_range(ch)
        if not self.is_valid_reading(ptp) or ptp <= 0:
            raise RuntimeError(
                "the counter reports no signal on channel %d (INP%d:LEV:PTP? ="
                " %s), the two levels of a transition time cannot be computed"
                % (ch, ch, ptp))
        wanted = (minimum + ptp * float(low) / 100.0,
                  minimum + ptp * float(high) / 100.0)
        limit = abs(ptp) * float(tolerance) / 100.0

        def write_levels():
            """
            Write both levels and switch the automatic level off afterwards.

            The HIGH reference (line 2) is written FIRST: the counter validates
            the pair on every write and replaces both levels with its defaults
            when the low reference is written before a high reference which is
            below it (-221 Settings conflict), which the retry loop then has to
            repair.  The automatic level is switched off afterwards because a
            level write can turn it back on and the counter answers an edge to
            edge interval instead of the transition time while it is active.
            """
            if relative:
                # in percent of the input signal: the counter converts it itself
                self.set_trigger_level(ch, relative=high, line=2)
                self.set_trigger_level(ch, relative=low, line=1)
            else:
                self.set_trigger_level(ch, volts=wanted[1], line=2)
                self.set_trigger_level(ch, volts=wanted[0], line=1)
            self.set_trigger_level(ch, auto=False)
            self.wait_opc()
            self.drain_notices('the two reference levels of channel %d' % ch)
            self.settle()

        level1 = level2 = auto = None
        for _ in range(max(1, int(tries))):
            write_levels()
            level1 = self.get_trigger_level(ch, line=1)
            level2 = self.get_trigger_level(ch, line=2)
            auto = self.get_trigger_level_auto(ch)
            if self.is_valid_reading(level1) and self.is_valid_reading(level2) \
                    and abs(level1 - wanted[0]) <= limit \
                    and abs(level2 - wanted[1]) <= limit and not auto:
                return level1, level2, auto, True
        return level1, level2, auto, False

    def prepare_transition_time(self, function=MeasurementFunction.RISE_TIME,
                                channel=1, references=(10, 90), attempt=1):
        """
        One of the five recipes which prepare a rise / fall time measurement.

        RTIM / FTIM are intervals between the two levels INP<ch>:LEV1 / LEV2 of
        the counter.  A level pair or an edge pair which does not fit the signal
        makes it answer an edge to edge interval (the pulse width) instead of the
        transition time, and which state the counter keeps is run to run
        different - so several recipes are available and the test repeats a row
        with the next one when the reading is not a transition time:

            1 *RST + the function and the channel + the references + the input
              settings of the test + both edges of the function + the explicit
              levels (automatic level off)
            2 like 1 without *RST
            3 like 1, but the two levels are written in percent of the signal
            4 the two edges + the references + a fresh automatic level
              (INP<ch>:LEV:AUTO ONCE)
            5 like 1 with the single trigger edge written as well (INP<ch>:SLOP)

        The function is selected FIRST, because selecting it re-initialises its
        settings.  Both edges and levels are read back and the automatic level has
        to be off, which is what makes a transition time work on the tested unit.
        Every recipe stops a running measurement (ABORt), leaves the free running
        mode (the spelling is looked for, see FREE_RUNNING_COMMANDS) and pauses
        (settle()) after the setting writes, which grows with the recipe number.

        :param function: MeasurementFunction.RISE_TIME (default) or FALL_TIME
        :param channel: input channel which is used
        :param references: low / high reference in percent
        :param attempt: 1 ... 5
        :raise RuntimeError: when the counter reports no signal on the channel
        """
        ch = self._ch(channel)
        edge = InputSlope.NEGATIVE \
            if self._token(function).upper().startswith('FTIM') \
            else InputSlope.POSITIVE
        edge_text = self._slope_text(self._token(edge))
        # a measurement which was started with the previous settings can come
        # back as the new result of READ?, so every recipe starts from a clean,
        # single shot measurement state
        self._write_once('ABOR', 'stop a running measurement')
        self._write_first(FREE_RUNNING_COMMANDS,
                          'leaving the free running mode')
        if attempt in (1, 5):
            # the counter keeps the pair and the edges of the measurement which
            # was done last, and a leftover error can block the setup as well
            self.reset()
        self.set_measurement_function(function, ch)
        self.set_rise_fall_references(references[0], references[1],
                                      function=function)
        self.settle()
        if attempt != 4:
            # the input state of the functional test: without it a transition
            # time answers the pulse width once a measurement changed the
            # coupling / the level
            self.configure_input(channel=ch, coupling=InputCoupling.DC,
                                 impedance=InputImpedance.OHM_1M,
                                 volts_range=5.0, auto_level=True,
                                 bandwidth=False)
        if attempt == 5:
            # the single trigger edge of the channel: a unit which uses it to
            # decide the direction of a transition time needs it to point in the
            # direction of the edge which is measured
            self.set_plain_edge(ch, edge)
        _, _, edges_ok = self.set_transition_edges(ch, edge)
        if not edges_ok:
            self._say("53230A: the counter did not keep the two edges of"
                      " channel %d (%s / %s instead of %s / %s) - the transition"
                      " time may not be measured correctly"
                      % (ch, self._slope_text(self.get_slope(ch, line=1)),
                         self._slope_text(self.get_slope(ch, line=2)),
                         edge_text, edge_text))
        if attempt == 4:
            # let the counter build its pair of levels from the signal
            self.set_trigger_level(ch, auto=LevelAuto.ONCE)
            self.wait_opc()
            self.drain_notices('the automatic level of channel %d' % ch)
            self.settle()
            return
        _, _, auto, levels_ok = self.set_transition_levels(
            ch, references[0], references[1], relative=(attempt == 3))
        if not levels_ok:
            self._say("53230A: the counter did not keep the two levels of"
                      " channel %d (%s %% / %s %% of the signal) - the"
                      " transition time may not be measured correctly"
                      % (ch, references[0], references[1]))
            if auto:
                self._say("53230A: the automatic level of channel %d is still on"
                          " (INP%d:LEV:AUTO? = %s) - the counter answers an edge"
                          " to edge interval instead of the transition time while"
                          " it is active" % (ch, ch, auto))
        self.drain_notices('the settings of recipe %d' % attempt)
        self.wait_opc()
        # the counter has to build its reference points from the levels which
        # were written; the pause grows with the recipe number, so a unit which
        # simply needs more time is served by the later recipes
        self.settle(self.settle_time + 0.1 * (attempt - 1))

    # ------------------------------------------------------------------
    # Single shot measurements (MEASure:<function>?)
    # ------------------------------------------------------------------
    def measure(self, function=MeasurementFunction.FREQUENCY, channel=None,
                stop_channel=None):
        """
        Take a single measurement of any function (MEAS:<function>?).

        :param function: MeasurementFunction member (or a plain string)
        :param channel: measurement channel, 1 or 2 (optional); when given, the
                        function and the channel are selected with SENS:FUNC
                        before the reading
        :param stop_channel: stop channel of a time interval / phase measurement
        """
        if channel is not None:
            self.set_measurement_function(function, channel, stop_channel)
        else:
            self.function = self._token(function)
        return self._value(self._qr('MEAS:%s?' % self._token(function)))

    def measure_frequency(self, channel=None):
        """Measure the frequency (MEAS:FREQ?), unit Hz"""
        return self.measure(MeasurementFunction.FREQUENCY, channel)

    def measure_period(self, channel=None):
        """Measure the period (MEAS:PER?), unit s"""
        return self.measure(MeasurementFunction.PERIOD, channel)

    def measure_pulse_width(self, channel=None):
        """
        Measure the positive pulse width (MEAS:PWID?), unit s - the interval
        between the rising and the falling edge of the signal on one input.
        """
        return self.measure(MeasurementFunction.PULSE_WIDTH, channel)

    def measure_negative_pulse_width(self, channel=None):
        """
        Measure the negative pulse width (MEAS:NWID?), unit s - the interval
        between the falling and the rising edge of the signal on one input.
        """
        return self.measure(MeasurementFunction.NEGATIVE_PULSE_WIDTH, channel)

    def measure_duty_cycle(self, channel=None):
        """
        Measure the positive duty cycle (MEAS:PDUT?).

        The tested 53230A answers the RATIO (0.5 for a 50 % duty cycle), use
        measure_duty_cycle_percent() for the percentage.
        """
        return self.measure(MeasurementFunction.DUTY_CYCLE, channel)

    def measure_duty_cycle_percent(self, channel=None):
        """
        Measure the positive duty cycle in percent (MEAS:PDUT? * 100).

        A firmware which answers the percentage directly is read with
        measure_duty_cycle() instead - check the value with a known signal.
        """
        return self.measure_duty_cycle(channel) * 100.0

    def measure_rise_time(self, channel=None):
        """
        Measure the rise time (MEAS:RTIM?), unit s.

        The counter derives the low and high reference from the signal; see
        set_rise_fall_references() and prepare_transition_time() for the explicit
        references the functional test uses.
        """
        return self.measure(MeasurementFunction.RISE_TIME, channel)

    def measure_fall_time(self, channel=None):
        """Measure the fall time (MEAS:FTIM?), unit s - see measure_rise_time()"""
        return self.measure(MeasurementFunction.FALL_TIME, channel)

    def measure_time_interval(self, channel=None, stop_channel=None):
        """
        Measure the time interval between two channels (MEAS:TINT?), unit s.

        :param channel: start channel of the measurement, 1 (default) or 2
        :param stop_channel: stop channel (optional), the other channel is used
                             when it is not given
        """
        return self.measure(MeasurementFunction.TIME_INTERVAL, channel,
                            stop_channel)

    def measure_phase(self, channel=None, stop_channel=None):
        """
        Measure the phase between two channels (MEAS:PHAS?), unit degrees.

        :param channel: channel of the reference signal, 1 (default) or 2
        :param stop_channel: second channel (optional), the other channel is used
                             when it is not given
        """
        return self.measure(MeasurementFunction.PHASE, channel, stop_channel)

    def measure_single_period(self, channel=None):
        """
        Measure the period of a single input cycle (MEAS:SPER?), unit s - the
        time between two rising edges of the input, so PWID + NWID = SPER.
        """
        return self.measure(MeasurementFunction.SINGLE_PERIOD, channel)

    # ------------------------------------------------------------------
    # Sample count, initiate / fetch / read
    # ------------------------------------------------------------------
    def set_sample_count(self, count=1):
        """Set the number of samples taken per trigger (SAMP:COUN <n>)"""
        count = int(count)
        if count < 1:
            raise ValueError("sample count must be greater than or equal to 1")
        self._wr('SAMP:COUN %d' % count)

    def get_sample_count(self):
        """Query the number of samples per trigger (SAMP:COUN?)"""
        return int(self._value(self._qr('SAMP:COUN?')))

    def init(self):
        """Start a measurement (INIT[:IMM]) without reading the result"""
        self._wr('INIT')

    def fetch(self):
        """
        Read the result of a running measurement (FETC?).

        :return: float for one sample, else a list of floats
        """
        values = self._values(self._qr('FETC?'))
        return values[0] if len(values) == 1 else values

    def abort(self):
        """Stop the measurement (ABOR)"""
        self._wr('ABOR')

    def read(self, channel=None, stop_channel=None, timeout=None):
        """
        Start a measurement and read the result (READ? = INITiate + FETCh?).

        :param channel: measurement channel, 1 or 2 (optional); when given, the
                        remembered function and the channel are selected with
                        SENS:FUNC before the measurement
        :param stop_channel: stop channel of a time interval / phase measurement
        :param timeout: optional timeout in ms for this reading; a long gate time
                        or a large sample count needs more time than the default
        :return: float for one sample, else a list of floats
        """
        if channel is not None:
            self.set_measurement_function(
                self.function or MeasurementFunction.FREQUENCY,
                channel, stop_channel)
        if timeout is None:
            values = self._values(self._qr('READ?'))
        else:
            old = self.res.timeout
            self.res.timeout = timeout
            try:
                values = self._values(self._qr('READ?'))
            finally:
                self.res.timeout = old
        return values[0] if len(values) == 1 else values

    # ------------------------------------------------------------------
    # Trigger (TRIGger subsystem)
    # ------------------------------------------------------------------
    def set_trigger_source(self, source=TriggerSource.IMMEDIATE):
        """
        Select the trigger source (TRIG:SOUR): IMMediate (default, the
        measurement starts as soon as the counter is ready), EXTernal (trigger
        input) or BUS (software trigger, *TRG).
        """
        self._wr('TRIG:SOUR %s' % self._token(source))

    def get_trigger_source(self):
        """Query the trigger source (TRIG:SOUR?)"""
        return self._qr('TRIG:SOUR?')

    def set_trigger_slope(self, slope=TriggerSlope.POSITIVE):
        """Set the slope of the external trigger input (TRIG:SLOP)"""
        self._wr('TRIG:SLOP %s' % self._token(slope))

    def get_trigger_slope(self):
        """Query the slope of the external trigger input (TRIG:SLOP?)"""
        return self._qr('TRIG:SLOP?')

    def set_trigger_count(self, count=1):
        """Set the number of triggers the counter reacts on (TRIG:COUN <n>)"""
        count = int(count)
        if count < 1:
            raise ValueError("trigger count must be greater than or equal to 1")
        self._wr('TRIG:COUN %d' % count)

    def get_trigger_count(self):
        """Query the trigger count (TRIG:COUN?)"""
        return int(self._value(self._qr('TRIG:COUN?')))

    def set_trigger_delay(self, seconds=0.0):
        """Set the delay between trigger and measurement start (TRIG:DEL <s>)"""
        self._wr('TRIG:DEL %s' % self._num(seconds))

    def get_trigger_delay(self):
        """Query the trigger delay (TRIG:DEL?), unit s"""
        return self._value(self._qr('TRIG:DEL?'))

    def configure_trigger(self, source=None, slope=None, count=None, delay=None):
        """
        Configure the trigger with one call - only the parameters which are not
        None are sent, the meaning is the same as in the individual methods.
        """
        if source is not None:
            self.set_trigger_source(source)
        if slope is not None:
            self.set_trigger_slope(slope)
        if count is not None:
            self.set_trigger_count(count)
        if delay is not None:
            self.set_trigger_delay(delay)

    # ------------------------------------------------------------------
    # Gate
    # ------------------------------------------------------------------
    def set_gate_source(self, function=MeasurementFunction.FREQUENCY,
                        source=GateSource.TIMER):
        """
        Select the gate source of a measurement (SENS:<function>:GATE:SOUR).

        The internal gate timer is the power-on default, so a measurement which
        uses it does not have to write this command.  The tested 53230A answers
        -224 Illegal parameter value for 'SENS:FREQ:GATE:SOUR TIM', which is why
        measure_gated() leaves the gate source untouched.
        """
        self._wr('%s %s' % (self._gate_node(function, 'SOUR'),
                            self._token(source)))

    def get_gate_source(self, function=MeasurementFunction.FREQUENCY):
        """Query the gate source (SENS:<function>:GATE:SOUR?)"""
        return self._qr('%s?' % self._gate_node(function, 'SOUR'))

    def set_gate_time(self, seconds=1.0, function=MeasurementFunction.FREQUENCY):
        """
        Set the gate time (SENS:FREQ:GATE:TIME or SENS:TOT:GATE:TIME), unit s.

        The gate time is the measurement window over which the counter averages.
        Frequency, period and single period measurements share this setting; a
        time interval or phase measurement is gated by the input edges and has no
        gate timer, a ValueError is raised for these functions.
        """
        if not self._has_gate_timer(function):
            raise ValueError("the function %s has no gate timer"
                             % self._token(function))
        self.gate_time = float(seconds)
        self._wr('%s %s' % (self._gate_node(function, 'TIME'),
                            self._num(seconds)))

    def get_gate_time(self, function=MeasurementFunction.FREQUENCY):
        """Query the gate time (SENS:FREQ:GATE:TIME?), unit s"""
        if not self._has_gate_timer(function):
            raise ValueError("the function %s has no gate timer"
                             % self._token(function))
        return self._value(self._qr('%s?' % self._gate_node(function, 'TIME')))

    def set_gate_polarity(self, function=MeasurementFunction.FREQUENCY,
                          polarity=GatePolarity.POSITIVE):
        """Set the polarity of the gate signal (SENS:<function>:GATE:POL)"""
        self._wr('%s %s' % (self._gate_node(function, 'POL'),
                            self._token(polarity)))

    def get_gate_polarity(self, function=MeasurementFunction.FREQUENCY):
        """Query the polarity of the gate signal (SENS:<function>:GATE:POL?)"""
        return self._qr('%s?' % self._gate_node(function, 'POL'))

    def configure_gate(self, function=MeasurementFunction.FREQUENCY,
                       source=GateSource.TIMER, gate_time=None, polarity=None):
        """
        Configure the gate of a measurement with one call.

        :param source: GateSource.TIMER (default) or GateSource.EXTERNAL; None
                       leaves the gate source as it is (measure_gated() does that,
                       the internal gate timer is the power-on default)
        :param gate_time: gate time in s (optional), only sent when the function
                          has a gate timer
        :param polarity: GatePolarity of the gate signal (optional)
        """
        if source is not None:
            self.set_gate_source(function, source)
        if polarity is not None:
            self.set_gate_polarity(function, polarity)
        if gate_time is not None:
            if self._has_gate_timer(function):
                self.set_gate_time(gate_time, function)
            else:
                # a time interval / phase measurement is gated by the input
                # edges, the instrument has no gate time for it
                self.gate_time = float(gate_time)

    # ------------------------------------------------------------------
    # Triggered and gated measurement with the internal reference clock
    # ------------------------------------------------------------------
    def measure_gated(self, function=MeasurementFunction.FREQUENCY, gate_time=1.0,
                      channel=1, stop_channel=None, samples=1,
                      reference=ReferenceClock.INTERNAL,
                      external_reference_frequency=None,
                      trigger_source=TriggerSource.IMMEDIATE,
                      trigger_slope=None, trigger_count=None, trigger_delay=None,
                      coupling=None, impedance=None, volts_range=None,
                      trigger_level=None, auto_level=None, slope=None,
                      bandwidth=None, timeout=None, check_steps=False):
        """
        Triggered and gated measurement.

        Sequence: a running measurement is stopped (ABORt) -> the timebase is
        selected -> the function and the measurement channel are selected
        (CONF:<function>, SENSe:FUNCtion "<function> <channel>") -> the input
        channel is configured (only the parameters which are not None are sent)
        -> the trigger is configured -> the gate is configured and the gate time
        is written -> the counter gets a moment to process the settings
        (settle()) -> the measurement is started and read with READ?.

        :param function: MeasurementFunction - typically FREQUENCY, PERIOD or
                         TIME_INTERVAL
        :param gate_time: gate (measurement) time in s for frequency / period /
                          single period / totalize; a time interval measurement is
                          gated by the input edges and does not use it
        :param channel: measurement channel and input channel of the trigger
                        settings, 1 (default) or 2
        :param stop_channel: stop channel of a time interval / phase measurement,
                        the channel pair is then (channel, stop_channel)
        :param samples: number of readings, 1 (default) or more
        :param reference: ReferenceClock.INTERNAL (default) or EXTERNAL
        :param external_reference_frequency: frequency of the external reference
                                             in Hz (optional)
        :param trigger_source: TriggerSource, default IMMEDIATE
        :param trigger_slope / trigger_count / trigger_delay: trigger settings
                        (optional)
        :param coupling / impedance / volts_range / trigger_level / auto_level /
               slope / bandwidth: input settings (optional)
        :param timeout: optional timeout in ms for the reading; the default is
                        derived from the gate time and the number of samples
        :param check_steps: True -> read the error queue after every step and
                            print the step which the counter refused
        :return: float for a single sample, else a list of floats
        """
        def step_error(label):
            """Report an error of a step (only with check_steps=True)"""
            if check_steps:
                self.check_error(label)

        # a measurement which was started with the PREVIOUS settings can be in
        # flight, and READ? would return that result instead of the one of the
        # new setup (measured on hardware: a frequency of 1956.8 Hz for a 1 kHz
        # signal).  The free running mode cannot be switched off with a remote
        # command on the tested 53230A, ABORt is the command which works; a
        # firmware which refuses it is reported once.
        self._write_once('ABOR', 'stop a running measurement')

        self.set_reference_clock(reference, external_reference_frequency)
        step_error('1 reference clock')

        self.configure(function)
        step_error('2 CONFigure %s' % self._token(function))
        self.set_measurement_function(function, channel, stop_channel)
        step_error('3 SENSe:FUNCtion %s %s' % (self._token(function), channel))

        # a channel pair only gives start / stop of the measurement, the input
        # settings belong to the first channel of the pair
        input_channel = self._ch(channel[0] if isinstance(channel, (tuple, list))
                                 else channel)
        self.configure_input(channel=input_channel, coupling=coupling,
                             impedance=impedance, volts_range=volts_range,
                             level=trigger_level, auto_level=auto_level,
                             slope=slope, bandwidth=bandwidth)
        step_error('4 input settings of channel %d' % input_channel)

        self.configure_trigger(source=trigger_source, slope=trigger_slope,
                               count=trigger_count, delay=trigger_delay)
        step_error('5 TRIGger subsystem')

        # only the gate time is written: the internal gate timer is the power-on
        # default and the tested 53230A refuses 'SENS:FREQ:GATE:SOUR TIM'
        self.configure_gate(function, source=None, gate_time=gate_time)
        step_error('6 gate of %s' % self._token(function))
        if check_steps and self._has_gate_timer(function):
            try:
                stored = self.get_gate_time(function)
                if abs(stored - float(gate_time)) > 1e-12:
                    self._say("53230A: the counter reports the gate time %s s"
                              " although %s s was written" % (stored, gate_time))
            except Exception as exc:
                self._say("53230A: the gate time cannot be read back: %s" % exc)

        samples = int(samples)
        self.set_sample_count(samples)
        step_error('7 SAMPle:COUNt')
        if timeout is None:
            timeout = max(self.timeout,
                          int(abs(self.gate_time) * samples * 3000) + 5000)
        # the settings have to be processed before the measurement starts: the
        # commands above follow each other within milliseconds and a setting which
        # is not applied yet gives a reading which does not belong to this setup
        self.settle()
        return self.read(timeout=timeout)

    def measure_frequency_gated(self, gate_time=1.0, channel=1, samples=1,
                                **kwargs):
        """
        Gated frequency measurement, unit Hz (see measure_gated).

        :param gate_time: gate time in s, a long gate time gives a higher
                          resolution
        :param channel: measurement channel, 1 (default) or 2
        :param samples: number of readings, 1 (default) or more
        """
        return self.measure_gated(MeasurementFunction.FREQUENCY,
                                  gate_time=gate_time, channel=channel,
                                  samples=samples, **kwargs)

    def measure_period_gated(self, gate_time=1.0, channel=1, samples=1, **kwargs):
        """
        Gated period measurement, unit s (see measure_gated).

        :param gate_time: gate time in s, the counter averages over this time
        :param channel: measurement channel, 1 (default) or 2
        :param samples: number of readings, 1 (default) or more
        """
        return self.measure_gated(MeasurementFunction.PERIOD,
                                  gate_time=gate_time, channel=channel,
                                  samples=samples, **kwargs)

    def measure_time_interval_gated(self, gate_time=1.0, channel=1,
                                    stop_channel=None, samples=1, **kwargs):
        """
        Gated time interval measurement, unit s (see measure_gated).

        The interval is measured between the edges of the start channel and the
        stop channel (the other channel when stop_channel is not given).  The
        start / stop edge and level are selected with set_slope() /
        set_trigger_level(line=1|2); both channels need a valid level and slope,
        otherwise the counter answers INVALID_READING.

        A same channel pair ('TINT 1,1') is refused by the tested 53230A with
        -224, the single channel form 'TINT 1' is selected with channel=(1,) and
        measures the interval between the two edges of that input (see
        FREQ53230A_TINT_TEST).  The alternatives are measure_pulse_width()
        (rising -> falling), measure_negative_pulse_width() (falling -> rising)
        and measure_single_period() (rising -> rising).

        :param gate_time: expected measurement duration in s (timeout only)
        :param channel: start channel of the measurement, 1 (default) or 2
        :param stop_channel: stop channel (optional); the same channel as
                             'channel' gives an edge to edge measurement on one
                             input, use channel=(1,) for the single channel form
        :param samples: number of readings, 1 (default) or more
        """
        return self.measure_gated(MeasurementFunction.TIME_INTERVAL,
                                  gate_time=gate_time, channel=channel,
                                  stop_channel=stop_channel, samples=samples,
                                  **kwargs)


# ==============================================================================
# Functional test - one function per measurement item
#
# FREQ53230A_INIT() prepares the counter and is the only place which connects;
# every item function measures, prints exactly one result line and returns the
# value, so the counter is created once by the caller:
#
#     counter = FREQ53230A_INIT('USB0::0x0957::0x1907::MY64200013::INSTR')
#     if counter is not None:
#         print(FREQ53230A_FREQ_TEST(counter, gate_time=0.1, channel=1))
#         counter.close()
#
# FREQ53230A_TEST() at the end of the section runs every item over ONE
# connection and adds the cross checks FREQ x PER = 1, PWID + NWID = SPER and
# TINT = PWID.
# ==============================================================================

def FREQ53230A_INIT(addr, channel=1, verbose=False):
    """
    Prepare a counter for the test functions.

    Connect -> *RST (waited for with *OPC?) -> the input settings of the test
    (DC coupling, 1 Mohm, 5 V range, automatic trigger level, rising slope,
    bandwidth limiting filter off) of the measurement channel -> the automatic
    reference selection off + the internal reference clock.  A timebase which
    does not match its setting scales every reading of the counter, so the
    internal oscillator is not only written but confirmed by reading it back.
    The counter is put into quiet mode (self.quiet), so the item functions report
    their measurement only; verbose=True keeps the notices of the driver as well.

    :param addr: VISA resource string, e.g.
                 'USB0::0x0957::0x1907::MY64200013::INSTR'
    :param channel: input channel which is used, 1 (default) or 2
    :param verbose: True -> print the notices of the driver as well
    :return: the configured counter, or None when there is no connection
    """
    counter = FREQ53230A(addr)
    if not counter.connected:
        return None
    counter.quiet = not verbose
    counter.reset()
    counter.configure_input(channel=channel, coupling=InputCoupling.DC,
                            impedance=InputImpedance.OHM_1M,
                            volts_range=5.0, auto_level=True,
                            slope=InputSlope.POSITIVE, bandwidth=False)
    counter.check_error('input settings')
    # the automatic switch over to an external reference is switched off before
    # the internal oscillator is selected: a reference which does not match its
    # setting scales every reading, and SOURce INT alone does not leave such a
    # lock while the automatic switch over is on.  Not every firmware revision
    # offers the command, so it goes through _write_first().
    counter._write_first(('SENS:ROSC:SOUR:AUTO OFF',),
                         'switching the automatic reference selection off')
    counter.set_reference_clock(ReferenceClock.INTERNAL)
    return counter


def _report(name, value, unit, note=''):
    """One result line of a measurement item, e.g. 'PWID  : 0.0005 s'"""
    print("%-5s : %s %s%s" % (name, value, unit, note))


def _reading_note(counter, value):
    """Note of a result line: an invalid reading (9.91e+37) is marked"""
    return '' if counter.is_valid_reading(value) \
        else '   (no valid reading - check the input signal)'


def _test_input(counter, channel):
    """
    Write the input settings of the functional test to one channel.

    FREQ53230A_INIT() configures its own channel only and a channel keeps the
    state of the last measurement which touched it, so the input of a channel
    which the preparation never configured stays as `*RST` / the front panel left
    it - the tested 53230A answered 1950 ... 1989 Hz for a 1 kHz signal on a
    channel which was in AC coupling.  Every item writes the settings of the
    channel it measures before it starts, which is also what the time interval /
    phase items do with their stop channel.

    The trigger slope is NOT written here: a time interval and a rise / fall time
    measurement set INP<ch>:SLOP1 / SLOP2 themselves.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is measured, 1 or 2
    """
    counter.configure_input(channel=channel, coupling=InputCoupling.DC,
                            impedance=InputImpedance.OHM_1M,
                            volts_range=5.0, auto_level=True, bandwidth=False)


def _test_transition_time(counter, function, name, channel=1, references=(10, 90),
                          transition_recipes=(1, 2)):
    """
    Measure a rise / fall time (the implementation of FTIM and RTIM).

    The pulse width of the same input is measured first as the reference: a
    transition time is a small fraction of it (the pulse width is what the
    counter answers when the preparation did not work).  Every recipe of
    `transition_recipes` is prepared and measured TRANSITION_REPEATS times until
    the reading is a transition time.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param function: MeasurementFunction.RISE_TIME or FALL_TIME
    :param name: name used for the result line, 'RTIM' or 'FTIM'
    :param channel: input channel which is used, 1 (default) or 2
    :param references: low / high reference in percent, (10, 90) by default
    :param transition_recipes: recipes of prepare_transition_time() which are
                               tried
    :return: the transition time in s, or None when the measurement failed
    """
    try:
        ch = counter._ch(channel)
        reference = counter.measure_pulse_width(ch)
        recipes = tuple(transition_recipes) or (1, 2)

        def plausible(value):
            """A transition time is a small fraction of the pulse width"""
            if not counter.is_valid_reading(value) or \
                    not counter.is_valid_reading(reference):
                return True
            return abs(value) <= 0.2 * abs(reference)

        value, good = None, False
        for attempt in recipes:
            for _ in range(TRANSITION_REPEATS):
                counter.prepare_transition_time(function, ch, references,
                                                attempt)
                value = counter.read()
                good = plausible(value)
                if good:
                    break
            if good:
                break
        note = ''
        if not counter.is_valid_reading(value):
            note = '   (no valid reading - check the input signal)'
        elif not good:
            note = '   (not the expected result - check the input signal)'
        _report(name, value, 's', note)
        return value
    except Exception as exc:
        print("%-5s : FAILED - %s" % (name, exc))
        return None


def FREQ53230A_FREQ_TEST(counter, gate_time=1.0, channel=1, samples=1):
    """
    Measure the frequency, unit Hz; the value is printed as
    'FREQ  : <value> Hz' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param gate_time: gate (measurement) time in s, 1.0 by default - a longer
                      gate time gives a higher resolution
    :param channel: input channel which is used, 1 (default) or 2
    :param samples: number of readings, 1 (default) or more (the answer is then
                    a list)
    :return: the frequency in Hz, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_frequency_gated(gate_time=gate_time,
                                                channel=channel,
                                                samples=samples)
        _report('FREQ', value, 'Hz')
        return value
    except Exception as exc:
        print("FREQ  : FAILED - %s" % exc)
        return None


def FREQ53230A_PER_TEST(counter, gate_time=1.0, channel=1, samples=1):
    """
    Measure the period, unit s; the value is printed as 'PER   : <value> s' and
    returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param gate_time: gate (measurement) time in s, 1.0 by default
    :param channel: input channel which is used, 1 (default) or 2
    :param samples: number of readings, 1 (default) or more
    :return: the period in s, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_period_gated(gate_time=gate_time,
                                             channel=channel, samples=samples)
        _report('PER', value, 's')
        return value
    except Exception as exc:
        print("PER   : FAILED - %s" % exc)
        return None


def FREQ53230A_PWID_TEST(counter, channel=1):
    """
    Measure the positive pulse width (rising -> falling edge of one input),
    unit s; it is the reference of NWID and SPER and of the transition time
    checks.  The value is printed as 'PWID  : <value> s' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :return: the pulse width in s, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_pulse_width(counter._ch(channel))
        _report('PWID', value, 's', _reading_note(counter, value))
        return value
    except Exception as exc:
        print("PWID  : FAILED - %s" % exc)
        return None


def FREQ53230A_NWID_TEST(counter, channel=1):
    """
    Measure the negative pulse width (falling -> rising edge of one input),
    unit s; together with PWID the two edges of one input are covered.  The value
    is printed as 'NWID  : <value> s' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :return: the negative pulse width in s, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_negative_pulse_width(counter._ch(channel))
        _report('NWID', value, 's', _reading_note(counter, value))
        return value
    except Exception as exc:
        print("NWID  : FAILED - %s" % exc)
        return None


def FREQ53230A_PDUT_TEST(counter, channel=1):
    """
    Measure the positive duty cycle in percent; the tested 53230A answers the
    ratio (0.5 for a 50 % signal), so the value is multiplied by 100.  The value
    is printed as 'PDUT  : <value> %' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :return: the duty cycle in percent, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_duty_cycle_percent(counter._ch(channel))
        _report('PDUT', value, '%')
        return value
    except Exception as exc:
        print("PDUT  : FAILED - %s" % exc)
        return None


def FREQ53230A_TINT_TEST(counter, channel=1, stop_channel=None):
    """
    Measure the time interval, unit s.

    stop_channel = None (default) -> ONE input: the start edge is the rising edge
    (INP<ch>:SLOP1) and the stop edge the falling edge (INP<ch>:SLOP2) of
    `channel`, so the interval is the pulse width.  The tested 53230A refuses a
    same channel pair ('TINT 1,1', -224) but accepts the single channel form
    'TINT 1', which is confirmed before it is used.

    stop_channel = 2 (for channel 1) -> the interval between the edges of two
    channels; both channels need a valid trigger level, the stop channel is
    configured here as well.

    The value is printed as 'TINT  : <value> s' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :param stop_channel: stop channel of the measurement (optional, see above)
    :return: the time interval in s, or None when the measurement failed
    """
    try:
        ch = counter._ch(channel)
        stop = None if stop_channel is None else counter._ch(stop_channel)
        _test_input(counter, ch)
        if stop is None or stop == ch:
            counter.set_slope(ch, InputSlope.POSITIVE, line=1)
            counter.set_slope(ch, InputSlope.NEGATIVE, line=2)
            counter.check_error('start / stop edge of the time interval')
            accepted, _, _ = counter.check_measurement_function_string(
                MeasurementFunction.TIME_INTERVAL, str(ch))
            if not accepted:
                print("TINT  : a single input time interval is not offered by"
                      " this firmware - use PWID, NWID and SPER instead")
                return None
            value = counter.measure_time_interval_gated(channel=(ch,))
        else:
            _test_input(counter, stop)
            value = counter.measure_time_interval_gated(channel=ch,
                                                        stop_channel=stop)
        _report('TINT', value, 's', _reading_note(counter, value))
        return value
    except Exception as exc:
        print("TINT  : FAILED - %s" % exc)
        return None


def FREQ53230A_FTIM_TEST(counter, channel=1, references=(10, 90),
                         transition_recipes=(1, 2, 3, 4, 5)):
    """
    Measure the fall time, unit s.

    The fall time is the time in which the falling edge of the input passes the
    two reference levels, which are given in percent of the signal ((10, 90) by
    default, (20, 80) is used as well).  The counter gets the two levels written
    (automatic level off) and both edges of the channel set to falling, see
    prepare_transition_time().

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :param references: low / high reference in percent, (10, 90) by default
    :param transition_recipes: recipes of prepare_transition_time() which are
                               tried until the reading is a transition time
    :return: the fall time in s, or None when the measurement failed
    """
    return _test_transition_time(counter, MeasurementFunction.FALL_TIME, 'FTIM',
                                 channel, references, transition_recipes)


def FREQ53230A_RTIM_TEST(counter, channel=1, references=(10, 90),
                         transition_recipes=(1, 2, 3, 4, 5)):
    """
    Measure the rise time, unit s.

    The rise time is the time in which the rising edge of the input passes the
    two reference levels; the arguments are the same as in
    FREQ53230A_FTIM_TEST().  Both edges of the input are set to rising for this
    measurement.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :param references: low / high reference in percent, (10, 90) by default
    :param transition_recipes: recipes of prepare_transition_time() which are
                               tried until the reading is a transition time
    :return: the rise time in s, or None when the measurement failed
    """
    return _test_transition_time(counter, MeasurementFunction.RISE_TIME, 'RTIM',
                                 channel, references, transition_recipes)


def FREQ53230A_PHAS_TEST(counter, channel=1, stop_channel=None):
    """
    Measure the phase between two channels, unit degrees; the value is printed as
    'PHAS  : <value> deg' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: reference channel, 1 (default) or 2
    :param stop_channel: second channel (optional), the other channel is used
                         when it is not given
    :return: the phase in degrees, or None when the measurement failed
    """
    try:
        ch = counter._ch(channel)
        stop = (2 if ch == 1 else 1) if stop_channel is None \
            else counter._ch(stop_channel)
        # both channels are measured by this item, so both are configured
        _test_input(counter, ch)
        _test_input(counter, stop)
        value = counter.measure_phase(ch, stop)
        note = '' if counter.is_valid_reading(value) \
            else '   (no valid reading - check the signal of both channels)'
        _report('PHAS', value, 'deg', note)
        return value
    except Exception as exc:
        print("PHAS  : FAILED - %s" % exc)
        return None


def FREQ53230A_SPER_TEST(counter, channel=1):
    """
    Measure the single period (the time between two rising edges of the input),
    unit s; the value is printed as 'SPER  : <value> s' and returned.

    :param counter: a counter which is connected and prepared (FREQ53230A_INIT)
    :param channel: input channel which is used, 1 (default) or 2
    :return: the single period in s, or None when the measurement failed
    """
    try:
        _test_input(counter, channel)
        value = counter.measure_single_period(counter._ch(channel))
        _report('SPER', value, 's', _reading_note(counter, value))
        return value
    except Exception as exc:
        print("SPER  : FAILED - %s" % exc)
        return None


def FREQ53230A_TEST(addr, gate_time=1.0, channel=1, stop_channel=None,
                    samples=1, rtime_references=(10, 90),
                    transition_recipes=(1, 2, 3, 4, 5)):
    """
    Functional test of the Keysight 53230A over ONE connection.

    Every item of the module is measured in the order which the shared resources
    of the counter need (the transition time rows after the single input
    intervals), one result line per reading, followed by the cross checks

        FREQ x PER = 1, PWID + NWID = SPER and TINT = PWID.

    :param addr: VISA resource string
    :param gate_time: gate time of the frequency / period measurement in s
    :param channel: input channel used for the measurements
    :param stop_channel: stop channel of the time interval / phase measurement
                         (None -> one input for TINT, the other channel for PHAS)
    :param samples: number of readings per measurement
    :param rtime_references: low / high reference of the rise / fall time
                             measurement in percent, (10, 90) by default
    :param transition_recipes: recipes of prepare_transition_time() which are
                               tried when a transition time row does not answer a
                               transition time
    :return: True when every measurement worked and every cross check passed,
             else False
    """
    counter = FREQ53230A_INIT(addr, channel)
    if counter is None:
        print("53230A test FAILED: no connection to %s" % addr)
        return False
    try:
        single_input = stop_channel is None or \
            counter._ch(stop_channel) == counter._ch(channel)
        print("IDN   : %s" % counter.idn())
        values = {}
        for name, call in (
                ("FREQ", lambda: FREQ53230A_FREQ_TEST(
                    counter, gate_time=gate_time, channel=channel,
                    samples=samples)),
                ("PER", lambda: FREQ53230A_PER_TEST(
                    counter, gate_time=gate_time, channel=channel,
                    samples=samples)),
                ("PWID", lambda: FREQ53230A_PWID_TEST(counter, channel=channel)),
                ("TINT", lambda: FREQ53230A_TINT_TEST(
                    counter, channel=channel, stop_channel=stop_channel)),
                ("NWID", lambda: FREQ53230A_NWID_TEST(counter, channel=channel)),
                ("PDUT", lambda: FREQ53230A_PDUT_TEST(counter, channel=channel)),
                ("FTIM", lambda: FREQ53230A_FTIM_TEST(
                    counter, channel=channel, references=rtime_references,
                    transition_recipes=transition_recipes)),
                ("RTIM", lambda: FREQ53230A_RTIM_TEST(
                    counter, channel=channel, references=rtime_references,
                    transition_recipes=transition_recipes)),
                ("PHAS", lambda: FREQ53230A_PHAS_TEST(counter, channel=channel)),
                ("SPER", lambda: FREQ53230A_SPER_TEST(counter, channel=channel)),
        ):
            values[name] = call()

        failed = [name for name, value in values.items() if value is None]

        def cross_check(label, difference, tolerance, unit='s'):
            """One cross check line, adds to failed when it does not pass"""
            ok = abs(difference) <= tolerance
            print("CHECK : %-18s %+.3e %s (tolerance %.0e) %s"
                  % (label, difference, unit, tolerance,
                     'ok' if ok else 'FAILED'))
            if not ok:
                failed.append(label)
            return ok

        def valid(*names):
            """True when every named reading is a valid number"""
            return all(values.get(name) is not None
                       and counter.is_valid_reading(values[name])
                       for name in names)

        if valid('PWID', 'NWID', 'SPER'):
            cross_check('PWID + NWID = SPER',
                        values['PWID'] + values['NWID'] - values['SPER'], 1e-6)
        if single_input and valid('TINT', 'PWID'):
            cross_check('TINT = PWID', values['TINT'] - values['PWID'], 1e-6)
        if valid('FREQ', 'PER'):
            cross_check('FREQ x PER = 1',
                        values['FREQ'] * values['PER'] - 1.0, 1e-6, unit='')

        counter.check_error('measurement')
        print("53230A test is done..................................\n")
        if failed:
            print("53230A test FAILED for: %s" % ', '.join(failed))
        return not failed
    finally:
        counter.close()


if __name__ == "__main__":
    counter = FREQ53230A_INIT("USB0::0x0957::0x1907::MY64200013::INSTR")
    if counter is not None:
        for i in range(5):
            print(i, "CH1_SPER:", FREQ53230A_SPER_TEST(counter, channel=1))
            print(i, "CH1_FREQ :", FREQ53230A_FREQ_TEST(counter, gate_time=0.1, channel=1))
            print(i, "CH1_PER :", FREQ53230A_PER_TEST(counter, gate_time=0.1, channel=1))
            print(i, "CH1_PWID :", FREQ53230A_PWID_TEST(counter, channel=1))
            print(i, "CH1_TINT :", FREQ53230A_TINT_TEST(counter, channel=1, stop_channel=None))
            print(i, "CH1_NWID :", FREQ53230A_NWID_TEST(counter, channel=1))
            print(i, "CH1_PDUT :", FREQ53230A_PDUT_TEST(counter, channel=1))
            print(i, "CH1_FTIM :", FREQ53230A_FTIM_TEST(counter, channel=1, references=(10, 90)))
            print(i, "CH1_RTIM :", FREQ53230A_RTIM_TEST(counter, channel=1, references=(10, 90)))
    counter.close()
