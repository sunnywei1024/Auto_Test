import sys
import os
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import time
import xlsxwriter
import xlwt
from xlwt import easyxf
from xlutils.copy import copy
from Layer1.GK_I2C import GK_I2C
from Layer1.MXO4 import *
from ctypes import *


def Trigger_Test(myapi, temp, item_dir,**Parameters):  
    INSTR_FILE_OUT_DIR = "temp_files"
    INSTR_IMAGE_DIR = "temp_shots"
    print(item_dir)
    start_time = time.time()
    print(f"程序开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    myapi.OSC.clear_status()
    myapi.OSC.reset()
    myapi.OSC.set_display_update(True)
    myapi.OSC.opc_timeout = 60000   

    # ---- 1. 通道与时基配置 ----
    myapi.OSC.channel_state(1, True)
    myapi.OSC.channel_state(2, True)
    myapi.OSC.channel_coupling(1, ChannelCoupling.DC)
    myapi.OSC.channel_coupling(2, ChannelCoupling.DC)
    # myapi.OSC.channel_bandwidth(1, 20e6)
    # myapi.OSC.channel_bandwidth(2, 20e6)
    myapi.OSC.channel_range(1, 10.0)
    myapi.OSC.channel_range(2, 10.0)
    myapi.OSC.channel_scale(1, 1)
    myapi.OSC.channel_scale(2, 1)


    myapi.OSC.sample_rate_mode(SampleRateMode.MANUAL)   #手动配置
    # myapi.OSC.sample_rate_mode(SampleRateMode.AUTO)   #自动配置
    print("当前采样率模式:", myapi.OSC.get_sample_rate_mode())
    # 辅助函数示例：按时基自动估算并配置采样率与 1 Mpts 
    print("自动配置采样:", myapi.OSC.auto_sampling_for_timebase(2e-4, points="1M", wait=True))
    myapi.OSC.set_display_brightness(brightness=100)
    # print(myapi.OSC.get_display_brightness())
    myapi.OSC.set_signal_intensity(100)        # 波形亮度设为 100%
    # print(myapi.OSC.get_signal_intensity())  # 读取当前波形亮度
    # ---- 2. 边沿触发: 保存波形 → 导出 CSV ----
    myapi.OSC.channel_label(1, "RX")
    myapi.OSC.channel_label(2, "TX")
        
    myapi.OSC.configure_measurement(measure_index=1, source="C2", main="AMPlitude",
                        category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=2, source="C2", main="FREquency",
                                category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=3, source="C2", main="RMS",
                                category=None, additional=None, enable=True)  
    
    myapi.OSC.trigger_mode(TriggerMode.NORMAL)
    myapi.OSC.configure_edge_trigger(source=1, level=0.5, slope=EdgeSlope.POSITIVE)
    myapi.OSC.single_and_wait(1000)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_edge.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=True,localfile=False)
    myapi.OSC.save_waveform_csv('1,2', pc_path=os.path.join(item_dir, "edge.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False) 

    print("Tigger test is done..................................\n")
    end_time = time.time()
    print(f"程序结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"运行耗时: {end_time - start_time:.3f} 秒")