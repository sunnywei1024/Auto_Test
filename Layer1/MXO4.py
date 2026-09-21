# -*- coding: utf-8 -*-
"""
Created on Sep 11, 2026
Chicago
@author: lijiangwei

R&S MXO 4 Series Driver (Base RsInstrument)
==============================================

This《R&S MXO 4 系列示波器 User Manual》中的 SCPI 远程控制命令,
封装了继承自 :class:`RsInstrument` 的示波器驱动类 :class:`MXO4`, 主要功能包括:

1. 仪器连接 / 复位 / 身份识别 / 错误查询
2. 通道 (垂直) 与水平 (时基) 配置
3. 触发系统配置: 边沿 / 脉宽 / 毛刺 / 矮脉冲 / 窗口 / 超时 / 码型 / 串行总线触发
4. 协议分析 (串行总线解码): I2C / SPI / UART 的配置与解码结果读取
5. 波形采集: 单次 / 连续 / 停止, 读取波形数据 (ASCII / 二进制)
6. 波形保存: 导出 CSV 文件、保存原始数据、截屏保存
7. 眼图分析 (Eye Diagram): 眼图配置与眼高/眼宽/眼幅度测量
8. 抖动分析 (Jitter): 高级抖动分析 (快速开始 / 手动分量) 与结果读取

依赖安装::

    pip install RsInstrument

还需要在 PC 上安装 VISA 后端, 例如 R&S VISA 或 NI-VISA。
(仅使用 TCPIP socket 时也可用 ``SelectVisa='socket'`` 选项, 无需任何 VISA。)

连接方式 (VISA 资源字符串示例)::

    TCPIP::192.168.1.100::INSTR
    TCPIP::192.168.1.100::hislip0::INSTR
    USB::0x0AAD::0x0A0C::xxxxxx::INSTR

注意:
    * 串行总线解码 (协议分析) 与串行总线触发需要仪器安装相应的选件许可
      (例如 I2C/SPI: K510, UART/RS-232/422/485: K520 等)。
    * 不同固件版本个别命令参数可能略有差异, 已尽量按手册标准语法编写。
"""

import csv
import os
import time
from enum import Enum

from RsInstrument import *  # noqa: F401,F403  提供 RsInstrument 基类与 BinFloatFormat 等枚举




# ==============================================================================
# 枚举定义 (与 MXO4 SCPI 参数一一对应)
# ==============================================================================

class TriggerType(Enum):
    """触发类型 ``TRIGger:EVENt1:TYPe``"""
    EDGE = "EDGE"                # 边沿触发
    GLITCH = "GLITch"            # 毛刺触发
    WIDTH = "WIDTh"              # 脉宽触发
    RUNT = "RUNT"                # 矮脉冲触发
    WINDOW = "WINdow"            # 窗口触发
    TIMEOUT = "TIMeout"          # 超时触发
    INTERVAL = "INTerval"        # 间隔触发
    SLEW_RATE = "SLEWrate"       # 斜率触发
    DATA_TO_CLOCK = "DATatoclock"  # 数据到时钟 (建立/保持时间) 触发
    STATE = "STATe"              # 状态触发
    PATTERN = "PATtern"          # 码型触发
    SERIAL_BUS = "SERialbus"     # 串行总线触发 (协议触发)


class EdgeSlope(Enum):
    """边沿方向 ``TRIGger:EVENt1:EDGE:SLOPe``"""
    POSITIVE = "POSitive"        # 上升沿
    NEGATIVE = "NEGative"        # 下降沿
    EITHER = "EITHer"            # 任意沿


class TriggerMode(Enum):
    """触发模式 ``TRIGger:MODE``"""
    AUTO = "AUTO"                # 自动 (无触发事件时自由运行)
    NORMAL = "NORMal"            # 正常 (无触发事件时等待)
    FREE_RUN = "FREErun"         # 自由运行


class ChannelCoupling(Enum):
    """通道耦合 ``CHANnel<n>:COUPling``"""
    DC = "DCLimit"               # 直流 (限幅)
    AC = "ACLimit"               # 交流 (限幅)
    GND = "GND"                  # 接地


class AcquisitionMode(Enum):
    """采集模式 ``ACQuire:MODe``"""
    RTIME = "RTIMe"              # 实时
    PEAK = "PEAK"                # 峰值检测
    AVERAGE = "AVERage"          # 平均
    HRES = "HRESolution"         # 高分辨率
    ERES = "ERESolution"         # 增强分辨率


class SampleRateMode(Enum):
    """采样率模式 / SR 模式 ``ACQuire:SRATe:MODE``。"""
    AUTO = "AUTO"
    MANUAL = "MANual"
    NORMAL = "NORMal"
    HIGH_RES = "HRESolution"
    PEAK = "PEAK"


class BusType(Enum):
    """串行总线 (协议) 类型 ``BUS<n>:TYPE``"""
    I2C = "I2C"                  # I2C (Inter-IC)
    SPI = "SPI"                  # SPI
    QSPI = "QSPI"                # QSPI (Quad SPI)
    UART = "UART"                # UART / RS-232 / RS-422 / RS-485
    CAN = "CAN"                  # CAN
    LIN = "LIN"                  # LIN
    FLEXRAY = "FLEXray"          # FlexRay
    I2S = "I2S"                  # I2S 音频
    MIL1553 = "MIL"              # MIL-STD-1553
    ARINC429 = "ARINc"           # ARINC 429
    SENT = "SENT"                # SENT
    SPMI = "SPMI"                # MIPI SPMI


class I2CTriggerCondition(Enum):
    """I2C 串行总线触发条件"""
    START = "STARt"
    STOP = "STOP"
    RESTART = "RESTart"
    NO_ACK = "NOAck"
    ADDRESS = "ADDRess"
    DATA = "DATA"
    PATTERN = "PATTern"


class UARTTriggerCondition(Enum):
    """UART 串行总线触发条件"""
    START = "STBT"
    STOP = "STOP"
    DATA = "DATA"
    PARITY = "PARity"
    PATTERN = "PATTern"
    FRAME = "FRAMe"


class UARTParity(Enum):
    """UART 校验位"""
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
    """UART 位序"""
    MSB_FIRST = "MSBF"
    LSB_FIRST = "LSBF"


class SPIPolarity(Enum):
    """SPI 时钟极性"""
    IDLE_LOW = "IDLELOW"     # 空闲低电平
    IDLE_HIGH = "IDLEHIGH"   # 空闲高电平


class STOPBit(Enum):
    """SPI 时钟极性"""
    ONE_BIT = "B1"     # 1 个停止位
    ONE_P_FIVE_BITS = "B15"  # 1.5 个停止位
    TWO_BITS = "B2"    # 2 个停止位


class WaveformFormat(Enum):
    """波形数据格式 ``FORMat:DATA``"""
    ASCII = "ASC"
    BINARY_FLOAT32 = "REAL,32"
    BINARY_FLOAT64 = "REAL,64"
    BINARY_INT16 = "INT,16"


class CursorFunction(Enum):
    """光标类型 ``CURSor<n>:FUNCtion``"""
    VERTICAL = "VERTical"      # 垂直光标 X1/X2, 测时间 (ΔX)
    HORIZONTAL = "HORizontal"  # 水平光标 Y1/Y2, 测幅度 (ΔY)
    PAIRED = "PAIRed"          # 垂直 + 水平同时显示


class EyeMeasurement(Enum):
    """眼图测量项 (MEASurement 的 MAIN / ADDitional)"""
    EYE_HEIGHT = "EHEight"          # 眼高 (Eye Height)
    EYE_WIDTH = "EWIDth"            # 眼宽 (Eye Width)
    EYE_AMPLITUDE = "EAMPlitude"    # 眼幅度 (Eye Amplitude)


class JitterComponent(Enum):
    """高级抖动分析分量 (对应 COMPonents 编号)"""
    TJ_AT_BER = 4     # 指定误码率下的总抖动 Total Jitter @ BER
    RJ = 5            # 随机抖动 Random Jitter
    TJ = 7            # 总抖动 Total Jitter
    DJ = 8            # 确定性抖动 Deterministic Jitter
    DDJ = 9           # 数据相关抖动 Data-Dependent Jitter
    DCD = 10          # 占空比失真 Duty Cycle Distortion
    PJ = 11           # 周期性抖动 Periodic Jitter
    ISI = 12          # 符号间干扰 Inter-Symbol Interference


# ==============================================================================
# 驱动类
# ==============================================================================

class MXO4(RsInstrument):
    """R&S MXO 4 系列示波器驱动类 (继承自 RsInstrument)。"""

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------
    def __init__(self, resource, timeout=60000, reset=True, idn=True, options="SelectVisa='rs'"):
        """
        初始化仪器连接 (RsInstrument 在构造时即建立连接)。
  
        :param resource: VISA 资源字符串, 例如 ``'TCPIP::192.168.1.100::INSTR'``
        :param timeout:  VISA 读写超时, 单位 ms (采集大数据时建议调大)
        :param reset:    初始化时是否执行 ``*RST``
        :param idn:      初始化时是否执行 ``*IDN?`` 校验仪器
        :param options:  RsInstrument 初始化选项, 例如 ``"SelectVisa='ni'"``
                        或 ``"SelectVisa='socket'"``; 不指定时自动探测已安装的 VISA 后端
        """
        super().__init__(resource, id_query=idn, reset=reset, options=options)
        # 兼容旧接口的属性
        self.resource = resource
        self.timeout = timeout
        self.visa_timeout = timeout
        if self.idn_string:
            print(f"已连接: {self.idn_string}")

    def connect(self):
        """RsInstrument 在构造时已建立连接, 此方法仅为兼容旧接口保留。"""
        return self

    def close(self):
        """关闭连接 (会话已失效时忽略异常, 不使程序崩溃)。"""
        try:
            super().close()
        except Exception as e:
            print(f"警告: 关闭仪器会话失败 (忽略): {e}")

    # ------------------------------------------------------------------
    # 基础读写与通用命令
    # ------------------------------------------------------------------
    # write / query / write_str / query_str / query_bin_block 等底层方法
    # 均继承自 RsInstrument, 无需在此重复实现。

    def write_list(self, cmds):
        """批量发送多条命令 (list)。"""
        for c in cmds:
            self.write(c)

    def reset(self):
        """复位到预设状态 ``*RST`` 并等待完成。"""
        super().reset()
        self.wait_opc()

    def get_error(self):
        """读取一条错误 ``SYSTem:ERRor?``, 返回字符串。"""
        return self.query("SYSTem:ERRor?")

    def opc_polling(self):
        """轮询操作状态寄存器, 等待采集停止 (bit4 为 0)。"""
        while True:
            cond = int(self.query("STATus:OPERation:CONDition?"))
            # 采集运行位 (具体 bit 请对照手册 "Operation Status Register" 章节)
            if cond & 0x10 == 0:   # bit4 为 0 表示已不在采集
                break
            time.sleep(0.05)

    def wait_opc(self, timeout=None):
        """发送 ``*OPC?`` 等待之前所有命令执行完毕。"""
        if timeout:
            self.query_opc(timeout)
        else:
            self.query_opc()

    def set_display_update(self, on=True):
        """远程控制时是否刷新屏幕显示 ``SYSTem:DISPlay:UPDate``。"""
        self.write(f"SYSTem:DISPlay:UPDate {'ON' if on else 'OFF'}")

    def set_display_brightness(self, brightness=100):
        """
        设置屏幕亮度 ``DISPlay:BACKlight:BRIGtness``。  

        :param brightness: 触摸屏背光亮度, 范围 5~100 (超出范围会被钳位)
        """
        val = int(brightness)
        val = max(5, min(100, val))
        self.write(f"DISPlay:BACKlight:BRIGtness {val}")

    def get_display_brightness(self):
        """查询屏幕亮度 ``DISPlay:BACKlight:BRIGtness?``, 返回 int (5~100)。"""
        return int(self.query("DISPlay:BACKlight:BRIGtness?"))

    def set_display_dimming(self, timeout="OFF"):
        """
        设置屏幕自动变暗 (省电) 时间 ``DISPlay:BACKlight:DIMMing``。

        :param timeout: 无操作多久后降低屏幕亮度,
                        OFF / T1Minute / T2Minutes / T3Minutes / T5Minutes /
                        T10Minutes / T15Minutes / T20Minutes / T25Minutes /
                        T30Minutes / T45Minutes / T1Hour / T2Hours / T3Hours / T4Hours
        """
        self.write(f"DISPlay:BACKlight:DIMMing {timeout}")

    def set_signal_intensity(self, intensity=50):
        """
        设置信号 (波形) 亮度 ``DISPlay:INTensity``。

        该值决定波形迹线在屏幕上的显示强弱, 与屏幕背光亮度
        (``set_display_brightness``) 是两套独立设置。

        :param intensity: 波形亮度百分比, 范围 0~100 (默认 50, 0 为不可见)
        """
        val = float(intensity)
        val = max(0.0, min(100.0, val))
        self.write(f"DISPlay:INTensity {val}")

    def get_signal_intensity(self):
        """查询信号 (波形) 亮度 ``DISPlay:INTensity?``, 返回 float (0~100)。"""
        return float(self.query("DISPlay:INTensity?"))

    def autoset(self):
        """自动设置 ``AUTOSet EXECUTE`` (等效 ``AUToscale``)。"""
        self.write("AUTOSet EXECUTE")
        self.wait_opc()

    # ------------------------------------------------------------------
    # 通道 (垂直) 配置
    # ------------------------------------------------------------------
    @staticmethod
    def _ch(channel):
        """通道号归一化, 支持 int(1~4) 或 str('1'~'4' / 'C1')。"""
        if isinstance(channel, int):
            return str(channel)
        s = str(channel).upper().replace("CHAN", "").replace("CH", "").replace("C", "")
        return s

    @staticmethod
    def _src(source):
        """触发/解码信源归一化: 支持 int(1~4)->'C1', 或直接传 'C1'/'SBUS1'/'EXT'/'LINE'。"""
        if isinstance(source, int):
            return f"C{source}"
        s = str(source).upper()
        return s

    def channel_state(self, channel, on=True):
        """开关通道 ``CHANnel<n>:STATe ON|OFF``。"""
        self.write(f"CHANnel{self._ch(channel)}:STATe {'ON' if on else 'OFF'}")

    def channel_coupling(self, channel, coupling=ChannelCoupling.DC):
        """通道耦合 ``CHANnel<n>:COUPling``。"""
        val = coupling.value if isinstance(coupling, ChannelCoupling) else coupling
        self.write(f"CHANnel{self._ch(channel)}:COUPling {val}")

    def channel_range(self, channel, volts):
        """垂直满量程 (V) ``CHANnel<n>:RANGe <NR3>``, 例如 2.0 表示 ±1V 满屏。"""
        self.write(f"CHANnel{self._ch(channel)}:RANGe {volts}")

    def channel_scale(self, channel, volts_per_div):
        """垂直灵敏度 (V/div) ``CHANnel<n>:SCALe <NR3>``。"""
        self.write(f"CHANnel{self._ch(channel)}:SCALe {volts_per_div}")

    def channel_offset(self, channel, volts):
        """垂直偏置 (V) ``CHANnel<n>:OFFSet <NR3>``。"""
        self.write(f"CHANnel{self._ch(channel)}:OFFSet {volts}")

    def channel_position(self, channel, divisions):
        """垂直位置 (div) ``CHANnel<n>:POSition <NR3>``。"""
        self.write(f"CHANnel{self._ch(channel)}:POSition {divisions}")

    def channel_impedance(self, channel, ohms):
        """输入阻抗 ``CHANnel<n>:IMPedance <NR3>`` (1e6 或 50)。"""
        self.write(f"CHANnel{self._ch(channel)}:IMPedance {ohms}")

    def channel_label(self, channel, label):
        """
        设置通道标签 ``DISPlay:SIGNal:LABel <signal>,<label>``。

        MXO4 的通道标签命令不在 ``CHANnel`` 子树下 (MXO4 的 ``CHANnel`` 没有
        LABel 命令), 而是通过 ``DISPlay:SIGNal:LABel`` 设置,
        例如 ``DISPlay:SIGNal:LABel C1,'VBUS'``。

        :param channel: 通道号 (int 1~4, 或 '1'~'4' / 'C1' 等)
        :param label:   标签文本 (请勿包含单引号)
        """
        signal = "C" + self._ch(channel)
        self.write(f"DISPlay:SIGNal:LABel {signal},'{label}'")

    def get_channel_label(self, channel):
        """
        查询通道标签 ``DISPlay:SIGNal:LABel?``, 返回标签字符串。

        :param channel: 通道号 (该查询本身不带信源参数, 返回当前信源的标签)
        """
        return self.query("DISPlay:SIGNal:LABel?")

    def digital_channel_label(self, digital, label):
        """
        设置数字通道 (MSO 逻辑通道) 标签 ``DIGital<n>:LABel '<label>'``。

        数字通道标签与模拟通道标签是两套独立命令:
          * 模拟通道: ``DISPlay:SIGNal:LABel C1,'LABEL'``  (见 ``channel_label``)
          * 数字通道: ``DIGital<n>:LABel 'LABEL'``          (n 对应 D0~D15)

        :param digital: 数字通道号 (int 0~15, 对应 D0~D15)
        :param label:   标签文本 (请勿包含单引号)
        """
        self.write(f"DIGital{int(digital)}:LABel '{label}'")

    def get_digital_channel_label(self, digital):
        """查询数字通道标签 ``DIGital<n>:LABel?``, 返回标签字符串。"""
        return self.query(f"DIGital{int(digital)}:LABel?")

    def channel_bandwidth(self, channel, bandwidth="FULL"):
        """
        设置通道带宽限制 ``CHANnel<n>:BANDwidth``。

        :param channel:   通道号
        :param bandwidth: 带宽限制值:
                          * 数值 (Hz), 例如 20e6 / 50e6 / 100e6 / 200e6 / 350e6 / 500e6
                          * 字符串 'FULL' (满带宽, 关闭带宽限制)
        """
        val = bandwidth.upper() if isinstance(bandwidth, str) else bandwidth
        self.write(f"CHANnel{self._ch(channel)}:BANDwidth {val}")

    def get_channel_bandwidth(self, channel):
        """查询通道带宽限制 ``CHANnel<n>:BANDwidth?``, 返回 Hz 数值或 'FULL'。"""
        return self.query(f"CHANnel{self._ch(channel)}:BANDwidth?")

    # ------------------------------------------------------------------
    # 水平 (时基) 配置
    # ------------------------------------------------------------------
    def timebase_scale(self, sec_per_div):
        """时基 (s/div) ``TIMebase:SCALe <NR3>``。"""
        self.write(f"TIMebase:SCALe {sec_per_div}")

    def timebase_range(self, seconds):
        """整屏时间 (s) ``TIMebase:RANGe <NR3>``。"""
        self.write(f"TIMebase:RANGe {seconds}")

    def timebase_position(self, percent):
        """
        设置水平位置 (参考点位置) ``TIMebase:REFerence <NR3>``, 单位为屏幕百分比。

        MXO4 的水平位置命令是 ``TIMebase:REFerence`` (0~100%),
        而不是旧型号的 ``HORizontal:POSition``。

        :param percent: 参考点位置, 0~100 (%)
        """
        self.write(f"TIMebase:REFerence {percent}")

    def get_timebase_position(self):
        """查询水平位置 (参考点位置) ``TIMebase:REFerence?``, 返回百分比。"""
        return self.query("TIMebase:REFerence?")

    def timebase_offset(self, seconds):
        """
        设置触发偏置 (trigger offset) ``TIMebase:HORizontal:POSition <NR3>``, 单位为秒。

        该值表示参考点到触发点 (波形零点) 之间的时间距离。

        :param seconds: 触发偏置 (s)
        """
        self.write(f"TIMebase:HORizontal:POSition {seconds}")

    def get_timebase_offset(self):
        """查询触发偏置 ``TIMebase:HORizontal:POSition?``, 返回秒数。"""
        return self.query("TIMebase:HORizontal:POSition?")

    # ------------------------------------------------------------------
    # 采集控制
    # ------------------------------------------------------------------

    def max_acquisition_points(self):
        """
            尝试查询仪器支持的最大采集点数（多种常见 SCPI 变体）。
            返回 int (最大点数) 或 None（查询失败）。
        """
        candidates = [
            "ACQuire:POINts:MAX?",   # 常见形式
            "ACQ:POINts:MAX?",       # 可能的缩写
            "TIMebase:RECordlength:MAX?",  # 备用尝试（少见）
            "ACQuire:POINts? MAX",   # 某些仪器的变体（不常见）
        ]
        for cmd in candidates:
            try:
                resp = self.query(cmd)  
                if resp is None:
                    continue
                # 有的返回可能含文本，先尝试数值解析
                val = float(resp.strip().split()[0])
                return int(val)
            except Exception:
                # 捕获任何查询/解析错误，尝试下一个命令
                continue
        # 如果都失败，返回 None 表示无法确定
        return None
    
    def acquisition_mode(self, mode=AcquisitionMode.RTIME):
        """采集模式 ``ACQuire:MODe``。"""
        val = mode.value if isinstance(mode, AcquisitionMode) else mode
        self.write(f"ACQuire:MODe {val}")

    def acquisition_count(self, count):
        """平均次数 ``ACQuire:COUNt <NR1>`` (仅平均模式有效)。"""
        self.write(f"ACQuire:COUNt {int(count)}")

    def acquisition_points(self):
        """查询当前采集点数 ``ACQuire:POINts?``。"""
        return int(float(self.query("ACQuire:POINts?")))

    @staticmethod
    def _scpi_number(value):
        """将数值/字符串转换为 SCPI 兼容的科学计数法表示, 例如 1E9 / 1.23E+09。"""
        if isinstance(value, str):
            s = value.strip()
            if s.upper().endswith('E'):
                s = s + '0'
            try:
                num = float(s)
            except ValueError as exc:
                raise ValueError(f"无法解析为数值: {value}") from exc
        else:
            num = float(value)

        # 生成保留 12 位有效数字的科学计数法，确保 SCPI 兼容
        text = f"{num:.12E}"
        text = text.replace("E+0", "E+")
        text = text.replace("E-0", "E-")
        text = text.replace("E+", "E+")
        text = text.replace("E-", "E-")
        return text

    def sample_rate(self, rate):
        """
        设置采样率 ``ACQuire:SRATe <NR3>``。

        以科学计数法发送，允许接受普通数字或字符串表示 (如 1e9 / '1E9')。

        :param rate: 采样率 (samples/s), 例如 1e9 / 2.5e9 / 5e9 等
        """
        val = self._scpi_number(rate)
        self.write(f"ACQuire:SRATe {val}")

    def get_sample_rate(self):
        """查询当前采样率 ``ACQuire:SRATe?``，返回 float。"""
        return float(self.query("ACQuire:SRATe?"))

    def sample_rate_mode(self, mode=SampleRateMode.AUTO):
        """
        设置 SR 模式 / 采样率模式 ``ACQuire:SRATe:MODE``。

        常见模式通常为:
          - AUTO     : 自动采样率模式
          - MANual   : 手动采样率模式
          - NORMAL   : 普通模式
          - HRESolution: 高分辨率模式（如支持）
        """
        val = mode.value if isinstance(mode, SampleRateMode) else str(mode).upper()
        self.write(f"ACQuire:SRATe:MODE {val}")

    def get_sample_rate_mode(self):
        """查询当前 SR 模式 ``ACQuire:SRATe:MODE?``。"""
        return self.query("ACQuire:SRATe:MODE?")

    def configure_sampling(self, timebase_seconds_per_div=None, sample_rate=None,
                          points=None, wait=True):
        """
        一键配置采样率/记录深度/时基的辅助函数。

        规则：
        1. 若给定 ``timebase_seconds_per_div``，先执行 ``TIMebase:SCALe``。
        2. 若给定 ``points`` 与 ``timebase_seconds_per_div``，则按
           ``sample_rate = points / timebase_seconds_per_div / 10``
           估算采样率；仅在未显式给出 ``sample_rate`` 时才自动填充。
        3. 若给定 ``sample_rate``，执行 ``ACQuire:SRATe``。
        4. 若给定 ``points``，执行 ``ACQuire:POINts``。
        5. 最后可选 ``wait_opc`` 等待完成。

        :param timebase_seconds_per_div: 时基 s/div, 例如 5e-6
        :param sample_rate:              采样率 S/s, 如 1e9
        :param points:                   记录深度点数, 如 1_000_000 或 '1M'
        :param wait:                     是否等待命令完成
        :return:                         tuple (timebase, sample_rate, points)
        """
        # 允许传入字符串 '1M' / '1e6' / '1000000'
        if points is not None:
            if isinstance(points, str):
                s = points.strip().upper()
                if s.endswith('M') and s[:-1].replace('.', '', 1).isdigit():
                    points_val = int(float(s[:-1]) * 1_000_000)
                else:
                    try:
                        points_val = int(float(s))
                    except Exception as exc:
                        raise ValueError(f"无法解析采集点数: {points}") from exc
            else:
                points_val = int(points)
        else:
            points_val = None

        if timebase_seconds_per_div is not None and points_val is not None and sample_rate is None:
            # 经验估算公式：sample_rate = points / timebase_seconds_per_div / 10
            # 其中 10 为屏幕横向分辨率系数（典型近似）
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
        """将记录深度设置为 1 Mpts。"""
        return self.ensure_acquisition_points("1M", wait=wait)

    def auto_sampling_for_timebase(self, timebase_s_per_div, points="1M", wait=True):
        """
        根据时基自动估算并配置采样率与深度。

        使用公式：sample_rate = points / timebase_s_per_div / 10
        默认深度为 1 Mpts。
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
        设置采集点数 (record length / memory depth)。

        发送命令 ``ACQuire:POINts <n>`` 来设置当前记录长度。

        :param points: 要设置的点数 (int 可直接传入 1_000_000 或 '1M' / '1e6'等可被 int() 解析的值)
        :param wait:   是否在设置后等待操作完成 (使用 *OPC?)，默认 True
        :return:       设置后的点数 (int)
        """
        # 允许传入字符串 '1M' / '1e6' / '1000000'
        if isinstance(points, str):
            s = points.strip().upper()
            if s.endswith('M') and s[:-1].replace('.', '', 1).isdigit():
                points_val = int(float(s[:-1]) * 1_000_000)
            else:
                try:
                    points_val = int(float(s))
                except Exception:
                    raise ValueError(f"无法解析采集点数: {points}")
        else:
            points_val = int(points)

        # 发送设置命令
        self.write(f"ACQuire:POINts {points_val}")
        if wait:
            # 设置记录长度可能需要仪器内部重配置缓冲, 提升超时
            try:
                self.wait_opc(timeout=600000)  # 最长 10 分钟以应对大深度重配置
            except Exception:
                # 若等待失败, 仍继续返回设置值
                pass
        return points_val

    def ensure_acquisition_points(self, target_points, wait=True):
        """
        先查询当前采集深度, 若与目标不同则设置为目标点数。

        :param target_points: 目标点数 (int 或可解析的字符串, 如 '1M')
        :param wait: 是否在设置后等待完成
        :return: (old_points, new_points, changed)
        """
        old = None
        try:
            old = self.acquisition_points()
        except Exception:
            # 查询失败仍尝试设置
            old = None
        new = self.set_acquisition_points(target_points, wait=wait)
        changed = (old != new)
        return old, new, changed

    def run(self):
        """连续运行 (RUN)。"""
        self.write("RUN")

    def single(self):
        """单次采集 (SINGle / RUNSingle)。"""
        self.write("SINGle")

    def stop(self):
        """停止采集 (STOP)。"""
        self.write("STOP")

    def single_and_wait(self, timeout=None):
        """单次采集并等待完成 (SINGle;*OPC)。"""
        self.write("SINGle")
        # self.wait_opc(timeout)
        self.opc_polling()  #这里需要注意

    # ------------------------------------------------------------------
    # 触发系统
    # ------------------------------------------------------------------
    def trigger_mode(self, mode=TriggerMode.AUTO):
        """触发模式 ``TRIGger:MODE``。"""
        val = mode.value if isinstance(mode, TriggerMode) else mode
        self.write(f"TRIGger:MODE {val}")

    def trigger_source(self, source="C1"):
        """触发源 ``TRIGger:EVENt1:SOURce`` (C1..C4 / D0..D15 / EXT / LINE / SBUS1..)。"""
        self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")

    def trigger_level(self, level, source="C1"):
        """触发电平 ``TRIGger:EVENt1:LEVel1:VALue``。"""
        self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")
        self.write(f"TRIGger:EVENt1:LEVel1:VALue {level}")

    # ---- 边沿触发 (最常用) ----
    def configure_edge_trigger(self, source="C1", level=0.0, slope=EdgeSlope.POSITIVE):
        """配置边沿触发。"""
        sl = slope.value if isinstance(slope, EdgeSlope) else slope
        self.write_list([
            f"TRIGger:EVENt1:TYPe EDGE",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:EDGE:SLOPe {sl}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
        ])

    # ---- 脉宽触发 ----
    def configure_width_trigger(self, source="C1", level=0.0,
                                condition="WITHin", width=1e-6,
                                slope=EdgeSlope.POSITIVE):
        """
        脉宽触发: 在 ``condition`` (WITHin / OUTSide) 指定 ``width`` (s) 时触发。

        对应命令 ``TRIGger:EVENt1:WIDTh:CONDition`` / ``RANGe``。
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

    # ---- 毛刺触发 ----
    def configure_glitch_trigger(self, source="C1", level=0.0, width=1e-9,
                                 polarity="POSitive"):
        """毛刺触发: 小于 ``width`` (s) 的窄脉冲。"""
        self.write_list([
            f"TRIGger:EVENt1:TYPe GLITch",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
            f"TRIGger:EVENt1:GLITch:RANGe {width}",
            f"TRIGger:EVENt1:GLITch:POLarity {polarity}",
        ])

    # ---- 矮脉冲触发 ----
    def configure_runt_trigger(self, source="C1", upper_level=0.5, lower_level=0.1,
                               polarity="POSitive"):
        """矮脉冲 (Runt) 触发: 脉冲未能穿越上下电平之间。"""
        self.write_list([
            f"TRIGger:EVENt1:TYPe RUNT",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:RUNT:POLarity {polarity}",
            f"TRIGger:EVENt1:LEVel1:VALue {upper_level}",
            f"TRIGger:EVENt1:LEVel2:VALue {lower_level}",
        ])

    # ---- 窗口触发 ----
    def configure_window_trigger(self, source="C1", upper_level=0.5, lower_level=-0.5,
                                 condition="WITHin"):
        """窗口触发: 波形进入/离开电平窗口时触发。"""
        self.write_list([
            f"TRIGger:EVENt1:TYPe WINdow",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:WINdow:CONDition {condition}",
            f"TRIGger:EVENt1:LEVel1:VALue {upper_level}",
            f"TRIGger:EVENt1:LEVel2:VALue {lower_level}",
        ])

    # ---- 超时触发 ----
    def configure_timeout_trigger(self, source="C1", level=0.0, timeout=1e-6,
                                  condition="LONGer"):
        """超时触发: 电平保持时间超过/短于 ``timeout`` (s) 时触发。"""
        self.write_list([
            f"TRIGger:EVENt1:TYPe TIMeout",
            f"TRIGger:EVENt1:SOURce {self._src(source)}",
            f"TRIGger:EVENt1:LEVel1:VALue {level}",
            f"TRIGger:EVENt1:TIMeout:CONDition {condition}",
            f"TRIGger:EVENt1:TIMeout:RANGe {timeout}",
        ])

    # ---- 码型触发 ----
    def configure_pattern_trigger(self, sources=None, levels=None,
                                  pattern="1111"):
        """
        码型触发 (需要逻辑/MSO 选件)。

        :param sources: 信源列表, 例如 ['C1','C2'] 或 ['D0','D1']
        :param levels:  对应电平列表
        :param pattern: 码型字符串, 每个字符 0/1/X (不关心)
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

    # ---- 串行总线触发 (协议触发) ----
    def configure_serial_trigger(self, bus_number=1, bus_type=BusType.UART,
                                 source="SBUS1"):
        """
        设置串行总线触发 (协议触发)。

        对应 ``TRIGger:EVENt1:TYPe SERialbus``,
        触发源 ``TRIGger:EVENt1:SOURce`` 为串行总线 (默认 ``SBUS1``)。
        """
        bt = bus_type.value if isinstance(bus_type, BusType) else bus_type
        if bus_number not in [1, 2, 3, 4]:
            raise ValueError(f"bus_number 必须为 1~4, 当前: {bus_number}")
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
            # QSPI 没有硬件串行总线触发 (TRIGger:SBHW:QSPI 不存在),
            # 使用软件串行总线触发 TRIGger:SBSW:QSPI:*, 并需在
            # A → Serial bus 多事件序列 (MEVents) 中触发。
            self.write_list([
                "TRIGger:MEVents:MODE SEQuence",
                "TRIGger:MEVents:AEVents ASB",
                f"TRIGger:EVENt2:SOURce SBUS{bus_number}",
                "TRIGger:SBSW:QSPI:CLR",
                "TRIGger:SBSW:QSPI:FRENable ON",
            ])
        else:
            raise ValueError(f"不支持的总线配置: bus_number={bus_number}, bus_type={bus_type}")

    def configure_i2c_trigger(self, condition=None,
                              address=None, data=None, bus_number=2, source="SBUS2"):
        """配置 I2C 串行总线触发条件。"""
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
        """配置 SPI 串行总线触发条件 (MOSI/MISO 数据条件)。"""
        self.configure_serial_trigger(bus_number, BusType.SPI, source)
        self.write(f"TRIGger:EVENt{bus_number}:SERialbus:SPI:CONDition {condition}")
        if pattern is not None:
            self.write(f"TRIGger:EVENt{bus_number}:SERialbus:SPI:DATA {pattern}")

    def configure_qspi_trigger(self, bus_number=4, source="SBUS4", clock_source="C1",
                               frame_enable=True, invert=False):
        """
        配置 QSPI 软件串行总线触发 (A → Serial bus 序列)。

        注意: QSPI 没有硬件串行总线触发 (``TRIGger:SBHW:QSPI`` 不存在),
        使用软件触发 ``TRIGger:SBSW:QSPI:*``, 并需在 A → Serial bus
        多事件序列 (MEVents) 中触发。

        :param bus_number:   QSPI 解码所在的串行总线编号 (1..4)
        :param source:       串行总线源 (默认 SBUS4)
        :param clock_source: QSPI 触发时钟 (A 事件 arming 源)。
                             可为模拟通道 (如 'C1') 或数字通道 (如 'D0'),
                             大小写不敏感 ('c1'/'d0' 均可)。
        :param frame_enable: True 使能帧条件检查 (SBSW:QSPI:FRENable)
        :param invert:       True 反相整体触发条件
        """
        self.configure_serial_trigger(bus_number, BusType.QSPI, source)
        if clock_source is not None:
            self.write(f"TRIGger:EVENt1:SOURce {self._src(clock_source)}")
        self.write(f"TRIGger:SBSW:QSPI:FRENable {'ON' if frame_enable else 'OFF'}")
        if invert:
            self.write("TRIGger:SBSW:QSPI:INVert ON")



    def configure_uart_trigger(self, bus_number=1, source="SBUS1"):
        """配置 UART 串行总线触发条件。"""
        self.configure_serial_trigger(bus_number, BusType.UART, source)
        self.write_list([f"SBUS{bus_number}:ZCOupling {'ON'}",
                                  f"SBUS{bus_number}:RESult {'ON'}"
                                 ]) 


    # ------------------------------------------------------------------
    # 协议分析 (串行总线解码)
    # ------------------------------------------------------------------
    def bus_state(self, bus_number=1, on=True):
        """开关串行总线解码 ``SBUS<n>:STATe ON|OFF``。"""
        self.write(f"BUS{bus_number}:STATe {'ON' if on else 'OFF'}")

    def bus_result_table(self, bus_number=1, on=True):
        """
        开关串行总线解码结果表 ``SBUS<n>:RESult ON|OFF``。

        MXO4 屏幕下方的结果区会同时显示解码结果表与自动测量结果表;
        关闭解码表 (OFF) 后即可露出测量结果表 (RMS/FREQuency/AMPLitude 等),
        便于截屏保存测量界面。
        """
        self.write(f"SBUS{bus_number}:RESult {'ON' if on else 'OFF'}")

    def bus_type(self, bus_number=1, bus_type=BusType.I2C):
        """设置串行总线协议类型 ``SBUS<n>:TYPE``。"""
        bt = bus_type.value if isinstance(bus_type, BusType) else bus_type
        self.write(f"SBUS{bus_number}:TYPE {bt}")

    def bus_label(self, bus_number=1, label=""):
        """串行总线标签 ``SBUS<n>:LABel '<str>'``。"""
        self.write(f"SBUS{bus_number}:LABel '{label}'")

    def bus_threshold(self, bus_number=1, level=1.65):
        """逻辑电平阈值 ``SBUS<n>:THReshold <NR3>`` (V)。"""
        self.write(f"SBUS{bus_number}:THReshold {level}")

    def configure_i2c_decode(self, bus_number=1, scl="C1", sda="C2"):
        """
        配置 I2C 解码。

        :param bus_number:    串行总线编号 (1..4)
        :param scl:           SCL 时钟信源 (C1..C4 / D0..D15)
        :param sda:           SDA 数据信源
        :param address_mode:  地址模式 7BIT / 10BIT
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
        配置 SPI 解码。

        :param sclk: SCLK 时钟信源
        :param mosi: MOSI 数据信源 (仅主机模式)
        :param miso: MISO 数据信源 (仅从机模式)
        :param ss:   片选信源 (可 'NONE')
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
        配置 QSPI (Quad SPI) 解码。

        对应 ``SBUS<n>:TYPE QSPI`` 与 ``SBUS<n>:QSPI:*`` 子树:
          * 时钟 ``QSPI:SCLK:SOURce``, 片选 ``QSPI:CSEL:SOURce``
          * 数据线 ``QSPI:IOZero / IOONe / IOTWo / IOTHree:SOURce`` (IO0~IO3)
          * QSPI 由 opcode 指令表驱动, 每个 opcode 可单独设置地址/数据通道数
            (SINGle / DUAL / QUAD)、DDR、dummy cycles、地址字节数等

        :param bus_number:     串行总线编号 (1..4)
        :param sclk:           SCLK 时钟信源
        :param cs:             CS (片选) 信源
        :param io0..io3:       IO0~IO3 数据线信源
        :param sclk_polarity:  时钟极性 RISing / FALLing
        :param cs_polarity:    片选有效电平 ACTLow / ACTHigh
        :param instruction:    指令模式 SINGle / DUAL / QUAD
        :param opcodes:        opcode 表 (list[dict]), 每个元素可含:
                               code(0~255), ddr(bool 或 ON/OFF), adbytes(0~4),
                               adlanes/dtlanes(SINGle|DUAL|QUAD),
                               dmcycles(0~255), data(bool 或 ON/OFF)
        :param result_table:   True 显示解码结果表
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
        配置 UART (RS-232/422/485) 解码。

        :param rx:        RX 数据信源
        :param tx:        TX 数据信源 (可 'NONE')
        :param baud:      波特率
        :param data_bits: 数据位 (7/8/9)
        :param parity:    校验位
        :param stop_bits: 停止位 (1/1.5/2)
        :param idle:      空闲电平 IDLEHIGH / IDLELOW
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
        读取串行总线解码结果 ``SBUS<n>:RESult?``, 返回字符串。

        返回内容为按帧列出的解码数据 (格式取决于总线与固件版本),
        可自行按行/逗号解析。另可参考 ``SBUS<n>:RESult:FCOunt?`` 获取帧数。  
        """
        return self.query(f"SBUS{bus_number}:RESult?")

    def get_decoded_frame_count(self, bus_number=1):
        """查询解码出的帧数量 ``SBUS<n>:RESult:FCOunt?``。"""
        try:
            return int(float(self.query(f"SBUS{bus_number}:RESult:FCOunt?")))
        except Exception:
            # 部分固件使用 SBUS<n>:FCOunt?
            return int(float(self.query(f"SBUS{bus_number}:FCOunt?")))

    # ------------------------------------------------------------------
    # 数字 logic 解码 (MSO 数字通道 D0~D15 与逻辑组 PBUS/Logic1~4)
    # ------------------------------------------------------------------
    def digital_channel_state(self, digital, on=True):
        """开关数字通道 ``DIGital<n>:STATe ON|OFF`` (n=0..15, 即 D0~D15)。"""
        self.write(f"DIGital{int(digital)}:STATe {'ON' if on else 'OFF'}")

    def digital_probe_enable(self, probe=1, digital=0, on=True):
        """
        启用/关闭数字模块 (MSO 逻辑探头 pod) ``DIGital<n>:PROBe<m>:ENABle``。

        :param probe:   pod 编号 (1..2)
        :param digital: 数字通道号 (0..15)
        """
        self.write(f"DIGital{int(digital)}:PROBe{int(probe)}:ENABle {'ON' if on else 'OFF'}")

    def digital_channel_threshold(self, digital, volts=1.65):
        """设置数字通道阈值 ``DIGital<n>:THReshold <NR3>`` (V, 作用于所属逻辑组)。"""
        self.write(f"DIGital{int(digital)}:THReshold {volts}")

    def digital_channel_technology(self, digital, technology="V165"):
        """设置数字通道阈值技术预设 ``DIGital<n>:TECHnology`` (V165/V25/V125/V09/V15/VM13/V38/V20/V0/MANual)。"""
        self.write(f"DIGital{int(digital)}:TECHnology {technology}")

    def digital_channel_hysteresis(self, digital, hysteresis="NORMal"):
        """设置数字通道滞回 ``DIGital<n>:HYSTeresis`` (MAXimum/ROBust/NORMal)。"""
        self.write(f"DIGital{int(digital)}:HYSTeresis {hysteresis}")

    def digital_channel_threshold_coupling(self, digital, on=True):
        """阈值/滞回耦合 ``DIGital<n>:THCoupling ON|OFF``。"""
        self.write(f"DIGital{int(digital)}:THCoupling {'ON' if on else 'OFF'}")

    def pbus_state(self, pbus=1, on=True):
        """开关逻辑组 (并行总线) ``PBUS<n>:STATe ON|OFF`` (n=1..4)。"""
        self.write(f"PBUS{int(pbus)}:STATe {'ON' if on else 'OFF'}")

    def pbus_bit_state(self, pbus=1, bit=0, on=True):
        """使能逻辑组中的数字通道 BIT ``PBUS<n>:BIT<m>:STATe ON|OFF`` (m=0..15)。"""
        self.write(f"PBUS{int(pbus)}:BIT{int(bit)}:STATe {'ON' if on else 'OFF'}")

    def pbus_bit_label(self, pbus=1, bit=0, label=""):
        """设置逻辑组中某 BIT 的名称 ``PBUS<n>:BIT<m>:LABel '<label>'``。"""
        self.write(f"PBUS{int(pbus)}:BIT{int(bit)}:LABel '{label}'")

    def pbus_clear(self, pbus=1):
        """清空逻辑组中的全部通道 ``PBUS<n>:CLEar``。"""
        self.write(f"PBUS{int(pbus)}:CLEar")

    def pbus_decode_table(self, pbus=1, on=True):
        """开关逻辑组解码结果表 ``PBUS<n>:DECTable:SHOW ON|OFF`` (仅时钟总线有效)。"""
        self.write(f"PBUS{int(pbus)}:DECTable:SHOW {'ON' if on else 'OFF'}")

    def pbus_threshold(self, pbus=1, index=1, volts=1.65):
        """设置逻辑组阈值 ``PBUS<n>:THReshold<m> <NR3>`` (V, m=1..4)。"""
        self.write(f"PBUS{int(pbus)}:THReshold{int(index)} {volts}")

    def pbus_technology(self, pbus=1, technology="V165"):
        """设置逻辑组阈值技术预设 ``PBUS<n>:TECHnology``。"""
        self.write(f"PBUS{int(pbus)}:TECHnology {technology}")

    def pbus_hysteresis(self, pbus=1, index=1, hysteresis="NORMal"):
        """设置逻辑组滞回 ``PBUS<n>:HYSTeresis<m>`` (m=1..4)。"""
        self.write(f"PBUS{int(pbus)}:HYSTeresis{int(index)} {hysteresis}")

    def pbus_threshold_coupling(self, pbus=1, on=True):
        """逻辑组阈值/滞回耦合 ``PBUS<n>:THCoupling ON|OFF``。"""
        self.write(f"PBUS{int(pbus)}:THCoupling {'ON' if on else 'OFF'}")

    def pbus_clock(self, pbus=1, source="D0", slope="POSitive", on=True):
        """配置逻辑组时钟总线 ``PBUS<n>:CLON / CLOCk / CLSLope``。"""
        self.write(f"PBUS{int(pbus)}:CLON {'ON' if on else 'OFF'}")
        if source is not None:
            self.write(f"PBUS{int(pbus)}:CLOCk {self._src(source)}")
        if slope is not None:
            self.write(f"PBUS{int(pbus)}:CLSLope {slope}")

    def pbus_display(self, pbus=1, show_bus=True, show_digital=True):
        """逻辑组显示选项 ``PBUS<n>:DISPlay:SHBU / SHDI``。"""
        self.write(f"PBUS{int(pbus)}:DISPlay:SHBU {'ON' if show_bus else 'OFF'}")
        self.write(f"PBUS{int(pbus)}:DISPlay:SHDI {'ON' if show_digital else 'OFF'}")

    def get_pbus_data(self, pbus=1):
        """读取逻辑组解码数据 ``PBUS<n>:DATA:VALUES?``。"""
        return self.query(f"PBUS{int(pbus)}:DATA:VALUES?")

    def configure_logic_decode(self, pbus=1, bits=None, threshold=1.65,
                               technology="V165", hysteresis="NORMal",
                               clocked=False, clock_source="D0",
                               clock_slope="POSitive", decode_table=False,
                               show_bus=True, show_digital=True, enable=True):
        """
        一键配置数字逻辑组 (并行总线) 解码 (PBUS<n>, 对应 Logic1~Logic4)。

        :param pbus:         逻辑组编号 (1..4)
        :param bits:         使能的数字通道列表, 例如 [0,1,2,3] (即 D0~D3);
                             元素也可为 (bit, label) 元组
        :param threshold:    阈值电压 (V)
        :param technology:   阈值技术预设 (V165/V25/V125/V09/V15/VM13/V38/V20/V0/MANual)
        :param hysteresis:   滞回 (MAXimum/ROBust/NORMal)
        :param clocked:      True 使用一个通道作为总线时钟
        :param clock_source: 时钟通道 (D0..D15)
        :param clock_slope:  时钟边沿 (POSitive/NEGative/EITHer)
        :param decode_table: True 显示解码结果表 (仅时钟总线有效)
        :param show_bus/show_digital: 显示总线信号 / 数字通道
        :param enable:       True 启用该逻辑组
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
    # 自动测量 (通用)
    # ------------------------------------------------------------------
    def configure_measurement(self, measure_index=1, source="C1", main="AMPlitude",
                              category=None, additional=None, enable=True):
        """
        配置一个自动测量项 (MEASurement<n>)。

        :param measure_index: 测量编号 (1..N)
        :param source:        测量源 (C1..C4 / EYE1 / 数学信号等)
        :param main:          主测量类型, 例如 AMPlitude / FREQuency / EHEight
        :param category:      测量类别, 例如 EYEJitter
        :param additional:    附加测量列表, 元素可为 str 或 (name, on) 元组
        :param enable:        True 启用测量
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
        读取测量结果。

        :param measure_index: 测量编号
        :param result_index:  结果序号 (1 为主测量, >1 为附加测量)
        :return: 测量值字符串
        """
        if result_index <= 1:
            return self.query(f"MEASurement{measure_index}:RESult:ACTual?")
        return self.query(f"MEASurement{measure_index}:RESult{result_index}:ACTual?")

    # ------------------------------------------------------------------
    # 上升沿 / 幅值 专用测量辅助 (基于 MEASurement)
    # ------------------------------------------------------------------
    def configure_rise_time_measurement(self, measure_index=1, source="C1",
                                        enable=True):
        """
        配置上升沿时间自动测量 ``MEASurement<n>:MAIN RTIMe``。

        注意: MXO4 的上升沿时间参数为 ``RTIMe`` (而非 ``RISEtime``)。

        :param measure_index: 测量编号 (1..16)
        :param source:        测量源 (C1..C4 / D0..D15 / 数学信号等)
        :param enable:        True 启用
        """
        self.write(f"MEASurement{measure_index}:SOURce {self._src(source)}")
        self.write(f"MEASurement{measure_index}:MAIN RTIMe")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_amplitude_measurement(self, measure_index=1, source="C1",
                                        enable=True):
        """
        配置幅值自动测量 ``MEASurement<n>:MAIN AMPLitude``。
        """
        self.write(f"MEASurement{measure_index}:SOURce {self._src(source)}")
        self.write(f"MEASurement{measure_index}:MAIN AMPLitude")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def get_measurement_value(self, measure_index=1):
        """
        读取测量结果并尽量转换为 float; 转换失败时返回原始字符串。

        对应 ``MEASurement<n>:RESult:ACTual?``。
        """
        raw = self.query(f"MEASurement{measure_index}:RESult:ACTual?")
        try:
            return float(raw)
        except (ValueError, TypeError):
            return raw

    # ------------------------------------------------------------------
    # 光标测量 (Cursor)
    # ------------------------------------------------------------------
    def cursor_state(self, cursor=1, on=True):
        """开关光标显示 ``CURSor<n>:STATe ON|OFF``。"""
        self.write(f"CURSor{cursor}:STATe {'ON' if on else 'OFF'}")

    def cursor_all_off(self):
        """关闭所有光标 ``CURSor:AOFF`` (无后缀)。"""
        self.write("CURSor:AOFF")

    def cursor_function(self, cursor=1, function=CursorFunction.PAIRED):
        """设置光标类型 ``CURSor<n>:FUNCtion`` (VERTical / HORizontal / PAIRed)。"""
        val = function.value if isinstance(function, CursorFunction) else function
        self.write(f"CURSor{cursor}:FUNCtion {val}")

    def cursor_source(self, cursor=1, source="C1"):
        """设置光标信源 ``CURSor<n>:SOURce``。"""
        self.write(f"CURSor{cursor}:SOURce {self._src(source)}")

    def cursor_positions(self, cursor=1, x1=None, x2=None, y1=None, y2=None):
        """
        设置光标位置 ``CURSor<n>:X1Position / X2Position / Y1Position / Y2Position``。

        :param x1/x2: 垂直光标位置 (s); y1/y2: 水平光标位置 (V); None 表示不修改
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
        """设置光标跟踪 ``CURSor<n>:TRACking:STATe ON|OFF``。"""
        self.write(f"CURSor{cursor}:TRACking:STATe {'ON' if on else 'OFF'}")

    def cursor_display_values(self, cursor=1, on=True):
        """是否显示光标数值标签 ``CURSor<n>:DISPlay:VALues ON|OFF``。"""
        self.write(f"CURSor{cursor}:DISPlay:VALues {'ON' if on else 'OFF'}")

    def cursor_label_show(self, cursor=1, on=True):
        """是否显示光标标签 (名称) ``CURSor<n>:LABel ON|OFF``。"""
        self.write(f"CURSor{cursor}:LABel {'ON' if on else 'OFF'}")

    def cursor_vertical_label(self, cursor=1, line=1, label=""):
        """
        设置垂直光标线名称 ``CURSor<n>:VERTical<m>:LABel '<label>'``。

        :param cursor: 光标组编号 (1..2)
        :param line:   垂直光标线编号 (1..2)
        :param label:  名称文本 (请勿包含单引号)
        """
        self.write(f"CURSor{cursor}:VERTical{int(line)}:LABel '{label}'")

    def cursor_horizontal_label(self, cursor=1, line=1, label=""):
        """
        设置水平光标线名称 ``CURSor<n>:HORizontal<m>:LABel '<label>'``。

        :param cursor: 光标组编号 (1..2)
        :param line:   水平光标线编号 (1..2)
        :param label:  名称文本 (请勿包含单引号)
        """
        self.write(f"CURSor{cursor}:HORizontal{int(line)}:LABel '{label}'")

    def set_cursor_labels(self, cursor=1, v1=None, v2=None, h1=None, h2=None):
        """
        一键设置光标四条线的名称 (None 表示不修改)。

        :param v1/v2: 垂直光标线 1/2 的名称
        :param h1/h2: 水平光标线 1/2 的名称
        :return: self, 便于链式调用
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
        """读取垂直光标差值 ΔX (时间, s) ``CURSor<n>:XDELta?``。"""
        return float(self.query(f"CURSor{cursor}:XDELta?"))

    def get_cursor_delta_y(self, cursor=1):
        """读取水平光标差值 ΔY (幅度, V) ``CURSor<n>:YDELta?``。"""
        return float(self.query(f"CURSor{cursor}:YDELta?"))

    def configure_cursor(self, cursor=1, function=CursorFunction.PAIRED,
                         source="C1", x1=None, x2=None, y1=None, y2=None,
                         show=True, show_values=True, tracking=False):
        """
        一键配置光标: 类型 / 信源 / 位置 / 显示。

        :param cursor:      光标组编号 (1..2)
        :param function:    CursorFunction.VERTICAL (测时间) / HORIZONTAL (测幅度) / PAIRED (同时)
        :param source:      光标信源 (C1..C4 等)
        :param x1/x2:       垂直光标位置 (s)
        :param y1/y2:       水平光标位置 (V)
        :param show:        True 显示光标 (CURSor<n>:STATe ON); False 只配置不显示
        :param show_values: True 显示光标数值标签
        :param tracking:    是否跟踪波形
        :return: self, 便于链式调用
        """
        self.cursor_function(cursor, function)
        self.cursor_source(cursor, source)
        self.cursor_positions(cursor, x1=x1, x2=x2, y1=y1, y2=y2)
        self.cursor_tracking(cursor, tracking)
        self.cursor_display_values(cursor, show_values)
        self.cursor_state(cursor, show)
        return self

    # ------------------------------------------------------------------
    # 建立时间 / 保持时间测量 (Setup / Hold Time)
    # ------------------------------------------------------------------
    def configure_setup_time(self, measure_index=1, data_source="C1",
                             clock_source="C2", enable=True):
        """
        配置建立时间 (Setup Time) 自动测量。

        建立时间测量需要两个信源:
          * 数据信源 ``data_source``  -> ``MEASurement<n>:SOURce``
          * 时钟信源 ``clock_source`` -> ``MEASurement<n>:SSRC`` (第二信源)

        :param measure_index: 测量编号 (1..N)
        :param data_source:   数据信源 (C1..C4 / D0..D15 等)
        :param clock_source:  时钟 (参考) 信源, 建立时间以该信源的边沿为基准
        :param enable:        True 启用测量
        """
        self.write(f"MEASurement{measure_index}:MAIN SETup")
        self.write(f"MEASurement{measure_index}:SOURce {self._src(data_source)}")
        self.write(f"MEASurement{measure_index}:SSRC {self._src(clock_source)}")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_hold_time(self, measure_index=1, data_source="C1",
                            clock_source="C2", enable=True):
        """
        配置保持时间 (Hold Time) 自动测量。

        保持时间测量需要两个信源:
          * 数据信源 ``data_source``  -> ``MEASurement<n>:SOURce``
          * 时钟信源 ``clock_source`` -> ``MEASurement<n>:SSRC`` (第二信源)

        :param measure_index: 测量编号 (1..N)
        :param data_source:   数据信源 (C1..C4 / D0..D15 等)
        :param clock_source:  时钟 (参考) 信源, 保持时间以该信源的边沿为基准
        :param enable:        True 启用测量
        """
        self.write(f"MEASurement{measure_index}:MAIN HOLD")
        self.write(f"MEASurement{measure_index}:SOURce {self._src(data_source)}")
        self.write(f"MEASurement{measure_index}:SSRC {self._src(clock_source)}")
        self.write(f"MEASurement{measure_index}:ENABle {'ON' if enable else 'OFF'}")

    def configure_setup_hold(self, measure_index=1, data_source="C1",
                             clock_source="C2", enable=True):
        """
        同时配置建立时间 (SETup) 与保持时间 (HOLD) 两项测量。

        使用连续的两个测量编号:
          * ``measure_index``      -> 建立时间 ``SETup``
          * ``measure_index + 1``  -> 保持时间 ``HOLD``

        :param measure_index: 起始测量编号 (1..N)
        :param data_source:   数据信源
        :param clock_source:  时钟 (参考) 信源
        :param enable:        True 启用测量
        :return: (setup_index, hold_index) 两项测量分别占用的测量编号
        """
        self.configure_setup_time(measure_index, data_source, clock_source, enable)
        hold_index = measure_index + 1
        self.configure_hold_time(hold_index, data_source, clock_source, enable)
        return measure_index, hold_index

    def get_setup_hold_results(self, measure_index=1):
        """
        读取建立时间与保持时间测量结果 (``RESult:ACTual?``, 单位: 秒)。

        需先调用 ``configure_setup_hold`` (或分别调用 ``configure_setup_time`` /
        ``configure_hold_time``), 并保证示波器已完成采集。

        :param measure_index: 建立时间测量所占用的测量编号
        :return: dict, 键为 'setup' 与 'hold', 值为测量值字符串
        """
        return {
            "setup": self.get_measurement_result(measure_index),
            "hold": self.get_measurement_result(measure_index + 1),
        }

    # ------------------------------------------------------------------
    # 眼图 (Eye Diagram)
    # ------------------------------------------------------------------
    def configure_cdr(self, source="C1", bit_rate=None, sw_cdr=1):
        """
        配置软件时钟数据恢复 (CDR)。

        眼图 / 抖动分析需要 CDR 从串行数据流中恢复时钟。

        :param source:   数据信源 (C1..C4 / DIFF1 等)
        :param bit_rate: 码率 (bit/s), 例如 1e9 表示 1 Gbps
        :param sw_cdr:   软件 CDR 编号 (默认 1)
        """
        self.write(f"CDR:SOFTware{sw_cdr}:ESSRate:SOURce {self._src(source)}")
        if bit_rate is not None:
            self.write(f"CDR:SOFTware{sw_cdr}:ESSRate {bit_rate}")

    def configure_eye_diagram(self, source="C1", cdr_mode="SW", enable=True):
        """
        配置眼图 (Eye Diagram)。

        :param source:   信号源 (C1..C4 / DIFF1 / 数学信号)
        :param cdr_mode: CDR 模式: "SW" 软件 CDR (推荐), "HW" 硬件 CDR
        :param enable:   True 打开眼图, False 关闭
        """
        self.write(f"EYE1:SOURce {self._src(source)}")
        if str(cdr_mode).upper() in ("SW", "SOFTware", "SOFTWARE"):
            # 软件 CDR
            self.write("EYE1:TIMReference:SOURce CDR")
            self.write("EYE1:TIMReference:CDR:SELect SW")
            self.write("EYE1:TIMReference:CDR:SOFTware SW1")
            self.write(f"CDR:SOFTware1:ESSRate:SOURce {self._src(source)}")
        else:
            # 硬件 CDR (触发方式改为 CDR)
            self.write(f"TRIGger:EVENt1:SOURce {self._src(source)}")
            self.write("TRIGger:EVENt1:TYPe CDR")
        self.write(f"EYE1:STATe {'ON' if enable else 'OFF'}")
        self.wait_opc()

    def configure_eye_measurement(self, measure_index=1, source="EYE1",
                                  main=EyeMeasurement.EYE_HEIGHT,
                                  additional=None, enable=True):
        """
        配置眼图测量 (眼高 / 眼宽 / 眼幅度等)。

        :param measure_index: 测量编号
        :param source:        测量源, 默认 EYE1
        :param main:          主测量项 (EyeMeasurement 或字符串)
        :param additional:    附加测量项列表 (EyeMeasurement 或字符串)
        :param enable:        True 启用测量
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
        读取眼图测量结果。

        :param measure_index: 测量编号
        :param result_index:  1 = 主测量 (如眼高), >1 = 附加测量 (眼宽/眼幅度等)
        """
        return self.get_measurement_result(measure_index, result_index)

    # ------------------------------------------------------------------
    # 抖动分析 (Advanced Jitter)
    # ------------------------------------------------------------------
    def configure_jitter_quick_start(self, source="C1", timeout=120000):
        """
        高级抖动分析快速开始 (自动配置码率与 CDR, 并启用所有抖动分量)。

        注意: 该命令会自动启用 TJ@BER、RJ、TJ、DJ、PJ、DDJ 等分量。

        :param source:  数据信源 (C1..C4 / DIFF1 等)
        :param timeout: 等待超时 (ms), 快速开始可能需要 30~60 秒
        """
        self.write(f"ADVJitter:SIGNal:SOURce {self._src(source)}")
        self.write("ADVJitter:SIGNal:QUICkmeas")
        self.wait_opc(timeout=timeout)

    def configure_jitter_manual(self, source="C1", components=None):
        """
        手动配置高级抖动分量。

        :param source:     数据信源 (C1..C4 / DIFF1 等)
        :param components: JitterComponent 列表或分量编号列表
        """
        self.write(f"ADVJitter1:SIGNal:SOURce {self._src(source)}")
        self.write("ADVJitter1:RESult:ENABle ON")
        # 关闭快速开始自动开启的附加显示项
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
        """开关高级抖动结果显示 ``ADVJitter1:RESult:ENABle``。"""
        self.write(f"ADVJitter1:RESult:ENABle {'ON' if on else 'OFF'}")

    def enable_jitter_component(self, component, on=True):
        """开关单个抖动分量 ``ADVJitter1:DCOMposition:COMPonents<idx>:ENABle``。"""
        idx = component.value if isinstance(component, JitterComponent) else int(component)
        self.write(f"ADVJitter1:DCOMposition:COMPonents{idx}:ENABle {'ON' if on else 'OFF'}")

    def get_jitter_component_value(self, component):
        """
        读取抖动分量测量值 (单位: 秒)。

        命令: ADVJitter1:RESult:COMPonents<idx>:VALue?
        (个别固件版本命令可能略有差异, 可参照手册 "Advanced jitter" 章节调整)

        :param component: JitterComponent 枚举或分量编号
        """
        idx = component.value if isinstance(component, JitterComponent) else int(component)
        return self.query(f"ADVJitter1:RESult:COMPonents{idx}:VALue?")

    # ------------------------------------------------------------------
    # 波形读取与保存
    # ------------------------------------------------------------------
    def set_waveform_format(self, fmt=WaveformFormat.BINARY_FLOAT32):
        """设置波形数据格式 ``FORMat:DATA`` (二进制时同时设置小端字节序)。"""
        val = fmt.value if isinstance(fmt, WaveformFormat) else fmt
        if val.startswith("ASC"):
            self.write("FORMat:DATA ASC")
        else:
            self.write(f"FORMat:DATA {val}")
            self.write("FORMat:BORDer LSBFirst")

    def _parse_header(self, header_str):
        """
        解析 ``CHANnel<n>:DATA:HEADer?`` 返回的头部。

        MXO4 头部可能以两种格式返回, 统一转换为字典:
          1. name=value 逗号串:  XStart=-5e-6,XStop=5e-6,RecordLength=100000,ValsPerSmp=1
          2. 固定顺序数值串:      -5e-6,5e-6,100000,1  (XStart,XStop,RecordLength,ValsPerSmp)
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
            # 无 name=value 时按固定位置解析
            names = ("XStart", "XStop", "RecordLength", "ValsPerSmp")
            for name, val in zip(names, parts):
                d[name] = val
        return d

    @staticmethod
    def _header_value(header, *keys):
        """在头部字典中按 key (不区分大小写/模糊匹配) 查找值。"""
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
        """读取波形头 ``CHANnel<n>:DATA:HEADer?``, 返回字典。"""
        return self._parse_header(self.query(f"CHANnel{self._ch(channel)}:DATA:HEADer?"))

    # def get_waveform(self, channel, ascii_format=False):
    #     """
    #     读取单通道波形数据, 返回 (时间轴列表, 电压列表)。

    #     :param channel:      通道号
    #     :param ascii_format: True 使用 ASCII 传输 (慢但直观), False 使用 float32 二进制 (快)
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
    #         # 大记录长度下二进制传输耗时较长, 临时增大 VISA 超时与读取块大小,
    #         # 避免大数据量时出现超时报错 (VI_ERROR_TMO)
    #         old_timeout = self.visa_timeout
    #         old_chunk = self.data_chunk_size
    #         try:
    #             # 超时至少 30 秒, 足够传输数百万个采样点
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
    #             # 头部时间信息缺失/异常时, 用时基范围兜底重建时间轴, 避免时间列全为 0
    #             print("警告: 波形头时间信息无效, 使用 TIMebase:RANGe? 重建时间轴。")
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
    #     读取多通道波形, 返回 dict: {channel: (time_axis, volts)}。
    #     """
    #     result = {}
    #     for ch in channels:
    #         result[ch] = self.get_waveform(ch, ascii_format=ascii_format)
    #     return result

    # ------------------------------------------------------------------
    # 波形 ZOOM (UART 帧触发后自动框住 UART 帧; 仪器端显示放大 + PC 端绘图放大)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 1) 仪器端: 时基窗口放大 / 恢复
    # ------------------------------------------------------------------
    def get_timebase_state(self):
        """
        读取当前时基状态 (SCALe / RANGe / REFerence / HORizontal:POSition),
        用于 ZOOM 之后恢复原显示。
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
        """恢复由 :meth:`get_timebase_state` 保存的时基 (缩放/位置/参考点)。"""
        if not state:
            return
        # 先恢复参考点与跨度, 再恢复偏移, 最后恢复缩放, 避免中间状态越界
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
    # MXO4 分屏 ZOOM 窗口 (主区保留完整波形/解码帧, ZOOM 区只放大其中一帧)
    #   注意: MXO4 使用 LAYout<ly>:ZOOM<zo>:* 节点, 不是 TIMebase:ZOOM
    # ------------------------------------------------------------------
    def zoom_window_state(self, on=True, layout=1, zoom=1):
        """启用/关闭分屏 ZOOM 窗口 ``LAYout<ly>:ZOOM<zo>:ENABle``。"""
        self.write(f"LAYout{layout}:ZOOM{zoom}:ENABle {'ON' if on else 'OFF'}")

    def zoom_window_source(self, diagram=1, layout=1, zoom=1):
        """设置 ZOOM 放大哪个图 (diagram 索引) ``LAYout<ly>:ZOOM<zo>:SOURce``。"""
        self.write(f"LAYout{layout}:ZOOM{zoom}:SOURce {int(diagram)}")

    def get_zoom_window_diagram(self, layout=1, zoom=1):
        """查询当前 ZOOM 所放大的图索引 ``LAYout<ly>:ZOOM<zo>:DIAG?``。"""
        return self.query(f"LAYout{layout}:ZOOM{zoom}:DIAG?")

    def zoom_window_horizontal(self, mode="ABS", position=None, span=None,
                               start=None, stop=None, layout=1, zoom=1):
        """
        设置 ZOOM 区的水平范围。

        :param mode: 'ABS' 绝对时间 (s) / 'REL' 相对百分比 (%)
        :param position: ZOOM 区中心 (ABS: s, 0s=触发点; REL: %)
        :param span:     ZOOM 区宽度 (ABS: s; REL: %)
        :param start/stop: ZOOM 区下/上限 (ABS: s; REL: %)
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
        在示波器上把水平显示窗口放大到指定范围 (ZOOM), 供截屏保存放大波形。

        :param span:           整屏时间跨度 (s), 例如一帧 UART 数据对应的时间
        :param s_per_div:      每格时间 (s); 与 span 二选一 (s_per_div * 10 = span)
        :param t_center:       希望置于屏幕中央的绝对时间 (s, 需参考点为 50% 时生效)。
                               MXO4 的水平平移命令为 ``TIMebase:HORizontal:POSition``
                               (触发点 t=0 与参考点之间的距离, 即 offset = -t_center);
                               若放大后波形不在期望位置, 可对 t_center 取反微调。
        :param reacquire:      True 则重新执行一次 ``SINGle`` 刷新放大后的显示
                               (需触发能量新触发; 等待时间由 acquire_timeout 限制,
                               超时仅告警, 不中断流程)
        :param acquire_timeout: 重新采集等待超时 (ms)
        :return: dict(span, s_per_div, t_center) 实际采用的窗口
        """
        if s_per_div is not None:
            span = float(s_per_div) * 10.0
        if span is None:
            raise ValueError("zoom_display: 必须提供 span 或 s_per_div")
        span = float(span)
        self.timebase_range(span)
        if t_center is not None:
            self.timebase_offset(-float(t_center))   # 平移窗口使绝对时刻 t_center 位于屏中央
        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"警告: ZOOM 后重新采集失败/超时 (可能未再次触发): {exc}")
        return {"span": span, "s_per_div": span / 10.0, "t_center": t_center}

    def zoom_uart_display(self, baud=115200, data_bits=8,
                          parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                          margin_bits=2.0, diagram=1, layout=1, zoom=1,
                          reacquire=True, acquire_timeout=8000):
        """
        仪器端分屏 ZOOM: UART 串行总线触发成功后, 在主区保留完整波形
        (含 UART 解码区的全部数据帧), 只在 ZOOM 放大区显示其中一帧
        (默认放大触发点附近的那一帧)。

        与 :meth:`zoom_display` (直接修改整屏时基) 不同, 本方法使用 MXO4 的
        分屏 ZOOM 窗口 ``LAYout<ly>:ZOOM<zo>:*``:
          * 主区 (原 diagram) 继续显示完整波形与全部 UART 解码帧;
          * ZOOM 区按 ABS 水平窗口圈出单帧 (串行总线触发点在帧起始位 t≈0)。

        :param baud:        波特率
        :param data_bits:   数据位 (7/8/9)
        :param parity:      校验位
        :param stop_bits:   停止位
        :param margin_bits: 帧前后额外保留的空闲位数
        :param diagram:     ZOOM 所放大的 diagram 索引 (默认 1, 即主波形图)
        :param layout:      SmartGrid layout 索引 (默认 1)
        :param zoom:        ZOOM 窗口索引 (默认 1)
        :param reacquire:   True 则先重新执行一次 SINGle 刷新采集 (可选)
        :return: dict(frame_time, span, s_per_div, zoom_start, zoom_stop)
        """
        n_parity = MXO4._parity_bit_count(parity)
        n_stop = MXO4._stop_bit_count(stop_bits)
        bit_time = 1.0 / float(baud)
        frame_time = (1 + int(data_bits) + n_parity + n_stop) * bit_time
        margin = max(0.0, margin_bits) * bit_time
        zoom_start = -margin                        # 帧起始位(触发点 t≈0)前留 margin
        zoom_stop = frame_time + margin             # 帧结束(含停止位)后留 margin
        span = zoom_stop - zoom_start

        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"警告: ZOOM 前重新采集失败/超时 (可能未再次触发): {exc}")

        # 主区保留完整波形/解码帧; 仅启用 ZOOM 窗口并圈出单帧
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
        仪器端分屏 ZOOM: I2C 串行总线触发成功后, 在主区保留完整波形
        (含 I2C 解码区的全部数据帧), 只在 ZOOM 放大区显示其中一帧
        (默认放大 START 触发点之后的一个字节: 8 数据位 + 1 ACK = 9 SCL 时钟)。

        与 :meth:`zoom_display` (直接修改整屏时基) 不同, 本方法使用 MXO4 的
        分屏 ZOOM 窗口 ``LAYout<ly>:ZOOM<zo>:*``:
          * 主区 (原 diagram) 继续显示完整波形与全部 I2C 解码帧;
          * ZOOM 区按 ABS 水平窗口圈出单帧 (I2C START 触发点在 t≈0)。

        :param scl_freq:    SCL 时钟频率 (Hz), 例如 100e3 / 400e3 / 1e6
        :param frame_bits:  单帧占的 SCL 时钟数 (默认 9 = 8 数据位 + 1 ACK)
        :param margin_bits: 帧前后额外保留的 SCL 时钟数
        :param diagram:     ZOOM 所放大的 diagram 索引 (默认 1, 即主波形图)
        :param layout:      SmartGrid layout 索引 (默认 1)
        :param zoom:        ZOOM 窗口索引 (默认 1)
        :param reacquire:   True 则先重新执行一次 SINGle 刷新采集 (可选)
        :return: dict(frame_time, span, s_per_div, zoom_start, zoom_stop)
        """
        bit_time = 1.0 / float(scl_freq)
        frame_time = float(frame_bits) * bit_time
        margin = max(0.0, margin_bits) * bit_time
        zoom_start = -margin                        # START(触发点 t≈0)前留 margin
        zoom_stop = frame_time + 2*margin             # 一帧结束后留 margin
        span = zoom_stop - zoom_start

        if reacquire:
            try:
                self.write("SINGle")
                self.wait_opc(timeout=acquire_timeout)
            except Exception as exc:
                print(f"警告: ZOOM 前重新采集失败/超时 (可能未再次触发): {exc}")

        # 主区保留完整波形/解码帧; 仅启用 ZOOM 窗口并圈出单帧
        self.zoom_window_state(True, layout=layout, zoom=zoom)
        self.zoom_window_source(diagram, layout=layout, zoom=zoom)
        self.zoom_window_horizontal(mode="ABS", start=zoom_start, stop=zoom_stop,
                                    layout=layout, zoom=zoom)
        return {"frame_time": frame_time, "span": span,
                "s_per_div": span / 10.0,
                "zoom_start": zoom_start, "zoom_stop": zoom_stop}

    # ------------------------------------------------------------------
    # 2) UART 软件解码 / 帧定位 (自动框住 UART 帧的核心)
    # ------------------------------------------------------------------
    @staticmethod
    def _parity_bit_count(parity):
        """UART 校验位是否启用: NONE -> 0, 其余 -> 1。"""
        if isinstance(parity, UARTParity):
            s = parity.value.upper()
        else:
            s = str(parity).strip().upper()
        return 0 if s in ("NONE", "", "OFF") else 1

    @staticmethod
    def _stop_bit_count(stop_bits):
        """UART 停止位个数 (数值): 'B1'->1, 'B15'->1.5, 'B2'->2, 数值直接返回。"""
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
        纯软件 UART 帧解码 / 定位 (不依赖仪器的协议分析选件), 用于自动框选 ZOOM 区域。

        从已采集的 RX 波形中逐帧识别 UART 帧:
          * 帧结构 = 起始位 + 数据位 + (校验位) + 停止位(空闲电平);
          * 对每个候选起始沿, 在位中心处采样比特, 按 LSB first 重建数据。
        本方法是静态方法, 可在无仪器 / 离线场合直接调用 (便于本地验证与事后分析)。

        :param time_axis: 时间轴 (s)
        :param volts:     电压 (V), 与 time_axis 等长
        :param baud:      波特率
        :param data_bits: 数据位 (7/8/9)
        :param parity:    UARTParity.NONE / EVEN / ODD / MARK / SPC
        :param stop_bits: STOPBit.ONE_BIT / .ONE_P_FIVE_BITS / .TWO_BITS, 或数值 1/1.5/2
        :param idle:      UARTPOLarity.IDLHigh(空闲高) / IDLLow(空闲低)
        :param threshold: 逻辑判定阈值 (V)
        :return: list[dict], 按 t_start 升序; 每帧含:
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
        logic = (v >= float(threshold)).astype(bool)          # True = 高
        if isinstance(idle, UARTPOLarity):
            idle_high = (idle == UARTPOLarity.IDLHigh)
        else:
            idle_high = str(idle).strip().upper() in ("IDLHIGH", "IDLEHIGH", "1")
        n_parity = MXO4._parity_bit_count(parity)
        n_stop = MXO4._stop_bit_count(stop_bits)
        data_bits = int(data_bits)
        head_bits = 1 + data_bits + n_parity                   # 起始 + 数据 + 校验
        # 起始沿 = 空闲 -> 非空闲 的跳变沿
        if idle_high:
            edges = np.flatnonzero(logic[:-1] & ~logic[1:])    # 高 -> 低
        else:
            edges = np.flatnonzero(~logic[:-1] & logic[1:])    # 低 -> 高

        def _level_at(tt, default):
            """返回 tt 时刻附近的逻辑电平 (True=高), 越界用 default。"""
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
            # 起始位中心必须是非空闲电平
            if _level_at(t_start + 0.5 * bit_time, idle_high) == idle_high:
                continue
            t_frame_end = t_start + (head_bits + n_stop) * bit_time
            if t_frame_end > float(t[-1]) + bit_time:          # 帧超出记录范围
                continue
            # 与已接收帧重叠 (上一帧数据尚未结束), 跳过帧内部毛刺沿
            if t_start < last_frame_end - 0.2 * bit_time:
                continue
            bits = [_level_at(t_start + (k + 0.5) * bit_time, idle_high)
                    for k in range(head_bits)]
            if bits[0] == idle_high:                           # 起始位必须非空闲
                continue
            data_vals = bits[1:1 + data_bits]
            par_val = bits[1 + data_bits] if n_parity else None
            stop_val = _level_at(t_start + (head_bits + n_stop * 0.5) * bit_time,
                                 idle_high)
            # LSB first 组装数据
            data_int = sum((1 << j) for j, b in enumerate(data_vals) if b)
            # 奇偶校验
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
        读取指定 RX 通道波形并做软件 UART 帧定位。

        :return: (frames, (time_axis, volts))  frames 见 decode_uart_waveform
        """
        t, v = self.get_waveform(rx_channel, ascii_format=ascii_format)
        frames = self.decode_uart_waveform(t, v, baud=baud, data_bits=data_bits,
                                           parity=parity, stop_bits=stop_bits,
                                           idle=idle, threshold=threshold)
        return frames, (t, v)

    @staticmethod
    def pick_uart_frame(frames, which="trigger", index=0):
        """
        从解码帧列表中挑选用于 ZOOM 的一帧。

        :param which: 'trigger' -> 最靠近触发点 (t=0) 的一帧 (串行总线触发时通常即触发帧);
                      'first'/'index' -> 取列表第 index 帧; 'last' -> 最后一帧
        :return: 帧 dict 或 None
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
        由一帧计算自动 ZOOM 的水平窗口 (自动框住该 UART 帧)。

        :param margin_bits: 帧前后额外保留的空闲位数量
        :param min_span:    最小整屏时间 (s), 避免放大过深
        :return: dict(t_center, span, s_per_div, t_start_zoom, t_stop_zoom) 或 None
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
    # 3) PC 端: 波形 ZOOM 绘图 (matplotlib)
    # ------------------------------------------------------------------
    @staticmethod
    def _plot_waveform_png(t, v, out_path, window=None, frame=None,
                           title="", show_full_trace=False, dpi=150):
        """
        将 (t, v) 波形绘制为 PNG (核心绘图函数, 静态, 便于离线测试)。

        :param window:          (t0, t1) 放大区间, None 表示全貌
        :param frame:           UART 帧 dict, 用阴影+竖线标出帧区域
        :param show_full_trace: True 且指定 window 时, 用浅色画出完整波形作为背景
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
        读取指定通道波形并保存 PNG; 给定 window=(t0, t1) 时只放大绘制该时间区间。

        :return: 生成的 PNG 路径
        """
        if add_timestamp:
            out_path = self._stamp(out_path)
        self._ensure_dir(out_path)
        t, v = self.get_waveform(channel, ascii_format=ascii_format)
        title = title or f"MXO4 CH{self._ch(channel)} Waveform"
        self._plot_waveform_png(t, v, out_path, window=window, frame=None,
                                title=title, show_full_trace=show_full_trace)
        print(f"波形窗口图已保存: {out_path}")
        return out_path

    def save_uart_zoom_png(self, rx_channel, out_path, baud=115200, data_bits=8,
                           parity=UARTParity.NONE, stop_bits=STOPBit.ONE_BIT,
                           idle=UARTPOLarity.IDLHigh, threshold=1.65,
                           which="trigger", margin_bits=2.0, min_span=None,
                           ascii_format=False, add_timestamp=False,
                           show_full_trace=True, time_volts=None):
        """
        PC 端 ZOOM: 读取 RX 通道波形 -> 软件定位 UART 帧 -> 自动放大保存 PNG。

        :param rx_channel:    RX 通道号 (UART 波形所在通道, 例如 1)
        :param out_path:      输出 PNG 路径 (自动加 _zoom 后缀与可选时间戳)
        :param which:         选帧方式, 见 pick_uart_frame ('trigger' 默认)
        :param margin_bits:   帧前后保留的空闲位数量
        :param time_volts:    可选 (t, v), 提供时不再重复读取仪器波形
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
            print(f"警告: CH{ch} 波形中未定位到 UART 帧, 保存全貌波形。")
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
        print(f"UART 帧自动 ZOOM 图已保存: {zoom_path}  "
              f"(帧#{frame['index']}: 0x{frame['data_hex']} '{frame['data_ascii']}', "
              f"t = {frame['t_start']:.3e} ~ {frame['t_stop']:.3e} s)")
        return zoom_path, frame, win
##############################################################################################
##############################################################################################
##############################################################################################
    @staticmethod
    def _channel_list(channel):
        """
        将 channel 参数归一化为通道列表。

        支持: int/str 单通道; list/tuple 多通道; 逗号分隔字符串 (例如 '1,2')。
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
        直接从仪器读取单通道波形数据, 返回 (time_axis, volts)。

        与 :meth:`save_waveform_csv_direct` 使用相同的分块传输读取逻辑,
        但不写文件, 供多通道汇总使用。
        """
        ch = self._ch(channel)
        hdr = self.get_waveform_header(channel)
        self.opc_timeout = 5000
        if ascii_format:
            start = time.time()
            self.write_str("FORM:DATA ASC")
            self.data_chunk_size = 100000  # 按 100k 字节分块传输 (默认)
            print('Now start to transfer ASCII waveform data. Please wait for about 120 seconds...')
            data = self.query_bin_or_ascii_float_list(f"CHANnel{ch}:DATA:VALues?")
            print(f'ASCII waveform transfer elapsed time: {time.time() - start:.3f}sec')
            volts = data
        else:
            start = time.time()
            self.write_str("FORMat:DATA REAL,32;:FORMat:BORDer LSBFirst")
            self.bin_float_numbers_format = BinFloatFormat.Single_4bytes
            self.data_chunk_size = 100000  # 按 100k 字节分块传输 (默认)
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
        将多通道波形数据写入同一 CSV 文件。

        列: Time(s), CH<x>(V), CH<y>(V), ...
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
        print(f"波形已导出: {pc_path}  (共 {n} 点)")

    def _plot_waveforms(self, data, pc_path, channels):
        """
        用 matplotlib 将多通道波形描点绘制为 PNG (每个通道一条曲线 + 图例)。
        """
        try:
            import matplotlib
            matplotlib.use("Agg")          # 无界面后端, 便于在脚本/无显示环境运行
            import matplotlib.pyplot as plt
            root, ext = os.path.splitext(pc_path)
            pc_path_plot = f"{root}.png"   # 强制保存为 PNG 图片
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
            print(f"波形图片已保存: {pc_path_plot}  (共 {n} 点)")
        except ImportError:
            print("未安装 matplotlib, 跳过波形绘图。")

    def save_waveform_csv(self, channel, pc_path=None, instr_path=None, ascii_format=False,
                          add_timestamp=True, filesave=None, localfile=None):
        """
        将单通道或多通道波形导出为 CSV 文件, 并用 matplotlib 描点绘图。

        CSV 列: Time(s), CH<x>(V), CH<y>(V), ...

        :param channel:       通道号 (int/str) 或通道列表/元组 (例如 [1, 2] 或 '1,2')
        :param pc_path:       PC 上的 CSV 保存路径
        :param instr_path:    仪器上的保存目录或路径 (filesave=True 时使用)
        :param ascii_format:  True 使用 ASCII 传输, False 使用 float32 二进制 (快)
        :param add_timestamp: True 时在文件名中自动加入时间戳
        :param filesave:      False 直接读取; True 先经仪器文件保存再下载
        :param localfile:     filesave=True 时是否保留仪器上的临时文件
        :return: pc_path
        """
        channels = self._channel_list(channel)
        if not channels:
            raise ValueError("save_waveform_csv: channel 不能为空")
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
                # 仪器端 CSV 每次只能导出一个源, 多通道需在 PC 端合并写回
                self._write_waveforms_csv(pc_path, channels, data)

        self._plot_waveforms(data, pc_path, channels)
        return pc_path

    def save_waveforms_csv(self, channels, filename, ascii_format=False):
        """
        将多通道波形导出为同一 CSV 文件。

        列: Time(s), CH<x>(V), CH<y>(V), ...
        """
        data = self.get_waveforms(channels, ascii_format=ascii_format)
        # 以第一个通道的时间轴为基准
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
        print(f"多通道波形已导出: {filename}  (共 {n} 点)")
        return filename

    def save_waveform_binary(self, channel, filename, add_timestamp=True):
        """
        将波形原始电压值保存为二进制文件 (float32, 小端)。

        同时生成同名的 .txt 头文件记录采样点数与时间范围。

        :param add_timestamp: True 时在文件名中自动加入时间戳
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
        print(f"原始波形已保存: {filename} / {head_file}")
        return filename

    def save_waveform_image(self, filename, fmt="png", add_timestamp=True,
                          instr_dir=None, filesave=True,localfile=True):
        """
        将波形截屏保存为图片文件 (整合了原 save_screenshot 的两种保存方式)。

        :param filename:      波形图片保存路径 (建议扩展名 .png)
        :param fmt:           截屏图片格式 (PNG/BMP/JPG/GIF/TIFF)
        :param add_timestamp: True 时在文件名中自动加入时间戳
        :param filesave:      False 直接获取截屏数据 (HCOPy:DATA?); True 先在仪器上
                              保存文件再回传 PC (HCOPy:DESTination MMEM)
        :param instr_dir:     filesave=True 时在仪器上创建的临时文件夹名称
        :param localfile:     True 时将文件保存到本地
        :return: 生成的图片路径
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
        从示波器下载文件到 PC (``MMEMory:DATA?``)。

        对于大文件，PyVISA 的 ``query_binary_values`` 可能受超时和数据块解析影响；
        这里先提高超时与 chunk size，若仍失败则回退到 ``write() + read_raw()``
        并手动解析 SCPI 二进制块头 ``#N<length><data>`` 进行下载。

        :param instr_path: 示波器上的文件路径
        :param pc_path:    PC 上的保存路径
        :param localfile:  是否保留仪器上的临时文件
        :return: PC 文件路径
        """
        # self._ensure_dir(pc_path)
        # drives = self.get_drives()
        # base = (drives[0] if drives else "/home/storage/userData").rstrip("/")
        # instr_file = f"{base}/{instr_dir}/screenshot.{fmt.lower()}"
        # instr_file = self._stamp(instr_file)
        # self.opc_timeout = 600000  # 10 分钟5秒
        # self.wait_opc(self.opc_timeout)
        self._ensure_dir(pc_path)
        print(f"文件是否存在: {self.file_exists(instr_path)}")
        # time.sleep(5)
        self.read_file_from_instrument_to_pc(instr_path, pc_path, False)
        print(f"文件已下载到 PC: {pc_path}")
        return pc_path

    def save_waveform_csv_via_instrument(self, channel, pc_path=None, instr_path=None,
                                         scope="ALL", localfile=None):
        """
        方式一 (组合): 先将波形导出为 CSV 保存到示波器, 再下载到 PC。

        仪器端文件名与 PC 端文件名保持一致: 若 ``instr_path`` 为目录
        (例如 'temp_files'), 仪器端路径为 '<instr_path>/<pc_path 文件名>'。

        :param channel:    通道号
        :param pc_path:    PC 上的 CSV 保存路径
        :param instr_path: 仪器上的保存目录或路径 (可含子目录, 例如 'temp_files')
        :param scope:      导出范围: DISPlay / ALL / CURSor / GATE / MANual
        :param localfile:  是否保留仪器上的临时文件 (False 时删除)
        :return: (times, voltages) 时间与电压值列表
        """
        # 仪器端文件名与 PC 端文件名保持一致
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
        time.sleep(3)  # 等待仪器保存完成
        print(f"波形 CSV 已保存到示波器: {instr_full}")
        self.download_file(instr_full, pc_path, localfile=localfile)
        # 1. 解析 pc_path 对应的 CSV 文件, 得到时间和电压值
        times = []
        voltages = []
        with open(pc_path, "r", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过表头 (例如 "Time(s),CH1(V)")
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

        # 2. 若 localfile 为 False (或 None), 删除示波器上 instr_full 对应的文件
        if not localfile:
            try:
                self.write(f"MMEMory:DELete '{instr_full}'")
                print(f"已删除示波器上的临时文件: {instr_full}")
            except Exception as e:
                print(f"警告: 删除示波器文件失败 (忽略): {e}")

        # 3. 返回时间和电压值
        return times, voltages

       
#########################################################################################
#########################################################################################
#########################################################################################
    def save_waveform_csv_direct(self, channel,filename,ascii_format=True):
        """
        # 方式二: 直接从仪器读取波形数据, 在 PC 上保存 CSV (不在仪器上保存文件)。

        使用 ``CHANnel<n>:DATA:VALues?`` 读取 float32 二进制数据, 并用 numpy
        接收 (内存约为 Python list 的 1/8), 分块写入 CSV, 适合 10Mpts 大记录长度。

        :param channel:       通道号
        :param filename:      PC 上的 CSV 保存路径
        :return: (t, v), t 为时间轴 (s), v 为电压 (V), 均为 numpy 数组
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
            #     # 大记录长度传输耗时较长, 临时增大超时与读取块大小
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
        # 生成完整时间轴 (既用于写文件, 也作为返回值)
        if n > 1:
            t = np.linspace(xstart, xstop, n, dtype=np.float64)
        else:
            t = np.array([xstart], dtype=np.float64)

        with open(filename, "w", newline="") as f:
            f.write(f"Time(s),CH{ch}(V)\n")
            # 分块写入, 避免一次性拼接巨大字符串占用内存
            chunk = 100_000
            for i in range(0, n, chunk):
                end = i + chunk
                lines = [f"{tt:.9e},{vv:.6f}" for tt, vv in zip(t[i:end], volts[i:end])]
                f.write("\n".join(lines) + "\n")
        print(f"波形已导出: {filename}  (共 {n} 点)")
        return t, volts

    def get_drives(self):
        """
        查询仪器可用的存储路径 ``MMEMory:DRIVes?``, 返回路径列表。

        MXO4 通常返回用户数据目录, 例如 ``['/home/storage/userData']``;
        外接 U 盘等存储设备时可能返回多个路径。
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
        方式一: 直接获取截图数据 (``HCOPy:DATA?``), 无需在仪器上保存文件。

        该命令直接返回 PNG 图片的二进制数据, 写入 ``pc_path``。
        不涉及仪器文件系统, 因此不存在找不到仪器临时路径的问题。

        :param pc_path: PC 上的保存路径 (建议扩展名 .png)
        :return: 生成的图片路径
        """
        self._ensure_dir(pc_path)
        # data = self.instrument.query_binary_values("HCOPy:DATA?", datatype="B")
        data = self.query_bin_block_with_opc("HCOPy:DATA?",timeout =6000) 
        with open(pc_path, "wb") as f:
            f.write(bytes(data))
        print(f"截屏已保存 (直接方式): {pc_path}")
        return pc_path

    def  save_screenshot_via_file(self, pc_path, fmt="PNG", instr_dir=None, localfile = False):
        """
        方式二: 在仪器上创建临时文件夹保存截图, 再回传 PC。

        通过 ``MMEMory:DRIVes?`` 自动查询仪器的用户数据目录, 在其中创建
        ``instr_dir`` 文件夹并保存截图, 用 ``MMEMory:DATA?`` 回传到 PC,
        最后删除仪器上的临时文件。

        :param pc_path:   PC 上的保存路径
        :param fmt:       图片格式 (PNG / JPG / BMP / GIF / TIFF)
        :param instr_dir: 在仪器上创建的临时文件夹名称
        :return: 生成的图片路径
        """
        self._ensure_dir(pc_path)
        drives = self.get_drives()
        base = (drives[0] if drives else "/home/storage/userData").rstrip("/")
        instr_file = f"{base}/{instr_dir}/screenshot.{fmt.lower()}"
        instr_file = self._stamp(instr_file)
        # 创建临时文件夹 (已存在则忽略错误)
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
        # 清理仪器上的临时文件 (失败也不影响结果)
        self.write_str("HCOPy:DESTination1 MMEM")
        self.write_str("HCOPy:DEVice1:LANGuage PNG")
        self.write_str(f"MMEMory:NAME '{instr_file}'")
        self.write_str_with_opc("HCOPy:IMMediate1")
        time.sleep(3)  # 等待仪器生成文件
        self.read_file_from_instrument_to_pc(instr_file, pc_path)
        print(f'Transferred screen shot to {pc_path}')
        try:
            if not localfile:
                self.write(f"MMEMory:DELete '{instr_file}'") # 删除仪器上的临时文件
                time.sleep(3)  # 等待删除完成
                print(f"已删除示波器上的临时文件: {instr_file}")
        except Exception as e:
            print(f"警告: 删除示波器文件失败 (忽略): {e}")
        print(f"截屏已保存 (文件方式): {pc_path}")
        return pc_path
#########################################################################################
#########################################################################################
#########################################################################################
    @staticmethod
    def _timestamp():
        """返回时间戳字符串, 例如 20260821_153000_123 (精确到毫秒)。"""
        return time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"

    @staticmethod
    def _stamp(path, ts=None):
        """在文件名 (不含扩展名) 后追加时间戳, 返回新路径。"""
        ts = ts or MXO4._timestamp()
        root, ext = os.path.splitext(path)
        return f"{root}_{ts}{ext}"

    @staticmethod
    def _ensure_dir(path):
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.exists(d):
            os.makedirs(d)


# ==============================================================================
# 示例
# ==============================================================================
if __name__ == "__main__":
    # 修改为你的示波器 IP / VISA 资源字符串
    RESOURCE = "TCPIP::192.168.18.100::INSTR"
    # 波形与 CSV 输出目录
    PC_OUT_DIR = "waveforms"
    INSTR_FILE_OUT_DIR = "temp_files"
    INSTR_IMAGE_DIR = "temp_shots"
    # 记录代码运行开始时间
    start_time = time.time()
    print(f"程序开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    mxo = MXO4(RESOURCE, timeout=10000)

    # mxo.download_file("/home/storage/userData/Waveforms/Waveform_2026-08-24_0_075310.csv", "edge_ch1_20260831_192344_996.csv")
    try:
        for i in range(100):
            mxo.clear_status()
            mxo.reset()
            mxo.set_display_update(True)
            mxo.opc_timeout = 60000 
            # ---- 1. 通道与时基配置 ----
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
            
            mxo.sample_rate_mode(SampleRateMode.MANUAL)   #手动配置
            # mxo.sample_rate_mode(SampleRateMode.AUTO)   #自动配置
            print("当前采样率模式:", mxo.get_sample_rate_mode())
            # 辅助函数示例：按时基自动估算并配置采样率与 1 Mpts
            print("自动配置采样:", mxo.auto_sampling_for_timebase(2e-4, points="1M", wait=True))
            mxo.set_display_brightness(brightness=100)
            # print(mxo.get_display_brightness())
            mxo.set_signal_intensity(100)       # 波形亮度设为 100%
            # print(mxo.get_signal_intensity())  # 读取当前波形亮度

            # ---- 2. 边沿触发: 保存波形 → 导出 CSV ----
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
            # 假设 UART RX 接通道1, TX 接通道2, 波特率 115200
            mxo.configure_uart_decode(bus_number=1, rx="C1", tx="C2", baud=115200)  
            mxo.trigger_mode(TriggerMode.NORMAL)
            mxo.configure_uart_trigger(bus_number=1, source="SBUS1")
            mxo.single_and_wait(10000)
            time.sleep(3)  # 等待仪器完成解码
            mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart.png"),fmt="png",add_timestamp=True,instr_dir= INSTR_IMAGE_DIR,filesave=False,localfile=True)
            mxo.save_waveform_csv(2, os.path.join(PC_OUT_DIR, "uart.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)
            

        #     # ---- 3b. UART 波形 ZOOM (仅示波器端) + 上升沿/幅值测量 + 光标 ----
        #     # 1) 仪器端 ZOOM: 放大到一帧 UART 数据 (按协议参数估算, 无需回读波形)
        #     uart_zoom = mxo.zoom_uart_display(baud=115200, data_bits=8,
        #                                     parity=UARTParity.NONE,
        #                                     stop_bits=STOPBit.ONE_BIT,
        #                                     margin_bits=2.0, reacquire=True)
        #     frame_time = uart_zoom["frame_time"]

        #     # 2) 自动测量: CH1(RX) 上升沿时间 + 幅值 (+ 低/高电平用于放置水平光标)
        #     mxo.configure_rise_time_measurement(measure_index=4, source="C2", enable=True)
        #     mxo.configure_amplitude_measurement(measure_index=5, source="C2", enable=True)
        #     mxo.configure_measurement(measure_index=6, source="C2", main="LOW", enable=True)  
        #     mxo.configure_measurement(measure_index=7, source="C2", main="HIGH", enable=True)
        #     mxo.wait_opc(5000)          # 等待测量刷新, 避免读到旧值
        #     rise_time = mxo.get_measurement_result(4)
        #     amplitude = mxo.get_measurement_result(5)
        #     print(f"CH2 上升沿时间 (RTIMe):   {rise_time} s")
        #     print(f"CH2 幅值 (AMPLitude):     {amplitude} V")
        #     try:
        #         low_level = float(mxo.get_measurement_result(6))
        #         high_level = float(mxo.get_measurement_result(7))
        #     except (ValueError, TypeError):
        #         low_level, high_level = 0.0, 5.0

        #     # 3) 光标测量: 垂直 X1/X2 量一帧时间, 水平 Y1/Y2 量幅值 (显示可选)
        #     mxo.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
        #                         x1=0.0, x2=frame_time, y1=low_level, y2=high_level,
        #                         show=True, show_values=True, tracking=False)
        #     mxo.wait_opc(2000)
        #     try:
        #         dx = mxo.get_cursor_delta_x(1)
        #         dy = mxo.get_cursor_delta_y(1)
        #         print(f"光标 ΔX (一帧时间): {dx:.6e} s")
        #         print(f"光标 ΔY (幅值):     {dy:.4f} V")
        #     except Exception as exc:
        #         print(f"读取光标结果失败 (忽略): {exc}")
            
        #     # 4) 截屏 (放大后的波形 + 测量 + 光标)
        #     mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart_zoom_meas_ch1.png"),
        #                             fmt="png", add_timestamp=True,
        #                             instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
            
        #     # 5) 隐藏 SBUS1 解码结果表, 露出自动测量结果表 (RMS/FREQuency/AMPLitude/RTIMe...), 再截一张图
        #     mxo.bus_result_table(bus_number=1, on=False)   # 关闭 SBUS1 解码表
        #     mxo.wait_opc(50000)
        #     time.sleep(3)
        #     mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "uart_meas_result_ch1.png"),
        #                             fmt="png", add_timestamp=True,
        #                             instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
        #     mxo.bus_result_table(bus_number=1, on=True)    # 恢复解码表显示

            # ---- 4. I2C 解码 + 串行总线触发: 保存波形 → 导出 CSV ----
            # 假设 I2C SDA 接通道1, SCL 接通道2
            # mxo.channel_label(1, "SDA")
            # mxo.channel_label(2, "SCL")
            # mxo.configure_i2c_decode(bus_number=2, scl="C2", sda="C1")
            # mxo.trigger_mode(TriggerMode.NORMAL)
            # mxo.configure_i2c_trigger(bus_number=2, condition=None)
            # mxo.single_and_wait(10000)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            # mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "i2c_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=True)

            # # ---- 4b. I2C 波形 ZOOM (仅示波器端) + 上升沿/幅值测量 + 光标 ----
            # # 1) 仪器端 ZOOM: 放大到一帧 I2C 数据 (按协议参数估算, 无需回读波形)
            # i2c_zoom = mxo.zoom_i2c_display(scl_freq=150000, frame_bits=9,
            #                                 margin_bits=2.0, reacquire=True)
            # i2c_frame_time = i2c_zoom["frame_time"]

            # # 2) 自动测量: CH1(SDA)/CH2(SCL) 上升沿时间 + 幅值 (+ 低/高电平用于放置水平光标)
            # mxo.configure_rise_time_measurement(measure_index=4, source="C1", enable=True)
            # mxo.configure_amplitude_measurement(measure_index=5, source="C1", enable=True)
            # mxo.configure_measurement(measure_index=6, source="C1", main="LOW", enable=True)
            # mxo.configure_measurement(measure_index=7, source="C1", main="HIGH", enable=True)
            # mxo.configure_rise_time_measurement(measure_index=8, source="C2", enable=True)
            # mxo.configure_amplitude_measurement(measure_index=9, source="C2", enable=True)
            # mxo.configure_measurement(measure_index=10, source="C2", main="LOW", enable=True)
            # mxo.configure_measurement(measure_index=11, source="C2", main="HIGH", enable=True)
            # mxo.wait_opc(5000)          # 等待测量刷新, 避免读到旧值
            # rise_c1 = mxo.get_measurement_result(4)
            # amp_c1 = mxo.get_measurement_result(5)
            # rise_c2 = mxo.get_measurement_result(8)
            # amp_c2 = mxo.get_measurement_result(9)
            # print(f"CH1(SDA) 上升沿时间 (RTIMe): {rise_c1} s,  幅值 (AMPLitude): {amp_c1} V")
            # print(f"CH2(SCL) 上升沿时间 (RTIMe): {rise_c2} s,  幅值 (AMPLitude): {amp_c2} V")
            # try:
            #     low_c1 = float(mxo.get_measurement_result(6))
            #     high_c1 = float(mxo.get_measurement_result(7))
            # except (ValueError, TypeError):
            #     low_c1, high_c1 = 0.0, 5.0

            # # 3) 光标测量: 垂直 X1/X2 量一帧时间, 水平 Y1/Y2 量幅值 (显示可选)
            # mxo.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
            #                      x1=0.0, x2=i2c_frame_time, y1=low_c1, y2=high_c1,
            #                      show=True, show_values=True, tracking=False)
            # mxo.wait_opc(5000)
            # try:
            #     dx = mxo.get_cursor_delta_x(1)
            #     dy = mxo.get_cursor_delta_y(1)
            #     print(f"光标 ΔX (一帧时间): {dx:.6e} s")
            #     print(f"光标 ΔY (幅值):     {dy:.4f} V")
            # except Exception as exc:
            #     print(f"读取光标结果失败 (忽略): {exc}")

            # # 4) 截屏 (放大后的波形 + 测量 + 光标)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c_zoom_meas.png"),
            #                         fmt="png", add_timestamp=True,
            #                         instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)

            # # 5) 隐藏 SBUS2 解码结果表, 露出自动测量结果表 (RMS/FREQuency/AMPLitude/RTIMe...), 再截一张图
            # mxo.bus_result_table(bus_number=2, on=False)   # 关闭 SBUS2 解码表
            # mxo.wait_opc(50000)
            # time.sleep(3)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "i2c_meas_result.png"),
            #                         fmt="png", add_timestamp=True,
            #                         instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
            # mxo.bus_result_table(bus_number=2, on=True)    # 恢复解码表显示
          
            
        
            # ---- 5. SPI 解码 + 串行总线触发: 保存波形 → 导出 CSV ----
            # 假设 SCLK=C1, MOSI=C2, MISO=C3, SS=C4
            # mxo.configure_spi_decode(bus_number=3, sclk="C1", mosi="C2", miso="C3", ss="C4")
            # mxo.trigger_mode(TriggerMode.NORMAL)
            # mxo.configure_spi_trigger(bus_number=3, condition="MOSI")
            # mxo.single_and_wait(10000)
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "spi_ch1.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            # mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "spi_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=True)
            # print(f"SPI 解码结果:\n{mxo.get_decoded_data(3)}")

            # ---- 6. QSPI 解码: 保存波形 → 导出 CSV ----
            # 假设 SCLK=C1, CS=C2, IO0=C3, IO1=C4, IO2=C5, IO3=C6

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
                           clock_source="D0",    # 触发时钟: 模拟 C1 或数字 D0
                           frame_enable=True, invert=False)
            mxo.single_and_wait(10000)
            mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "qspi.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
            mxo.save_waveform_csv(1, os.path.join(PC_OUT_DIR, "qspi_ch1.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=True,localfile=False)
            print(f"QSPI 解码结果:\n{mxo.get_decoded_data(4)}")

            # # ---- 6. 截屏保存 ----
            # mxo.save_waveform_image(os.path.join(PC_OUT_DIR, "screen.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=True)
    finally:
        mxo.close()

    # 记录代码运行结束时间, 并计算打印耗时  
    end_time = time.time()
    print(f"程序结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"运行耗时: {end_time - start_time:.3f} 秒")
