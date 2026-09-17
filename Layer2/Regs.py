#!/usr/bin/env python  
# -*- coding: utf-8 -*-

""" 
@version: v1.0 
@author: BaiLi
@license: Apache Licence, modefied by Jiangwei.li 
@contact: BaiLi@queentest.com 
@site: http://www.queentest.com/index.html 
@software: Examples for all QT11xx DAQ cards 
@file: Regs.py 
@time: 2017/5/17 19:20 
"""

def KILO(k): return (  1000 * (k))

def MEGA(m): return (  1000 * 1000 * (m))

def GIGA(g): return (  1000 * 1000 * 1000 * (g))

def KILO_B(k): return (  1024 * (k))

def MEGA_B(m): return (  1024 * 1024 * (m))

def GIGA_B(g): return (  1024 * 1024 * 1024 * (g))

PingPangBufIsOverFlow     = 0x00000000 # true is overflow

SRate                     = 0x00000001 # Sample rate in Hz

part_number              = 0x00000002 # 具体编号，用于区分不同性能
channel_number           = 0x00000003 # AD/DA物理通道数目
product_number           = 0x00000004 # 1125,1128,1130,1135,1138,1156,etc.-1 if undefined.
couple_type              = 0x00000005 # 0xAC:AC;0xDC:DC;0xDB:DC and VG supported
product_model            = 0x00000006 # 1125AC4,1125DC1,1125DC2,1125DC4,1128AC1,1128AC2,
                                      # 1130AC1,1130AC2,1130AC4,
                                      # 1135AC1,1135AC2,1135AC4,
                                      # 1138AC1,1138AC2,1138AC4,1138AC6,1138AC8,
                                      # 1138DC1,1138DC2,1138DC4
empty                     = 0x00000007
full                      = 0x00000008

iCardNo                   = 0x00000009
uiErrCode                 = 0x0000000a
EachTransferLen_Tx        = 0x0000000b
EachTransferLen_Rx        = 0x0000000c
DmaCnt_Tx                 = 0x0000000d
DmaCnt_Rx                 = 0x0000000e
Remain_Tx                 = 0x0000000f
Remain_Rx                 = 0x00000010
TransferTimeOut_Tx        = 0x00000011
TransferTimeOut_Rx        = 0x00000012
CurTransferLen_Tx         = 0x00000013
KeepRun                   = 0x00000014 # true if board is running; false if data sample and transfer is stopped.
bThreadWriteBuf           = 0x00000015 # true if ThreadWriteBuf is alive; false if ThreadWriteBuf is dead
MaxEachDmaLenB            = 0x00000016 # DAM length in byte to notify a event

lSetChannels              = 0x00000017 # number of used channels for this run
SegmentCnt                = 0x00000018
SegmentSize               = 0x00000019 # TODO:change to uint type
PreSamples                = 0x0000001a
gABAMode                  = 0x0000001b

lResolution               = 0x0000001c # resolution of analog channels
lMaxADCValue              = 0x0000001d # maximum range, normally 2^(Resolution-1) but can be limited
lPathCount                = 0x0000001e # number of input paths
lRangeCount               = 0x0000001f # number of analog input ranges
NumGain                   = 0x00000020 # 增益档位个数 AC:1; DC:>=1
bInputTermAvailable       = 0x00000021 # input termination available
bDiffModeAvailable        = 0x00000022 # differential mode available
bACCouplingAvailable      = 0x00000023 # AC/DC coupling softwar selectable
bBWLimitAvailable         = 0x00000024 # bandwidth limit available
bOffsPercentMode          = 0x00000025 # offset programmed in percent of range
unChOpt                   = 0x00000026 # ADC channel mode for QT1125 only
InputChannelMask          = 0x00000027 # Input Channel selection bit mask
DataFormat                = 0x00000028 # 0: offset binary code; 1: two's complement code
bForceIOdelay             = 0x00000029 # Flag to indicate whether force io delay or not

lMaxDACValue              = 0x0000002a # maximum range, normally 2^(Resolution-1) but can be limited
bGainProgrammable         = 0x0000002b # programmable gain available
bOffsetProgrammable       = 0x0000002c # programmable offset available
bFilterAvailable          = 0x0000002d # programmable filters available
bStopLevelProgrammable    = 0x0000002e # programmable stop level available

