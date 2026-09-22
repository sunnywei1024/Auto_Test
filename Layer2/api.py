'''
Created on Sep 11, 2026
Chicago
@author: lijiangwei
'''
import time
import os
import sys 
import importlib

# Ensure the project root (the folder containing Layer1/Layer2/Layer3) is on
# sys.path, so these packages can be imported regardless of the current directory.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from xlutils.copy import copy
from Layer1 import GK_I2C
from Layer1 import pyQueen
from Layer1.KEYSIGHT34461A import *
from Layer1.MXO4 import *
from Layer1.SerialPort import *
from Layer1.PS9080 import *
from Layer1.EL63200A import *
from Layer2.TestInput import *

class api(GK_I2C.GK_I2C, pyQueen.PyQueen):
    def __init__(self):
        # Initialize both parent classes (each one loads its own driver library)
        GK_I2C.GK_I2C.__init__(self)
        pyQueen.PyQueen.__init__(self)

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
            elif i['设备类型']=='Multimeter':
                if i['设备型号'] =='34461A':
                    if 'I' in i['设备名称']:
                        names[i['设备名称']] = KEYSIGHT34461A(i['设备地址'],'I')
                    else:
                        names[i['设备名称']] = KEYSIGHT34461A(i['设备地址'],'V')
            elif i['设备类型']=='ELoad':
                if i['设备型号'] =='63200A':
                    names[i['设备名称']] = EL63200A(i['设备地址'])
            elif i['设备类型']=='PSU':
                if i['设备型号'] =='PS9080':
                    names[i['设备名称']] = PS9080(i['设备地址'])
  

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
            elif i['设备类型']=='Multimeter':
                if i['设备型号'] =='34461A':
                    names[i['设备名称']].close()
            elif i['设备类型']=='ELoad':
                if i['设备型号'] =='63200A':
                    names[i['设备名称']].close()
            elif i['设备类型']=='PSU':
                if i['设备型号'] =='PS9080':
                    names[i['设备名称']].close()
            
if __name__ == "__main__":
    myapi = api()
    print("API Initialization Complete!")