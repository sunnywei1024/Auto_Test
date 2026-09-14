'''
Created on Sep 11, 2026
Chicago
@author: lijiangwei
'''
import time
import os
import xlwt
import pymodbus
from Layer2.TestInput import TestInput
from Layer2.api import *
from pymodbus.client import ModbusTcpClient
import Layer3.FF
import Layer3.SS
import Layer3.FS
import Layer3.BASE

# -------------------------------------------------------------------------------------------------#
def AutoTest():
    print(os.path.dirname(__file__))
    Instrs = TestInput(os.path.dirname(__file__) + "\\TestInput.xlsx").get_instr()    # Get instrument information
    TestItems = TestInput(os.path.dirname(__file__) + "\\TestInput.xlsx").get_data()  # Get test items
    TestIC = TestInput(os.path.dirname(__file__) + "\\TestInput.xlsx").get_IC()       # Get IC information
    print(TestIC)
    isTem = TestInput(os.path.dirname(__file__) + "\\TestInput.xlsx").get_isTemp()    # Get temperature is needed 
    temp_list = TestInput(os.path.dirname(__file__) + "\\TestInput.xlsx").get_Temp()  # Get temperature information
    if isTem:
        temp_list = temp_list
    else:
        temp_list = [25,]
    myapi = api()
    myapi.instrs_init(*Instrs)  # Init instruments
    for temp in temp_list:
        for j in range(len(TestItems)):
            TestItems[j] = {**TestItems[j]}
            print(TestItems[j]['测试函数'])
            item_name = str(TestItems[j]['测试函数']).strip()
            item_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),"Report",TestIC,item_name)
            if not os.path.exists(item_dir):
                os.makedirs(item_dir)
            # Execute test function
            ti = eval('Layer3' + '.' + TestIC + '.' + TestItems[j]['测试函数'])(myapi, temp, item_dir, **TestItems[j])
    myapi.instrs_close(*Instrs)

if __name__ == "__main__":
    # xw.Book("TestInput.xlsm").set_mock_caller()
    AutoTest()
    exit()
