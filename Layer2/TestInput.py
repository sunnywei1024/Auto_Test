import sys
import os
from xlutils.copy import copy
# from mcush import *
from openpyxl import load_workbook  # import openpyxl

# Handle Excel
class TestInput:
    def __init__(self,file_name):
        self.filename=file_name
	#Get methods from Excel
    def get_data(self): 
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['测试项'] # locate the sheet
        test_data= [] # create an empty list
        for row in range(3, sheet.max_row + 1):
            sub_data = {}
            # print(sheet.cell(row, 1).value)
            # print(sheet.cell(row, 2).value)
            if(sheet.cell(row, 1).value != None)&(sheet.cell(row, 2).value == '是'):
                # for column in range(1, sheet.max_column + 1):
                for column in range(1, sheet.max_column+1):
                    # if sheet.cell(row, column).value != '/':
                    sub_data[sheet.cell(2, column).value] = sheet.cell(row, column).value   # The first row of Excel data as the key of the dictionary;
                test_data.append(sub_data) # Add each row of data to the list
        return test_data
    
    def get_instr(self): 
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['仪器信息'] # locate the sheet
        test_data= [] # create an empty list
        for row in range(2, sheet.max_row + 1):
            sub_data = {}
            # print(sheet.cell(row, 1).value)
            if(sheet.cell(row, 1).value != None)&(sheet.cell(row, 5).value == '是'):
                for column in range(1, sheet.max_column + 1):
                    sub_data[sheet.cell(1, column).value] = sheet.cell(row, column).value  # The first row of Excel data as the key of the dictionary
                test_data.append(sub_data) # Add each row of data to the list
        return test_data

    def get_map(self): 
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['万用表通道映射'] # locate the sheet
        test_data= {} # create an empty dictionary
        for row in range(2, sheet.max_row + 1):
            sub_data = []
            if(sheet.cell(row, 1).value != None):
                for column in range(2, sheet.max_column + 1):
                    sub_data.append(sheet.cell(row, column).value)  # The first row of Excel data as the key of the dictionary
                test_data[sheet.cell(row, 1).value]=sub_data # Add each row of data to the dictionary
        return test_data
    
    def get_IC(self):
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['IC'] # locate the sheet
        return sheet.cell(2, 1).value

    def get_isTemp(self):
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['IC'] # locate the sheet
        if sheet.cell(2, 2).value=='是':
            isTem=True
        else:
            isTem=False
        return isTem

    def get_Temp(self):
        wb = load_workbook(self.filename) # Open Excel
        sheet = wb['IC'] # locate the sheet
        tem= [] # create an empty list
        for row in range(2, sheet.max_row + 1):
            if(sheet.cell(row, 3).value != None):
                tem.append(sheet.cell(row, 3).value)  
        return tem

if __name__ == '__main__':
   res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_instr()
   print(res)
   res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_data()
   print(res)
   res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_IC()
   print(res)
   res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_isTemp()
   print(res)
   res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_Temp()
   print(res)
#    res=TestInput(os.getcwd()+r"\TestInput.xlsx").get_map()
#    print(res)
