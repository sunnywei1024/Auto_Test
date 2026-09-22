# -*- coding: UTF-8 -*-
# 34461A multimeter
import pyvisa
from pyvisa.constants import *
import xlwt
import time
import os


class KEYSIGHT34461A:
    # open the multimeter
    def __init__(self, addr,type):
        rm = pyvisa.ResourceManager()
        tupl = rm.list_resources()
        print(tupl)
        if len(tupl) <= 0:
            print("can not find port !")
        else:
            self.res = rm.open_resource(addr, AccessModes.no_lock, 3000, None)
            self.V_avg_value = 0
            self.V_max_value = 0
            self.V_min_value = 0
            self.I_avg_value = 0
            self.I_max_value = 0
            self.I_min_value = 0
            self.O_avg_value = 0
            self.O_max_value = 0
            self.O_min_value = 0
            if type=='I':
                self.res.write('CONF:CURR:DC 10')
            else:
                self.res.write('CONF:VOLT:DC AUTO')

            # self.res.write('SYST:REM')
        # self.res.write('SYSTem:PRESet')



    def DCV(self, volt_value=100, count=1, delay=100):
        """
            @:param volt_value 100mv~1000V  test voltage
            @:param count 1~100  number of samples
            @:param delay delay 100ms
        """

        if volt_value < 0 or delay < 0:
            raise [Exception(" DCV test volt_value or delay Not less than zero"), volt_value, delay]
        try:

            self.res.write('*RST')
            self.res.write('*CLS')
            self.res.write('CONF:VOLT:DC')
            self.res.write('TRIG:SOUR IMM')
            self.res.write('TRIG:DEL:AUTO ON')
            self.res.write('TRIG:COUN 1')
            self.res.write('SAMP:COUN 1')
            # time.sleep((count-1) *0.7)
            self.res.write('READ?')
            time.sleep((count-1) *0.7)
            dcv_res = self.res.read().encode('utf-8')
            dcv_result = dcv_res.split(b',')
            Sum = 0
            for index in range(len(dcv_result)):
                Sum = float(dcv_result[index]) + Sum
                dcv_result[index] = float(dcv_result[index])
            self.V_avg_value = Sum / len(dcv_result)
            self.V_max_value = max(dcv_result)
            self.V_min_value = min(dcv_result)
            print("DC voltage samples=%d max=%s min=%s avg=%f" % (count, self.V_max_value, self.V_min_value, self.V_avg_value))
            return self.V_avg_value
        except ValueError:
            print(ValueError)
        # finally:
            # self.res.write('*CLS')
            # self.res.write('SYSTem:LOCal')

    # test DCI 10A range ,100uA resolution
    def DCI(self, dampere_range=10, dampere_res=0.0001,
            count=1, delay=100):
        """
        :param ampere_max:10A   test current
        :param ampere_min:0.0001A test current
        :param count: 1~100  number of samples
        :param delay:delay 100ms
        :return:
        """
        if dampere_range < 0 or dampere_res < 0:
            raise [Exception("DCI test volt_value or count Not less than zero"), dampere_range, dampere_res]
        try:

            self.res.write('*CLS')
            # self.res.write('CONF:CURR:DC AUTO')
            # self.res.write('CURR:DC:ZERO:AUTO OFF')
            self.res.write('CURR:DC:TERM %f' % dampere_range)
            self.res.write('SAMP:COUN %d' % count)
            self.res.write('TRIG:DELay %f' % (delay / 1000.0))
            time.sleep((count-1) *0.6)
            self.res.write('READ?')
            time.sleep((count-1) *0.6)
            dci_res = self.res.read().encode('utf-8')
            dci_result = dci_res.split(b',')
            Sum = 0
            for index in range(len(dci_result)):
                Sum = float(dci_result[index]) + Sum
                dci_result[index] = float(dci_result[index])
            self.I_avg_value = Sum / len(dci_result)
            self.I_max_value = max(dci_result)
            self.I_min_value = min(dci_result)
            print("DC current samples=%d max=%s min=%s avg=%f" % (count, self.I_max_value, self.I_min_value, self.I_avg_value))
            return self.I_avg_value
        except ValueError:
            print(ValueError)
        # finally:
        #     self.res.write('*CLS')
        #     self.res.write('SYSTem:LOCal')


    # test OHM 100ohm range ,100uOhm resolution
    def OHM(self, ohm_max=100, ohm_min=0.0001, count=100,
            delay=100):
        """
            @:param ohm_max maximum resistance, 100 ohm by default
            @:param ohm_min minimum resistance, 0.0001 ohm by default
            @:param count 1~100  number of samples
            @:param delay delay 100ms
        """

        if ohm_max < 0 or ohm_min < 0:
            raise [Exception("OHM test ohm_max or ohm_min Not less than zero"), ohm_max, ohm_min]
        try:

            res = self.ResourceManager()
            res.write('SYSTem:REM')
            res.write('SYSTem:PRESet')
            res.write('*CLS')
            res_range = 'CONF:RES {0}, {1}'.format(ohm_max, ohm_min)
            res.write(res_range)
            res.write('SAMP:COUN %d' % count)
            res.write('TRIG:DELay %f' % (delay / 1000.0))
            time.sleep(count * 0.5)
            res.write('READ?')
            ohm_value = res.read().encode('utf-8')
            ohm_result = ohm_value.split(b',')
            Sum = 0
            for index in range(len(ohm_result)):
                Sum = float(ohm_result[index]) + Sum
                ohm_result[index] = float(ohm_result[index])
            self.O_avg_value = Sum / len(ohm_result)
            self.O_max_value = max(ohm_result)
            self.O_min_value = min(ohm_result)
            print("Resistance samples=%d max=%s min=%s avg=%f" % (count, self.O_max_value, self.O_min_value, self.O_avg_value))
        except ValueError:
            print(ValueError)
        finally:
            res.write('*CLS')
            res.write('SYSTem:LOCal')
            # test Temperature reading with  a 5K thermistor

    def Temperature(self, count=10, delay=100):
        """
            :param Temprange: maximum temperature 5000
            :param count:  1~100  number of samples
            :param delay:  delay 100ms
            :return:
            """
        try:
            time_string = str(time.strftime('%Y%m%d%H%M%S') + 'TemperatureTest')
            dev_string = './' + time_string + '.xls'
            path = os.path.abspath(dev_string)
            book = xlwt.Workbook(encoding='utf-8', style_compression=0)
            sheet = book.add_sheet("TemperatureLog", cell_overwrite_ok=True)
            sheet.write(0, 0, 'Temperature value(A)')
            sheet.write(1, 0, 'Max temperature(A)')
            sheet.write(2, 0, 'Min temperature(A)')
            sheet.write(3, 0, 'Avg temperature(A)')
            res = self.ResourceManager()
            res.write('SYSTem:REM')
            res.write('SYSTem:PRESet')
            res.write('*CLS')
            res.write('CONF:Temp THER,5000')
            res.write('UNIT:TEMP F')
            res.write('MEAS:TEMP? FRTD')
            res.write('SAMP:COUN %d' % count)
            res.write('TRIG:DELay %f' % (delay / 1000.0))
            time.sleep(count * 0.5)
            res.write('READ?')
            tem_value = res.read()
            tem_result = tem_value.split(',')
            Sum = 0
            for index in range(len(tem_result)):
                Sum = float(tem_result[index]) + Sum
                tem_result[index] = float(tem_result[index])
            for index in tem_result:
                row = 0
                while (row < count):
                    sheet.write(0, row + 1, index)
                    row = row + 1
            avg_value = Sum / len(tem_result)
            max_value = max(tem_result)
            min_value = min(tem_result)
            sheet.write(1, 1, max_value)
            sheet.write(2, 1, min_value)
            sheet.write(3, 1, avg_value)
            book.save(path)
            print("Temperature samples=%d max=%s min=%s avg=%f" % (count, max_value, min_value, avg_value))

        finally:
            res.write('*CLS')
            res.write('SYSTem:LOCal')
    
    def close(self):
        err_cnt = 0
        while True:
            try:
                self.res.write('*CLS')
                self.res.write('SYST:LOC')
                self.res.close()
                print("Close Keysight 34465A successfully!")
                return True
            except:
                if err_cnt<3:
                    err_cnt+=1
                    time.sleep(3)
                else:
                    print("Close failed!")
                    return False 

if __name__ == "__main__":
    m = KEYSIGHT34461A('USB0::0x2A8D::0x1301::MY64022314::INSTR','I')
    m.close()
    time.sleep(3)

