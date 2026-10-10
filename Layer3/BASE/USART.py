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
    print(f"Program start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    myapi.OSC.clear_status()
    myapi.OSC.reset()
    myapi.OSC.set_display_update(True)
    myapi.OSC.opc_timeout = 60000 

    # ---- 1. Channel and timebase configuration ----
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

    myapi.OSC.sample_rate_mode(SampleRateMode.MANUAL)   # manual configuration
    # myapi.OSC.sample_rate_mode(SampleRateMode.AUTO)   # automatic configuration
    print("Current sample rate mode:", myapi.OSC.get_sample_rate_mode())
    # Helper example: auto-estimate and configure the sample rate and 1 Mpts from the timebase
    print("Auto-configured sampling:", myapi.OSC.auto_sampling_for_timebase(2e-4, points="1M", wait=True))
    myapi.OSC.set_display_brightness(brightness=100)
    # print(myapi.OSC.get_display_brightness())
    myapi.OSC.set_signal_intensity(100)        # set waveform intensity to 100%
    # print(myapi.OSC.get_signal_intensity())  # read the current waveform intensity

    myapi.OSC.configure_measurement(measure_index=1, source="C1", main="AMPlitude",
                        category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=2, source="C1", main="FREquency",
                                category=None, additional=None, enable=True)
    myapi.OSC.configure_measurement(measure_index=3, source="C1", main="RMS",
                                category=None, additional=None, enable=True)  
    
    # ---- 2. UART decode + serial bus trigger: save waveform -> export CSV ---
    # Assume UART RX is connected to channel 1, TX to channel 2, baud rate 115200
    myapi.OSC.configure_uart_decode(bus_number=1, rx="C1", tx="C2", baud=115200)  
    myapi.OSC.trigger_mode(TriggerMode.NORMAL)
    myapi.OSC.configure_uart_trigger(bus_number=1, source="SBUS1")
    myapi.OSC.single_and_wait(10000)
    time.sleep(3)  # wait for the instrument to finish decoding
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_uart.png"),fmt="png",add_timestamp=True,instr_dir= INSTR_IMAGE_DIR,filesave=False,localfile=True)
    myapi.OSC.save_waveform_csv('1,2', os.path.join(item_dir, "uart.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)          
    # ---- 3b. UART waveform ZOOM (instrument side only) + rise time/amplitude measurement + cursors ----
    # 1) Instrument-side ZOOM: zoom to one UART frame (estimated from protocol parameters, no waveform readback needed)
    uart_zoom = myapi.OSC.zoom_uart_display(baud=115200, data_bits=8,
                                    parity=UARTParity.NONE,
                                    stop_bits=STOPBit.ONE_BIT,
                                    margin_bits=2.0, reacquire=True)
    frame_time = uart_zoom["frame_time"]
    # 2) Automatic measurements: CH1(RX) rise time + amplitude (+ low/high levels used to place the horizontal cursors)
    myapi.OSC.configure_rise_time_measurement(measure_index=4, source="C2", enable=True)
    myapi.OSC.configure_amplitude_measurement(measure_index=5, source="C2", enable=True)
    myapi.OSC.configure_measurement(measure_index=6, source="C2", main="LOW", enable=True)  
    myapi.OSC.configure_measurement(measure_index=7, source="C2", main="HIGH", enable=True)

    myapi.OSC.wait_opc(5000)          # wait for measurements to refresh so stale values are not read
    rise_time = myapi.OSC.get_measurement_result(4)
    amplitude = myapi.OSC.get_measurement_result(5)
    print(f"CH2 rise time (RTIMe):   {rise_time} s")
    print(f"CH2 amplitude (AMPLitude):     {amplitude} V") 
    try:
        low_level = float(myapi.OSC.get_measurement_result(6))
        high_level = float(myapi.OSC.get_measurement_result(7))
    except (ValueError, TypeError):
        low_level, high_level = 0.0, 5.0 

    # 3) Cursor measurements: vertical X1/X2 for one frame time, horizontal Y1/Y2 for amplitude (display optional)
    myapi.OSC.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C2",
                        x1=0.0, x2=frame_time, y1=low_level, y2=high_level,
                        show=True, show_values=True, tracking=False)
    myapi.OSC.wait_opc(2000)
    try:
        dx = myapi.OSC.get_cursor_delta_x(1)
        dy = myapi.OSC.get_cursor_delta_y(1)
        print(f"Cursor dX (one frame time): {dx:.6e} s")
        print(f"Cursor dY (amplitude):     {dy:.4f} V")
    except Exception as exc:
        print(f"Failed to read cursor results (ignored): {exc}")
    
    # 4) Screenshot (zoomed waveform + measurements + cursors)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_uart_decode.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
    
    # 5) Hide the SBUS1 decode result table so the automatic measurement table (RMS/FREQuency/AMPLitude/RTIMe...) is visible, then take another screenshot
    myapi.OSC.bus_result_table(bus_number=1, on=False)   # turn off the SBUS1 decode table
    myapi.OSC.wait_opc(50000)
    time.sleep(3)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_uart_meas.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
    myapi.OSC.bus_result_table(bus_number=1, on=True)    # restore the decode table display
    print("Usart test is done..................................\n")
    
    for i in range(0,100):
        myapi.VDMM.DCV()
        time.sleep(1)
    end_time = time.time()
    print(f"Program end time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed time: {end_time - start_time:.3f} s")
