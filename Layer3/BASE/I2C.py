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


def I2C_Test(myapi, temp, item_dir, **Parameters):
    INSTR_FILE_OUT_DIR = "temp_files"
    INSTR_IMAGE_DIR = "temp_shots"
    print(item_dir)
    start_time = time.time()
    print(f"Script start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    myapi.OSC.clear_status()
    myapi.OSC.reset()
    myapi.OSC.set_display_update(True)
    myapi.OSC.opc_timeout = 60000 
    # ---- 1. channel and timebase configuration ----
    myapi.OSC.channel_state(3, True)
    myapi.OSC.channel_state(4, True)

    myapi.OSC.channel_coupling(3, ChannelCoupling.DC)
    myapi.OSC.channel_coupling(4, ChannelCoupling.DC)

    # mxo.channel_bandwidth(1, 20e6)
    # mxo.channel_bandwidth(2, 20e6)
    myapi.OSC.channel_range(3, 10.0)
    myapi.OSC.channel_range(4, 10.0)
    myapi.OSC.channel_scale(3, 1)
    myapi.OSC.channel_scale(4, 1)
    
    myapi.OSC.sample_rate_mode(SampleRateMode.MANUAL)   # manual configuration
    # mxo.sample_rate_mode(SampleRateMode.AUTO)   # automatic configuration
    print("Current sample rate mode:",  myapi.OSC.get_sample_rate_mode())
    # helper example: estimate and configure the sample rate and 1 Mpts from the timebase
    print("Automatic sampling setup:", myapi.OSC.auto_sampling_for_timebase(2e-4, points="1M", wait=True))
    myapi.OSC.set_display_brightness(brightness=100)
    # print(mxo.get_display_brightness())
    myapi.OSC.set_signal_intensity(100)       # waveform intensity 100%
    # print(mxo.get_signal_intensity())  # read the current waveform intensity

    # ---- 1. I2C decoding + serial bus trigger: save waveform -> export CSV ----
    # I2C SDA on channel 1, SCL on channel 2
    myapi.OSC.channel_label(3, "SCL")
    myapi.OSC.channel_label(4, "SDA")
    myapi.OSC.configure_i2c_decode(bus_number=2, scl="C3", sda="C4")
    myapi.OSC.trigger_mode(TriggerMode.NORMAL)
    myapi.OSC.configure_i2c_trigger(bus_number=2, condition=None)
    myapi.OSC.single_and_wait(10000)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_i2c.png"),fmt="png",add_timestamp=True,instr_dir=INSTR_IMAGE_DIR, filesave=False,localfile=False)
    myapi.OSC.save_waveform_csv('3,4', os.path.join(item_dir,"i2c.csv"),instr_path=INSTR_FILE_OUT_DIR, ascii_format=False, add_timestamp=True, filesave=False,localfile=False)

    # ---- 2. I2C waveform ZOOM (scope side only) + rise time/amplitude measurement + cursor ----
    # 1) scope side ZOOM: magnify to one I2C frame (estimated from the
    #    protocol parameters, no waveform readback needed)
    i2c_zoom = myapi.OSC.zoom_i2c_display(scl_freq=150000, frame_bits=9,
                                    margin_bits=2.0, reacquire=True)
    i2c_frame_time = i2c_zoom["frame_time"]

    # 2) automatic measurement: CH1(SDA)/CH2(SCL) rise time + amplitude (+ low/high level for the cursor)
    myapi.OSC.configure_rise_time_measurement(measure_index=4, source="C3", enable=True)
    myapi.OSC.configure_amplitude_measurement(measure_index=5, source="C3", enable=True)
    myapi.OSC.configure_measurement(measure_index=6, source="C3", main="LOW", enable=True)
    myapi.OSC.configure_measurement(measure_index=7, source="C3", main="HIGH", enable=True)
    myapi.OSC.configure_rise_time_measurement(measure_index=8, source="C4", enable=True)
    myapi.OSC.configure_amplitude_measurement(measure_index=9, source="C4", enable=True)
    myapi.OSC.configure_measurement(measure_index=10, source="C4", main="LOW", enable=True)
    myapi.OSC.configure_measurement(measure_index=11, source="C4", main="HIGH", enable=True)
    myapi.OSC.wait_opc(5000)          # wait for a measurement refresh to avoid reading old values
    rise_c3 = myapi.OSC.get_measurement_result(4)
    amp_c3  = myapi.OSC.get_measurement_result(5)
    rise_c4 = myapi.OSC.get_measurement_result(8)
    amp_c4 = myapi.OSC.get_measurement_result(9)
    print(f"CH3(SCL) rise time (RTIMe): {rise_c3} s,  amplitude (AMPLitude): {amp_c3} V")
    print(f"CH4(SDA) rise time (RTIMe): {rise_c4} s,  amplitude (AMPLitude): {amp_c4} V")
    try:
        low_c3 = float(myapi.OSC.get_measurement_result(6))
        high_c3 = float(myapi.OSC.get_measurement_result(7))
    except (ValueError, TypeError):
        low_c3, high_c3 = 0.0, 5.0

    # 3) cursor measurement: vertical X1/X2 for one frame time, horizontal Y1/Y2 for the amplitude (display optional)
    myapi.OSC.configure_cursor(cursor=1, function=CursorFunction.PAIRED, source="C4",
                         x1=0.0, x2=i2c_frame_time, y1=low_c3, y2=high_c3,
                         show=True, show_values=True, tracking=True)
    myapi.OSC.wait_opc(5000)
    # 18.12.1 Zoom how to Adjust the Disply Zone
    



    try:
        dx = myapi.OSC.get_cursor_delta_x(1)
        dy = myapi.OSC.get_cursor_delta_y(1)
        print(f"cursor delta X (one frame time): {dx:.6e}  s")
        print(f"cursor delta Y (amplitude):     {dy:.4f} V")
    except Exception as exc:
        print(f"reading the cursor result failed (ignored): {exc}")

    # 4) screenshot (magnified waveform + measurements + cursors)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_i2c_decode.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)

    # 5) hide the SBUS2 decode result table so the automatic measurement result table
    #    (RMS/FREQuency/AMPLitude/RTIMe...) becomes visible, then take another screenshot
    myapi.OSC.bus_result_table(bus_number=2, on=False)   # switch the SBUS2 decode table off
    myapi.OSC.wait_opc(50000)
    time.sleep(3)
    myapi.OSC.save_waveform_image(os.path.join(item_dir, "scope_i2c_meas.png"),
                            fmt="png", add_timestamp=True,
                            instr_dir=INSTR_IMAGE_DIR, filesave=False, localfile=True)
    myapi.OSC.bus_result_table(bus_number=2, on=True)    # restore the decode table display

    # for key in Parameters.keys():
    #     if key == 'Start':
    #         START=Parameters[key]
    #     elif key == 'Stop':
    #         STOP=Parameters[key]
    #     elif key == 'Step':
    #         STEP=Parameters[key]
    #     elif key == 'CHG_MODE':
    #         CHG_MODE=Parameters[key]
    #     elif key == 'Item':
    #         ITEMS=Parameters[key]
    #     elif key == 'CHG_EN':
    #         CHG_EN=Parameters[key]
    #     elif key == 'FSW':
    #         FSW=Parameters[key] 
    #     elif key == 'Imax':
    #         Imax=Parameters[key] 
    #     elif key == 'Voutset':
    #         Voutset=Parameters[key] 
    end_time = time.time()
    print(f"Script end time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed time: {end_time - start_time:.3f} s")
    print("I2C test is done..................................\n")
    pass
