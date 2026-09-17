#!/usr/bin/env python  
# -*- coding: utf-8 -*-

""" 
@version: v1.0 
@author: BaiLi,modified by Jiangwei.li
@license: Apache Licence  
@contact: BaiLi@queentest.com 
@site: http://www.queentest.com/index.html 
@software: Examples for all QT11xx DAQ cards 
@file: Regs.py 
@time: 2017/5/17 19:20 
"""

#PCIE Register
REGISTER_PCIE_CONTROL_STATUS                        = 0 # Device Control Status Register (DCSR)
REGISTER_PCIE_DMA_CONTROL_STATUS                    = 0x04 # Device DMA Control Status Register (DDMACR)
REGISTER_PCIE_DMA_UP_TLP_ADDRESS_1                  = 0x08 # DMA up TLP Address
REGISTER_PCIE_DMA_UP_TLP_ADDRESS_2                  = 0x0c # DMA up TLP Address
REGISTER_PCIE_DMA_UP_TLP_ADDRESS_3                  = 0x10 # DMA up TLP Address
REGISTER_PCIE_DMA_UP_TLP_ADDRESS_4                  = 0x14 # DMA up TLP Address
REGISTER_PCIE_DMA_DOWN_TLP_ADDRESS_1                = 0x18 # DMA down TLP Address
REGISTER_PCIE_DMA_DOWN_TLP_ADDRESS_2                = 0x1c # DMA down TLP Address
REGISTER_PCIE_DMA_DOWN_TLP_ADDRESS_3                = 0x20 # DMA down TLP Address
REGISTER_PCIE_DMA_DOWN_TLP_ADDRESS_4                = 0x24 # DMA down TLP Address
REGISTER_PCIE_MAILBOX_DOWN_TLP_ADDRESS_1            = 0x50 # Mailbox down TLP Address
REGISTER_PCIE_MAILBOX_DOWN_TLP_ADDRESS_2            = 0x54 # Mailbox down TLP Address
REGISTER_PCIE_MAILBOX_DOWN_TLP_ADDRESS_3            = 0x58 # Mailbox down TLP Address
REGISTER_PCIE_MAILBOX_DOWN_TLP_ADDRESS_4            = 0x5c # Mailbox down TLP Address
REGISTER_PCIE_MAILBOX_UP_TLP_ADDRESS_1              = 0x60 # Mailbox up TLP Address
REGISTER_PCIE_MAILBOX_UP_TLP_ADDRESS_2              = 0x64 # Mailbox up TLP Address
REGISTER_PCIE_MAILBOX_UP_TLP_ADDRESS_3              = 0x68 # Mailbox up TLP Address
REGISTER_PCIE_MAILBOX_UP_TLP_ADDRESS_4              = 0x6c # Mailbox up TLP Address
REGISTER_PCIE_TEST_READ_WRITE                       = 0x70 # Test register
REGISTER_PCIE_SYSTEM_CONTROL                        = 0x74 # System Control Register
REGISTER_PCIE_DMA_UP_TLP_STATUS                     = 0x78 # DMA up TLP Status
REGISTER_PCIE_DMA_UP_TX_TIME_LSB                    = 0X88 # DMA UP time
REGISTER_PCIE_DMA_UP_TX_TIME_MSB                    = 0X8c # DMA UP time
#MicroBlaze Register
REGISTER_MICROBLAZE_MAILBOX_DOWN_TLP_ADDR_1         = 0 # Mailbox down TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_DOWN_TLP_ADDR_2         = 0x04 # Mailbox down TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_DOWN_TLP_ADDR_3         = 0x08 # Mailbox down TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_DOWN_TLP_ADDR_4         = 0x0c # Mailbox down TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_UP_TLP_ADDR_1           = 0x10 # Mailbox up TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_UP_TLP_ADDR_2           = 0x14 # Mailbox up TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_UP_TLP_ADDR_3           = 0x18 # Mailbox up TLP Address for MicroBlaze
REGISTER_MICROBLAZE_MAILBOX_UP_TLP_ADDR_4           = 0x1c # Mailbox up TLP Address for MicroBlaze
REGISTER_MICROBLAZE_INTERRUPT                       = 0x20 # Interrupt Register for MicroBlaze
#SPI Register
REGISTER_SPI_CONTROL                                = 0 #
REGISTER_SPI_CONFIG                                 = 0x04 #
REGISTER_SPI_GPO_CONFIG                             = 0x08 #
REGISTER_SPI_ADDRESS                                = 0x0c # SPI地址(包括命令)，最高两位为2则是写，为1则为读
REGISTER_SPI_WRITE                                  = 0x10 #
REGISTER_SPI_READ                                   = 0x14 #
REGISTER_SPI_STROBE_CONFIG                          = 0x18 #
#ADDA Register
REGISTER_ADDA_BASEADDR                              = 0x7ae00000 # 基地址
REGISTER_ADDA_CONTROL_CONFIG                        = 0 # 本通道的控制和设置
REGISTER_ADDA_TRIGGER_REF_LEVEL                     = 0x04 # 通道触发上下沿基准电平
REGISTER_ADDA_PULSE_PERIOD                          = 0x08 # 内部脉冲周期（AD时钟数）
REGISTER_ADDA_PULSE_WIDTH                           = 0x0c # 内部脉冲宽度（AD时钟数）
REGISTER_ADDA_TRIGGER_LENGTH                        = 0x10 # 触发长度（AD时钟数）
REGISTER_ADDA_TRIGGER_LATENCY_LOW                   = 0x14 # 触发延时低位（AD时钟数）
REGISTER_ADDA_TRIGGER_LATENCY_HIGH                  = 0x18 # 触发延时高位（AD时钟数）
REGISTER_ADDA_TRIGGER_TIMES                         = 0x1c # 触发次数
REGISTER_ADDA_TRIGGER_SOURCE_LOW                    = 0x20 # 触发源设置低位,16个触发源的设置
REGISTER_ADDA_TRIGGER_SOURCE_HIGH                   = 0x24 # 触发源设置高位,16个触发源的设置
REGISTER_ADDA_CURRENT_TIME_LOW                      = 0x28 # 当前时间设置低位
REGISTER_ADDA_CURRENT_TIME_HIGH                     = 0x2c # 当前时间设置高位
REGISTER_ADDA_IODELAY_CONTROL                       = 0x30 # 用于调整AD数据总线上的IODELAY
REGISTER_ADDA_DMA_LENGTH                            = 0x34 # AD DMA长度,单位为DMA位宽，用于产生tlast信号
REGISTER_ADDA_TIMESTAMP_LENGTH                      = 0x38 # 时间戳DMA长度,单位为DMA位宽，用于产生tlast信号
REGISTER_ADDA_MAX_DMA_LEGNTH                        = 0x3c # 最大DMA长度限制，单位为AD时钟数，单次工作总数据量（不包括最后的tlast）达到此长度时强制停止，并产生一个中断。设为0时禁用此功能。
REGISTER_ADDA_POST_TRIGGER_LENGTH                   = 0x40 # 触发结束后继续采集的长度（AD时钟数），仅用于电平触发
REGISTER_ADDA_TRIGGER_CHANNEL_SELECT                = 0x44 # 通道出发模式时通道选择寄存器
REGISTER_ADDA_PLL_CONFIG                            = 0x48 # PLL configuration
REGISTER_ADDA_DMA_COUNT                             = 0x78 # DMA计数,DMA发送长度计数
REGISTER_ADDA_STATUS_ERROR                          = 0x7c # 状态及错误
REGISTER_ADDA_CONTROL_CONFIG_CONT                   = 0x50 # 控制和设置续
REGISTER_ADDA_DC_OFFSET_TUNE                        = 0x54 # 各个通道直流电平量化值配置寄存器
REGISTER_ADDA_GPS_SECOND                            = 0x58 # GPS second config
REGISTER_ADDA_TS_COUNTING_PERIOD                    = 0x5c # (Period of AD clock)/(2^248)
REGISTER_ADDA_ACCUMULATOR_SET                       = 0x60 # Accumulator setting
REGISTER_ADDA_ABAMODE_SET                           = 0x64 # ABA mode setting
REGISTER_ADDA_PRETRIGGER_SET                        = 0x68 # Setup pre-trigger length
REGISTER_ADDA_AVERAGE_SET                           = 0x6c # average and gain
REGISTER_ADDA_STATUS                                = 0x7c # status
#SOC system registers
REGISTER_SOC_STATUS                                 = 0x7c # 系统状态及错误
#PCIe AXI registers
REGISTER_PCIE_AXI_STATUS                            = 0x7c # 状态寄存器
REGISTER_PCIE_AXI_TRIGLENGTH                        = 0x78 # 计数器模式下multiple模式的segment Length
# user register
REGISTER_USER_BASEADDR                              = 0x78200000 #Base address of user specific registers
#Commands
#Commit
CMD_MB_GET_DEVICE_INFO                              = 0x30000000 # read:PlatForm version,product code part1,product code part2
CMD_MB_GET_DEVICE_VERSION1                          = 0x30000001 # read:Hardware version,RTL version,Driver version
CMD_MB_GET_DEVICE_VERSION2                          = 0x30000002 # read:UI Version,EDK Version,APP Version
CMD_MB_GET_DEVICE_EXCEPTION_STATUS                  = 0x30000003 # read:get exception status in edk during transfer
CMD_MB_GET_CURRENT_RXDATA_LEN                       = 0x30000004 # Get current rx data length in buffer which is ready for transfer
CMD_MB_TRIGGER_SOURCE_READ                          = 0x30000315 # Read registers that AD_INTF_CFG6 command writes to # Read command with its tag starts with 0x3xxxxxxx
CMD_MB_READ_32BIT_REGISTER                          = 0x30000a01 # read 32 bit register
CMD_MB_GET_RXBUF_LEN                                = 0x30000601 # Return PCIe axi dma buffer length in Byte
CMD_MB_READ_FLASH_U32                               = 0x30000325 # Read specific flash address and return int16 data
CMD_MB_GPIO_READ                                    = 0x30000326 # Set direction, read current values on GPIO line
CMD_MB_READ_FLASH_DBL                               = 0x30000327 # Read data of double from XCF or SPI flash
CMD_MB_READ_FLASH_DEVICE_INFO                       = 0x30000328 # Read flash device ID and manufactory code from edk
CMD_MB_GET_DEVICE_FPGA_DMA                          = 0x10000130 # 读取FPGA-Dma版本信息
CMD_MB_CLOCK_CONFIG                                 = 0x300 # 时钟配置命令
CMD_MB_ALLINONE_CLOCK_CONFIG                        = 0x318 # Configure AllInOne Clock board
CMD_MB_CLOCK_INITIAL                                = 0x319 # Initialize AllInOne Clock board before configuration
CMD_MB_SOFT_TRIGGER_PULSE                           = 0x309 # Feed in a soft trigger pulse into ADC interface if soft trigger mode is enabled
CMD_MB_ENABLE_PULSE                                 = 0x30a # enable internal pulse generator(offset                                                                                                                                                                      = 0x0) bit[20]
CMD_MB_USER_STOP                                    = 0x30b # Send this command to board to disable trig_en if user press stop button
CMD_MB_GET_TIMESTAMP                                = 0x30d # Get Timestamp Data
CMD_MB_READY_TO_GET_DATA                            = 0x30e # This command is an acknowledge to board that PC is ready to receive new type of data. It indicates that the last pcie TX DMA is completed gracefully by PC then get pcie ready to receive new type of data.
CMD_MB_RESET_ADC_INTERFACE                          = 0x313 # To reset ADC interface logic.The command should be executed every time when ADC work mode changes.
CMD_MB_RESET_ADC_DEVICE                             = 0x314 # To reset ADC device.Rarely used.
CMD_MB_RESET_BOARD                                  = 0x900 # board system global soft-reset
CMD_MB_TX_DMA_COMPLETE                              = 0x20000000 # Send information to PC indicating that TX DMA transfer is done. Note that there might be datas not aligned with 128-byte to comprise of a TLP
CMD_MB_TIMESTAMP_READY                              = 0x20000001 # Write this command to PC indicating that a Timestamp DMA is just completed and require a pcie DMA slot to read these data out.
CMD_MB_WORK_MODE_SELECT                             = 0x600 # Choose transfer/trigger mode
CMD_MB_WORK_MODE_CONFIG                             = 0x601 # setup work mode step2
CMD_MB_AD_ENABLE                                    = 0x800 # AD ENABLE and get ready to start transfer. Samples are sent to memory once RX DMA is commenced
CMD_MB_WRITE_32BIT_REGISTER                         = 0xa00 # write 32 bit register
CMD_MB_WRITE_SPI_REGISTER                           = 0xa02 # write spi register
CMD_MB_SEND_32BIT_REGISTER                          = 0x20000002 # send read value of 32bit register to pc
CMD_MB_WRITE_IO_DELAY_REGISTER                      = 0xa04 # write IO delay register
CMD_MB_SET_IO_DELAY_OFFSET                          = 0xa05 # Set IO delay offset for a individual data bus
CMD_MB_DDS_CONFIG                                   = 0xb00 # Configurate DDS chip(AD9912) for ADC amplitue and phase calibration purpose.
CMD_MB_TUNE_DAC_OFFSET                              = 0x400 # offset dac tuning command
CMD_MB_TUNE_PGA                                     = 0x401 # PGA tuning
CMD_MB_TUNE_ADC_GAIN                                = 0x402 # tune digital gain in ADC
CMD_MB_PLL_PHASE_SHIFT                              = 0x31b # Config MMCM in FPGA to shift clock phase for QT1125 only
CMD_MB_FORCE_TLAST                                  = 0x31c # Force a tlast signal asserted to RX DMA
CMD_MB_ADDA_CONTROL_CONFIG_CONT                     = 0x31d # ADDA control(con't)
CMD_MB_TIMESTAMP_SELECT                             = 0x31e # Select timestamp source between system and user logic
#Config
CMD_MB_ADC_SETUP                                    = 0x301 # ADC Channel Setup
CMD_MB_ADC_INTF_MODE_CONFIG                         = 0x302 # ADC Work Mode Setup
CMD_MB_EDGE_VOLTAGE                                 = 0x303 # rise/fall-ing edge reference voltage level(0x4)
CMD_MB_PULSE_PERIOD_WIDTH                           = 0x304 # internal pulse period & width
CMD_MB_TRIGGER_LATENCY                              = 0x305 # Trigger latency
CMD_MB_TRIGGER_SOURCE                               = 0x307 # Trigger Source
CMD_MB_CURRENT_TIME                                 = 0x308 # Current Time
CMD_MB_TIMESTAMP_CONFIG                             = 0x30c # Enable/Disable Timestamp mode
CMD_MB_TRIGGER_MODE                                 = 0x30f # Trigger Mode
CMD_MB_TRIGGER_HOLD                                 = 0x310 # Trigger Hold
CMD_MB_TRIGGER_MASK                                 = 0x311 # Trigger Mask('or','and')
CMD_MB_DATA_COMPRESS                                = 0x312 # Data Width Convert, internal data compression is enabled to save bandwidth
CMD_MB_START_RX_DMA                                 = 0x700 # Start RX DMA
CMD_MB_START_DDS                                    = 0x701 # Start DDS
CMD_MB_START_REPLAY                                 = 0x702 # start replay
CMD_MB_SET_DA_PLAYBACK_MODE                         = 0xc00 # Setup DA play back mode
CMD_MB_TRIGGER_SOURCE_CONFIG                        = 0x315 # Enable/disable one trigger source each time this command is executed.
CMD_MB_TRIGGER_CHANNEL_SELECT                       = 0x316 # Choose which physical channel as trigger source
CMD_MB_SETUP_INPUT_CHANNEL                          = 0x31a # choose active input physical channel
CMD_MB_CALIB_STATUS_CONFIG                          = 0x317 # Flag calibration status to control other command behavior, such as 0x301, 0x900(3), etc.
CMD_MB_CREATE_WAVEFORM                              = 0x500 # Create waveform with its attributes such like index, length and loop count.
CMD_MB_POSTTRIGGER_LENGTH                           = 0x31f # Write post-trigger length, in samples, for level trigger only
CMD_MB_GPIO_SET                                     = 0x320 # Configure GPIO, direction, digital acquisitions
CMD_MB_ABAMODE_SET                                  = 0x321 # Setup ABA mode
CMD_MB_DIGIN_LATENCY                                = 0x322 # Change digital input latency by AD clock cycles
CMD_MB_DATA_FORMAT                                  = 0x323 # offset binary or Two's complement code
CMD_MB_GPIO_WRITE                                   = 0x324 # Set direction, write user define values
CMD_MB_WRITE_FLASH_DBL                              = 0x328 # Write data of double to XCF or SPI flash
CMD_MB_ERASE_FLASH                                  = 0x329 # Write data of double to XCF or SPI flash
CMD_MB_NOTIFY_SIZEB                                 = 0x330 # Minimize notified size in bytes
#BPI flash
FLASH_BASE_ADDR                                     = (0x07FFFC0*2) # Byte address
FLASH_DATA_LEN                                      = 0x24/2 #
#SPI flash(@ADDA card)
SPI_FLASH_BASE_ADDR                                 = 0x01000000 # Byte address

#To be revised
DMABUFCNT                                           = 2 #
DRV_MALLOC_LEN_FOR_DMA                              = 0x2000000 # 0x100000 is 32 MB
EACH_DMA_MAX_LEN                                    = (DRV_MALLOC_LEN_FOR_DMA/8) # tx max len is 8MB.
EACH_DMA_RX_MAX_LEN                                 = (EACH_DMA_MAX_LEN/2) # rx max len is 4MB.
EACH_DMA_MIN_LEN                                    = 0x20 #
#To be revised
QTFM_COMMON_BOARDID_1125                            = 0
QTFM_COMMON_BOARDID_1138                            = 1

QTFM_COMMON_CLOCK_REF_MODE_0                        = 0 # OCXO as reference clock with higher clock quality
QTFM_COMMON_CLOCK_REF_MODE_1                        = 1 # External reference clock input from panel
QTFM_COMMON_CLOCK_REF_MODE_2                        = 2 # TCXO as reference clock
QTFM_COMMON_CLOCK_VCO_MODE_0                        = 3 # Internal VCO mode
QTFM_COMMON_CLOCK_VCO_MODE_1                        = 4 # External VCO mode
QTFM_COMMON_CLOCK_INTERNAL_VCO_MIN                  = 2000000000 # Internal VCO minimum frequency
QTFM_COMMON_CLOCK_INTERNAL_VCO_MAX                  = 4100000000 # Internal VCO maximum frequency
QTFM_COMMON_CLOCK_EXTERNAL_VCO_FREQUENCY            = 2500000000 # Hz
QTFM_COMMON_CLOCK_FREQUENCY_MIN                     = 33064516 # Hz
QTFM_COMMON_CLOCK_FREQUENCY_MAX                     = 4100000000 # Hz
QTFM_COMMON_CLOCK_FREQUENCY_GRANULARITY             = 10 # Hz
QTFM_COMMON_CLOCK_INTERNAL_LF_BANDWIDTH             = 200000 # Hz bandwidth of internal pll loop filter

QTFM_COMMON_ADC_CLOCK_MODE_0                        = 0#Choose on-board PLL as clock source
QTFM_COMMON_ADC_CLOCK_MODE_1                        = 1#Choose external clock from panel as clock source

QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_6                = 1#416.67MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_5                = 2 #500MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_4                = 3 #625MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_3                = 4 #833.33MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_2                = 5 #1250MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_1                = 6 #2500MHz
QTFM_COMMON_CLOCK_FREQUENCY_DEVIDE_1_VALUE          = 2500#MHz


QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_1               = 1 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_2               = 2 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_3               = 3 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_4               = 4 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_5               = 5 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_6               = 6 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_7               = 7 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_8               = 8 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_9               = 9 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_10              = 10 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_11              = 11 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_12              = 12 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_EXTERNAL_13              = 13 #External Trigger
QTFM_COMMON_TRIGGER_SOURCE_CHANNEL                  = 14 #Channel Trigger
QTFM_COMMON_TRIGGER_SOURCE_PULSE                    = 15 #Pulse Trigger
QTFM_COMMON_TRIGGER_SOURCE_SOFTWARE                 = 16 #Software Trigger
QTFM_COMMON_TRIGGER_SOURCE_MAX                      = 17 #Caution:Change this

QTFM_COMMON_TRANSMIT_DIRECTION_BRD2PC               = 0 #tx
QTFM_COMMON_TRANSMIT_DIRECTION_PC2BRD               = 1 #rx

QTFM_COMMON_AD_WORK_MODE_NORMAL                     = 0#Normal
QTFM_COMMON_AD_WORK_MODE_RAMP                       = 1 #Ramp
QTFM_COMMON_AD_WORK_MODE_FLASH_11                   = 2 #Flash 11
QTFM_COMMON_AD_WORK_MODE_FLASH_12                   = 3 #Flash 12
QTFM_COMMON_AD_WORK_MODE_FLASH_16                   = 4#Flash 16

QTFM_COMMON_AD_INTERFACE_MODE_NORMAL                = 0#normal mode, where adc data is received and send to memory
QTFM_COMMON_AD_INTERFACE_MODE_TEST                  = 1#test mode, a counter will be send to memory

QTFM_COMMON_TIMESTAMP_INIT_MODE_DISABLE             = 0#Disable timestamp mode. Timestamp counter keep no change and values is param2 and param3 are ignored
QTFM_COMMON_TIMESTAMP_INIT_MODE_ENABLE              = 1#Enable timestamp and initialize timestamp counter to the values contains in Param2 and Parame3 column
QTFM_COMMON_TIMESTAMP_INIT_MODE_NO_CONFIG           = 2#Enable timestamp but not re-configurate timestamp counter values.

QTFM_COMMON_TRIGGER_MODE_EDGE                       = 0x50000000# 边沿触发
QTFM_COMMON_TRIGGER_MODE_LEVEL                      = 0x60000000 # 电平触发，此时触发延时和长度都无效

QTFM_COMMON_TRIGGER_TYPE_FALLING_EDGE               = 0
QTFM_COMMON_TRIGGER_TYPE_RISING_EDGE                = 1
QTFM_COMMON_TRIGGER_TYPE_LOW_LEVEL                  = 2
QTFM_COMMON_TRIGGER_TYPE_HIGH_LEVEL                 = 3
QTFM_COMMON_TRIGGER_TYPE_DOUBLE_EDGE                = 4

QTFM_COMMON_TRIGGER_KEEP_MODE_DISABLE               = 0# 禁止触发保持功能
QTFM_COMMON_TRIGGER_KEEP_MODE_ENABLE                = 1

QTFM_COMMON_TRIGGER_SOURCE_MASK_OR                  = 0#'or'
QTFM_COMMON_TRIGGER_SOURCE_MASK_AND                 = 1 #'and'

QTFM_COMMON_DWIDTH_CONVERT_MODE_0_COMPLEMENT        = 0# 高位补0
QTFM_COMMON_DWIDTH_CONVERT_MODE_COMPRESS            = 1 # '拼位

QTFM_COMMON_BOARD_WORK_MODE_STD_SIGNLE              = 0
QTFM_COMMON_BOARD_WORK_MODE_STD_MULTI               = 1
QTFM_COMMON_BOARD_WORK_MODE_FIFO_SINGLE             = 2
QTFM_COMMON_BOARD_WORK_MODE_FIFO_MULTI              = 3
QTFM_COMMON_BOARD_REPLAY_MODE_STD_SINGLE            = 4
QTFM_COMMON_BOARD_REPLAY_MODE_STD_CONTINUOUS        = 5
QTFM_COMMON_BOARD_REPLAY_MODE_STD_SINGLE_START      = 6
QTFM_COMMON_BOARD_REPLAY_MODE_STD_MULTIPLE          = 7
QTFM_COMMON_BOARD_REPLAY_MODE_FIFO_SINGLE           = 8
QTFM_COMMON_BOARD_REPLAY_MODE_FIFO_CONTINUOUS       = 9
QTFM_COMMON_BOARD_REPLAY_MODE_FIFO_MULTIPLE         = 10
QTFM_COMMON_BOARD_WORK_MODE_FIFO_SINGLE_LOOPBUF     = 11
QTFM_COMMON_BOARD_WORK_MODE_FIFO_MULTIPLE_LOOPBUF   = 12
QTFM_COMMON_BOARD_WORK_MODE_STD_SINGLE_PLUS_LOOPBUF = 13
QTFM_COMMON_BOARD_WORK_MODE_TIMED_TRANS             = 0x70000000
QTFM_COMMON_BOARD_WORK_MODE_COUNTER                 = 0X90000000

QTFM_COMMON_IOOFFSET_BUS_INDEX_0                    = 0 #Bus a
QTFM_COMMON_IOOFFSET_BUS_INDEX_1                    = 1 #Bus b
QTFM_COMMON_IOOFFSET_BUS_INDEX_2                    = 2 #Bus c
QTFM_COMMON_IOOFFSET_BUS_INDEX_3                    = 3 #Bus d

QTFM_COMMON_DDS_INDEX_0                             = 0#DDS setting for 2.5GHz/500MHz input clock frequency to ADC
QTFM_COMMON_DDS_INDEX_1                             = 1#DDS setting for 1.25GHz input clock frequency to ADC
QTFM_COMMON_DDS_INDEX_2                             = 2#DDS setting for 625MHz input clock frequency to ADC

QTFM_DA_PLAYBACK_MODE_STD_SINGLE                    = 0
QTFM_DA_PLAYBACK_MODE_STD_CONTINUOUS                = 1
QTFM_DA_PLAYBACK_MODE_STD_SINGLE_START              = 2
QTFM_DA_PLAYBACK_MODE_STD_MULTIPLE                  = 3
QTFM_DA_PLAYBACK_MODE_FIFO_SINGLE                   = 4
QTFM_DA_PLAYBACK_MODE_FIFO_CONTINUOUS               = 5
QTFM_DA_PLAYBACK_MODE_FIFO_MULTIPLE                 = 6

QTFM_PRODUCT_MODE_QT1125AC1                         = 0
QTFM_PRODUCT_MODE_QT1125AC2                         = 1
QTFM_PRODUCT_MODE_QT1125AC4                         = 2
QTFM_PRODUCT_MODE_QT1125DC1                         = 3
QTFM_PRODUCT_MODE_QT1125DC2                         = 4
QTFM_PRODUCT_MODE_QT1125DC4                         = 5
QTFM_PRODUCT_MODE_QT1128AC1                         = 6
QTFM_PRODUCT_MODE_QT1128AC2                         = 7
QTFM_PRODUCT_MODE_QT1128DC1                         = 8
QTFM_PRODUCT_MODE_QT1128DC2                         = 9
QTFM_PRODUCT_MODE_QT1130AC1                         = 10
QTFM_PRODUCT_MODE_QT1130AC2                         = 11
QTFM_PRODUCT_MODE_QT1130AC4                         = 12
QTFM_PRODUCT_MODE_QT1130DC1                         = 13
QTFM_PRODUCT_MODE_QT1130DC2                         = 14
QTFM_PRODUCT_MODE_QT1130DC4                         = 15
QTFM_PRODUCT_MODE_QT1135AC1                         = 16
QTFM_PRODUCT_MODE_QT1135AC2                         = 17
QTFM_PRODUCT_MODE_QT1135AC4                         = 18
QTFM_PRODUCT_MODE_QT1135DC1                         = 19
QTFM_PRODUCT_MODE_QT1135DC2                         = 20
QTFM_PRODUCT_MODE_QT1135DC4                         = 21
QTFM_PRODUCT_MODE_QT1138AC2                         = 22
QTFM_PRODUCT_MODE_QT1138AC4                         = 23
QTFM_PRODUCT_MODE_QT1138AC6                         = 24
QTFM_PRODUCT_MODE_QT1138AC8                         = 25
QTFM_PRODUCT_MODE_QT1138DC4                         = 26
QTFM_PRODUCT_MODE_QT1138DC3                         = 27
QTFM_PRODUCT_MODE_QT1138DC2                         = 28
QTFM_PRODUCT_MODE_QT1138DC1                         = 29
QTFM_PRODUCT_MODE_QT1229AC2                         = 30
QTFM_PRODUCT_MODE_QT1238AC8                         = 31
QTFM_PRODUCT_MODE_QT156AC1                          = 32
QTFM_PRODUCT_MODE_QT156AC2                          = 33

QTFM_COUPLE_AC                                      = 0
QTFM_COUPLE_DC                                      = 1

CHANNEL_0                                           = 0 #Physical channel 0
CHANNEL_1                                           = 1 #Physical channel 1
CHANNEL_2                                           = 2 #Physical channel 2
CHANNEL_3                                           = 3 #Physical channel 3
CHANNEL_4                                           = 4 #Physical channel 4
CHANNEL_5                                           = 5 #Physical channel 5
CHANNEL_6                                           = 6 #Physical channel 6
CHANNEL_7                                           = 7 #Physical channel 7

ABA_NORMAL_MODE                                     = 0#ABA mode is disabled
ABA_DUAL_MODE                                       = 1#ABA dual clock mode
ABA_SLOW_MODE                                       = 2#ABA slow clock mode
#
#输入档位选择
#对于QT1138VG，QTFM_INPUT_RANGE_1~4分别表示±0.5V，±1V，±2.5V，±5V；
#对于QT114x系列，QTFM_INPUT_RANGE_1~4分别表示±0.25V，±0.5V，±1V，±2V
#对于QT1125VG，QTFM_INPUT_RANGE_1~4分别表示±50mV，±100mV，±200mV，±500mV；
#QTFM_INPUT_RANGE_5:暂时保留，无定义；
QTFM_INPUT_RANGE_1                                  = 0 #1X +full_scale in mV
QTFM_INPUT_RANGE_2                                  = 1 #2X +full_scale in mV
QTFM_INPUT_RANGE_3                                  = 2 #5X +full_scale in mV
QTFM_INPUT_RANGE_4                                  = 3 #10X +full_scale in mV
QTFM_INPUT_RANGE_5                                  = 4 #10X +full_scale in mV

#QT1125 ADC通道模式
QTFM_1125_CHANNEL_MODE_4_CHANNEL                = 0x100  # Four-channel mode (1.25 Gsps per channel)
QTFM_1125_CHANNEL_MODE_2_CHANNEL_AC             = 0x104  # Two-channel mode (channel A and channel C, 2.5 Gsps per channel)
QTFM_1125_CHANNEL_MODE_2_CHANNEL_BC             = 0x105  # Two-channel mode (channel B and channel C, 2.5 Gsps per channel)
QTFM_1125_CHANNEL_MODE_2_CHANNEL_AD             = 0x106  # Two-channel mode (channel A and channel D, 2.5 Gsps per channel)
QTFM_1125_CHANNEL_MODE_2_CHANNEL_BD             = 0x107  # Two-channel mode (channel B and channel D, 2.5 Gsps per channel)
QTFM_1125_CHANNEL_MODE_1_CHANNEL_A              = 0x108  # One-channel mode (channel A, 5 Gsps)
QTFM_1125_CHANNEL_MODE_1_CHANNEL_B              = 0x109  # One-channel mode (channel B, 5 Gsps)
QTFM_1125_CHANNEL_MODE_1_CHANNEL_C              = 0x10a  # One-channel mode (channel C, 5 Gsps)
QTFM_1125_CHANNEL_MODE_1_CHANNEL_D              = 0x10b  # One-channel mode (channel D, 5 Gsps)
