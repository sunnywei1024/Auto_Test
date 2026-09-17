#!/usr/bin/env python  
# -*- coding: utf-8 -*-

""" 
@version: v1.0 
@author: BaiLi, modified by Jiangwei.li
@license: Apache Licence  
@contact: BaiLi@queentest.com 
@site: http://www.queentest.com/index.html 
@software: Examples for all QT11xx DAQ cards 
@file: daq_fifo_single.py 
@time: 2017/5/18 11:10 
"""
# Import matlab package
import numpy as np
import matplotlib.pyplot as plt
from ctypes import *
from Layer1.pyQueen import *
from Layer2.Comm import *
from Layer2.QTErrors import *
from Layer2.Regs import *
import time
import sys

# Import Queentest driver functions
# from pyQueentest import *

# ***********************************************************************
# * InitCard
# ***********************************************************************


def InitCard(myapi,unCardIdx):
    # ####################################
    # ##Clock parameters
    Fref = 10000000  # Reference clock frequency.
    RefClkMode = QTFM_COMMON_CLOCK_REF_MODE_2  # Change to QTFM_COMMON_CLOCK_REF_MODE_1 if external reference clock is required.
    ADCClkMode = QTFM_COMMON_ADC_CLOCK_MODE_0  # Change to QTFM_COMMON_ADC_CLOCK_MODE_1 if external sampling clock is required.

    CurrInputRange = double(QTFM_INPUT_RANGE_1)  # +full-scale in mV
    OffSet = double(0)  # [-fullscale,+fullscale] in uV

    # ####################################
    # ##Open card
    PyQueen.QTChkRT(myapi.QTOpenBoard(unCardIdx))
    PyQueen.QTChkRT(myapi.QTResetBoard(unCardIdx))
    # ####################################
    # Take max sample rate as default. Users feel free to change it by uncomment this line then assign new value.
    # QTSetRegs_i32(unCardIdx,SRate,250000000)
    # ####################################
    # ##Setup clock
    PyQueen.QTChkRT(myapi.QTClockSet(unCardIdx, Fref, 1, 0, QTFM_COMMON_CLOCK_VCO_MODE_0, RefClkMode, ADCClkMode, 1))
    # Get product information
    prod_num = int32(0)
    init_adc = int32(0)
    couple = int32(0)
    PyQueen.QTChkRT(myapi.QTGetRegs_i32(unCardIdx, product_number, byref(prod_num)))
    PyQueen.QTChkRT(myapi.QTGetRegs_i32(unCardIdx, bForceIOdelay, byref(init_adc)))
    PyQueen.QTChkRT(myapi.QTGetRegs_i32(unCardIdx, couple_type, byref(couple)))

    # ##Setup AFE
    unWorkMode = uint32(0)
    if init_adc.value == 1:
        unWorkMode = 0
    else:
        unWorkMode = 256
    if prod_num.value != 0x1125:
          PyQueen.QTChkRT (myapi.QTAdcModeSet(unCardIdx, 0, unWorkMode, 0))

    # ##Setup Input range and offset
    if couple.value == 0xDC:
        # ##Set analog input range first then offset
        PyQueen.QTChkRT(myapi.QTChannelRangeSet(unCardIdx, -1, CurrInputRange))
        # ##Set analog offset
        PyQueen.QTChkRT(myapi.QTChannelOffsetSet(unCardIdx, -1, OffSet))

    return RES_SUCCESS

# ************************************************************************#
# * QT_FifoMultiple                                                         *#
# ************************************************************************#


def QT_StdSingle (myapi, unCardIdx, loop):
    ##########################################################################
    ####Acquisition parameters
    NotifySizeB = MEGA_B(1)  # #The NotifySizeB defines the amount of bytes after which an interrupt should be generated.
    PreTriggerLen = 0  # #pre-trigger length in samples
    DataFormat = 1  # #0:offset binary 1:two's complement

    ##########################################################################
    # #Reset to clear FIFO in FPGA
    PyQueen.QTChkRT(myapi.QTResetBoard(unCardIdx))
    # Set notify size in byte
    PyQueen.QTChkRT(myapi.QTSetNotifySizeB(unCardIdx, NotifySizeB))
    # #Analog input enable. Run the command multiple times for other channels
    PyQueen.QTChkRT(myapi.QTInputChannelSet(unCardIdx, CHANNEL_0, 0, 0, 0, 0, 1))
    # #QTChkRT(QTInputChannelSet(unCardIdx, CHANNEL_1, 0, 0, 0, 0, 0))
    # #Select data format between offset binary code and two's complement
    PyQueen.QTChkRT(myapi.QTDataFormatSet(unCardIdx, DataFormat))
    # ###Setup work mode, acquisition parameters
    PyQueen.QTChkRT(myapi.QTABAModeSet(unCardIdx, ABA_NORMAL_MODE, 48, 1))
    # 设置采集模式
    PyQueen.QTChkRT(myapi.QTWorkModeSet(unCardIdx, 0, PreTriggerLen, 1,
                          (QTFM_COMMON_BOARD_WORK_MODE_FIFO_SINGLE_LOOPBUF | QTFM_COMMON_TRIGGER_MODE_EDGE), 0, 0))   # 有限点单次触发
    # 设置时间戳参数
    SampleRate = int32(0)
    PyQueen.QTChkRT(myapi.QTGetRegs_i32(unCardIdx, SRate, byref(SampleRate))) #读取采样率
    PyQueen.QTChkRT(myapi.QTTimestampSet(unCardIdx, 0, 0, 0, SampleRate, 0))
    # ###Setup trigger source and types
    PyQueen.QTChkRT(myapi.QTSoftTriggerSet(unCardIdx, QTFM_COMMON_TRIGGER_TYPE_RISING_EDGE, 1))
    # 内部周期性脉冲触发
    # QTChkRT(QTPulseTriggerSet(unCardIdx, QTFM_COMMON_TRIGGER_TYPE_RISING_EDGE, 0x20, 2 * SegmentLen, 1))    # 上升沿、内部脉冲触发
    # 外部触发
    ##QTChkRT(QTExtTriggerSet(unCardIdx, QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_1, QTFM_COMMON_TRIGGER_TYPE_RISING_EDGE, 1))

    # ###Define the total amount of data and allocate memory as an intermediate buffer
    Memsize = uint64(10 << 30)  # Total data length to get from card
    PerBufSize = int(10 << 20)  # buffer size
    pDataBuf0 = create_string_buffer(PerBufSize)
    # ###Check if buffer size is aligned with NotifySizeB
    if PerBufSize % NotifySizeB > 0:
        sys.stdout.write("data buffer size is not aligned with parameter NotifySizeB\n")
        exit()

    # ###Get PCIe DMA ready waiting for trigger events
    PyQueen.QTChkRT(myapi.QTStart(unCardIdx, QTFM_COMMON_TRANSMIT_DIRECTION_BRD2PC, 1, 0xffffffff, 0))

    ####Receive sample data to buffer
    RecvDataLen = int64(0)
    AvailableDate = int64(0)
    BufOverflow = int32(-1)
    NoBytesOverwritten = uint32(0)
    while RecvDataLen.value < Memsize.value:
        # 查询有效数据量
        myapi.QTBufStatusGet(unCardIdx, byref(AvailableDate), byref(BufOverflow), byref(NoBytesOverwritten))
        # 如果数据溢出，停止取数，跳出循环
        if (BufOverflow.value > 0) or (NoBytesOverwritten.value > 0):
            break
        RecvDataLen.value += NoBytesOverwritten.value
        # 有效数据量是否满足要求
        if AvailableDate.value < NotifySizeB.real:
            continue
        # 将指定长度的数据循环写入到缓存buffer中。如果数据量大于buffer size，则绕回并从头开始写
        PyQueen.QTChkRT(myapi.QTBufSDataGet(unCardIdx, addressof(pDataBuf0) + (RecvDataLen.value % PerBufSize), NotifySizeB))
        # 记录目前为止获取的数据总量
        RecvDataLen.value += NotifySizeB.real
        if RecvDataLen.value % (PerBufSize) == 0:
            print('RecvDataLen = %d(MB)' %(RecvDataLen.value >> 20))

    # #########################################################################
    # #Print error Info if overflows during acquisition
    # #########################################################################
    if BufOverflow.value > 0:
        sys.stdout.write("Samples data were lost! Either speed up buffer read rate or reduce sample rate\n")
    if NoBytesOverwritten.value > 0:
        sys.stdout.write("Samples data could be corrupted by overwritten!Either speed up buffer read rate or reduce sample rate\n")

     # plot data
    data = []
    # cast to pointer to 16bit integer
    if DataFormat.real == 1:
        pnData = cast(pDataBuf0, POINTER(c_int16))
    else:
        pnData = cast(pDataBuf0, POINTER(c_uint16))

    del pDataBuf0
    for i in range(0, PerBufSize/2):
        data.append(pnData[i])

    del pnData
    plt.figure(1)
    plt.clf()
    plt.plot(data, 'ro-')
    plt.grid(which='Major')
    plt.show()
    del data
    #  Stop acquisition and close card handle
    PyQueen.QTChkRT(myapi.QTStart(unCardIdx, QTFM_COMMON_TRANSMIT_DIRECTION_BRD2PC, 0, 0xffffffff, 0))
    return RES_SUCCESS

# ************************************************************************/
# * Test function                                                        */
# ************************************************************************/
def FIFO_Single_Test(myapi, temp, item_dir,**Parameters):

    NumOfBoard = int32(1)  # Specify the number of cards need to operate on.
    for i in range(0, NumOfBoard.value):
        loop = uint32(0)
        MaxLoop = uint32(1)  # define max loop count
        # Initialize card once
        PyQueen.QTChkRT(InitCard(myapi, i))
        # DAQ in loop
        while loop.value < MaxLoop.value:
            PyQueen.QTChkRT(QT_StdSingle(myapi, i, loop))
            loop.value += 1
        # Close card
        PyQueen.QTChkRT(myapi.QTCloseBoard(i))
