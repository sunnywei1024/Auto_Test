'''
Created on Sep 11, 2026
Chicago
@author: lijiangwei
'''
import time
import os
import sys
from xlutils.copy import copy
from Layer1 import GK_I2C
from Layer1.MXO4 import *
from Layer1.SerialPort import *
from Layer2.TestInput import *

class api(GK_I2C.GK_I2C):
    def __init__(self):
        GK_I2C.GK_I2C.__init__(self)

    def instrs_init(self, *instrs):
        names = self.__dict__
        for i in instrs:
            if i['设备类型']=='OSC':
                if i['设备型号'] =='RohdeSchwarz':
                    names[i['设备名称']] = MXO4(i['设备地址'])
                elif i['设备型号'] =='Keysight':
                    names[i['设备名称']] = MXO4(i['设备地址'])
                elif i['设备型号'] =='Tektronix':
                    names[i['设备名称']] = MXO4(i['设备地址'])
                elif i['设备型号'] =='Lecroy':
                    names[i['设备名称']] = MXO4(i['设备地址'])
            elif i['设备类型']=='COM':
                if i['设备型号'] =='SerialPort':
                    names[i['设备名称']] = SerialPort(port=i['设备地址'])  


    def instrs_close(self, *instrs):
        names = self.__dict__
        for i in instrs:
            if i['设备类型']=='OSC':
                if i['设备型号'] =='RohdeSchwarz':
                    names[i['设备名称']].close()
                elif i['设备型号'] =='Keysight':
                    names[i['设备名称']].close()
                elif i['设备型号'] =='Tektronix':
                    names[i['设备名称']].close()
                elif i['设备型号'] =='Lecroy':
                    names[i['设备名称']].close()
                elif i['设备型号'] =='Lecroy':
                    pass
            
