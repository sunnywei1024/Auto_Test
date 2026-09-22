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


def UR_Test(myapi, temp, item_dir, **Parameters):  
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
    myapi.OSC.set_signal_intensity(100)        # 波形亮度设为100%
    # print(myapi.OSC.get_signal_intensity())  # 读取当前波形亮度

    myapi.OSC.configure_measurement(measure_index=1, source="C1", main="AMPlitude",
                        category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=2, source="C1", main="FREquency",
                                category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=3, source="C1", main="RMS",
                                category=None, additional=None, enable=True)  
    
    # ---- 2. UART 解码 + 串行 总线触发: 保存波形 → 导出 CSV ---
    # 假设 UART RX 接通道1, TX 接通道2, 波特率 115200
    myapi.OSC.configure_uart_decode(bus_number=1, rx="C1", tx="C2", baud=115200)  
    myapi.OSC.trigger_mode(TriggerMode.NORMAL)
    myapi.OSC.configure_uart_trigger(bus_number=1, source="SBUS1")
    myapi.OSC.single_and_wait(10000)
    time.sleep(3)  # 等待仪器完成解码
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_uart.png"),fmt="png",add_timestamp=True,instr_dir= INSTR_IMAGE_DIR,filesave=False,localfile=True)
    myapi.OSC.save_waveform_csv('1,2', os.path.join(item_dir, "uart.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)          
    # ---- 3b. UART 波形 ZOOM (仅示波器端) + 上升沿/幅值测量 + 光标 ----
    # 1) 仪器端 ZOOM: 放大到一帧 UART 数据 (按协议参数估算, 无需回读波形)
    uart_zoom = myapi.OSC.zoom_uart_display(baud=115200, data_bits=8,
                                    parity=UARTParity.NONE,
                                    stop_bits=STOPBit.ONE_BIT,
                                    margin_bits=2.0, reacquire=True)
    frame_time = uart_zoom["frame_time"]
    # 2) 自动测量: CH1(RX) 上升沿时间 + 幅值 (+ 低/高电平用于放置水平光标)
    myapi.OSC.configure_rise_time_measurement(measure_index=4, source="C2", enable=True)
    myapi.OSC.configure_amplitude_measurement(measure_index=5, source="C2", enable=True)
    myapi.OSC.configure_measurement(measure_index=6, source="C2", main="LOW", enable=True)  
    myapi.OSC.configure_measurement(measure_index=7, source="C2", main="HIGH", enable=True)

    myapi.OSC.wait_opc(5000)          # 等待测量刷新, 避免读到旧值
    rise_time = myapi.OSC.get_measurement_result(4)
    amplitude = myapi.OSC.get_measurement_result(5)
    print(f"CH2 上升沿时间 (RTIMe):   {rise_time} s")
    print(f"CH2 幅值 (AMPLitude):     {amplitude} V") 
    try:
        low_level = float(myapi.OSC.get_measurement_result(6))
        high_level = float(myapi.OSC.get_measurement_result(7))
    except (ValueError, TypeError):
        low_level, high_level = 0.0, 5.0 

    # 3) 光标测量: 垂直 X1/X2 量一帧时间, 水平 Y1/Y2 量幅值 (显示可选)
    myapi.OSC.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
                        x1=0.0, x2=frame_time, y1=low_level, y2=high_level,
                        show=True, show_values=True, tracking=False)
    myapi.OSC.wait_opc(2000)
    try:
        dx = myapi.OSC.get_cursor_delta_x(1)
        dy = myapi.OSC.get_cursor_delta_y(1)
        print(f"光标 ΔX (一帧时间): {dx:.6e} s")
        print(f"光标 ΔY (幅值):     {dy:.4f} V")
    except Exception as exc:
        print(f"读取光标结果失败 (忽略): {exc}")
    
    # 4) 截屏 (放大后的波形 + 测量 + 光标)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "uart_zoom_meas.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
    
    # 5) 隐藏 SBUS1 解码结果表, 露出自动测量结果表 (RMS/FREQuency/AMPLitude/RTIMe...), 再截一张图
    myapi.OSC.bus_result_table(bus_number=1, on=False)   # 关闭 SBUS1 解码表
    myapi.OSC.wait_opc(50000)
    time.sleep(3)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "uart_meas_result.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
    myapi.OSC.bus_result_table(bus_number=1, on=True)    # 恢复解码表显示
    print("Usart test is done..................................\n")
    
    for i in range(0,100):
        myapi.VDMM.DCV()
        time.sleep(1)
    end_time = time.time()
    print(f"程序结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"运行耗时: {end_time - start_time:.3f} 秒")
