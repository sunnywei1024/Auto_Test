# -*- coding: utf-8 -*-
"""
Created on Sep 11, 2026
Shanghai
@author: lijiangwei

R&S MXO 4 Series Driver (Base RsInstrument)
==============================================

This driver wraps the SCPI remote control commands of the
"R&S MXO 4 Series Oscilloscope User Manual" into the scope driver class
:class:`MXO4`, which inherits from :class:`RsInstrument`. Main features:

1. Instrument connection / reset / identification / error query
2. Channel (vertical) and horizontal (timebase) configuration
3. Trigger system configuration: edge / width / glitch / runt / window /
   timeout / interval / pattern / serial bus trigger
4. Protocol analysis (serial bus decoding): I2C / SPI / UART configuration and
   decoding result readout
5. Waveform acquisition: single / continuous / stop, reading waveform data
   (ASCII / binary)
6. Waveform saving: export CSV files, save raw data, save screenshots
7. Eye diagram analysis: eye configuration and eye height / eye width /
   eye amplitude measurements
8. Jitter analysis: advanced jitter analysis (quick start / manual components)
   and result readout

Installation::

    pip install RsInstrument

A VISA backend (for example R&S VISA or NI-VISA) must also be installed on the
PC. When only a TCPIP socket is used, the option ``SelectVisa='socket'`` can be
used instead, which needs no VISA at all.

Connection methods (VISA resource string examples)::

    TCPIP::192.168.1.100::INSTR
    TCPIP::192.168.1.100::hislip0::INSTR
    USB::0x0AAD::0x0A0C::xxxxxx::INSTR

Notes:
    * Serial bus decoding (protocol analysis) and serial bus triggering require
      the corresponding option licence in the instrument (for example
      I2C/SPI: K510, UART/RS-232/422/485: K520, ...).
    * Individual command parameters may differ slightly between firmware
      versions, the commands below follow the standard manual syntax.
"""

import csv
import os
import time
from enum import Enum

from RsInstrument import *  # noqa: F401,F403  provides the RsInstrument base class and BinFloatFormat enums




# ==============================================================================
# Enumerations (one to one mapping with the MXO4 SCPI parameters)
# ==============================================================================

class TriggerType(Enum):
    """Trigger type ``TRIGger:EVENt1:TYPe``"""
    EDGE = "EDGE"                # edge trigger
    GLITCH = "GLITch"            # glitch trigger
    WIDTH = "WIDTh"              # width trigger
    RUNT = "RUNT"                # runt trigger
    WINDOW = "WINdow"            # window trigger
    TIMEOUT = "TIMeout"          # timeout trigger
    INTERVAL = "INTerval"        # interval trigger
    SLEW_RATE = "SLEWrate"       # slew rate trigger
    DATA_TO_CLOCK = "DATatoclock"  # data to clock (setup/hold time) trigger
    STATE = "STATe"              # state trigger
    PATTERN = "PATtern"          # pattern trigger
    SERIAL_BUS = "SERialbus"     # serial bus trigger (protocol trigger)


class EdgeSlope(Enum):
    """Edge slope ``TRIGger:EVENt1:EDGE:SLOPe``"""
    POSITIVE = "POSitive"        # rising edge
    NEGATIVE = "NEGative"        # falling edge
    EITHER = "EITHer"            # either edge


class TriggerMode(Enum):
    """Trigger mode ``TRIGger:MODE``"""
    AUTO = "AUTO"                # auto (free running when no trigger event)
    NORMAL = "NORMal"            # normal (waits when no trigger event)
    FREE_RUN = "FREErun"         # free run


class ChannelCoupling(Enum):
    """Channel coupling ``CHANnel<n>:COUPling``"""
    DC = "DCLimit"               # DC (terminated)
    AC = "ACLimit"               # AC (terminated)
    GND = "GND"                  # ground


class AcquisitionMode(Enum):
    """Acquisition mode ``ACQuire:MODe``"""
    RTIME = "RTIMe"              # real time
    PEAK = "PEAK"                # peak detect
    AVERAGE = "AVERage"          # average
    HRES = "HRESolution"         # high resolution
    ERES = "ERESolution"         # enhanced resolution


class SampleRateMode(Enum):
    """Sample rate mode / SR mode ``ACQuire:SRATe:MODE``."""
    AUTO = "AUTO"
    MANUAL = "MANual"
    NORMAL = "NORMal"
    HIGH_RES = "HRESolution"
    PEAK = "PEAK"


class BusType(Enum):
    """Serial bus (protocol) type ``BUS<n>:TYPE``"""
    I2C = "I2C"                  # I2C (Inter-IC)
    SPI = "SPI"                  # SPI
    QSPI = "QSPI"                # QSPI (Quad SPI)
    UART = "UART"                # UART / RS-232 / RS-422 / RS-485
    CAN = "CAN"                  # CAN
    LIN = "LIN"                  # LIN
    FLEXRAY = "FLEXray"          # FlexRay
    I2S = "I2S"                  # I2S audio
    MIL1553 = "MIL"              # MIL-STD-1553
    ARINC429 = "ARINc"           # ARINC 429
    SENT = "SENT"                # SENT
    SPMI = "SPMI"                # MIPI SPMI


class I2CTriggerCondition(Enum):
    """I2C serial bus trigger condition"""
    START = "STARt"
    STOP = "STOP"
    RESTART = "RESTart"
    NO_ACK = "NOAck"
    ADDRESS = "ADDRess"
    DATA = "DATA"
    PATTERN = "PATTern"


class UARTTriggerCondition(Enum):
    """UART serial bus trigger condition"""
    START = "STBT"
    STOP = "STOP"
    DATA = "DATA"
    PARITY = "PARity"
    PATTERN = "PATTern"
    FRAME = "FRAMe"


class UARTParity(Enum):
    """UART parity"""
    NONE = "NONE"
    EVEN = "EVEN"
    ODD = "ODD"
    MARK = "MARK"
    SPC = "SPC"
    DC = "DC" 


class UARTPOLarity(Enum):
    IDLLow = "IDLLOW"
    IDLHigh = "IDLHIGH"

class UARTBitOrder(Enum):
    """UART bit order"""
    MSB_FIRST = "MSBF"
    LSB_FIRST = "LSBF"


class SPIPolarity(Enum):
    """SPI clock polarity"""
    IDLE_LOW = "IDLELOW"     # idle low
    IDLE_HIGH = "IDLEHIGH"   # idle high


class STOPBit(Enum):
    """Number of stop bits"""
    ONE_BIT = "B1"     # 1 stop bit
    ONE_P_FIVE_BITS = "B15"  # 1.5 stop bits
    TWO_BITS = "B2"    # 2 stop bits


class WaveformFormat(Enum):
    """Waveform data format ``FORMat:DATA``"""
    ASCII = "ASC"
    BINARY_FLOAT32 = "REAL,32"
    BINARY_FLOAT64 = "REAL,64"
    BINARY_INT16 = "INT,16"


class CursorFunction(Enum):
    """Cursor type ``CURSor<n>:FUNCtion``"""
    VERTICAL = "VERTical"      # vertical cursors X1/X2, measure time (delta X)
    HORIZONTAL = "HORizontal"  # horizontal cursors Y1/Y2, measure amplitude (delta Y)
    PAIRED = "PAIRed"          # show vertical and horizontal cursors together


class EyeMeasurement(Enum):
    """Eye diagram measurement item (MEASurement MAIN / ADDitional)"""
    EYE_HEIGHT = "EHEight"          # eye height
    EYE_WIDTH = "EWIDth"            # eye width
    EYE_AMPLITUDE = "EAMPlitude"    # eye amplitude


class JitterComponent(Enum):
    """Advanced jitter analysis component (COMPonents index)"""
    TJ_AT_BER = 4     # total jitter at a given BER
    RJ = 5            # random jitter
    TJ = 7            # total jitter
    DJ = 8            # deterministic jitter
    DDJ = 9           # data-dependent jitter
    DCD = 10          # duty cycle distortion
    PJ = 11           # periodic jitter
    ISI = 12          # inter-symbol interference


# ==============================================================================
# Driver class
# ==============================================================================

class MXO4(RsInstrument):
    """R&S MXO 4 series oscilloscope driver class (inherits from RsInstrument)."""

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def __init__(self, resource, timeout=60000, reset=True, idn=True, options="SelectVisa='rs'"):
        """
        Instrument connection (RsInstrument connects in the constructor).
  
        :param resource: VISA resource string, e.g. ``'TCPIP::192.168.1.100::INSTR'``
        :param timeout:  VISA read/write timeout in ms (increase it when large
                         amounts of data are acquired)
        :param reset:    whether ``*RST`` is executed during initialization
        :param idn:      whether ``*IDN?`` is used to verify the instrument
        :param options:  RsInstrument initialization options, e.g.
                        ``"SelectVisa='ni'"`` or ``"SelectVisa='socket'"``;
                        when omitted the installed VISA backend is detected
        """
        super().__init__(resource, id_query=idn, reset=reset, options=options)
        # attributes kept for compatibility with the old interface
        self.resource = resource
        self.timeout = timeout
        self.visa_timeout = timeout
        if self.idn_string:
            print(f"Connected: {self.idn_string}")

    def connect(self):
        """RsInstrument connects in the constructor, kept for compatibility."""
        return self

    def close(self):
        """Close the connection (errors are ignored once the session is dead)."""
        try:
            super().close()
        except Exception as e:
            print(f"Warning: closing the instrument session failed (ignored): {e}")

    # ------------------------------------------------------------------
    # Low level read / write and common commands
    # ------------------------------------------------------------------
    # The low level methods write / query / write_str / query_str /
    # query_bin_block are inherited from RsInstrument and need no duplication.

    def write_list(self, cmds):
        """Send several commands in one go (list)."""
        for c in cmds:
            self.write(c)

    def reset(self):
        """Reset to the preset state ``*RST`` and wait for completion."""
        super().reset()
        self.wait_opc()

    def get_error(self):
        """Read one error ``SYSTem:ERRor?``, returns a string."""
        return self.query("SYSTem:ERRor?")

    def opc_polling(self):
        """Poll the operation status register until acquisition stops (bit4 = 0)."""
        while True:
            cond = int(self.query("STATus:OPERation:CONDition?"))
            # acquisition running bit (see the "Operation Status Register" chapter
            # of the manual for the exact bit assignment)
            if cond & 0x10 == 0:   # bit4 = 0 means acquisition is no longer running
                break
            time.sleep(0.05)

    def wait_opc(self, timeout=None):
        """Send ``*OPC?`` and wait until all previous commands have finished."""
        if timeout:
            self.query_opc(timeout)
        else:
            self.query_opc()

    def set_display_update(self, on=True):
        """Enable/disable the screen update in remote control ``SYSTem:DISPlay:UPDate``."""
        self.write(f"SYSTem:DISPlay:UPDate {'ON' if on else 'OFF'}")

    def set_display_brightness(self, brightness=100):
        """
        Set the screen brightness ``DISPlay:BACKlight:BRIGtness``.  

        :param brightness: touch screen backlight brightness, range 5~100
                           (values outside the range are clamped)
        """
        val = int(brightness)
        val = max(5, min(100, val))
        self.write(f"DISPlay:BACKlight:BRIGtness {val}")

    def get_display_brightness(self):
        """Query the screen brightness ``DISPlay:BACKlight:BRIGtness?``, returns int (5~100)."""
        return int(self.query("DISPlay:BACKlight:BRIGtness?"))

    def set_display_dimming(self, timeout="OFF"):
        """
        Set the automatic screen dimming (power save) time ``DISPlay:BACKlight:DIMMing``.

        :param timeout: how long without user action before the screen dims down,
                        OFF / T1Minute / T2Minutes / T3Minutes / T5Minutes /
                        T10Minutes / T15Minutes / T20Minutes / T25Minutes /
                        T30Minutes / T45Minutes / T1Hour / T2Hours / T3Hours / T4Hours
        """
        self.write(f"DISPlay:BACKlight:DIMMing {timeout}")

    def set_signal_intensity(self, intensity=50):
        """
        Set the signal (waveform) intensity ``DISPlay:INTensity``.

        This value controls how strong the waveform traces appear on the
        screen; it is an independent setting from the screen backlight
        brightness (``set_display_brightness``).

        :param intensity: waveform intensity in percent, range 0~100
                          (default 50, 0 makes the trace invisible)
        """
        val = float(intensity)
        val = max(0.0, min(100.0, val))
        self.write(f"DISPlay:INTensity {val}")
    def get_signal_intensity(self):
        """Query the signal (waveform) intensity ``DISPlay:INTensity?``, returns float (0~100)."""
        return float(self.query("DISPlay:INTensity?"))

    def autoset(self):
        """Automatic setup ``AUTOSet EXECUTE`` (equivalent to ``AUToscale``)."""
        self.write("AUTOSet EXECUTE")
        self.wait_opc()

    # ------------------------------------------------------------------
    # Channel (vertical) configuration
    # ------------------------------------------------------------------
    @staticmethod
    def _ch(channel):
        """Normalize a channel number, accepts int(1~4) or str('1'~'4' / 'C1')."""
        if isinstance(channel, int):
            return str(channel)
        s = str(channel).upper().replace("CHAN", "").replace("CH", "").replace("C", "")
        return s

    @staticmethod
    def _src(source):
        """Normalize a trigger/decoder source: int(1~4) -> 'C1', or 'C1'/'SBUS1'/'EXT'/'LINE'."""
        if isinstance(source, int):
            return f"C{source}"
        s = str(source).upper()
        return s

    def channel_state(self, channel, on=True):
        """Switch a channel on/off ``CHANnel<n>:STATe ON|OFF``."""
        self.write(f"CHANnel{self._ch(channel)}:STATe {'ON' if on else 'OFF'}")

    def channel_coupling(self, channel, coupling=ChannelCoupling.DC):
        """Channel coupling ``CHANnel<n>:COUPling``."""
        val = coupling.value if isinstance(coupling, ChannelCoupling) else coupling
        self.write(f"CHANnel{self._ch(channel)}:COUPling {val}")

    def channel_range(self, channel, volts):
        """Vertical full scale (V) ``CHANnel<n>:RANGe <NR3>``, e.g. 2.0 means ±1 V full screen."""
        self.write(f"CHANnel{self._ch(channel)}:RANGe {volts}")

    def channel_scale(self, channel, volts_per_div):
        """Vertical sensitivity (V/div) ``CHANnel<n>:SCALe <NR3>``."""
        self.write(f"CHANnel{self._ch(channel)}:SCALe {volts_per_div}")

    def channel_offset(self, channel, volts):
        """Vertical offset (V) ``CHANnel<n>:OFFSet <NR3>``."""
        self.write(f"CHANnel{self._ch(channel)}:OFFSet {volts}")

    def channel_position(self, channel, divisions):
        """Vertical position (div) ``CHANnel<n>:POSition <NR3>``."""
        self.write(f"CHANnel{self._ch(channel)}:POSition {divisions}")

    def channel_impedance(self, channel, ohms):
        """Input impedance ``CHANnel<n>:IMPedance <NR3>`` (1e6 or 50)."""
        self.write(f"CHANnel{self._ch(channel)}:IMPedance {ohms}")

    def channel_label(self, channel, label):
        """
        Set a channel label ``DISPlay:SIGNal:LABel <signal>,<label>``.

        The channel label command of the MXO4 is not inside the ``CHANnel``
        subtree (MXO4 ``CHANnel`` has no LABel command), the label is set with
        ``DISPlay:SIGNal:LABel``, e.g. ``DISPlay:SIGNal:LABel C1,'VBUS'``.

        :param channel: channel number (int 1~4, or '1'~'4' / 'C1', ...)
        :param label:   label text (do not use single quotes inside)
        """
        signal = "C" + self._ch(channel)
        self.write(f"DISPlay:SIGNal:LABel {signal},'{label}'")

    def get_channel_label(self, channel):
        """
        Query a channel label ``DISPlay:SIGNal:LABel?``, returns the label string.

        :param channel: channel number (the query takes no source parameter
                        itself, it returns the label of the current source)
        """
        return self.query("DISPlay:SIGNal:LABel?")

    def digital_channel_label(self, digital, label):
        """
        Set a digital channel (MSO logic channel) label ``DIGital<n>:LABel '<label>'``.

        Digital and analog channel labels use two independent commands:
          * analog channel: ``DISPlay:SIGNal:LABel C1,'LABEL'``  (see ``channel_label``)
          * digital channel: ``DIGital<n>:LABel 'LABEL'``        (n is D0~D15)

        :param digital: digital channel number (int 0~15, i.e. D0~D15)
        :param label:   label text (do not use single quotes inside)
        """
        self.write(f"DIGital{int(digital)}:LABel '{label}'")

    def get_digital_channel_label(self, digital):
        """Query a digital channel label ``DIGital<n>:LABel?``, returns the label string."""
        return self.query(f"DIGital{int(digital)}:LABel?")

    def channel_bandwidth(self, channel, bandwidth="FULL"):
        """
        Set the channel bandwidth limit ``CHANnel<n>:BANDwidth``.

        :param channel:   channel number
        :param bandwidth: bandwidth limit value:
                          * a number (Hz), e.g. 20e6 / 50e6 / 100e6 / 200e6 / 350e6 / 500e6
                          * the string 'FULL' (full bandwidth, bandwidth limit off)
        """
        val = bandwidth.upper() if isinstance(bandwidth, str) else bandwidth
        self.write(f"CHANnel{self._ch(channel)}:BANDwidth {val}")

    def get_channel_bandwidth(self, channel):
        """Query the channel bandwidth limit ``CHANnel<n>:BANDwidth?``, returns Hz or 'FULL'."""
        return self.query(f"CHANnel{self._ch(channel)}:BANDwidth?")

    # ------------------------------------------------------------------
    # Horizontal (timebase) configuration
    # ------------------------------------------------------------------
    def timebase_scale(self, sec_per_div):
        """Timebase (s/div) ``TIMebase:SCALe <NR3>``."""
        self.write(f"TIMebase:SCALe {sec_per_div}")

    def timebase_range(self, seconds):
        """Full screen time (s) ``TIMebase:RANGe <NR3>``."""
        self.write(f"TIMebase:RANGe {seconds}")

    def timebase_position(self, percent):
        """
        Set the horizontal position (reference point) ``TIMebase:REFerence <NR3>``,
        the unit is percent of the screen.

        The horizontal position command of the MXO4 is ``TIMebase:REFerence``
        (0~100%), not ``HORizontal:POSition`` as on older models.

        :param percent: reference point position, 0~100 (%)
        """
        self.write(f"TIMebase:REFerence {percent}")

    def get_timebase_position(self):
        """Query the horizontal position (reference point) ``TIMebase:REFerence?`` in percent."""
        return self.query("TIMebase:REFerence?")

    def timebase_offset(self, seconds):
        """
        Set the trigger offset ``TIMebase:HORizontal:POSition <NR3>``, unit s.

        The value is the time distance between the reference point and the
        trigger point (the waveform zero point).

        :param seconds: trigger offset (s)
        """
        self.write(f"TIMebase:HORizontal:POSition {seconds}")

    def get_timebase_offset(self):
        """Query the trigger offset ``TIMebase:HORizontal:POSition?``, in seconds."""
        return self.query("TIMebase:HORizontal:POSition?")

    # ------------------------------------------------------------------
    # Acquisition control
    # ------------------------------------------------------------------

    def max_acquisition_points(self):
        """
            Try to query the maximum number of acquisition points supported by
            the instrument (several common SCPI variants are tried).
            Returns int (maximum points) or None when the query failed.
        """
        candidates = [
            "ACQuire:POINts:MAX?",   # common form
            "ACQ:POINts:MAX?",       # possible abbreviation
            "TIMebase:RECordlength:MAX?",  # fallback attempt (rare)
            "ACQuire:POINts? MAX",   # variant of some instruments (uncommon)
        ]
        for cmd in candidates:
            try:
                resp = self.query(cmd)  
                if resp is None:
                    continue
                # the answer may contain text, so try a numeric parse first
                val = float(resp.strip().split()[0])
                return int(val)
            except Exception:
                # catch any query/parse error and try the next command
                continue
        # when everything failed, return None to signal "unknown"
        return None
    
    def acquisition_mode(self, mode=AcquisitionMode.RTIME):
        """Acquisition mode ``ACQuire:MODe``."""
        val = mode.value if isinstance(mode, AcquisitionMode) else mode
        self.write(f"ACQuire:MODe {val}")

    def acquisition_count(self, count):
        """Number of averages ``ACQuire:COUNt <NR1>`` (average mode only)."""
        self.write(f"ACQuire:COUNt {int(count)}")

    def acquisition_points(self):
        """Query the current number of acquisition points ``ACQuire:POINts?``."""
        return int(float(self.query("ACQuire:POINts?")))

    @staticmethod
    def _scpi_number(value):
        """Convert a number/string into a SCPI compatible scientific notation, e.g. 1E9 / 1.23E+09."""
        if isinstance(value, str):
            s = value.strip()
            if s.upper().endswith('E'):
                s = s + '0'
            try:
                num = float(s)
            except ValueError as exc:
                raise ValueError(f"cannot parse as a number: {value}") from exc
        else:
            num = float(value)

        # build scientific notation with 12 significant digits (SCPI compatible)
        text = f"{num:.12E}"
        text = text.replace("E+0", "E+")
        text = text.replace("E-0", "E-")
        text = text.replace("E+", "E+")
        text = text.replace("E-", "E-")
        return text

    def sample_rate(self, rate):
        """
        Set the sample rate ``ACQuire:SRATe <NR3>``.

        The value is sent in scientific notation; a plain number or a string
        such as 1e9 / '1E9' is accepted.

        :param rate: sample rate (samples/s), e.g. 1e9 / 2.5e9 / 5e9
        """
        val = self._scpi_number(rate)
        self.write(f"ACQuire:SRATe {val}")

    def get_sample_rate(self):
        """Query the current sample rate ``ACQuire:SRATe?``, returns float."""
        return float(self.query("ACQuire:SRATe?"))

    def sample_rate_mode(self, mode=SampleRateMode.AUTO):
        """
        Set the SR mode / sample rate mode ``ACQuire:SRATe:MODE``.

        The usual modes are:
          - AUTO     : automatic sample rate mode
          - MANual   : manual sample rate mode
          - NORMAL   : normal mode
          - HRESolution: high resolution mode (if supported)
        """
        val = mode.value if isinstance(mode, SampleRateMode) else str(mode).upper()
        self.write(f"ACQuire:SRATe:MODE {val}")

    def get_sample_rate_mode(self):
        """Query the current SR mode ``ACQuire:SRATe:MODE?``."""
        return self.query("ACQuire:SRATe:MODE?")

    def configure_sampling(self, timebase_seconds_per_div=None, sample_rate=None,
                          points=None, wait=True):
        """
        Helper that configures sample rate / record depth / timebase in one go.

        Rules:
        1. If ``timebase_seconds_per_div`` is given, ``TIMebase:SCALe`` is sent.
        2. If ``points`` and ``timebase_seconds_per_div`` are given, the sample
           rate is estimated as
           ``sample_rate = points / timebase_seconds_per_div / 10``
           and only used when ``sample_rate`` was not given explicitly.
        3. If ``sample_rate`` is given, ``ACQuire:SRATe`` is sent.
        4. If ``points`` is given, ``ACQuire:POINts`` is sent.
        5. Finally ``wait_opc`` can be used to wait for completion.

        :param timebase_seconds_per_div: timebase in s/div, e.g. 5e-6
        :param sample_rate:              sample rate in Sa/s, e.g. 1e9
        :param points:                   record depth in points, e.g. 1_000_000 or '1M'
        :param wait:                     whether to wait for command completion
        :return:                         tuple (timebase, sample_rate, points)
        """
        # a string such as '1M' / '1e6' / '1000000' is accepted
        if points is not None:
            if isinstance(points, str):
                s = points.strip().upper()
                if s.endswith('M') and s[:-1].replace('.', '', 1).isdigit():
                    points_val = int(float(s[:-1]) * 1_000_000)
                else:
                    try:
                        points_val = int(float(s))
                    except Exception as exc:
                        raise ValueError(f"cannot parse the number of points: {points}") from exc
            else:
                points_val = int(points)
        else:
            points_val = None

        if timebase_seconds_per_div is not None and points_val is not None and sample_rate is None:
            # empirical formula: sample_rate = points / timebase_seconds_per_div / 10
            # where 10 is the horizontal screen resolution factor (typical approximation)
            try:
                sample_rate = int(points_val / (float(timebase_seconds_per_div) * 10.0)) 
            except Exception:
                sample_rate = None

        if timebase_seconds_per_div is not None:
            self.timebase_scale(timebase_seconds_per_div)
        if sample_rate is not None:
            self.sample_rate(sample_rate)
        # if points_val is not None:
        #     self.set_acquisition_points(points_val, wait=False)
        if wait:
            try:
                self.wait_opc(timeout=600000)
            except Exception:
                pass

        current_tb = None
        current_sr = None
        current_pts = None
        try:
            current_tb = self.query("TIMebase:SCALe?")
        except Exception: 
            pass
        try:
            current_sr = float(self.query("ACQuire:SRATe?"))
        except Exception:
            pass
        try:
            current_pts = int(float(self.query("ACQuire:POINts?")))
        except Exception:
            pass
        return current_tb, current_sr, current_pts

    def set_memory_depth_1M(self, wait=True):
        """Set the record depth to 1 Mpts."""
        return self.ensure_acquisition_points("1M", wait=wait)

    def auto_sampling_for_timebase(self, timebase_s_per_div, points="1M", wait=True):
        """
        Estimate and configure the sample rate and the depth from the timebase.

        Uses the formula: sample_rate = points / timebase_s_per_div / 10
        The default depth is 1 Mpts.
        """
        if isinstance(points, str):
            s = points.strip().upper()
            if s.endswith('M') and s[:-1].replace('.', '', 1).isdigit():
                points_val = int(float(s[:-1]) * 1_000_000)
            else:
                points_val = int(float(s))
        else:
            points_val = int(points)

        sample_rate = points_val / float(timebase_s_per_div) / 10.0
        return self.configure_sampling(
             timebase_seconds_per_div=timebase_s_per_div,
            sample_rate=sample_rate,
            points=points_val,
            wait=wait,
        )

    def set_acquisition_points(self, points, wait=True):
        """
        Set the number of acquisition points (record length / memory depth).

        The command ``ACQuire:POINts <n>`` sets the current record length.

        :param points: number of points to set (an int, or a value that int()
                       can parse, e.g. 1_000_000 / '1M' / '1e6')
        :param wait:   whether to wait for completion after setting (using
                       *OPC?), default True
        :return:       the number of points after setting (int)
        """
        # a string such as '1M' / '1e6' / '1000000' is accepted
        if isinstance(points, str):
            s = points.strip().upper()
            if s.endswith('M') and s[:-1].replace('.', '', 1).isdigit():
                points_val = int(float(s[:-1]) * 1_000_000)
            else:
                try:
                    points_val = int(float(s))
                except Exception:
                    raise ValueError(f"cannot parse the number of points: {points}")
        else:
            points_val = int(points)

        # send the setting command
        self.write(f"ACQuire:POINts {points_val}")
        if wait:
            # setting the record length may require an internal buffer
            # reconfiguration, therefore the timeout is increased
            try:
                self.wait_opc(timeout=600000)  # up to 10 minutes for a deep reconfiguration
            except Exception:
                # when the wait fails, still return the value that was set
                pass
        return points_val

    def ensure_acquisition_points(self, target_points, wait=True):
        """
        Query the current acquisition depth and set it to the target if it differs.

        :param target_points: target number of points (int or a parseable string, e.g. '1M')
        :param wait: whether to wait for completion after setting
        :return: (old_points, new_points, changed)
        """
        old = None
        try:
            old = self.acquisition_points()
        except Exception:
            # when the query fails, still try to set the value
            old = None
        new = self.set_acquisition_points(target_points, wait=wait)
        changed = (old != new)
        return old, new, changed

    def run(self):
        """Run continuously (RUN)."""
        self.write("RUN")

    def single(self):
        """Single acquisition (SINGle / RUNSingle)."""
        self.write("SINGle")

    def stop(self):
        """Stop the acquisition (STOP)."""
        self.write("STOP")

    def single_and_wait(self, timeout=None):
        """Single acquisition and wait for completion (SINGle;*OPC)."""
        self.write("SINGle")
        # self.wait_opc(timeout)
        self.opc_polling()  # note: the operation status is polled here

    # ------------------------------------------------------------------
    # Trigger system
    # ------------------------------------------------------------------
    def trigger_mode(self, mode=TriggerMode.AUTO):
        """Trigger mode ``TRIGger:MODE``."""
        val = mode.value if isinstance(mode, TriggerMode) else mode
        self.write(f"TRIGger:MODE {val}")

    def trigger_source(self, source="C1"):
        """Trigger source ``TRIGger:EVENt1:SOURce`` (C1..C4 / D0..D15 / EXT / LINE / SBUS1..)."""
        self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")

    def trigger_level(self, level, source="C1"):
        """Trigger level ``TRIGger:EVENt1:LEVel1:VALue``."""
        self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")
        self.write(f"TRIGger:EVENt1:LEVel1:VALue {level}")

    # ---- Edge trigger (most common) ----
    def configure_edge_trigger(self, source="C1", level=0.0, slope=EdgeSlope.POSITIVE):
        """Configure an edge trigger."""
        sl = slope.value if isinstance(slope, EdgeSlope) else slope
        self.write_list([
            f"TRIGger:EVENt1:TYPe EDGE",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:EDGE:SLOPe {sl}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
        ])

    # ---- Width trigger ----
    def configure_width_trigger(self, source="C1", level=0.0,
                                condition="WITHin", width=1e-6,
                                slope=EdgeSlope.POSITIVE):
        """
        Width trigger: triggers when the pulse width matches ``width`` (s) as
        selected by ``condition`` (WITHin / OUTSide).

        Corresponding commands ``TRIGger:EVENt1:WIDTh:CONDition`` / ``RANGe``.
        """
        sl = slope.value if isinstance(slope, EdgeSlope) else slope
        self.write_list([
            f"TRIGger:EVENt1:TYPe WIDTh",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
            f"TRIGger:EVENt1:WIDTh:CONDition {condition}",
            f"TRIGger:EVENt1:WIDTh:RANGe {width}",
            f"TRIGger:EVENt1:EDGE:SLOPe {sl}",
        ])

    # ---- Glitch trigger ----
    def configure_glitch_trigger(self, source="C1", level=0.0, width=1e-9,
                                 polarity="POSitive"):
        """Glitch trigger: narrow pulses shorter than ``width`` (s)."""
        self.write_list([
            f"TRIGger:EVENt1:TYPe GLITch",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
            f"TRIGger:EVENt1:GLITch:RANGe {width}",
            f"TRIGger:EVENt1:GLITch:POLarity {polarity}",
        ])

    # ---- Runt trigger ----
    def configure_runt_trigger(self, source="C1", upper_level=0.5, lower_level=0.1,
                               polarity="POSitive"):
        """Runt trigger: the pulse does not cross the upper/lower level pair."""
        self.write_list([
            f"TRIGger:EVENt1:TYPe RUNT",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:RUNT:POLarity {polarity}",
            f"TRIGger:EVENt1:LEVel1:VALue {upper_level}",
            f"TRIGger:EVENt1:LEVel2:VALue {lower_level}",
        ])

    # ---- Window trigger ----
    def configure_window_trigger(self, source="C1", upper_level=0.5, lower_level=-0.5,
                                 condition="WITHin"):
        """Window trigger: triggers when the signal enters/leaves the level window."""
        self.write_list([
            f"TRIGger:EVENt1:TYPe WINdow",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:WINdow:CONDition {condition}",
            f"TRIGger:EVENt1:LEVel1:VALue {upper_level}",
            f"TRIGger:EVENt1:LEVel2:VALue {lower_level}",
        ])

    # ---- Timeout trigger ----
    def configure_timeout_trigger(self, source="C1", level=0.0, timeout=1e-6,
                                  condition="LONGer"):
        """Timeout trigger: triggers when the level duration is longer/shorter than ``timeout`` (s)."""
        self.write_list([
            f"TRIGger:EVENt1:TYPe TIMeout",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
            f"TRIGger:EVENt1:TIMeout:CONDition {condition}",
            f"TRIGger:EVENt1:TIMeout:RANGe {timeout}",
        ])

    # ---- Pattern trigger ----
    def configure_pattern_trigger(self, sources=None, levels=None,
                                  pattern="1111"):
        """
        Pattern trigger (requires the logic / MSO option).

        :param sources: list of sources, e.g. ['C1','C2'] or ['D0','D1']
        :param levels:  matching list of levels
        :param pattern: pattern string, every character is 0/1/X (don't care)
        """
        sources = sources or ["C1", "C2"]
        self.write_list([
            "TRIGger:EVENt1:TYPe PATtern",
        ])
        for i, src in enumerate(sources, start=1):
            self.write(f"TRIGger:EVENt1:PATTern:SOURce{i} {self._src(src)}")
            if levels and i <= len(levels):
                self.write(f"TRIGger:EVENt1:LEVel{i}:VALue {levels[i - 1]}")
        self.write(f"TRIGger:EVENt1:PATTern:CONDition TRUE")
        self.write(f"TRIGger:EVENt1:PATTern:PATTern {pattern}")

    # ---- Serial bus trigger (protocol trigger) ----
    def configure_serial_trigger(self, bus_number=1, bus_type=BusType.UART,
                                 source="SBUS1"):
        """
        Set up a serial bus trigger (protocol trigger).

        Corresponds to ``TRIGger:EVENt1:TYPe SERialbus``, the trigger source
        ``TRIGger:EVENt1:SOURce`` is the serial bus (``SBUS1`` by default).
        """
        bt = bus_type.value if isinstance(bus_type, BusType) else bus_type
        if bus_number not in [1, 2, 3, 4]:
            raise ValueError(f"bus_number must be 1~4, given: {bus_number}")
        elif bus_number == 1 and bus_type == BusType.UART:    
            self.write_list([
            f"TRIGger:EVENt{bus_number}:TYPE {'EDGE'}",
            f"TRIGger:EVENt{bus_number}:SOURce {self._src(source)}",
            f"TRIGger:SBHW:{bt}:SOURce {'TX'}",
            f"TRIGger:SBHW:{bt}:TYPE {'STBT'} ",
        ])
        elif bus_number == 2 and bus_type == BusType.I2C:
            self.write_list([
            f"TRIGger:EVENt{bus_number-1}:TYPE {'EDGE'}",
            f"TRIGger:EVENt{bus_number-1}:SOURce {self._src(source)}",
            f"TRIGger:SBHW:{bt}:TYPE {'STARt'} ",  # STARt | REPStart | STOP | NACK | ADDRess | DATA | ADAT
        ])
        elif bus_number == 3 and bus_type == BusType.SPI:
            self.write_list([
            f"TRIGger:EVENt{bus_number}:TYPE {'EDGE'}",
            f"TRIGger:EVENt{bus_number}:SOURce {self._src(source)}",
            f"TRIGger:SBHW:{bt}:SOURce {'SDA'}",
            f"TRIGger:SBHW:{bt}:TYPE {'STBT'} ",
        ])
        elif bus_number == 4 and bus_type == BusType.QSPI:
            # QSPI has no hardware serial bus trigger (there is no
            # TRIGger:SBHW:QSPI); the software serial bus trigger
            # TRIGger:SBSW:QSPI:* is used instead and has to be triggered in
            # the A -> Serial bus multi event sequence (MEVents).
            self.write_list([
                "TRIGger:MEVents:MODE SEQuence",
                "TRIGger:MEVents:AEVents ASB",
                f"TRIGger:EVENt2:SOURce SBUS{bus_number}",
                "TRIGger:SBSW:QSPI:CLR",
                "TRIGger:SBSW:QSPI:FRENable ON",
            ])
        else:
            raise ValueError(f"unsupported bus configuration: bus_number={bus_number}, bus_type={bus_type}")

    def configure_i2c_trigger(self, condition=None,
                              address=None, data=None, bus_number=2, source="SBUS2"):
        """Configure an I2C serial bus trigger condition."""
        cond = condition.value if isinstance(condition, I2CTriggerCondition) else condition
        self.configure_serial_trigger(bus_number, BusType.I2C, source)
        if condition is not None:
            self.write(f"TRIGger:SBHW:I2C:CONDition {cond}")  #EQUal | NEQual | LTHan | LETHan | GTHan | GETHan |INRange | OORange,Address Operater
        if address is not None: 
            self.write(f"TRIGger:SBHW:I2C:ADDRess {address}") # Initial Address
        if data is not None:
            self.write(f"TRIGger:SBHW:I2C:DMIN {data}")       
            # Specifies the data bit pattern, or sets the start value of a data pattern range. Enter the
            # bytes in MSB first bit order. The maximum pattern length is 64 bit. Waveform data is
            # compared with the pattern byte-by-byte.

        self.write_list([f"SBUS{bus_number}:ZCOupling {'ON'}",
                                          f"SBUS{bus_number}:RESult {'ON'}"
                                         ]) 
        
  
    def configure_spi_trigger(self, condition="MOSI", pattern=None,
                              bus_number=3, source="SBUS3"):
        """Configure an SPI serial bus trigger condition (MOSI/MISO data condition)."""
        self.configure_serial_trigger(bus_number, BusType.SPI, source)
        self.write(f"TRIGger:EVENt{bus_number}:SERialbus:SPI:CONDition {condition}")
        if pattern is not None:
            self.write(f"TRIGger:EVENt{bus_number}:SERialbus:SPI:DATA {pattern}")

    def configure_qspi_trigger(self, bus_number=4, source="SBUS4", clock_source="C1",
                               frame_enable=True, invert=False):
        """
        Configure the QSPI software serial bus trigger (A -> Serial bus sequence).

        Note: QSPI has no hardware serial bus trigger (there is no
        ``TRIGger:SBHW:QSPI``); the software trigger ``TRIGger:SBSW:QSPI:*`` is
        used instead and has to be triggered in the A -> Serial bus multi event
        sequence (MEVents).

        :param bus_number:   number of the serial bus used by the QSPI decoder (1..4)
        :param source:       serial bus source (SBUS4 by default)
        :param clock_source: QSPI trigger clock (A event arming source).
                             Can be an analog channel (e.g. 'C1') or a digital
                             channel (e.g. 'D0'), case insensitive ('c1'/'d0').
        :param frame_enable: True enables the frame condition check (SBSW:QSPI:FRENable)
        :param invert:       True inverts the complete trigger condition
        """
        self.configure_serial_trigger(bus_number, BusType.QSPI, source)
        if clock_source is not None:
            self.write(f"TRIGger:EVENt1:SOURce {self._src(clock_source)}")
        self.write(f"TRIGger:SBSW:QSPI:FRENable {'ON' if frame_enable else 'OFF'}")
        if invert:
            self.write("TRIGger:SBSW:QSPI:INVert ON")



    def configure_uart_trigger(self, bus_number=1, source="SBUS1"):
        """Configure a UART serial bus trigger condition."""
        self.configure_serial_trigger(bus_number, BusType.UART, source)
        self.write_list([f"SBUS{bus_number}:ZCOupling {'ON'}",
                                  f"SBUS{bus_number}:RESult {'ON'}"
                                 ]) 


    # ------------------------------------------------------------------
    # Protocol analysis (serial bus decoding)
    # ------------------------------------------------------------------
    def bus_state(self, bus_number=1, on=True):
        """Switch the serial bus decoding on/off ``SBUS<n>:STATe ON|OFF``."""
        self.write(f"BUS{bus_number}:STATe {'ON' if on else 'OFF'}")

    def bus_result_table(self, bus_number=1, on=True):
        """
        Switch the serial bus decode result table ``SBUS<n>:RESult ON|OFF``.

        The result area at the bottom of the MXO4 screen shows the decode result
        table and the automatic measurement result table at the same time;
        switching the decode table off (OFF) reveals the measurement result
        table (RMS/FREQuency/AMPLitude, ...), which makes it easier to save a
        screenshot of the measurement screen.
        """
        self.write(f"SBUS{bus_number}:RESult {'ON' if on else 'OFF'}")

    def bus_type(self, bus_number=1, bus_type=BusType.I2C):
        """Set the serial bus protocol type ``SBUS<n>:TYPE``."""
        bt = bus_type.value if isinstance(bus_type, BusType) else bus_type
        self.write(f"SBUS{bus_number}:TYPE {bt}")

    def bus_label(self, bus_number=1, label=""):
        """Serial bus label ``SBUS<n>:LABel '<str>'``."""
        self.write(f"SBUS{bus_number}:LABel '{label}'")

    def bus_threshold(self, bus_number=1, level=1.65):
        """Logic level threshold ``SBUS<n>:THReshold <NR3>`` (V)."""
        self.write(f"SBUS{bus_number}:THReshold {level}")

    def configure_i2c_decode(self, bus_number=1, scl="C1", sda="C2"):
        """
        Configure the I2C decoder.

        :param bus_number:   serial bus number (1..4)
        :param scl:          SCL clock source (C1..C4 / D0..D15)
        :param sda:          SDA data source
        :param address_mode: address mode 7BIT / 10BIT
        """
        self.write_list([
            f"SBUS{bus_number}:TYPE I2C",
            f"SBUS{bus_number}:I2C:SCL:SOURce {self._src(scl)}",
            f"SBUS{bus_number}:I2C:SDA:SOURce {self._src(sda)}",
            f"SBUS{bus_number}:I2C:SDA:THReshold {2.0}",
            f"SBUS{bus_number}:I2C:SCL:THReshold {2.0}",
            # f"SBUS{bus_number}:I2C:ADDRess:MODE {address_mode}",
            f"SBUS{bus_number}:STATe ON",
        ])

    def configure_spi_decode(self, bus_number=1, sclk="C1", mosi="C2",
                             miso="C3", ss="C4", polarity=SPIPolarity.IDLE_LOW,
                             bit_order=UARTBitOrder.MSB_FIRST, ss_active="LOW"):
        """
        Configure the SPI decoder.

        :param sclk: SCLK clock source
        :param mosi: MOSI data source (master mode only)
        :param miso: MISO data source (slave mode only)
        :param ss:   chip select source (can be 'NONE')
        """
        pol = polarity.value if isinstance(polarity, SPIPolarity) else polarity
        bo = bit_order.value if isinstance(bit_order, UARTBitOrder) else bit_order
        self.write_list([
            f"SBUS{bus_number}:TYPE SPI",
            f"SBUS{bus_number}:SPI:SCLK:SOURce {self._src(sclk)}",
            f"SBUS{bus_number}:SPI:MOSI:SOURce {self._src(mosi)}",
            f"SBUS{bus_number}:SPI:MISO:SOURce {self._src(miso)}",
            f"SBUS{bus_number}:SPI:SS:SOURce {self._src(ss)}",
            f"SBUS{bus_number}:SPI:POLarity {pol}",
            f"SBUS{bus_number}:SPI:BITorder {bo}",
            f"SBUS{bus_number}:SPI:SS:ACTive {ss_active}",
            f"SBUS{bus_number}:STATe ON",
        ])

    def configure_qspi_decode(self, bus_number=1, sclk="C1", cs="C2",
                              io0="C3", io1="C4", io2="C5", io3="C6",
                              sclk_polarity="RISing", cs_polarity="ACTLow",
                              instruction="QUAD", opcodes=None, result_table=True):
        """
        Configure the QSPI (Quad SPI) decoder.

        Corresponds to ``SBUS<n>:TYPE QSPI`` and the ``SBUS<n>:QSPI:*`` subtree:
          * clock ``QSPI:SCLK:SOURce``, chip select ``QSPI:CSEL:SOURce``
          * data lines ``QSPI:IOZero / IOONe / IOTWo / IOTHree:SOURce`` (IO0~IO3)
          * QSPI is driven by an opcode instruction table; each opcode can set
            the number of address/data lanes (SINGle / DUAL / QUAD), DDR,
            dummy cycles, number of address bytes, etc.

        :param bus_number:     serial bus number (1..4)
        :param sclk:           SCLK clock source
        :param cs:             CS (chip select) source
        :param io0..io3:       IO0~IO3 data line sources
        :param sclk_polarity:  clock polarity RISing / FALLing
        :param cs_polarity:    chip select active level ACTLow / ACTHigh
        :param instruction:    instruction mode SINGle / DUAL / QUAD
        :param opcodes:        opcode table (list[dict]); every element may hold
                               code(0~255), ddr(bool or ON/OFF), adbytes(0~4),
                               adlanes/dtlanes(SINGle|DUAL|QUAD),
                               dmcycles(0~255), data(bool or ON/OFF)
        :param result_table:   True shows the decode result table
        """
        def _on_off(v):
            if isinstance(v, bool):
                return "ON" if v else "OFF"
            return v

        self.write_list([
            f"SBUS{bus_number}:TYPE QSPI",
            f"SBUS{bus_number}:QSPI:SCLK:SOURce {self._src(sclk)}",
            f"SBUS{bus_number}:QSPI:CSEL:SOURce {self._src(cs)}",  
            f"SBUS{bus_number}:QSPI:IOZero:SOURce {self._src(io0)}",
            f"SBUS{bus_number}:QSPI:IOONe:SOURce {self._src(io1)}",
            f"SBUS{bus_number}:QSPI:IOTWo:SOURce {self._src(io2)}",
            f"SBUS{bus_number}:QSPI:IOTHree:SOURce {self._src(io3)}",
            f"SBUS{bus_number}:QSPI:SCLK:POLarity {sclk_polarity}",
            f"SBUS{bus_number}:QSPI:CSEL:POLarity {cs_polarity}",
            f"SBUS{bus_number}:QSPI:INSTruction {instruction}",

        ]) 
        opcodes = opcodes or []
        # self.write(f"SBUS{bus_number}:QSPI:OPCode:SIZE?")
        for idx, op in enumerate(opcodes, start=1):
            self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:CODE {int(op.get('code', 0))}")
            if op.get("ddr") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:DDR {_on_off(op['ddr'])}")
            if op.get("adbytes") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:ADBYtes {int(op['adbytes'])}")
            if op.get("adlanes") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:ADLanes {op['adlanes']}")
            if op.get("dtlanes") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:DTLanes {op['dtlanes']}")
            if op.get("dmcycles") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:DMCYcles {int(op['dmcycles'])}")
            if op.get("data") is not None:
                self.write(f"SBUS{bus_number}:QSPI:OPCode:ITEM{idx}:DATA {_on_off(op['data'])}")
        self.write(f"SBUS{bus_number}:STATe ON")
        if result_table:
            self.write(f"SBUS{bus_number}:RESult ON")

    def configure_uart_decode(self, bus_number=1, rx="C1", tx="C2",
                              baud=115200, data_bits=8, parity=UARTParity.NONE,
                              stop_bits=STOPBit.ONE_BIT, bit_order=UARTBitOrder.LSB_FIRST,
                              idle=UARTPOLarity.IDLHigh):
        """
        Configure the UART (RS-232/422/485) decoder.

        :param rx:        RX data source
        :param tx:        TX data source (can be 'NONE')
        :param baud:      baud rate
        :param data_bits: number of data bits (7/8/9)
        :param parity:    parity
        :param stop_bits: stop bits (1/1.5/2)
        :param idle:      idle level IDLEHIGH / IDLELOW
        """
        par = parity.value if isinstance(parity, UARTParity) else parity
        bo = bit_order.value if isinstance(bit_order, UARTBitOrder) else bit_order
        stb = stop_bits.value if isinstance(stop_bits, STOPBit) else stop_bits
        idle = idle.value if isinstance(idle, UARTPOLarity) else idle
        self.write_list([
            f"SBUS{bus_number}:TYPE UART",
            f"SBUS{bus_number}:UART:RX:SOURce {self._src(rx)}",
            f"SBUS{bus_number}:UART:TX:SOURce {self._src(tx)}",
            f"SBUS{bus_number}:UART:BAUDrate {int(baud)}",
            f"SBUS{bus_number}:UART:SSIZe {int(data_bits)}",
            f"SBUS{bus_number}:UART:PARity {par}",
            f"SBUS{bus_number}:UART:SBIT {stb}",
            f"SBUS{bus_number}:UART:BORDer {bo}",
            f"SBUS{bus_number}:UART:POLarity {idle}",
            f"SBUS{bus_number}:STATe ON",
        ])

    def get_decoded_data(self, bus_number=1):
        """
        Read the serial bus decode result ``SBUS<n>:RESult?``, returns a string.

        The answer holds the decoded data listed per frame (the format depends
        on the bus and the firmware version), it can be parsed line by line or
        by comma. ``SBUS<n>:RESult:FCOunt?`` gives the number of frames.  
        """
        return self.query(f"SBUS{bus_number}:RESult?")

    def get_decoded_frame_count(self, bus_number=1):
        """Query the number of decoded frames ``SBUS<n>:RESult:FCOunt?``."""
        try:
            return int(float(self.query(f"SBUS{bus_number}:RESult:FCOunt?")))
        except Exception:
            # some firmware revisions use SBUS<n>:FCOunt?
            return int(float(self.query(f"SBUS{bus_number}:FCOunt?")))

    # ------------------------------------------------------------------
    # Digital logic decoding (MSO digital channels D0~D15 and logic groups PBUS/Logic1~4)
    # ------------------------------------------------------------------
    def digital_channel_state(self, digital, on=True):
        """Switch a digital channel on/off ``DIGital<n>:STATe ON|OFF`` (n=0..15, i.e. D0~D15)."""
        self.write(f"DIGital{int(digital)}:STATe {'ON' if on else 'OFF'}")

    def digital_probe_enable(self, probe=1, digital=0, on=True):
        """
        Enable/disable a digital channel of the MSO logic probe pod
        ``DIGital<n>:PROBe<m>:ENABle``.

        :param probe:   pod number (1..2)
        :param digital: digital channel number (0..15)
        """
        self.write(f"DIGital{int(digital)}:PROBe{int(probe)}:ENABle {'ON' if on else 'OFF'}")

    def digital_channel_threshold(self, digital, volts=1.65):
        """Set the digital channel threshold ``DIGital<n>:THReshold <NR3>`` (V, affects the whole logic group)."""
        self.write(f"DIGital{int(digital)}:THReshold {volts}")

    def digital_channel_technology(self, digital, technology="V165"):
        """Set the digital channel threshold technology preset ``DIGital<n>:TECHnology`` (V165/V25/V125/V09/V15/VM13/V38/V20/V0/MANual)."""
        self.write(f"DIGital{int(digital)}:TECHnology {technology}")

    def digital_channel_hysteresis(self, digital, hysteresis="NORMal"):
        """Set the digital channel hysteresis ``DIGital<n>:HYSTeresis`` (MAXimum/ROBust/NORMal)."""
        self.write(f"DIGital{int(digital)}:HYSTeresis {hysteresis}")

    def digital_channel_threshold_coupling(self, digital, on=True):
        """Threshold/hysteresis coupling ``DIGital<n>:THCoupling ON|OFF``."""
        self.write(f"DIGital{int(digital)}:THCoupling {'ON' if on else 'OFF'}")

    def pbus_state(self, pbus=1, on=True):
        """Switch a logic group (parallel bus) on/off ``PBUS<n>:STATe ON|OFF`` (n=1..4)."""
        self.write(f"PBUS{int(pbus)}:STATe {'ON' if on else 'OFF'}")

    def pbus_bit_state(self, pbus=1, bit=0, on=True):
        """Enable the digital channel BIT of a logic group ``PBUS<n>:BIT<m>:STATe ON|OFF`` (m=0..15)."""
        self.write(f"PBUS{int(pbus)}:BIT{int(bit)}:STATe {'ON' if on else 'OFF'}")

    def pbus_bit_label(self, pbus=1, bit=0, label=""):
        """Set the name of one BIT in a logic group ``PBUS<n>:BIT<m>:LABel '<label>'``."""
        self.write(f"PBUS{int(pbus)}:BIT{int(bit)}:LABel '{label}'")

    def pbus_clear(self, pbus=1):
        """Clear all channels of a logic group ``PBUS<n>:CLEar``."""
        self.write(f"PBUS{int(pbus)}:CLEar")

    def pbus_decode_table(self, pbus=1, on=True):
        """Switch the logic group decode result table ``PBUS<n>:DECTable:SHOW ON|OFF`` (clocked bus only)."""
        self.write(f"PBUS{int(pbus)}:DECTable:SHOW {'ON' if on else 'OFF'}")

    def pbus_threshold(self, pbus=1, index=1, volts=1.65):
        """Set a logic group threshold ``PBUS<n>:THReshold<m> <NR3>`` (V, m=1..4)."""
        self.write(f"PBUS{int(pbus)}:THReshold{int(index)} {volts}")

    def pbus_technology(self, pbus=1, technology="V165"):
        """Set the logic group threshold technology preset ``PBUS<n>:TECHnology``."""
        self.write(f"PBUS{int(pbus)}:TECHnology {technology}")

    def pbus_hysteresis(self, pbus=1, index=1, hysteresis="NORMal"):
        """Set a logic group hysteresis ``PBUS<n>:HYSTeresis<m>`` (m=1..4)."""
        self.write(f"PBUS{int(pbus)}:HYSTeresis{int(index)} {hysteresis}")

    def pbus_threshold_coupling(self, pbus=1, on=True):
        """Logic group threshold/hysteresis coupling ``PBUS<n>:THCoupling ON|OFF``."""
        self.write(f"PBUS{int(pbus)}:THCoupling {'ON' if on else 'OFF'}")

    def pbus_clock(self, pbus=1, source="D0", slope="POSitive", on=True):
        """Configure the logic group clocked bus ``PBUS<n>:CLON / CLOCk / CLSLope``."""
        self.write(f"PBUS{int(pbus)}:CLON {'ON' if on else 'OFF'}")
        if source is not None:
            self.write(f"PBUS{int(pbus)}:CLOCk {self._src(source)}")
        if slope is not None:
            self.write(f"PBUS{int(pbus)}:CLSLope {slope}")

    def pbus_display(self, pbus=1, show_bus=True, show_digital=True):
        """Logic group display options ``PBUS<n>:DISPlay:SHBU / SHDI``."""
        self.write(f"PBUS{int(pbus)}:DISPlay:SHBU {'ON' if show_bus else 'OFF'}")
        self.write(f"PBUS{int(pbus)}:DISPlay:SHDI {'ON' if show_digital else 'OFF'}")

    def get_pbus_data(self, pbus=1):
        """Read the logic group decoded data ``PBUS<n>:DATA:VALUES?``."""
        return self.query(f"PBUS{int(pbus)}:DATA:VALUES?")

    def configure_logic_decode(self, pbus=1, bits=None, threshold=1.65,
                               technology="V165", hysteresis="NORMal",
                               clocked=False, clock_source="D0",
                               clock_slope="POSitive", decode_table=False,
                               show_bus=True, show_digital=True, enable=True):
        """
        Configure a digital logic group (parallel bus) decoder in one go
        (PBUS<n>, corresponding to Logic1~Logic4).

        :param pbus:         logic group number (1..4)
        :param bits:         list of digital channels to enable, e.g. [0,1,2,3]
                             (i.e. D0~D3); elements can also be (bit, label) tuples
        :param threshold:    threshold voltage (V)
        :param technology:   threshold technology preset
                             (V165/V25/V125/V09/V15/VM13/V38/V20/V0/MANual)
        :param hysteresis:   hysteresis (MAXimum/ROBust/NORMal)
        :param clocked:      True uses one channel as the bus clock
        :param clock_source: clock channel (D0..D15)
        :param clock_slope:  clock edge (POSitive/NEGative/EITHer)
        :param decode_table: True shows the decode result table (clocked bus only)
        :param show_bus/show_digital: show the bus signal / the digital channels
        :param enable:       True enables this logic group
        """
        bits = bits or []
        # self.pbus_state(pbus, enable)
        # self.pbus_clear(pbus)
        self.pbus_threshold(pbus, 1, threshold)
        self.pbus_technology(pbus, technology)
        self.pbus_hysteresis(pbus, 1, hysteresis)
        for item in bits:
            if isinstance(item, (tuple, list)):
                bit, label = item[0], item[1]
            else:
                bit, label = item, None
            self.pbus_bit_state(pbus, bit, True)
            if label is not None:
                self.pbus_bit_label(pbus, bit, label)
        if clocked:
            self.pbus_clock(pbus, source=clock_source, slope=clock_slope, on=True)
            self.pbus_decode_table(pbus, decode_table)
        self.pbus_display(pbus, show_bus=show_bus, show_digital=show_digital)
        self.pbus_state(pbus, enable)

    # ------------------------------------------------------------------
    # Automatic measurements (generic)
    # ------------------------------------------------------------------
    def configure_measurement(self, measure_index=1, source="C1", main="AMPlitude",
                              category=None, additional=None, enable=True):
        """
        Configure one automatic measurement item (MEASurement<n>).

        :param measure_index: measurement number (1..N)
        :param source:        measurement source (C1..C4 / EYE1 / math signal, ...)
        :param main:          main measurement type, e.g. AMPlitude / FREQuency / EHEight
        :param category:      measurement category, e.g. EYEJitter
        :param additional:    list of additional measurements, elements can be a
                              str or a (name, on) tuple
        :param enable:        True enables the measurement
        """
        if category is not None:
            self.write(f"MEASurement{measure_index}:CATegory {category}")
        self.write(f"MEASurement{measure_index}:SOURce {source}")
        self.write(f"MEASurement{measure_index}:MAIN {main}")
        if additional:
            for item in additional:
                if isinstance(item, str):
                    name, on = item, True
                else:
                    name, on = item[0], item[1]
                self.write(
                    f"MEASurement{measure_index}:ADDitional {name},{'ON' if on else 'OFF'}")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def get_measurement_result(self, measure_index=1, result_index=1):
        """
        Read a measurement result.

        :param measure_index: measurement number
        :param result_index:  result index (1 is the main measurement, >1 the
                              additional measurements)
        :return: the measurement value as a string
        """
        if result_index <= 1:
            return self.query(f"MEASurement{measure_index}:RESult:ACTual?")
        return self.query(f"MEASurement{measure_index}:RESult{result_index}:ACTual?")

    # ------------------------------------------------------------------
    # Rise time / amplitude measurement helpers (based on MEASurement)
    # ------------------------------------------------------------------
    def configure_rise_time_measurement(self, measure_index=1, source="C1",
                                        enable=True):
        """
        Configure the rise time automatic measurement ``MEASurement<n>:MAIN RTIMe``.

        Note: the MXO4 rise time parameter is ``RTIMe`` (not ``RISEtime``).

        :param measure_index: measurement number (1..16)
        :param source:        measurement source (C1..C4 / D0..D15 / math signal, ...)
        :param enable:        True enables the measurement
        """
        self.write(f"MEASurement{measure_index}:SOURce {self._src(source)}")
        self.write(f"MEASurement{measure_index}:MAIN RTIMe")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_amplitude_measurement(self, measure_index=1, source="C1",
                                        enable=True):
        """
        Configure the amplitude automatic measurement ``MEASurement<n>:MAIN AMPLitude``.
        """
        self.write(f"MEASurement{measure_index}:SOURce {self._src(source)}")
        self.write(f"MEASurement{measure_index}:MAIN AMPLitude")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def get_measurement_value(self, measure_index=1):
        """
        Read a measurement result and convert it to float when possible;
        the raw string is returned when the conversion fails.

        Corresponds to ``MEASurement<n>:RESult:ACTual?``.
        """
        raw = self.query(f"MEASurement{measure_index}:RESult:ACTual?")
        try:
            return float(raw)
        except (ValueError, TypeError):
            return raw

    # ------------------------------------------------------------------
    # Cursor measurements (Cursor)
    # ------------------------------------------------------------------
    def cursor_state(self, cursor=1, on=True):
        """Switch the cursor display on/off ``CURSor<n>:STATe ON|OFF``."""
        self.write(f"CURSor{cursor}:STATe {'ON' if on else 'OFF'}")

    def cursor_all_off(self):
        """Switch all cursors off ``CURSor:AOFF`` (no suffix)."""
        self.write("CURSor:AOFF")

    def cursor_function(self, cursor=1, function=CursorFunction.PAIRED):
        """Set the cursor type ``CURSor<n>:FUNCtion`` (VERTical / HORizontal / PAIRed)."""
        val = function.value if isinstance(function, CursorFunction) else function
        self.write(f"CURSor{cursor}:FUNCtion {val}")

    def cursor_source(self, cursor=1, source="C1"):
        """Set the cursor source ``CURSor<n>:SOURce``."""
        self.write(f"CURSor{cursor}:SOURce {self._src(source)}")

    def cursor_positions(self, cursor=1, x1=None, x2=None, y1=None, y2=None):
        """
        Set the cursor positions
        ``CURSor<n>:X1Position / X2Position / Y1Position / Y2Position``.

        :param x1/x2: vertical cursor positions (s); y1/y2: horizontal cursor
                      positions (V); None keeps the current value
        """
        if x1 is not None:
            self.write(f"CURSor{cursor}:X1Position {x1}")
        if x2 is not None:
            self.write(f"CURSor{cursor}:X2Position {x2}")
        if y1 is not None:
            self.write(f"CURSor{cursor}:Y1Position {y1}")
        if y2 is not None:
            self.write(f"CURSor{cursor}:Y2Position {y2}")

    def cursor_tracking(self, cursor=1, on=True):
        """Set the cursor tracking ``CURSor<n>:TRACking:STATe ON|OFF``."""
        self.write(f"CURSor{cursor}:TRACking:STATe {'ON' if on else 'OFF'}")

    def cursor_display_values(self, cursor=1, on=True):
        """Whether the cursor value labels are shown ``CURSor<n>:DISPlay:VALues ON|OFF``."""
        self.write(f"CURSor{cursor}:DISPlay:VALues {'ON' if on else 'OFF'}")

    def cursor_label_show(self, cursor=1, on=True):
        """Whether the cursor labels (names) are shown ``CURSor<n>:LABel ON|OFF``."""
        self.write(f"CURSor{cursor}:LABel {'ON' if on else 'OFF'}")

    def cursor_vertical_label(self, cursor=1, line=1, label=""):
        """
        Set the name of a vertical cursor line ``CURSor<n>:VERTical<m>:LABel '<label>'``.

        :param cursor: cursor group number (1..2)
        :param line:   vertical cursor line number (1..2)
        :param label:  name text (do not use single quotes inside)
        """
        self.write(f"CURSor{cursor}:VERTical{int(line)}:LABel '{label}'")

    def cursor_horizontal_label(self, cursor=1, line=1, label=""):
        """
        Set the name of a horizontal cursor line ``CURSor<n>:HORizontal<m>:LABel '<label>'``.

        :param cursor: cursor group number (1..2)
        :param line:   horizontal cursor line number (1..2)
        :param label:  name text (do not use single quotes inside)
        """
        self.write(f"CURSor{cursor}:HORizontal{int(line)}:LABel '{label}'")

    def set_cursor_labels(self, cursor=1, v1=None, v2=None, h1=None, h2=None):
        """
        Set the names of all four cursor lines in one go (None keeps the name).

        :param v1/v2: names of vertical cursor lines 1/2
        :param h1/h2: names of horizontal cursor lines 1/2
        :return: self, allows chaining
        """
        if v1 is not None:
            self.cursor_vertical_label(cursor, 1, v1)
        if v2 is not None:
            self.cursor_vertical_label(cursor, 2, v2)
        if h1 is not None:
            self.cursor_horizontal_label(cursor, 1, h1)
        if h2 is not None:
            self.cursor_horizontal_label(cursor, 2, h2)
        return self

    def get_cursor_delta_x(self, cursor=1):
        """Read the vertical cursor difference delta X (time, s) ``CURSor<n>:XDELta?``."""
        return float(self.query(f"CURSor{cursor}:XDELta?"))

    def get_cursor_delta_y(self, cursor=1):
        """Read the horizontal cursor difference delta Y (amplitude, V) ``CURSor<n>:YDELta?``."""
        return float(self.query(f"CURSor{cursor}:YDELta?"))

    def configure_cursor(self, cursor=1, function=CursorFunction.PAIRED,
                         source="C1", x1=None, x2=None, y1=None, y2=None,
                         show=True, show_values=True, tracking=False):
        """
        Configure a cursor in one go: type / source / positions / display.

        :param cursor:      cursor group number (1..2)
        :param function:    CursorFunction.VERTICAL (measure time) /
                            HORIZONTAL (measure amplitude) / PAIRED (both)
        :param source:      cursor source (C1..C4, ...)
        :param x1/x2:       vertical cursor positions (s)
        :param y1/y2:       horizontal cursor positions (V)
        :param show:        True shows the cursors (CURSor<n>:STATe ON);
                            False only configures them
        :param show_values: True shows the cursor value labels
        :param tracking:    whether the cursors track the waveform
        :return: self, allows chaining
        """
        self.cursor_function(cursor, function)
        self.cursor_source(cursor, source)
        self.cursor_positions(cursor, x1=x1, x2=x2, y1=y1, y2=y2)
        self.cursor_tracking(cursor, tracking)
        self.cursor_display_values(cursor, show_values)
        self.cursor_state(cursor, show)
        return self

    # ------------------------------------------------------------------
    # Setup / hold time measurements
    # ------------------------------------------------------------------
    def configure_setup_time(self, measure_index=1, data_source="C1",
                             clock_source="C2", enable=True):
        """
        Configure the setup time automatic measurement.

        A setup time measurement needs two sources:
          * data source ``data_source``   -> ``MEASurement<n>:SOURce``
          * clock source ``clock_source`` -> ``MEASurement<n>:SSRC`` (second source)

        :param measure_index: measurement number (1..N)
        :param data_source:   data source (C1..C4 / D0..D15, ...)
        :param clock_source:  clock (reference) source; the setup time is
                              referenced to the edge of this source
        :param enable:        True enables the measurement
        """
        self.write(f"MEASurement{measure_index}:MAIN SETup")
        self.write(f"MEASurement{measure_index}:SOURce {self._src(data_source)}")
        self.write(f"MEASurement{measure_index}:SSRC {self._src(clock_source)}")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_hold_time(self, measure_index=1, data_source="C1",
                            clock_source="C2", enable=True):
        """
        Configure the hold time automatic measurement.

        A hold time measurement needs two sources:
          * data source ``data_source``   -> ``MEASurement<n>:SOURce``
          * clock source ``clock_source`` -> ``MEASurement<n>:SSRC`` (second source)

        :param measure_index: measurement number (1..N)
        :param data_source:   data source (C1..C4 / D0..D15, ...)
        :param clock_source:  clock (reference) source; the hold time is
                              referenced to the edge of this source
        :param enable:        True enables the measurement
        """
        self.write(f"MEASurement{measure_index}:MAIN HOLD")
        self.write(f"MEASurement{measure_index}:SOURce {self._src(data_source)}")
        self.write(f"MEASurement{measure_index}:SSRC {self._src(clock_source)}")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_setup_hold(self, measure_index=1, data_source="C1",
                             clock_source="C2", enable=True):
        """
        Configure the setup time (SETup) and hold time (HOLD) measurement together.

        Two consecutive measurement numbers are used:
          * ``measure_index``      -> setup time ``SETup``
          * ``measure_index + 1``  -> hold time ``HOLD``

        :param measure_index: first measurement number (1..N)
        :param data_source:   data source
        :param clock_source:  clock (reference) source
        :param enable:        True enables the measurements
        :return: (setup_index, hold_index), the measurement numbers used by the
                 two measurements
        """
        self.configure_setup_time(measure_index, data_source, clock_source, enable)
        hold_index = measure_index + 1
        self.configure_hold_time(hold_index, data_source, clock_source, enable)
        return measure_index, hold_index

    def get_setup_hold_results(self, measure_index=1):
        """
        Read the setup time and hold time measurement results
        (``RESult:ACTual?``, unit: seconds).

        ``configure_setup_hold`` has to be called first (or ``configure_setup_time`` /
        ``configure_hold_time`` separately) and the scope must have finished the
        acquisition.

        :param measure_index: measurement number used by the setup time measurement
        :return: dict with the keys 'setup' and 'hold' and string values
        """
        return {
            "setup": self.get_measurement_result(measure_index),
            "hold": self.get_measurement_result(measure_index + 1),
        }

    # ------------------------------------------------------------------
    # Eye diagram
    # ------------------------------------------------------------------
    def configure_cdr(self, source="C1", bit_rate=None, sw_cdr=1):
        """
        Configure the software clock data recovery (CDR).

        Eye diagram / jitter analysis need a CDR to recover the clock from the
        serial data stream.

        :param source:   data source (C1..C4 / DIFF1, ...)
        :param bit_rate: bit rate (bit/s), e.g. 1e9 for 1 Gbps
        :param sw_cdr:   software CDR number (1 by default)
        """
        self.write(f"CDR:SOFTware{sw_cdr}:ESSRate:SOURce {self._src(source)}")
        if bit_rate is not None:
            self.write(f"CDR:SOFTware{sw_cdr}:ESSRate {bit_rate}")

    def configure_eye_diagram(self, source="C1", cdr_mode="SW", enable=True):
        """
        Configure the eye diagram.

        :param source:   signal source (C1..C4 / DIFF1 / math signal)
        :param cdr_mode: CDR mode: "SW" software CDR (recommended), "HW" hardware CDR
        :param enable:   True switches the eye diagram on, False off
        """
        self.write(f"EYE1:SOURce {self._src(source)}")
        if str(cdr_mode).upper() in ("SW", "SOFTware", "SOFTWARE"):
            # software CDR
            self.write("EYE1:TIMReference:SOURce CDR")
            self.write("EYE1:TIMReference:CDR:SELect SW")
            self.write("EYE1:TIMReference:CDR:SOFTware SW1")
            self.write(f"CDR:SOFTware1:ESSRate:SOURce {self._src(source)}")
        else:
            # hardware CDR (the trigger type is switched to CDR)
            self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")
            self.write("TRIGger:EVENt1:TYPe CDR")
        self.write(f"EYE1:STATe {'ON' if enable else 'OFF'}")
        self.wait_opc()

    def configure_eye_measurement(self, measure_index=1, source="EYE1",
                                  main=EyeMeasurement.EYE_HEIGHT,
                                  additional=None, enable=True):
        """
        Configure an eye diagram measurement (eye height / eye width / eye amplitude, ...).

        :param measure_index: measurement number
        :param source:        measurement source, EYE1 by default
        :param main:          main measurement (EyeMeasurement or a string)
        :param additional:    list of additional measurements (EyeMeasurement or strings)
        :param enable:        True enables the measurement
        """
        m = main.value if isinstance(main, EyeMeasurement) else main
        self.write(f"MEASurement{measure_index}:CATegory EYEJitter")
        self.write(f"MEASurement{measure_index}:SOURce {source}")
        self.write(f"MEASurement{measure_index}:MAIN {m}")
        if additional:
            for item in additional:
                name = item.value if isinstance(item, EyeMeasurement) else item
                self.write(f"MEASurement{measure_index}:ADDitional {name},ON")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def get_eye_result(self, measure_index=1, result_index=1):
        """
        Read an eye diagram measurement result.

        :param measure_index: measurement number
        :param result_index:  1 = main measurement (e.g. eye height),
                              >1 = additional measurements (eye width, ...)
        """
        return self.get_measurement_result(measure_index, result_index)

    # ------------------------------------------------------------------
    # Advanced jitter analysis
    # ------------------------------------------------------------------
    def configure_jitter_quick_start(self, source="C1", timeout=120000):
        """
        Advanced jitter analysis quick start (configures bit rate and CDR
        automatically and enables all jitter components).

        Note: this command enables the components TJ@BER, RJ, TJ, DJ, PJ, DDJ, ...
        automatically.

        :param source:  data source (C1..C4 / DIFF1, ...)
        :param timeout: wait timeout (ms), the quick start may take 30~60 seconds
        """
        self.write(f"ADVJitter:SIGNal:SOURce {self._src(source)}")
        self.write("ADVJitter:SIGNal:QUICkmeas")
        self.wait_opc(timeout=timeout)

    def configure_jitter_manual(self, source="C1", components=None):
        """
        Configure the advanced jitter components manually.

        :param source:     data source (C1..C4 / DIFF1, ...)
        :param components: list of JitterComponent members or component numbers
        """
        self.write(f"ADVJitter1:SIGNal:SOURce {self._src(source)}")
        self.write("ADVJitter1:RESult:ENABle ON")
        # switch off the additional displays enabled by the quick start
        for cmd in ("ADVJitter1:RESult:STEPresponse OFF",
                    "ADVJitter1:RESult:BATHtub OFF",
                    "ADVJitter1:RESult:NBAThtub OFF"):
            try:
                self.write(cmd)
            except Exception:
                pass
        for comp in (components or []):
            idx = comp.value if isinstance(comp, JitterComponent) else int(comp)
            self.write(f"ADVJitter1:DCOMposition:COMPonents{idx}:ENABle ON")
            self.write(f"ADVJitter1:RESult:COMPonents{idx}:HISTogram ON")

    def enable_jitter_result(self, on=True):
        """Switch the advanced jitter result display on/off ``ADVJitter1:RESult:ENABle``."""
        self.write(f"ADVJitter1:RESult:ENABle {'ON' if on else 'OFF'}")

    def enable_jitter_component(self, component, on=True):
        """Switch a single jitter component on/off ``ADVJitter1:DCOMposition:COMPonents<idx>:ENABle``."""
        idx = component.value if isinstance(component, JitterComponent) else int(component)
        self.write(f"ADVJitter1:DCOMposition:COMPonents{idx}:ENABle {'ON' if on else 'OFF'}")

    def get_jitter_component_value(self, component):
        """
        Read a jitter component measurement value (unit: seconds).

        Command: ADVJitter1:RESult:COMPonents<idx>:VALue?
        (individual firmware revisions may differ slightly, see the
        "Advanced jitter" chapter of the manual)

        :param component: JitterComponent member or component number
        """
        idx = component.value if isinstance(component, JitterComponent) else int(component)
        return self.query(f"ADVJitter1:RESult:COMPonents{idx}:VALue?")

    # ------------------------------------------------------------------
    # Waveform readout and saving
    # ------------------------------------------------------------------
    def set_waveform_format(self, fmt=WaveformFormat.BINARY_FLOAT32):
        """Set the waveform data format ``FORMat:DATA`` (little endian is set for binary formats too)."""
        val = fmt.value if isinstance(fmt, WaveformFormat) else fmt
        if val.startswith("ASC"):
            self.write("FORMat:DATA ASC")
        else:
            self.write(f"FORMat:DATA {val}")
            self.write("FORMat:BORDer LSBFirst")

    def _parse_header(self, header_str):
        """
        Parse the header returned by ``CHANnel<n>:DATA:HEADer?``.

        The MXO4 may return the header in two formats, both are converted into a
        dictionary:
          1. name=value comma string: XStart=-5e-6,XStop=5e-6,RecordLength=100000,ValsPerSmp=1
          2. fixed order numeric string: -5e-6,5e-6,100000,1  (XStart,XStop,RecordLength,ValsPerSmp)
        """
        header_str = header_str.replace("\n", "").replace(";", ",").strip()
        parts = [p.strip() for p in header_str.split(",") if p.strip() != ""]
        d = {}
        if any("=" in p for p in parts):
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    d[k.strip()] = v.strip()
        else:
            # parse by fixed position when no name=value pairs are present
            names = ("XStart", "XStop", "RecordLength", "ValsPerSmp")
            for name, val in zip(names, parts):
                d[name] = val
        return d

    @staticmethod
    def _header_value(header, *keys):
        """Look up a value in the header dictionary by key (case insensitive / fuzzy match)."""
        low = {k.lower(): v for k, v in header.items()}
        for key in keys:
            k = key.lower()
            if k in low:
                return low[k]
        for k, v in low.items():
            for key in keys:
                if key.lower() in k:
                    return v
        return None

    def get_waveform_header(self, channel):
        """Read the waveform header ``CHANnel<n>:DATA:HEADer?``, returns a dictionary."""
        return self._parse_header(self.query(f"CHANnel{self._ch(channel)}:DATA:HEADer?"))

    # def get_waveform(self, channel, ascii_format=False):
    #     """
    #     Read the waveform data of one channel, returns (time axis list, voltage list).

    #     :param channel:      channel number
    #     :param ascii_format: True uses ASCII transfer (slow but readable),
    #                          False uses float32 binary (fast)
    #     """
    #     ch = self._ch(channel)
    #     hdr = self.get_waveform_header(channel)
    #     if ascii_format:
    #         self.write("FORMat:DATA ASC")
    #         raw = self.query(f"CHANnel{ch}:DATA:VALues?")
    #         volts = [float(x) for x in raw.split(",") if x.strip() != ""]
    #     else:
    #         self.write("FORMat:DATA REAL,32")
    #         self.write("FORMat:BORDer LSBFirst")
    #         self.bin_float_numbers_format = BinFloatFormat.Single_4bytes
    #         # a binary transfer of a large record length takes a long time, so the
    #         # VISA timeout and the read chunk size are increased temporarily to
    #         # avoid a timeout error (VI_ERROR_TMO) with large amounts of data
    #         old_timeout = self.visa_timeout
    #         old_chunk = self.data_chunk_size
    #         try:
    #             # a timeout of at least 30 seconds, enough for millions of samples
    #             self.visa_timeout = max(int(old_timeout or 0), 300000)
    #             self.data_chunk_size = 10_000_000
    #             volts = self.query_bin_or_ascii_float_list(
    #                 f"CHANnel{ch}:DATA:VALues?")
    #         finally:
    #             self.visa_timeout = old_timeout
    #             self.data_chunk_size = old_chunk

    #     xstart = float(self._header_value(hdr, "Xstart", "Start") or 0.0)
    #     xstop = float(self._header_value(hdr, "Xstop", "Stop") or 0.0)
    #     n = len(volts)
    #     if n > 1:
    #         if xstop == xstart:
    #             # when the time information of the header is missing or invalid, the
    #             # time axis is rebuilt from the timebase range so that the time column
    #             # does not consist of zeros
    #             print("Warning: invalid waveform header time information, rebuilding the time axis from TIMebase:RANGe?.")
    #             try:
    #                 t_range = float(self.query("TIMebase:RANGe?"))
    #             except Exception:
    #                 t_range = 0.0
    #             xstart, xstop = -t_range / 2.0, t_range / 2.0
    #         step = (xstop - xstart) / (n - 1)
    #         time_axis = [xstart + step * i for i in range(n)]
    #     else:
    #         time_axis = [xstart]
    #     return time_axis, volts
    

    # def get_waveforms(self, channels, ascii_format=False):
    #     """
    #     Read the waveforms of several channels, returns dict: {channel: (time_axis, volts)}.
    #     """
    #     result = {}
    #     for ch in channels:
    #         result[ch] = self.get_waveform(ch, ascii_format=ascii_format)
    #     return result

    # ------------------------------------------------------------------
    # Waveform ZOOM (frames the UART frame automatically after a UART frame
    # trigger; instrument side display zoom + PC side plot zoom)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 1) instrument side: zoom the timebase window / restore it
    # ------------------------------------------------------------------
    def get_timebase_state(self):
        """
        Read the current timebase state (SCALe / RANGe / REFerence /
        HORizontal:POSition) so the original display can be restored after a ZOOM.
        """
        state = {}
        for key, cmd in (("scale", "TIMebase:SCALe?"),
                         ("range", "TIMebase:RANGe?"),
                         ("reference", "TIMebase:REFerence?"),
                         ("position", "TIMebase:HORizontal:POSition?")):
            try:
                state[key] = float(self.query(cmd))
            except Exception:
                state[key] = None
        return state

    def restore_timebase(self, state):
        """Restore a timebase saved by :meth:`get_timebase_state` (scale/position/reference)."""
        if not state:
            return
        # restore reference point and span first, then the offset and the scale
        # last, so that no intermediate state goes out of range
        if state.get("reference") is not None:
            try:
                self.timebase_position(state["reference"])
            except Exception:
                pass
        if state.get("range") is not None:
            try:
                self.timebase_range(state["range"])
            except Exception:
                pass
        if state.get("position") is not None:
            try:
                self.timebase_offset(state["position"])
            except Exception:
                pass
        if state.get("scale") is not None:
            try:
                self.timebase_scale(state["scale"])
            except Exception:
                pass

    # ------------------------------------------------------------------
    # MXO4 split screen ZOOM window (the main area keeps the complete waveform /
    # decoded frame, the ZOOM area only magnifies one of them)
    #   note: the MXO4 uses the LAYout<ly>:ZOOM<zo>:* node, not TIMebase:ZOOM
    # ------------------------------------------------------------------
    def zoom_window_state(self, on=True, layout=1, zoom=1):
        """Enable/disable the split screen ZOOM window ``LAYout<ly>:ZOOM<zo>:ENABle``."""
        self.write(f"LAYout{layout}:ZOOM{zoom}:ENABle {'ON' if on else 'OFF'}")

    def zoom_window_source(self, diagram=1, layout=1, zoom=1):
        """Select which diagram is magnified by the ZOOM (diagram index) ``LAYout<ly>:ZOOM<zo>:SOURce``."""
        self.write(f"LAYout{layout}:ZOOM{zoom}:SOURce {int(diagram)}")

    def get_zoom_window_diagram(self, layout=1, zoom=1):
        """Query the index of the diagram currently magnified by the ZOOM ``LAYout<ly>:ZOOM<zo>:DIAG?``."""
        return self.query(f"LAYout{layout}:ZOOM{zoom}:DIAG?")

    def zoom_window_horizontal(self, mode="ABS", position=None, span=None,
                               start=None, stop=None, layout=1, zoom=1):
        """
        Set the horizontal range of the ZOOM area.

        :param mode: 'ABS' absolute time (s) / 'REL' relative percentage (%)
        :param position: centre of the ZOOM area (ABS: s, 0 s = trigger point; REL: %)
        :param span:     width of the ZOOM area (ABS: s; REL: %)
        :param start/stop: lower/upper limit of the ZOOM area (ABS: s; REL: %)
        """
        mode = "ABS" if str(mode).upper() in ("ABS", "ABSOLUTE") else "REL"
        node = "ABSolute" if mode == "ABS" else "RELative"
        self.write(f"LAYout{layout}:ZOOM{zoom}:HORizontal:MODE {mode}")
        if position is not None:
            self.write(f"LAYout{layout}:ZOOM{zoom}:HORizontal:{node}:POSition {position}")
        if span is not None:
            self.write(f"LAYout{layout}:ZOOM{zoom}:HORizontal:{node}:SPAN {span}")
        if start is not None:
            self.write(f"LAYout{layout}:ZOOM{zoom}:HORizontal:{node}:STARt {start}")
        if stop is not None:
            self.write(f"LAYout{layout}:ZOOM{zoom}:HORizontal:{node}:STOP {stop}")

    def zoom_display(self, span=None, s_per_div=None, t_center=None,
                     reacquire=True, acquire_timeout=8000):
        """
        Magnify the horizontal display window on the scope to a given range (ZOOM)
        so that a zoomed waveform can be saved as a screenshot.

        :param span:           full screen time span (s), e.g. the time of one UART frame
        :param s_per_div:      time per division (s); alternative to span
                               (s_per_div * 10 = span)
        :param t_center:       absolute time (s) that should be centred on the
                               screen (only effective with a reference point of
                               50%). The MXO4 horizontal shift command is
                               ``TIMebase:HORizontal:POSition`` (distance between
                               the trigger point t=0 and the reference point, i.e.
                               offset = -t_center); invert t_center for fine tuning
                               if the magnified waveform is not where you expect it.
        :param reacquire:      True runs another ``SINGle`` to refresh the magnified
                               display (this needs a trigger; the wait time is
                               limited by acquire_timeout, a timeout only warns and
                               does not interrupt the flow)
        :param acquire_timeout: timeout for the re-acquisition (ms)
        :return: dict(span, s_per_div, t_center) actually used window
        """
        if s_per_div is not None:
            span = float(s_per_div) * 10.0
        if span is None:
            raise ValueError("zoom_display: span or s_per_div must be given")
        span = float(span)
        self.timebase_range(span)
        if t_center is not None:
            self.timebase_offset(-float(t_center))   # shift the window so that t_center is centred on the screen
        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"Warning: re-acquisition after ZOOM failed/timed out (no new trigger?): {exc}")
        return {"span": span, "s_per_div": span / 10.0, "t_center": t_center}

    def zoom_uart_display(self, baud=115200, data_bits=8,
                          parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                          margin_bits=2.0, diagram=1, layout=1, zoom=1,
                          reacquire=True, acquire_timeout=8000):
        """
        Instrument side split screen ZOOM: after a successful UART serial bus
        trigger the main area keeps the complete waveform (all data frames of the
        UART decoder) and the ZOOM area magnifies just one frame (the frame
        around the trigger point by default).

        Unlike :meth:`zoom_display` (which changes the full screen timebase), this
        method uses the MXO4 split screen ZOOM window ``LAYout<ly>:ZOOM<zo>:*``:
          * the main area (original diagram) keeps showing the complete waveform
            and all UART decoded frames;
          * the ZOOM area frames a single frame with an ABS horizontal window
            (the serial bus trigger point is at the frame start bit, t~0).

        :param baud:        baud rate
        :param data_bits:   number of data bits (7/8/9)
        :param parity:      parity
        :param stop_bits:   stop bits
        :param margin_bits: extra idle bit times kept before and after the frame
        :param diagram:     diagram index magnified by the ZOOM (1 = main waveform by default)
        :param layout:      SmartGrid layout index (1 by default)
        :param zoom:        ZOOM window index (1 by default)
        :param reacquire:   True runs another SINGle to refresh the acquisition first
        :return: dict(frame_time, span, s_per_div, zoom_start, zoom_stop)
        """
        n_parity = MXO4._parity_bit_count(parity)
        n_stop = MXO4._stop_bit_count(stop_bits)
        bit_time = 1.0 / float(baud)
        frame_time = (1 + int(data_bits) + n_parity + n_stop) * bit_time
        margin = max(0.0, margin_bits) * bit_time
        zoom_start = -margin                        # keep a margin before the frame start bit (trigger point t~0)
        zoom_stop = frame_time + margin             # keep a margin after the frame end (incl. stop bits)
        span = zoom_stop - zoom_start

        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"Warning: re-acquisition before ZOOM failed/timed out (no new trigger?): {exc}")

        # the main area keeps the complete waveform/decoded frames; only the ZOOM
        # window is enabled and frames a single frame
        self.zoom_window_state(True, layout=layout, zoom=zoom)
        self.zoom_window_source(diagram, layout=layout, zoom=zoom)
        self.zoom_window_horizontal(mode="ABS", start=zoom_start, stop=zoom_stop,
                                    layout=layout, zoom=zoom)
        return {"frame_time": frame_time, "span": span,
                "s_per_div": span / 10.0,
                "zoom_start": zoom_start, "zoom_stop": zoom_stop}

    def zoom_i2c_display(self, scl_freq=100000, frame_bits=9, margin_bits=2.0,
                         diagram=1, layout=1, zoom=1,
                         reacquire=True, acquire_timeout=8000):
        """
        Instrument side split screen ZOOM: after a successful I2C serial bus
        trigger the main area keeps the complete waveform (all data frames of the
        I2C decoder) and the ZOOM area magnifies just one frame (one byte after
        the START trigger point by default: 8 data bits + 1 ACK = 9 SCL clocks).

        Unlike :meth:`zoom_display` (which changes the full screen timebase), this
        method uses the MXO4 split screen ZOOM window ``LAYout<ly>:ZOOM<zo>:*``:
          * the main area (original diagram) keeps showing the complete waveform
            and all I2C decoded frames;
          * the ZOOM area frames a single frame with an ABS horizontal window
            (the I2C START trigger point is at t~0).

        :param scl_freq:    SCL clock frequency (Hz), e.g. 100e3 / 400e3 / 1e6
        :param frame_bits:  number of SCL clocks of one frame (9 by default = 8 data bits + 1 ACK)
        :param margin_bits: extra SCL clocks kept before and after the frame
        :param diagram:     diagram index magnified by the ZOOM (1 = main waveform by default)
        :param layout:      SmartGrid layout index (1 by default)
        :param zoom:        ZOOM window index (1 by default)
        :param reacquire:   True runs another SINGle to refresh the acquisition first
        :return: dict(frame_time, span, s_per_div, zoom_start, zoom_stop)
        """
        bit_time = 1.0 / float(scl_freq)
        frame_time = float(frame_bits) * bit_time
        margin = max(0.0, margin_bits) * bit_time
        zoom_start = -margin                        # keep a margin before START (trigger point t~0)
        zoom_stop = frame_time + 2*margin             # keep a margin after one frame
        span = zoom_stop - zoom_start

        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"Warning: re-acquisition before ZOOM failed/timed out (no new trigger?): {exc}")

        # the main area keeps the complete waveform/decoded frames; only the ZOOM
        # window is enabled and frames a single frame
        self.zoom_window_state(True, layout=layout, zoom=zoom)
        self.zoom_window_source(diagram, layout=layout, zoom=zoom)
        self.zoom_window_horizontal(mode="ABS", start=zoom_start, stop=zoom_stop,
                                    layout=layout, zoom=zoom)
        return {"frame_time": frame_time, "span": span,
                "s_per_div": span / 10.0,
                "zoom_start": zoom_start, "zoom_stop": zoom_stop}

    # ------------------------------------------------------------------
    # 2) Software UART decoding / frame localization (core of the automatic framing)
    # ------------------------------------------------------------------
    @staticmethod
    def _parity_bit_count(parity):
        """Whether the UART parity bit is enabled: NONE -> 0, anything else -> 1."""
        if isinstance(parity, UARTParity):
            s = parity.value.upper()
        else:
            s = str(parity).strip().upper()
        return 0 if s in ("NONE", "", "OFF") else 1

    @staticmethod
    def _stop_bit_count(stop_bits):
        """Number of UART stop bits: 'B1'->1, 'B15'->1.5, 'B2'->2, numbers are returned as is."""
        if isinstance(stop_bits, STOPBit):
            s = stop_bits.value.upper()
        else:
            s = str(stop_bits).strip().upper()
        s = s.replace("B", "")                       # 'B1'/'B15'/'B2' -> '1'/'15'/'2'
        if s in ("", "1"):
            return 1.0
        if s == "15":
            return 1.5
        try:
            return float(s)
        except Exception:
            return 1.0

    @staticmethod
    def decode_uart_waveform(time_axis, volts, baud=115200, data_bits=8,
                             parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                             idle=UARTPOLarity.IDLHigh, threshold=1.65):
        """
        Pure software UART frame decoding / localization (independent of the
        protocol analysis option of the instrument), used to frame the ZOOM area
        automatically.

        UART frames are identified one by one in the acquired RX waveform:
          * frame structure = start bit + data bits + (parity bit) + stop bit(s) (idle level);
          * for every candidate start edge the bits are sampled at the bit centre
            and the data is rebuilt LSB first.
        This static method can be called without an instrument / offline, which is
        convenient for local verification and post-processing.

        :param time_axis: time axis (s)
        :param volts:     voltage (V), same length as time_axis
        :param baud:      baud rate
        :param data_bits: number of data bits (7/8/9)
        :param parity:    UARTParity.NONE / EVEN / ODD / MARK / SPC
        :param stop_bits: STOPBit.ONE_BIT / .ONE_P_FIVE_BITS / .TWO_BITS, or 1/1.5/2
        :param idle:      UARTPOLarity.IDLHigh (idle high) / IDLLow (idle low)
        :param threshold: logic decision threshold (V)
        :return: list[dict] sorted by t_start; every frame holds:
            index / t_start / t_stop / t_center / bit_time /
            bits / data_int / data_bin / data_hex / data_ascii /
            parity_error / stop_ok / valid
        """
        import numpy as np
        t = np.asarray(time_axis, dtype=np.float64)
        v = np.asarray(volts, dtype=np.float64)
        if t.ndim != 1 or v.ndim != 1 or len(t) != len(v) or len(t) < 8:
            return []
        bit_time = 1.0 / float(baud)
        logic = (v >= float(threshold)).astype(bool)          # True = high
        if isinstance(idle, UARTPOLarity):
            idle_high = (idle == UARTPOLarity.IDLHigh)
        else:
            idle_high = str(idle).strip().upper() in ("IDLHIGH", "IDLEHIGH", "1")
        n_parity = MXO4._parity_bit_count(parity)
        n_stop = MXO4._stop_bit_count(stop_bits)
        data_bits = int(data_bits)
        head_bits = 1 + data_bits + n_parity                   # start + data + parity
        # start edge = transition from idle to non-idle
        if idle_high:
            edges = np.flatnonzero(logic[:-1] & ~logic[1:])    # high -> low
        else:
            edges = np.flatnonzero(~logic[:-1] & logic[1:])    # low -> high

        def _level_at(tt, default):
            """Return the logic level near time tt (True=high), default when out of range."""
            idx = int(np.searchsorted(t, tt))
            if idx <= 0:
                return bool(logic[0])
            if idx >= len(t):
                return bool(default)
            if tt - t[idx - 1] <= t[idx] - tt:
                return bool(logic[idx - 1])
            return bool(logic[idx])

        parity_text = (parity.value if isinstance(parity, UARTParity)
                       else str(parity)).strip().upper()
        frames = []
        last_frame_end = float("-inf")
        for i0 in edges:
            t_start = float(t[i0])
            # the centre of the start bit must be the non-idle level
            if _level_at(t_start + 0.5 * bit_time, idle_high) == idle_high:
                continue
            t_frame_end = t_start + (head_bits + n_stop) * bit_time
            if t_frame_end > float(t[-1]) + bit_time:          # frame exceeds the record
                continue
            # overlap with an already received frame (the previous frame has not
            # ended yet): skip glitch edges inside a frame
            if t_start < last_frame_end - 0.2 * bit_time:
                continue
            bits = [_level_at(t_start + (k + 0.5) * bit_time, idle_high)
                    for k in range(head_bits)]
            if bits[0] == idle_high:                           # the start bit must be non-idle
                continue
            data_vals = bits[1:1 + data_bits]
            par_val = bits[1 + data_bits] if n_parity else None
            stop_val = _level_at(t_start + (head_bits + n_stop * 0.5) * bit_time,
                                 idle_high)
            # assemble the data LSB first
            data_int = sum((1 << j) for j, b in enumerate(data_vals) if b)
            # parity check
            parity_error = False
            if n_parity and par_val is not None:
                ones = sum(1 for b in data_vals if b)
                if parity_text == "EVEN":
                    want = ones % 2
                elif parity_text == "ODD":
                    want = 1 - (ones % 2)
                elif parity_text == "MARK":
                    want = 1
                elif parity_text in ("SPC", "SPACE", "DC"):
                    want = 0
                else:
                    want = None
                parity_error = (want is not None and bool(par_val) != bool(want))
            stop_ok = bool(stop_val == idle_high)
            ndig = (data_bits + 3) // 4
            data_int = int(data_int)
            ascii_ch = chr(data_int) if 32 <= data_int <= 126 else "."
            frames.append({
                "index": len(frames),
                "t_start": t_start,
                "t_stop": t_start + (head_bits + n_stop) * bit_time,
                "t_center": t_start + (head_bits + n_stop) * bit_time / 2.0,
                "bit_time": bit_time,
                "bits": "".join("1" if b else "0" for b in bits),
                "data_int": data_int,
                "data_bin": "".join("1" if b else "0" for b in data_vals),
                "data_hex": f"{data_int:0{ndig}X}",
                "data_ascii": ascii_ch,
                "parity_error": parity_error,
                "stop_ok": stop_ok,
                "valid": (not parity_error) and stop_ok,
            })
            last_frame_end = frames[-1]["t_stop"]
        return frames

    def get_uart_frames(self, rx_channel, baud=115200, data_bits=8,
                        parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                        idle=UARTPOLarity.IDLHigh, threshold=1.65,
                        ascii_format=False):
        """
        Read the waveform of the given RX channel and localize the UART frames in software.

        :return: (frames, (time_axis, volts)); see decode_uart_waveform for frames
        """
        t, v = self.get_waveform(rx_channel, ascii_format=ascii_format)
        frames = self.decode_uart_waveform(t, v, baud=baud, data_bits=data_bits,
                                           parity=parity, stop_bits=stop_bits,
                                           idle=idle, threshold=threshold)
        return frames, (t, v)

    @staticmethod
    def pick_uart_frame(frames, which="trigger", index=0):
        """
        Pick the frame used for the ZOOM out of the list of decoded frames.

        :param which: 'trigger' -> the frame closest to the trigger point (t=0),
                      which is normally the triggering frame for a serial bus trigger;
                      'first'/'index' -> frame number index; 'last' -> the last frame
        :return: frame dict or None
        """
        if not frames:
            return None
        w = str(which).strip().lower()
        if w in ("index", "nth"):
            idx = max(0, min(int(index), len(frames) - 1))
            return frames[idx]
        if w == "last":
            return frames[-1]
        return min(frames, key=lambda f: abs(f["t_center"]))   # 'trigger' / 'first'

    @staticmethod
    def uart_zoom_window(frame, margin_bits=2.0, min_span=None):
        """
        Compute the horizontal window of the automatic ZOOM from one frame
        (frames that UART frame automatically).

        :param margin_bits: number of extra idle bit times kept before/after the frame
        :param min_span:    minimum full screen time (s) so that the zoom is not too deep
        :return: dict(t_center, span, s_per_div, t_start_zoom, t_stop_zoom) or None
        """
        if frame is None:
            return None
        bit_time = frame["bit_time"]
        pad = max(0.0, margin_bits) * bit_time
        lo = frame["t_start"] - pad
        hi = frame["t_stop"] + pad
        span = hi - lo
        if min_span is not None and span < float(min_span):
            mid = (lo + hi) / 2.0
            span = float(min_span)
            lo, hi = mid - span / 2.0, mid + span / 2.0
        return {
            "t_center": (lo + hi) / 2.0,
            "span": span,
            "s_per_div": span / 10.0,
            "t_start_zoom": lo,
            "t_stop_zoom": hi,
        }

    # ------------------------------------------------------------------
    # 3) PC side: waveform ZOOM plotting (matplotlib)
    # ------------------------------------------------------------------
    @staticmethod
    def _plot_waveform_png(t, v, out_path, window=None, frame=None,
                           title="", show_full_trace=False, dpi=150):
        """
        Plot the (t, v) waveform into a PNG (core plotting function, static, which
        makes offline testing easy).

        :param window:          (t0, t1) zoom range, None for the complete view
        :param frame:           UART frame dict, marked with a shaded area + vertical lines
        :param show_full_trace: True together with a window draws the complete
                                waveform in a light colour as background
        """
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        t = np.asarray(t, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        fig, ax = plt.subplots(figsize=(12, 6))
        if show_full_trace and window is not None:
            ax.plot(t, v, linewidth=0.5, color="0.75", label="Full trace")
        if window is not None:
            lo, hi = float(window[0]), float(window[1])
            mask = (t >= lo) & (t <= hi)
            ax.plot(t[mask], v[mask], linewidth=0.9, color="#1f77b4")
            ax.set_xlim(lo, hi)
        else:
            ax.plot(t, v, linewidth=0.7, color="#1f77b4", label="Waveform")
        if frame is not None:
            fs, fe = frame["t_start"], frame["t_stop"]
            ax.axvspan(fs, fe, alpha=0.18, color="orange", label="UART frame")
            ax.axvline(fs, color="red", ls="--", lw=1.0)
            ax.axvline(fe, color="green", ls="--", lw=1.0)
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            ax.text(fs, y1 - (y1 - y0) * 0.05,
                    f"start {fs:.3e}s", color="red", fontsize=9, va="top")
            ax.text(fe, y1 - (y1 - y0) * 0.05,
                    f"stop {fe:.3e}s", color="green", fontsize=9, va="top")
            ax.text(frame["t_center"], y1 - (y1 - y0) * 0.14,
                    f"frame#{frame['index']}: 0x{frame['data_hex']} "
                    f"'{frame['data_ascii']}'", color="k", fontsize=10, ha="center")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Voltage (V)")
        if title:
            ax.set_title(title)
        ax.grid(True, linestyle="--", alpha=0.5)
        if window is None and frame is None:
            ax.legend(loc="best", fontsize=8)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        plt.tight_layout()
        plt.savefig(out_path, dpi=dpi)
        plt.close(fig)

    def save_waveform_window_png(self, channel, out_path, window=None,
                                 ascii_format=False, add_timestamp=False,
                                 title=None, show_full_trace=True):
        """
        Read the waveform of the given channel and save it as a PNG; when
        window=(t0, t1) is given only that time range is magnified and plotted.

        :return: path of the generated PNG
        """
        if add_timestamp:
            out_path = self._stamp(out_path)
        self._ensure_dir(out_path)
        t, v = self.get_waveform(channel, ascii_format=ascii_format)
        title = title or f"MXO4 CH{self._ch(channel)} Waveform"
        self._plot_waveform_png(t, v, out_path, window=window, frame=None,
                                title=title, show_full_trace=show_full_trace)
        print(f"Waveform window image saved: {out_path}")
        return out_path

    def save_uart_zoom_png(self, rx_channel, out_path, baud=115200, data_bits=8,
                           parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                           idle=UARTPOLarity.IDLHigh, threshold=1.65,
                           which="trigger", margin_bits=2.0, min_span=None,
                           ascii_format=False, add_timestamp=False,
                           show_full_trace=True, time_volts=None):
        """
        PC side ZOOM: read the RX channel waveform -> localize the UART frame in
        software -> magnify and save it as a PNG automatically.

        :param rx_channel:  RX channel number (channel carrying the UART signal, e.g. 1)
        :param out_path:    output PNG path (a _zoom suffix and an optional timestamp are added)
        :param which:       frame selection, see pick_uart_frame ('trigger' by default)
        :param margin_bits: number of idle bit times kept before/after the frame
        :param time_volts:  optional (t, v); when given the instrument waveform is
                            not read again
        :return: (png_path, frame, window)
        """
        if add_timestamp:
            out_path = self._stamp(out_path)
        root, ext = os.path.splitext(out_path)
        zoom_path = f"{root}_zoom{ext}"
        self._ensure_dir(zoom_path)

        if time_volts is not None:
            t, v = time_volts
        else:
            t, v = self.get_waveform(rx_channel, ascii_format=ascii_format)
        frames = self.decode_uart_waveform(t, v, baud=baud, data_bits=data_bits,
                                           parity=parity, stop_bits=stop_bits,
                                           idle=idle, threshold=threshold)
        frame = self.pick_uart_frame(frames, which=which)
        win = self.uart_zoom_window(frame, margin_bits=margin_bits,
                                    min_span=min_span) if frame else None
        ch = self._ch(rx_channel)
        if frame is None:
            print(f"Warning: no UART frame found in the CH{ch} waveform, saving the complete waveform.")
            self._plot_waveform_png(t, v, zoom_path, window=None, frame=None,
                                    title=f"MXO4 CH{ch} Waveform (no UART frame found)")
            return zoom_path, None, None
        title = (f"MXO4 CH{ch} UART ZOOM  (frame#{frame['index']}  "
                 f"0x{frame['data_hex']} '{frame['data_ascii']}', "
                 f"baud={baud})")
        self._plot_waveform_png(t, v, zoom_path,
                                window=(win["t_start_zoom"], win["t_stop_zoom"]),
                                frame=frame, title=title,
                                show_full_trace=show_full_trace)
        print(f"UART frame auto ZOOM image saved: {zoom_path}  "
              f"(frame#{frame['index']}: 0x{frame['data_hex']} '{frame['data_ascii']}', "
              f"t = {frame['t_start']:.3e} ~ {frame['t_stop']:.3e} s)")
        return zoom_path, frame, win
##############################################################################################
##############################################################################################
##############################################################################################
    @staticmethod
    def _channel_list(channel):
        """
        Normalize the channel argument into a list of channels.

        Supports: int/str for a single channel; list/tuple for several channels;
        a comma separated string (e.g. '1,2').
        """
        if channel is None:
            return []
        if isinstance(channel, (list, tuple)):
            return list(channel)
        if isinstance(channel, str) and "," in channel:
            return [p.strip() for p in channel.split(",") if p.strip()]
        return [channel]

    def _read_waveform_direct(self, channel, ascii_format=False):
        """
        Read the waveform data of one channel directly from the instrument,
        returns (time_axis, volts).

        It uses the same chunked transfer readout logic as
        :meth:`save_waveform_csv_direct` but does not write a file, so it can be
        used to gather several channels.
        """
        ch = self._ch(channel)
        hdr = self.get_waveform_header(channel)
        self.opc_timeout = 5000
        if ascii_format:
            start = time.time()
            self.write_str("FORM:DATA ASC")
            self.data_chunk_size = 100000  # transfer in 100k byte chunks (default)
            print('Now start to transfer ASCII waveform data. Please wait for about 120 seconds...')
            data = self.query_bin_or_ascii_float_list(f"CHANnel{ch}:DATA:VALues?")
            print(f'ASCII waveform transfer elapsed time: {time.time() - start:.3f}sec')
            volts = data
        else:
            start = time.time()
            self.write_str("FORMat:DATA REAL,32;:FORMat:BORDer LSBFirst")
            self.bin_float_numbers_format = BinFloatFormat.Single_4bytes
            self.data_chunk_size = 100000  # transfer in 100k byte chunks (default)
            print('Now start to transfer binary waveform data. Please wait for about 20 seconds...')
            data = self.query_bin_or_ascii_float_list(f"CHANnel{ch}:DATA:VALues?")
            print(f'Binary waveform transfer elapsed time: {time.time() - start:.3f}sec')
            volts = data

        import numpy as np
        xstart = float(self._header_value(hdr, "Xstart", "Start") or 0.0)
        xstop = float(self._header_value(hdr, "Xstop", "Stop") or 0.0)
        n = len(volts)
        if n > 1:
            t = np.linspace(xstart, xstop, n, dtype=np.float64)
        else:
            t = np.array([xstart], dtype=np.float64)
        return t, volts

    def _write_waveforms_csv(self, pc_path, channels, data):
        """
        Write the waveform data of several channels into one CSV file.

        Columns: Time(s), CH<x>(V), CH<y>(V), ...
        """
        first = channels[0]
        t, _ = data[first]
        self._ensure_dir(pc_path)
        with open(pc_path, "w", newline="") as f:
            writer = csv.writer(f)
            header = ["Time(s)"] + [f"CH{self._ch(ch)}(V)" for ch in channels]
            writer.writerow(header)
            n = len(t)
            for i in range(n):
                row = [t[i]]
                for ch in channels:
                    _, v = data[ch]
                    row.append(v[i] if i < len(v) else "")
                writer.writerow(row)
        print(f"Waveform exported: {pc_path}  ({n} points)")

    def _plot_waveforms(self, data, pc_path, channels):
        """
        Plot the waveform of several channels into a PNG with matplotlib
        (one curve and one legend entry per channel).
        """
        try:
            import matplotlib
            matplotlib.use("Agg")          # headless backend, for scripts / display-less environments
            import matplotlib.pyplot as plt
            root, ext = os.path.splitext(pc_path)
            pc_path_plot = f"{root}.png"   # always save as a PNG image
            plt.figure(figsize=(10, 6))
            for ch in channels:
                t, v = data[ch]
                plt.plot(t, v, linewidth=0.7, label=f"CH{self._ch(ch)}")
            plt.xlabel("Time (s)")
            plt.ylabel("Voltage (V)")
            plt.title("MXO4 Waveform")
            plt.grid(True, linestyle="--", alpha=0.5)
            if len(channels) > 1:
                plt.legend(loc="best", fontsize=8)
            plt.tight_layout()
            self._ensure_dir(pc_path)
            plt.savefig(pc_path_plot, dpi=150)
            plt.close()
            n = max((len(v) for _, v in data.values()), default=0)
            print(f"Waveform image saved: {pc_path_plot}  ({n} points)")
        except ImportError:
            print("matplotlib is not installed, waveform plotting skipped.")

    def save_waveform_csv(self, channel, pc_path=None, instr_path=None, ascii_format=False,
                          add_timestamp=True, filesave=None, localfile=None):
        """
        Export the waveform of one or several channels into a CSV file and plot it
        with matplotlib.

        CSV columns: Time(s), CH<x>(V), CH<y>(V), ...

        :param channel:       channel number (int/str) or a channel list/tuple
                              (e.g. [1, 2] or '1,2')
        :param pc_path:       CSV path on the PC
        :param instr_path:    save folder or path on the instrument (used when filesave=True)
        :param ascii_format:  True uses ASCII transfer, False uses float32 binary (fast)
        :param add_timestamp: True adds a timestamp to the file name automatically
        :param filesave:      False reads directly; True saves the file on the
                              instrument first and downloads it
        :param localfile:     whether the temporary file on the instrument is kept
                              when filesave=True
        :return: pc_path
        """
        channels = self._channel_list(channel)
        if not channels:
            raise ValueError("save_waveform_csv: channel must not be empty")
        if add_timestamp:
            pc_path = self._stamp(pc_path)

        data = {}
        if not filesave:
            for ch in channels:
                data[ch] = self._read_waveform_direct(ch, ascii_format=ascii_format)
            self._write_waveforms_csv(pc_path, channels, data)
        else:
            for ch in channels:
                data[ch] = self.save_waveform_csv_via_instrument(
                    ch, pc_path=pc_path, instr_path=instr_path, localfile=localfile)
            if len(channels) > 1:
                # the instrument can only export one source per CSV file, so
                # several channels are merged and written back on the PC
                self._write_waveforms_csv(pc_path, channels, data)

        self._plot_waveforms(data, pc_path, channels)
        return pc_path

    def save_waveforms_csv(self, channels, filename, ascii_format=False):
        """
        Export the waveforms of several channels into one CSV file.

        Columns: Time(s), CH<x>(V), CH<y>(V), ...
        """
        data = self.get_waveforms(channels, ascii_format=ascii_format)
        # use the time axis of the first channel as the reference
        first = channels[0]
        t, _ = data[first]
        self._ensure_dir(filename)
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            header = ["Time(s)"] + [f"CH{self._ch(ch)}(V)" for ch in channels]
            writer.writerow(header)
            n = len(t)
            for i in range(n):
                row = [t[i]]
                for ch in channels:
                    _, v = data[ch]
                    row.append(v[i] if i < len(v) else "")
                writer.writerow(row)
        print(f"Multiple channel waveform exported: {filename}  ({n} points)")
        return filename

    def save_waveform_binary(self, channel, filename, add_timestamp=True):
        """
        Save the raw voltage values of a waveform into a binary file
        (float32, little endian).

        A .txt header file with the same name records the number of samples and the
        time range.

        :param add_timestamp: True adds a timestamp to the file name automatically
        """
        if add_timestamp:
            filename = self._stamp(filename)
        t, v = self.get_waveform(channel, ascii_format=False)
        self._ensure_dir(filename)
        import struct
        payload = struct.pack(f"<{len(v)}f", *v)
        with open(filename, "wb") as f:
            f.write(payload)
        head_file = os.path.splitext(filename)[0] + ".txt"
        with open(head_file, "w") as f:
            f.write(f"Channel=CH{self._ch(channel)}\n")
            f.write(f"Samples={len(v)}\n")
            f.write(f"XStart={t[0]:.9e}\n")
            f.write(f"XStop={t[-1]:.9e}\n")
            f.write("Format=float32 little-endian\n")
        print(f"Raw waveform saved: {filename} / {head_file}")
        return filename

    def save_waveform_image(self, filename, fmt="png", add_timestamp=True,
                          instr_dir=None, filesave=True,localfile=True):
        """
        Save a waveform screenshot as an image file (combines both saving methods
        of the former save_screenshot).

        :param filename:      path of the waveform image (a .png extension is recommended)
        :param fmt:           screenshot image format (PNG/BMP/JPG/GIF/TIFF)
        :param add_timestamp: True adds a timestamp to the file name automatically
        :param filesave:      False reads the screenshot data directly (HCOPy:DATA?);
                              True saves a file on the instrument first and transfers
                              it back to the PC (HCOPy:DESTination MMEM)
        :param instr_dir:     name of the temporary folder created on the instrument
                              when filesave=True
        :param localfile:     True saves the file locally
        :return: path of the generated image
        """
        if add_timestamp:
            filename = self._stamp(filename)
        root, ext = os.path.splitext(filename)
        screenshot_path = f"{root}{ext}"
        if not filesave:
            return self.save_screenshot_direct(screenshot_path)
        else:
            return self.save_screenshot_via_file(screenshot_path,fmt=fmt.upper(),instr_dir=instr_dir,localfile=localfile)
 
#########################################################################################
#########################################################################################
#########################################################################################  
    def download_file(self, instr_path, pc_path,localfile=None):
        """
        Download a file from the scope to the PC (``MMEMory:DATA?``).

        For large files the PyVISA ``query_binary_values`` may be affected by
        timeouts and data block parsing; the timeout and the chunk size are
        increased first, and if this still fails the code falls back to
        ``write() + read_raw()`` and parses the SCPI binary block header
        ``#N<length><data>`` manually.

        :param instr_path: file path on the scope
        :param pc_path:    save path on the PC
        :param localfile:  whether the temporary file on the instrument is kept
        :return: PC file path
        """
        # self._ensure_dir(pc_path)
        # drives = self.get_drives()
        # base = (drives[0] if drives else "/home/storage/userData").rstrip("/")
        # instr_file = f"{base}/{instr_dir}/screenshot.{fmt.lower()}"
        # instr_file = self._stamp(instr_file)
        # self.opc_timeout = 600000  # 10 minutes
        # self.wait_opc(self.opc_timeout)
        self._ensure_dir(pc_path)
        print(f"File exists: {self.file_exists(instr_path)}")
        # time.sleep(5)
        self.read_file_from_instrument_to_pc(instr_path, pc_path, False)
        print(f"File downloaded to the PC: {pc_path}")
        return pc_path

    def save_waveform_csv_via_instrument(self, channel, pc_path=None, instr_path=None,
                                         scope="ALL", localfile=None):
        """
        Method one (combined): export the waveform as a CSV on the scope first and
        download it to the PC afterwards.

        The file name on the instrument is kept identical to the PC file name: when
        ``instr_path`` is a directory (e.g. 'temp_files'), the path on the instrument
        becomes '<instr_path>/<pc_path file name>'.

        :param channel:    channel number
        :param pc_path:    CSV save path on the PC
        :param instr_path: save folder or path on the instrument (may include a
                           sub folder, e.g. 'temp_files')
        :param scope:      export range: DISPlay / ALL / CURSor / GATE / MANual
        :param localfile:  whether the temporary file on the instrument is kept
                           (deleted when False)
        :return: (times, voltages) lists of time and voltage values
        """
        # keep the file name on the instrument identical to the PC file name
        base_name = os.path.basename(pc_path)
        if instr_path:
            instr_file = f"{instr_path.rstrip('/')}/{base_name}"
        else:
            instr_file = base_name
        ch = self._ch(channel)
        self.write(f"EXPort:WAVeform:SOURce C{ch}")
        self.write(f"EXPort:WAVeform:SCOPe {scope}")
        instr_full = f"/home/storage/userData/{instr_file}"
        self.write(f"EXPort:WAVeform:NAME '{instr_full}'")
        self.write("EXPort:WAVeform:SAVE")
        time.sleep(3)  # wait until the instrument has finished saving
        print(f"Waveform CSV saved on the scope: {instr_full}")
        self.download_file(instr_full, pc_path, localfile=localfile)
        # 1. parse the CSV file at pc_path to get the time and voltage values
        times = []
        voltages = []
        with open(pc_path, "r", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip the header (e.g. "Time(s),CH1(V)")
            for row in reader:
                if not row or row[0].strip() == "":
                    continue
                try:
                    t = float(row[0])
                    v = float(row[1])
                except (ValueError, IndexError):
                    continue
                times.append(t)
                voltages.append(v)

        # 2. delete the file instr_full on the scope when localfile is False (or None)
        if not localfile:
            try:
                self.write(f"MMEMory:DELete '{instr_full}'")
                print(f"Temporary file deleted from the scope: {instr_full}")
            except Exception as e:
                print(f"Warning: deleting the scope file failed (ignored): {e}")

        # 3. return the time and voltage values
        return times, voltages

       
#########################################################################################
#########################################################################################
#########################################################################################
    def save_waveform_csv_direct(self, channel,filename,ascii_format=True):
        """
        # Method two: read the waveform data directly from the instrument and save
        # the CSV on the PC (no file is stored on the instrument).

        ``CHANnel<n>:DATA:VALues?`` is used to read float32 binary data which is
        received with numpy (about 1/8 of the memory of a Python list) and written
        to the CSV in chunks, which suits large record lengths such as 10 Mpts.

        :param channel:  channel number
        :param filename: CSV save path on the PC
        :return: (t, v), t is the time axis (s) and v the voltage (V), both numpy arrays
        """
        ch = self._ch(channel)
        hdr = self.get_waveform_header(channel)
        self._ensure_dir(filename)
        self.opc_timeout = 5000 
        if ascii_format:
            # self.write("FORMat:DATA ASC")
            # raw = self.query(f"CHANnel{ch}:DATA:VALues?")
            # volts = [float(x) for x in raw.split(",") if x.strip() != ""]
            start = time.time()
            self.write_str("FORM:DATA ASC")
            self.data_chunk_size = 100000  # transfer in blocks of 100k bytes (default)
            print('Now start to transfer ASCII waveform data. Please wait for about 120 seconds...')
            data = self.query_bin_or_ascii_float_list(f"CHANnel{ch}:DATA:VALues?")
            print(f'ASCII waveform transfer elapsed time: {time.time() - start:.3f}sec')
            volts = data
        else:
            start = time.time()
            self.write_str("FORMat:DATA REAL,32;:FORMat:BORDer LSBFirst")
            self.bin_float_numbers_format = BinFloatFormat.Single_4bytes
            self.data_chunk_size = 100000  # transfer in blocks of 100k bytes (default)
            print('Now start to transfer binary waveform data. Please wait for about 20 seconds...')
            data = self.query_bin_or_ascii_float_list(f"CHANnel{ch}:DATA:VALues?")
            print(f'Binary waveform transfer elapsed time: {time.time() - start:.3f}sec\n')
            volts = data
       
            # self.write("FORMat:DATA REAL,32")
            # self.write("FORMat:BORDer LSBFirst")
            # import numpy as np
            # old_timeout = self.instrument.timeout
            # old_chunk = getattr(self.instrument, "chunk_size", None)
            # try:
            #     # a large record length takes a long time to transfer, so the timeout
            #     # and the read chunk size are increased temporarily
            #     self.instrument.timeout = max(int(old_timeout or 0), 500000)
            #     if old_chunk is not None:
            #         self.instrument.chunk_size = 100_000
            #     raw = self.instrument.query_binary_values(
            #         f"CHANnel{ch}:DATA:VALues?", datatype="f", is_big_endian=False, container=np.array)
            #     volts = np.asarray(raw, dtype=np.float32)
            # finally:
            #     self.instrument.timeout = old_timeout
            #     if old_chunk is not None:
            #         self.instrument.chunk_size = old_chunk
        import numpy as np
        xstart = float(self._header_value(hdr, "Xstart", "Start") or 0.0)
        xstop = float(self._header_value(hdr, "Xstop", "Stop") or 0.0)
        n = len(volts)
        # build the complete time axis (used for the file and as return value)
        if n > 1:
            t = np.linspace(xstart, xstop, n, dtype=np.float64)
        else:
            t = np.array([xstart], dtype=np.float64)

        with open(filename, "w", newline="") as f:
            f.write(f"Time(s),CH{ch}(V)\n")
            # write in chunks to avoid building one huge string in memory
            chunk = 100_000
            for i in range(0, n, chunk):
                end = i + chunk
                lines = [f"{tt:.9e},{vv:.6f}" for tt, vv in zip(t[i:end], volts[i:end])]
                f.write("\n".join(lines) + "\n")
        print(f"Waveform exported: {filename}  ({n} points)")
        return t, volts

    def get_drives(self):
        """
        Query the usable storage paths of the instrument ``MMEMory:DRIVes?``,
        returns a list of paths.

        The MXO4 normally returns the user data folder, e.g.
        ``['/home/storage/userData']``; several paths may be returned when a USB
        stick or another storage device is connected.
        """
        try:
            resp = self.query("MMEMory:DRIVes?")
            return [p.strip().strip("'\"") for p in resp.split(",") if p.strip()]
        except Exception:
            return []
#########################################################################################
#########################################################################################
#########################################################################################

    def save_screenshot_direct(self, pc_path):
        """
        Method one: read the screenshot data directly (``HCOPy:DATA?``), no file has
        to be saved on the instrument.

        The command returns the binary data of a PNG image which is written to
        ``pc_path``. The instrument file system is not involved, so a missing
        temporary path on the instrument cannot happen.

        :param pc_path: save path on the PC (a .png extension is recommended)
        :return: path of the generated image
        """
        self._ensure_dir(pc_path)
        # data = self.instrument.query_binary_values("HCOPy:DATA?", datatype="B")
        data = self.query_bin_block_with_opc("HCOPy:DATA?",timeout =6000) 
        with open(pc_path, "wb") as f:
            f.write(bytes(data))
        print(f"Screenshot saved (direct method): {pc_path}")
        return pc_path

    def  save_screenshot_via_file(self, pc_path, fmt="PNG", instr_dir=None, localfile = False):
        """
        Method two: create a temporary folder on the instrument, save the screenshot
        there and transfer it back to the PC.

        ``MMEMory:DRIVes?`` is used to find the user data folder of the instrument
        automatically; the folder ``instr_dir`` is created there, the screenshot is
        saved in it and transferred to the PC with ``MMEMory:DATA?``, and finally
        the temporary file on the instrument is deleted.

        :param pc_path:   save path on the PC
        :param fmt:       image format (PNG / JPG / BMP / GIF / TIFF)
        :param instr_dir: name of the temporary folder created on the instrument
        :return: path of the generated image
        """
        self._ensure_dir(pc_path)
        drives = self.get_drives()
        base = (drives[0] if drives else "/home/storage/userData").rstrip("/")
        instr_file = f"{base}/{instr_dir}/screenshot.{fmt.lower()}"
        instr_file = self._stamp(instr_file)
        # create the temporary folder (errors are ignored when it already exists)
        # try:
        #     self.write(f"MMEMory:MDIRectory '{base}/{instr_dir}'")
        # except Exception:
        #     pass
        # self.write(f"HCOPy:DEVice:LANGuage {fmt}")
        # self.write("HCOPy:DESTination1 MMEM")
        # self.write(f"MMEMory:NAME '{instr_file}'")
        # self.write("HCOPy:IMMediate")
        # self.wait_opc()
        # # data = self.instrument.query_binary_values(
        # #     f"MMEMory:DATA? '{instr_file}'", datatype="B")
        # self.query_bin_block_to_file(f"MMEMory:DATA? '{instr_file}'", pc_path)
        # with open(pc_path, "wb") as f:
        #     f.write(bytes(data))
        # clean up the temporary file on the instrument (a failure does not matter)
        self.write_str("HCOPy:DESTination1 MMEM")
        self.write_str("HCOPy:DEVice1:LANGuage PNG")
        self.write_str(f"MMEMory:NAME '{instr_file}'")
        self.write_str_with_opc("HCOPy:IMMediate1")
        time.sleep(3)  # wait until the instrument has created the file
        self.read_file_from_instrument_to_pc(instr_file, pc_path)
        print(f'Transferred screen shot to {pc_path}')
        try:
            if not localfile:
                self.write(f"MMEMory:DELete '{instr_file}'") # delete the temporary file on the instrument
                time.sleep(3)  # wait until the deletion has finished
                print(f"Temporary file deleted from the scope: {instr_file}")
        except Exception as e:
            print(f"Warning: deleting the scope file failed (ignored): {e}")
        print(f"Screenshot saved (file method): {pc_path}")
        return pc_path
#########################################################################################
#########################################################################################
#########################################################################################
    @staticmethod
    def _timestamp():
        """Return a timestamp string, e.g. 20260821_153000_123 (millisecond resolution)."""
        return time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"

    @staticmethod
    def _stamp(path, ts=None):
        """Append a timestamp to the file name (without extension) and return the new path."""
        ts = ts or MXO4._timestamp()
        root, ext = os.path.splitext(path)
        return f"{root}_{ts}{ext}"

    @staticmethod
    def _ensure_dir(path):
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.exists(d):
            os.makedirs(d)


# ==============================================================================
# Example
# ==============================================================================
if __name__ == "__main__":
    # change this to the IP / VISA resource string of your scope
    RESOURCE = "TCPIP::192.168.18.100::INSTR"
    # output folders for the waveforms and the CSV files
    PC_OUT_DIR = "waveforms"
    INSTR_FILE_OUT_DIR = "temp_files"
    INSTR_IMAGE_DIR = "temp_shots"
    # remember the start time of this script
    start_time = time.time()
    print(f"Script start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    mxo = MXO4(RESOURCE, timeout=10000)

    # mxo.download_file("/home/storage/userData/Waveforms/Waveform_2026-08-24_0_075310.csv", "edge_ch1_20260831_192344_996.csv")
    try:
        for i in range(100):
            mxo.clear_status()
            mxo.reset()
            mxo.set_display_update(True)
            mxo.opc_timeout = 60000 
            # ---- 1. channel and timebase configuration ----
            mxo.channel_state(1, True)
            mxo.channel_state(2, True)

            mxo.channel_coupling(1, ChannelCoupling.DC)
            mxo.channel_coupling(2, ChannelCoupling.DC)

            # mxo.channel_bandwidth(1, 20e6)
            # mxo.channel_bandwidth(2, 20e6)
            
            mxo.channel_range(1, 10.0)
            mxo.channel_range(2, 10.0)
    
            mxo.channel_scale(1, 1)
            mxo.channel_scale(2, 1)
            
            mxo.sample_rate_mode(SampleRateMode.MANUAL)   # manual configuration
            # mxo.sample_rate_mode(SampleRateMode.AUTO)   # automatic configuration
            print("Current sample rate mode:", mxo.get_sample_rate_mode())
            # helper example: estimate and configure the sample rate and 1 Mpts from the timebase
            print("Automatic sampling setup:", mxo.auto_sampling_for_timebase(2e-4, points="1M", wait=True))
            mxo.set_display_brightness(brightness=100)
            # print(mxo.get_display_brightness())
            mxo.set_signal_intensity(100)       # waveform intensity 100%
            # print(mxo.get_signal_intensity())  # read the current waveform intensity

            # ---- 2. edge trigger: save waveform -> export CSV ----
            mxo.channel_label(1, "RX")
            mxo.channel_label(2, "TX")
              
            mxo.configure_measurement(measure_index=1, source="C2", main="AMPlitude",
                                category=None, additional=None, enable=True)
            mxo.configure_measurement(measure_index=2, source="C2", main="FREquency",
                                        category=None, additional=None, enable=True)
            mxo.configure_measurement(measure_index=3, source="C2", main="RMS",
                                        category=None, additional=None, enable=True)        
            # mxo.trigger_mode(TriggerMode.NORMAL)
            # mxo.configure_edge_trigger(source=1, level=0.5, slope=EdgeSlope.POSITIVE)
            # mxo.single_and_wait(1000)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "edge.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=False)
            # mxo.save_waveform_csv(1, pc_path=os.path.join(PC_OUT_DIR, "edge_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)  

            # ---- 3. UART 解码 + 串行 总线触发: 保存波形 → 导出 CSV ---
            # UART RX on channel 1, TX on channel 2, baud rate 115200
            mxo.configure_uart_decode(bus_number=1, rx="C1", tx="C2", baud=115200)  
            mxo.trigger_mode(TriggerMode.NORMAL)
            mxo.configure_uart_trigger(bus_number=1, source="SBUS1")
            mxo.single_and_wait(10000)
            time.sleep(3)  # wait until the instrument finished decoding
            mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart.png"),fmt="png",add_timestamp=True,instr_dir= INSTR_IMAGE_DIR,filesave=False,localfile=True)
            mxo.save_waveform_csv(2, os.path.join(PC_OUT_DIR, "uart.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)
            

        #     # ---- 3b. UART waveform ZOOM (scope side only) + rise time/amplitude measurement + cursor ----
        #     # 1) scope side ZOOM: magnify to one UART frame (estimated from the
        #     #    protocol parameters, no waveform readback needed)
        #     uart_zoom = mxo.zoom_uart_display(baud=115200, data_bits=8,
        #                                     parity=UARTParity.NONE,
        #                                     stop_bits=STOPBit.ONE_BIT,
        #                                     margin_bits=2.0, reacquire=True)
        #     frame_time = uart_zoom["frame_time"]

        #     # 2) automatic measurement: CH1(RX) rise time + amplitude (+ low/high level for the horizontal cursor)
        #     mxo.configure_rise_time_measurement(measure_index=4, source="C2", enable=True)
        #     mxo.configure_amplitude_measurement(measure_index=5, source="C2", enable=True)
        #     mxo.configure_measurement(measure_index=6, source="C2", main="LOW", enable=True)  
        #     mxo.configure_measurement(measure_index=7, source="C2", main="HIGH", enable=True)
        #     mxo.wait_opc(5000)          # wait for a measurement refresh to avoid reading old values
        #     rise_time = mxo.get_measurement_result(4)
        #     amplitude = mxo.get_measurement_result(5)
        #     print(f"CH2 rise time (RTIMe):   {rise_time} s")
        #     print(f"CH2 amplitude (AMPLitude):     {amplitude} V")
        #     try:
        #         low_level = float(mxo.get_measurement_result(6))
        #         high_level = float(mxo.get_measurement_result(7))
        #     except (ValueError, TypeError):
        #         low_level, high_level = 0.0, 5.0

        #     # 3) cursor measurement: vertical X1/X2 for one frame time, horizontal Y1/Y2 for the amplitude (display optional)
        #     mxo.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
        #                         x1=0.0, x2=frame_time, y1=low_level, y2=high_level,
        #                         show=True, show_values=True, tracking=False)
        #     mxo.wait_opc(2000)
        #     try:
        #         dx = mxo.get_cursor_delta_x(1)
        #         dy = mxo.get_cursor_delta_y(1)
        #         print(f"cursor delta X (one frame time): {dx:.6e} s")
        #         print(f"cursor delta Y (amplitude):     {dy:.4f} V")
        #     except Exception as exc:
        #         print(f"reading the cursor result failed (ignored): {exc}")
            
        #     # 4) screenshot (magnified waveform + measurements + cursors)
        #     mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart_zoom_meas_ch1.png"),
        #                             fmt="png", add_timestamp=True,
        #                             instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
            
        #     # 5) hide the SBUS1 decode result table so the automatic measurement result table
        #     #    (RMS/FREQuency/AMPLitude/RTIMe...) becomes visible, then take another screenshot
        #     mxo.bus_result_table(bus_number=1, on=False)   # switch the SBUS1 decode table off
        #     mxo.wait_opc(50000)
        #     time.sleep(3)
        #     mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart_meas_result_ch1.png"),
        #                             fmt="png", add_timestamp=True,
        #                             instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
        #     mxo.bus_result_table(bus_number=1, on=True)    # restore the decode table display

            # ---- 4. I2C decoding + serial bus trigger: save waveform -> export CSV ----
            # I2C SDA on channel 1, SCL on channel 2
            # mxo.channel_label(1, "SDA")
            # mxo.channel_label(2, "SCL")
            # mxo.configure_i2c_decode(bus_number=2, scl="C2", sda="C1")
            # mxo.trigger_mode(TriggerMode.NORMAL)
            # mxo.configure_i2c_trigger(bus_number=2, condition=None)
            # mxo.single_and_wait(10000)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            # mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "i2c_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=True)

            # # ---- 4b. I2C waveform ZOOM (scope side only) + rise time/amplitude measurement + cursor ----
            # # 1) scope side ZOOM: magnify to one I2C frame (estimated from the
            # #    protocol parameters, no waveform readback needed)
            # i2c_zoom = mxo.zoom_i2c_display(scl_freq=150000, frame_bits=9,
            #                                 margin_bits=2.0, reacquire=True)
            # i2c_frame_time = i2c_zoom["frame_time"]

            # # 2) automatic measurement: CH1(SDA)/CH2(SCL) rise time + amplitude (+ low/high level for the cursor)
            # mxo.configure_rise_time_measurement(measure_index=4, source="C1", enable=True)
            # mxo.configure_amplitude_measurement(measure_index=5, source="C1", enable=True)
            # mxo.configure_measurement(measure_index=6, source="C1", main="LOW", enable=True)
            # mxo.configure_measurement(measure_index=7, source="C1", main="HIGH", enable=True)
            # mxo.configure_rise_time_measurement(measure_index=8, source="C2", enable=True)
            # mxo.configure_amplitude_measurement(measure_index=9, source="C2", enable=True)
            # mxo.configure_measurement(measure_index=10, source="C2", main="LOW", enable=True)
            # mxo.configure_measurement(measure_index=11, source="C2", main="HIGH", enable=True)
            # mxo.wait_opc(5000)          # wait for a measurement refresh to avoid reading old values
            # rise_c1 = mxo.get_measurement_result(4)
            # amp_c1 = mxo.get_measurement_result(5)
            # rise_c2 = mxo.get_measurement_result(8)
            # amp_c2 = mxo.get_measurement_result(9)
            # print(f"CH1(SDA) rise time (RTIMe): {rise_c1} s,  amplitude (AMPLitude): {amp_c1} V")
            # print(f"CH2(SCL) rise time (RTIMe): {rise_c2} s,  amplitude (AMPLitude): {amp_c2} V")
            # try:
            #     low_c1 = float(mxo.get_measurement_result(6))
            #     high_c1 = float(mxo.get_measurement_result(7))
            # except (ValueError, TypeError):
            #     low_c1, high_c1 = 0.0, 5.0

            # # 3) cursor measurement: vertical X1/X2 for one frame time, horizontal Y1/Y2 for the amplitude (display optional)
            # mxo.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
            #                      x1=0.0, x2=i2c_frame_time, y1=low_c1, y2=high_c1,
            #                      show=True, show_values=True, tracking=False)
            # mxo.wait_opc(5000)
            # try:
            #     dx = mxo.get_cursor_delta_x(1)
            #     dy = mxo.get_cursor_delta_y(1)
            #     print(f"cursor delta X (one frame time): {dx:.6e} s")
            #     print(f"cursor delta Y (amplitude):     {dy:.4f} V")
            # except Exception as exc:
            #     print(f"reading the cursor result failed (ignored): {exc}")

            # # 4) screenshot (magnified waveform + measurements + cursors)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c_zoom_meas.png"),
            #                         fmt="png", add_timestamp=True,
            #                         instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)

            # # 5) hide the SBUS2 decode result table so the automatic measurement result table
            # #    (RMS/FREQuency/AMPLitude/RTIMe...) becomes visible, then take another screenshot
            # mxo.bus_result_table(bus_number=2, on=False)   # switch the SBUS2 decode table off
            # mxo.wait_opc(50000)
            # time.sleep(3)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c_meas_result.png"),
            #                         fmt="png", add_timestamp=True,
            #                         instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
            # mxo.bus_result_table(bus_number=2, on=True)    # restore the decode table display
          
            
        
            # ---- 5. SPI decoding + serial bus trigger: save waveform -> export CSV ----
            # SCLK=C1, MOSI=C2, MISO=C3, SS=C4
            # mxo.configure_spi_decode(bus_number=3, sclk="C1", mosi="C2", miso="C3", ss="C4")
            # mxo.trigger_mode(TriggerMode.NORMAL)
            # mxo.configure_spi_trigger(bus_number=3, condition="MOSI")
            # mxo.single_and_wait(10000)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "spi_ch1.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            # mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "spi_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=True)
            # print(f"SPI decode result:\n{mxo.get_decoded_data(3)}")

            # ---- 6. QSPI decoding: save waveform -> export CSV ----
            # SCLK=C1, CS=C2, IO0=C3, IO1=C4, IO2=C5, IO3=C6

            mxo.configure_logic_decode(pbus=1, bits=[(0,"SCLK"), (1,"CS"), (2,"IO0"), (3,"IO1"), (4,"IO2"), (5,"IO3")], 
                           threshold=1.65, technology="V165")
            mxo.configure_qspi_decode(
                bus_number=4, sclk="d0", cs="d1",
                io0="d2", io1="d3", io2="d4", io3="d5",
                sclk_polarity="RISing", cs_polarity="ACTLow",  
                instruction="QUAD",
                opcodes=[{"code": 0x6B, "adbytes": 3, "adlanes": "QUAD",
                          "dtlanes": "QUAD", "dmcycles": 8, "ddr": False,
                          "data": True}])
            mxo.configure_qspi_trigger(bus_number=4, source="SBUS4",
                           clock_source="D0",    # trigger clock: analog C1 or digital D0
                           frame_enable=True, invert=False)
            mxo.single_and_wait(10000)
            mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "qspi.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "qspi_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=True,localfile=False)
            print(f"QSPI decode result:\n{mxo.get_decoded_data(4)}")

            # # ---- 6. screenshot saving ----
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "screen.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
    finally:
        mxo.close()

    # remember the end time of this script and print the elapsed time  
    end_time = time.time()
    print(f"Script end time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed time: {end_time - start_time:.3f} s")
