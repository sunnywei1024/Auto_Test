import sys
import os
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import time
import xlsxwriter
import xlwt
from xlwt import easyxf
from xlutils.copy import copy
from Layer1.GK_I2C import GK_I2C
from ctypes import *

def UR_Test(myapi, temp, item_dir,**Parameters):

    myapi.MCU.open()
    nRet = myapi.VII_ScanDevice(1)
    if(nRet <= 0):
        print("No device connect!")
        exit()
    else:
        print("Connected device number is:"+repr(nRet))
        # Open device
    nRet = myapi.VII_OpenDevice(GK_I2C.VII_USBI2C, 0, 0)
    if(nRet != GK_I2C.ERR_SUCCESS):
        print("Open device error!")
        exit()
    else:
        print("Open device success!")
    
    # Initialize device
    I2C_InitConfig = GK_I2C.VII_INIT_CONFIG()
    # Master mode
    I2C_InitConfig.MasterMode = GK_I2C.VII_MASTER
    # Hardware control
    I2C_InitConfig.ControlMode = GK_I2C.VII_HCTL_MODE
    # 7-bit address mode
    I2C_InitConfig.AddrType = GK_I2C.VII_ADDR_7BIT
    # Sub address width->1byte
    I2C_InitConfig.SubAddrWidth = GK_I2C.VII_SUB_ADDR_1BYTE
    # Clock speed (in Hz)
    I2C_InitConfig.ClockSpeed = 400000
    nRet = myapi.VII_InitI2C(GK_I2C.VII_USBI2C, 0, 0, byref(I2C_InitConfig))
    if(nRet != GK_I2C.ERR_SUCCESS):
        print("Initialize device error!")
        exit()
    else:
        print("Initialize device success!")
    
    for key in Parameters.keys():
        if key == 'Start':
            START=Parameters[key]
        elif key == 'Stop':
            STOP=Parameters[key]
        elif key == 'Step':
            STEP=Parameters[key]
        elif key == 'CHG_MODE':
            CHG_MODE=Parameters[key]
        elif key == 'Item':
            ITEMS=Parameters[key]
        elif key == 'CHG_EN':
            CHG_EN=Parameters[key]
        elif key == 'FSW':
            FSW=Parameters[key] 
        elif key == 'Imax':
            Imax=Parameters[key] 
        elif key == 'Voutset':
            Voutset=Parameters[key] 
    print("UR_Test START\n")
    pass

