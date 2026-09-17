#!/usr/bin/env python  
# encoding: utf-8  

""" 
@version: v1.0 
@author: BaiLi,modified by Jiangwei.li
@license: Apache Licence  
@contact: BaiLi@queentest.com 
@site: http://www.queentest.com/index.html 
@software: Examples for all QT11xx DAQ cards 
@file: pyQueentest.py 
@time: 2017/5/17 10:50 
"""
import os
import platform
import sys
from ctypes import *

# load registers for easier access
# from Regs import *
# from Comm import *
# load errors for easier access
# from QTErrors import *

# define pointer aliases
int8  = c_int8
int16 = c_int16
int32 = c_int32
int64 = c_int64
char  = c_char
byte  = c_byte
longlong = c_longlong
double = c_double

ptr8  = POINTER(int8)
ptr16 = POINTER(int16)
ptr32 = POINTER(int32)
ptr64 = POINTER(int64)
pchar = c_char_p
ptrlonglong = POINTER(longlong)
ptrdouble = POINTER(double)

uint8  = c_uint8
uint16 = c_uint16
uint32 = c_uint32
uint64 = c_uint64
ubyte  = c_ubyte
ulonglong = c_ulonglong

uptr8  = POINTER(uint8)
uptr16 = POINTER(uint16)
uptr32 = POINTER(uint32)
uptr64 = POINTER(uint64)
upbyte = POINTER(ubyte)
ptrulonglong = POINTER(ulonglong)

class PyQueen(object):
    """Wrapper for the QueenTest dotNetQTDrv DLL.
    The DLL is loaded and all driver functions are bound in __init__.
    """

    def __init__(self):
        # determine bit width of os
        oPlatform = platform.architecture()
        if oPlatform[0] == '64bit':
            print("64bit OS")
            self.bIs64Bit = 1
        else:
            print("32bit OS")
            self.bIs64Bit = 0

        if os.name == 'nt':
            sys.stdout.write("Windows found")
            # The DLL is under the "common" folder next to this file:
            # common/x64 for 64-bit, common/Win32 for 32-bit
            _common_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "common")

            # define card handle type
            if self.bIs64Bit:
                # for unknown reasons c_void_p gets messed up on Win7/64bit,  but this works:
                self.drv_handle = POINTER(c_uint64)
                # Load DLL into memory.
                # use windll because all driver access functions use _stdcall calling convention under windows
                self.QueentestDll = windll.LoadLibrary(os.path.join(_common_dir, "x64", "dotNetQTDrv.dll"))
            else:
                self.drv_handle = c_void_p
                # Load DLL into memory.
                # use windll because all driver access functions use _stdcall calling convention under windows
                self.QueentestDll = windll.LoadLibrary(os.path.join(_common_dir, "Win32", "dotNetQTDrv.dll"))

            # load QTGetRegs_i32
            self.QTGetRegs_i32 = getattr(self.QueentestDll, "QTGetRegs_i32")
            self.QTGetRegs_i32.argtype = [(uint32, uint32, ptr32)]
            self.QTGetRegs_i32.restype = int32
            # load QTSetRegs_i32
            self.QTSetRegs_i32 = getattr(self.QueentestDll, "QTSetRegs_i32")
            self.QTSetRegs_i32.argtype = [(uint32, uint32, ptr32)]
            self.QTSetRegs_i32.restype = int32
            # load QTOpenBoard
            self.QTOpenBoard = getattr(self.QueentestDll, "QTOpenBoard")
            self.QTOpenBoard.argtype = [uint32]
            self.QTOpenBoard.restype = int32
            # load QTResetBoard
            self.QTResetBoard = getattr(self.QueentestDll, "QTResetBoard")
            self.QTResetBoard.argtype = [uint32]
            self.QTResetBoard.restype = int32
            # load QTCloseBoard
            self.QTCloseBoard = getattr(self.QueentestDll, "QTCloseBoard")
            self.QTCloseBoard.argtype = [uint32]
            self.QTCloseBoard.restype = int32
            # load QTAdcModeSet
            self.QTAdcModeSet = getattr(self.QueentestDll, "QTAdcModeSet")
            self.QTAdcModeSet.argtype = [uint32, uint32, uint32, uint32]
            self.QTAdcModeSet.restype = int32
            # load QTWorkModeSet
            self.QTWorkModeSet = getattr(self.QueentestDll, "QTWorkModeSet")
            self.QTWorkModeSet.argtype = [uint32, uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTWorkModeSet.restype = int32
            # load QTClockSet
            self.QTClockSet = getattr(self.QueentestDll, "QTClockSet")
            self.QTClockSet.argtype = [uint32, uint32, uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTClockSet.restype = int32
            # load QTSoftTriggerSet
            self.QTSoftTriggerSet = getattr(self.QueentestDll, "QTSoftTriggerSet")
            self.QTSoftTriggerSet.argtype = [uint32, uint32, uint32]
            self.QTSoftTriggerSet.restype = int32
            # load QTExtTriggerSet
            self.QTExtTriggerSet = getattr(self.QueentestDll, "QTExtTriggerSet")
            self.QTExtTriggerSet.argtype = [uint32, uint32, uint32, uint32]
            self.QTExtTriggerSet.restype = int32
            # load QTChannelTriggerSet
            self.QTChannelTriggerSet = getattr(self.QueentestDll, "QTChannelTriggerSet")
            self.QTChannelTriggerSet.argtype = [uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTChannelTriggerSet.restype = int32
            # load QTPulseTriggerSet
            self.QTPulseTriggerSet = getattr(self.QueentestDll, "QTPulseTriggerSet")
            self.QTPulseTriggerSet.argtype = [uint32, uint32, uint32, uint32, uint32]
            self.QTPulseTriggerSet.restype = int32
            # load QTTriggerSourceMaskSet
            self.QTTriggerSourceMaskSet = getattr(self.QueentestDll, "QTTriggerSourceMaskSet")
            self.QTTriggerSourceMaskSet.argtype = [uint32, uint32, uint32, uint32]
            self.QTTriggerSourceMaskSet.restype = int32
            # load QTInputChannelSet
            self.QTInputChannelSet = getattr(self.QueentestDll, "QTInputChannelSet")
            self.QTInputChannelSet.argtype = [uint32, uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTInputChannelSet.restype = int32
            # load QTTimestampSet
            self.QTTimestampSet = getattr(self.QueentestDll, "QTTimestampSet")
            self.QTTimestampSet.argtype = [uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTTimestampSet.restype = int32
            # load QTStart
            self.QTStart = getattr(self.QueentestDll, "QTStart")
            self.QTStart.argtype = [uint32, uint32, int32, uint32, int32]
            self.QTStart.restype = int32
            # load QTWaitDMA
            self.QTWaitDMA = getattr(self.QueentestDll, "QTWaitDMA")
            self.QTWaitDMA.argtype = [uint32, uint32, uint32]
            self.QTWaitDMA.restype = int32
            # load QTDMADone
            self.QTDMADone = getattr(self.QueentestDll, "QTDMADone")
            self.QTDMADone.argtype = [uint32, uint32]
            self.QTDMADone.restype = int32
            # load QTGetData
            self.QTGetData = getattr(self.QueentestDll, "QTGetData")
            self.QTGetData.argtype = [uint32, pchar, uint32, uint32]
            self.QTGetData.restype = int32
            # load QTADCCalibration
            self.QTADCCalibration = getattr(self.QueentestDll, "QTADCCalibration")
            self.QTADCCalibration.argtype = [uint32, uint32, uint32, uint32, uint32, uint32, uint32, uint32, uint32]
            self.QTADCCalibration.restype = int32
            # load QTWriteRegister
            self.QTWriteRegister = getattr(self.QueentestDll, "QTWriteRegister")
            self.QTWriteRegister.argtype = [uint32, uint32, uint32, uint32]
            self.QTWriteRegister.restype = int32
            # load QTReadRegister
            self.QTReadRegister = getattr(self.QueentestDll, "QTReadRegister")
            self.QTReadRegister.argtype = [uint32, uptr32, uptr32, uptr32]
            self.QTReadRegister.restype = int32
            # load QTStoreInit
            self.QTStoreInit = getattr(self.QueentestDll, "QTStoreInit")
            self.QTStoreInit.argtype = [uint32]
            self.QTStoreInit.restype = int32
            # load QTStoreParamSet
            self.QTStoreParamSet = getattr(self.QueentestDll, "QTStoreParamSet")
            self.QTStoreParamSet.argtype = [uint32, uint32, pchar, pchar, uint32, uint32, uint32, uint32]
            self.QTStoreParamSet.restype = int32
            # load QTStoreData
            self.QTStoreData = getattr(self.QueentestDll, "QTStoreData")
            self.QTStoreData.argtype = [uint32, pchar, int32]
            self.QTStoreData.restype = int32
            # load QTStoreStop
            self.QTStoreStop = getattr(self.QueentestDll, "QTStoreStop")
            self.QTStoreStop.argtype = [uint32]
            self.QTStoreStop.restype = int32
            # load QTStartGetFFTData
            self.QTStartGetFFTData = getattr(self.QueentestDll, "QTStartGetFFTData")
            self.QTStartGetFFTData.argtype = [uint32]
            self.QTStartGetFFTData.restype = int32
            # load QTStopGetFFTData
            self.QTStopGetFFTData = getattr(self.QueentestDll, "QTStopGetFFTData")
            self.QTStopGetFFTData.argtype = [uint32]
            self.QTStopGetFFTData.restype = int32
            # load QTGetDiskSpace
            self.QTGetDiskSpace = getattr(self.QueentestDll, "QTGetDiskSpace")
            self.QTGetDiskSpace.argtype = [uint32, ptrdouble, ptrdouble]
            self.QTGetDiskSpace.restype = int32
            # load QTGetDataToFFT
            self.QTGetDataToFFT = getattr(self.QueentestDll, "QTGetDataToFFT")
            self.QTGetDataToFFT.argtype = [uint32, upbyte, uint32, uint32]
            self.QTGetDataToFFT.restype = int32
            # load QTPollGetDataStatus
            self.QTPollGetDataStatus = getattr(self.QueentestDll, "QTPollGetDataStatus")
            self.QTPollGetDataStatus.argtype = [uint32]
            self.QTPollGetDataStatus.restype = int32
            # load QTWriteFileDone
            self.QTWriteFileDone = getattr(self.QueentestDll, "QTWriteFileDone")
            self.QTWriteFileDone.argtype = [uint32]
            self.QTWriteFileDone.restype = int32
            # load QTFreeMemrory
            self.QTFreeMemrory = getattr(self.QueentestDll, "QTFreeMemrory")
            self.QTFreeMemrory.argtype = [uint32]
            self.QTFreeMemrory.restype = int32
            # load QTGPIOSet
            self.QTGPIOSet = getattr(self.QueentestDll, "QTGPIOSet")
            self.QTGPIOSet.argtype = [uint32, uint32, uint32, uint32]
            self.QTGPIOSet.restype = int32
            # load QTGPIODelaySet
            self.QTGPIODelaySet = getattr(self.QueentestDll, "QTGPIODelaySet")
            self.QTGPIODelaySet.argtype = [uint32, int32, double]
            self.QTGPIODelaySet.restype = int32
            # load QTChannelOffsetSet
            self.QTChannelOffsetSet = getattr(self.QueentestDll, "QTChannelOffsetSet")
            self.QTChannelOffsetSet.argtype = [uint32, int32, double]
            self.QTChannelOffsetSet.restype = int32
            # load QTChannelRangeSet
            self.QTChannelRangeSet = getattr(self.QueentestDll, "QTChannelRangeSet")
            self.QTChannelRangeSet.argtype = [uint32, int32, double]
            self.QTChannelRangeSet.restype = int32
            # load QTBufStatusGet
            self.QTBufStatusGet = getattr(self.QueentestDll, "QTBufStatusGet")
            self.QTBufStatusGet.argtype = [uint32, ptrlonglong, ptr32, uptr32]
            self.QTBufStatusGet.restype = int32
            # load QTBufSDataGet
            self.QTBufSDataGet = getattr(self.QueentestDll, "QTBufSDataGet")
            self.QTBufSDataGet.argtype = [uint32, upbyte, uint32]
            self.QTBufSDataGet.restype = int32
            # load QTABAModeSet
            self.QTABAModeSet = getattr(self.QueentestDll, "QTABAModeSet")
            self.QTABAModeSet.argtype = [uint32, uint32, uint32, uint32]
            self.QTABAModeSet.restype = int32
            # load QTDigInLatency
            self.QTDigInLatency = getattr(self.QueentestDll, "QTDigInLatency")
            self.QTDigInLatency.argtype = [uint32, uint32]
            self.QTDigInLatency.restype = int32
            # load QTDataFormatSet
            self.QTDataFormatSet = getattr(self.QueentestDll, "QTDataFormatSet")
            self.QTDataFormatSet.argtype = [uint32, uint32]
            self.QTDataFormatSet.restype = int32
            # load QTCalDataSet
            self.QTCalDataSet = getattr(self.QueentestDll, "QTCalDataSet")
            self.QTCalDataSet.argtype = [uint32, upbyte, upbyte]
            self.QTCalDataSet.restype = int32
            # load QTGPIOWrite
            self.QTGPIOWrite = getattr(self.QueentestDll, "QTGPIOWrite")
            self.QTGPIOWrite.argtype = [uint32, int32, uint32]
            self.QTGPIOWrite.restype = int32
            # load QTGPIORead
            self.QTGPIORead = getattr(self.QueentestDll, "QTGPIORead")
            self.QTGPIORead.argtype = [uint32, int32, uptr32]
            self.QTGPIORead.restype = int32
            # load QTDumpRegister
            self.QTDumpRegister = getattr(self.QueentestDll, "QTDumpRegister")
            self.QTDumpRegister.argtype = [uint32, uint32, uint32]
            self.QTDumpRegister.restype = int32
            # load QTGetFeat
            self.QTGetFeat = getattr(self.QueentestDll, "QTGetFeat")
            self.QTGetFeat.argtype = [uint32, uptr32]
            self.QTGetFeat.restype = int32
            # load QTWaitDataReady
            self.QTWaitDataReady = getattr(self.QueentestDll, "QTWaitDataReady")
            self.QTWaitDataReady.argtype = [uint32, uint32, uint32]
            self.QTWaitDataReady.restype = int32
            # load QTSetNotifySizeB
            self.QTSetNotifySizeB = getattr(self.QueentestDll, "QTSetNotifySizeB")
            self.QTSetNotifySizeB.argtype = [uint32, uint32]
            self.QTSetNotifySizeB.restype = int32
        elif os.name == 'posix':
            sys.stdout.write("Linux found which is currently not supported by pyQueentest")
        else:
            raise Exception('Operating system not supported by pyQueentest')

    @staticmethod
    def QTChkRT(RTVal):
        if RTVal != 0:
            sys.stdout.write("Return with ERROR...\n")
            exit()
        else:
            return

if __name__ == "__main__":
    qt = PyQueen()                 # Complete DLL Loading
    qt.QTOpenBoard(0)              # Call driver functions through the instance
    PyQueen.QTChkRT(0) 