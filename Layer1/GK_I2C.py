"""
Program test environment
Pyhone version:3.4.1
Firmware version:2.8.28
Dependent files(MacOSX):libGinkgo_Driver.dylib,libusb-0.1.4.dylib,libusb-1.0.0.dylib
Dependent files(Windows):Ginkgo_Driver.dll
Dependent files(Linux):libGinkgo_Driver.so,libusb-1.0.so
More Infomation:www.viewtool.com
"""
'''
Modified on Sep 11, 2026
Chicago
@author: lijiangwei
'''
from ctypes import *
import platform
import os
from time import sleep

# I2C data types initialization Define
class VII_INIT_CONFIG(Structure):  
	_fields_ = [
		("MasterMode", c_ubyte),	# Master-slave choice: 0-slave, 1-master
		("ControlMode", c_ubyte),	# Control mode: 0-Standard slave mode, 1-Standard mode, 2-GPIO mode
		("AddrType", c_ubyte),		# 7-7bit mode, 10-10bit mode
		("SubAddrWidth",c_ubyte),	# Sub-Address width: value of 0~4, 0 means no Sub-Address mode
		("Addr",c_ushort),			# Device address in salve mode
		("ClockSpeed",c_uint)		# Clock frequency(HZ)
	];
# Data types of Ginkgo series adapter information.
class VII_BOARD_INFO(Structure):  
	_fields_ = [
		("ProductName", c_ubyte*32),	# Product name
		("FirmwareVersion", c_ubyte*4),	# Firmware version
		("HardwareVersion", c_ubyte*4),	# Hardware version
		("SerialNumber",c_ubyte*12),	# The adapter serial number
	];
# I2C time parameter definition in GPIO mode(ms)
class VII_TIME_CONFIG(Structure):
	_fields_ = [
		("tHD_STA",c_ushort),		# Timing for start signal Keeping
		("tSU_STA",c_ushort),		# Timing for start signal be established
		("tLOW",c_ushort),			# Timing for clock low level
		("tHIGH",c_ushort),			# Timing for clock high level
		("tSU_DAT",c_ushort),		# Timing for data input be established
		("tSU_STO",c_ushort),		# Timing for stop signal be established
		("tDH",c_ushort),			# Timing for data output Keeping
		("tDH_DAT",c_ushort),		# Timing for data input Keeping
		("tAA",c_ushort),			# SCL lower to SDA output and response signal
		("tR",c_ushort),			# Timing for SDA and SCL rising
		("tF",c_ushort),			# Timing for SDA and SCL going down
		("tBuf",c_ushort),			# Free timing of the bus until the new mission
		("tACK",c_ubyte*4),
		("tStart",c_ushort),
		("tStop",c_ushort)
	];

class GK_I2C:
	# The adapter type definition
	VAI_USBADC	=	1
	VCI_USBCAN1	=	3
	VCI_USBCAN2	=	4
	VGI_USBGPIO	=	1
	VII_USBI2C	=	1
	VSI_USBSPI	=	2
	# The adapter data initialization definition
	VII_ADDR_7BIT		=	7	# 7-bit address mode
	VII_ADDR_10BIT		=	10	# 10-bit address mode
	VII_HCTL_SLAVE_MODE =   0   # Standard slave mode
	VII_HCTL_MODE		=	1	# Standard mode
	VII_SCTL_MODE		=	2	# GPIO mode
	VII_MASTER			=	1	# Master
	VII_SLAVE			=	0	# Slave
	VII_SUB_ADDR_NONE	=	0	# No sub-address
	VII_SUB_ADDR_1BYTE	=	1	# 1Byte sub-address
	VII_SUB_ADDR_2BYTE	=	2	# 2Byte sub-address
	VII_SUB_ADDR_3BYTE	=	3	# 3Byte sub-address
	VII_SUB_ADDR_4BYTE	=	4	# 4Byte sub-address
	# Error Type
	ERR_SUCCESS					=	(0)		#
	ERR_PARAMETER_NULL			=	(-1)	#
	ERR_INPUT_DATA_TOO_MUCH		=	(-2)	# 
	ERR_INPUT_DATA_TOO_LESS		=	(-3)	# 
	ERR_INPUT_DATA_ILLEGALITY	=	(-4)	#
	ERR_USB_WRITE_DATA			=	(-5)	# 
	ERR_USB_READ_DATA			=	(-6)	# 
	ERR_READ_NO_DATA			=	(-7)	#
	ERR_OPEN_DEVICE				=	(-8)	#
	ERR_CLOSE_DEVICE			=	(-9)	#
	ERR_EXECUTE_CMD				=	(-10)	#
	ERR_SELECT_DEVICE			=	(-11)	#
	ERR_DEVICE_OPENED			=	(-12)	#
	ERR_DEVICE_NOTOPEN			=	(-13)	#
	ERR_BUFFER_OVERFLOW			=	(-14)	#
	ERR_DEVICE_NOTEXIST			=	(-15)	#
	ERR_LOAD_KERNELDLL			=	(-16)	#
	ERR_CMD_FAILED				=	(-17)	#
	ERR_BUFFER_CREATE			=	(-18)	#

	# I2C data structure definitions (exposed as class attributes)
	VII_INIT_CONFIG = VII_INIT_CONFIG
	VII_BOARD_INFO = VII_BOARD_INFO
	VII_TIME_CONFIG = VII_TIME_CONFIG

	def __init__(self):
		'Load the Ginkgo driver library'
		lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
		if(platform.system()=="Windows"):
			if "64bit" in platform.architecture():
				self.GinkgoLib = windll.LoadLibrary( os.path.join(lib_dir, "windows", "64bit", "Ginkgo_Driver.dll") )
			else:
				self.GinkgoLib = windll.LoadLibrary( os.path.join(lib_dir, "windows", "32bit", "Ginkgo_Driver.dll") )
		elif(platform.system()=="Darwin"):
			self.GinkgoLib = cdll.LoadLibrary( os.path.join(lib_dir, "macos", "libGinkgo_Driver.dylib") )
		elif(platform.system()=="Linux"):
			if "64bit" in platform.architecture():
				self.GinkgoLib = cdll.LoadLibrary( os.path.join(lib_dir, "linux", "64bit", "libGinkgo_Driver.so") )
			else:
				self.GinkgoLib = cdll.LoadLibrary( os.path.join(lib_dir, "linux", "32bit", "libGinkgo_Driver.so") )
		else:
			print("Unknown system")

	# Scan device
	def VII_ScanDevice(self, NeedInit=1):
		'Scan device'
		return self.GinkgoLib.VII_ScanDevice(c_ubyte(NeedInit))

	# Open device 
	def VII_OpenDevice(self, DevType, DevIndex, Reserved=0):
		'Open device'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_OpenDevice(c_int(DevType), c_int(DevIndex), c_int(Reserved))

	# Close device
	def VII_CloseDevice(self, DevType, DevIndex):
		'Close device'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_CloseDevice(c_int(DevType), c_int(DevIndex))

	# Read board infomation
	def VII_ReadBoardInfo(self, DevIndex, pBoardInfo):
		'Read board infomation'
		try:
			assert DevIndex >= 0, 'Device index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_ReadBoardInfo(c_int(DevIndex), pBoardInfo)

	# Config I2C Timing(GPIO Mode)
	def VII_TimeConfig(self, DevType, DevIndex, I2CIndex, pTimeConfig):
		'Read board infomation'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0<=I2CIndex<8, 'Channel index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_TimeConfig(c_int(DevType),c_int(DevIndex),c_int(I2CIndex), pTimeConfig)

	# Config I2C
	def VII_InitI2C(self, DevType, DevIndex, I2CIndex, pInitConfig):
		'Config USB-I2C adapter'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0<=I2CIndex<8, 'Channel index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_InitI2C(c_int(DevType),c_int(DevIndex),c_int(I2CIndex), pInitConfig)

	# Write bytes to I2C bus
	def VII_WriteBytes(self, DevType, DevIndex, I2CIndex, SlaveAddr, SubAddr, pWriteData, WriteLen):
		'Write bytes to I2C bus'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0<=I2CIndex<8, 'Channel index error!'
			assert 0 < WriteLen < 10230, 'Too much data'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_WriteBytes(DevType,c_int(DevIndex),c_int(I2CIndex),c_ushort(SlaveAddr), c_int(SubAddr), pWriteData, c_ushort(WriteLen))

	# Read bytes from I2C bus
	def VII_ReadBytes(self, DevType, DevIndex, I2CIndex, SlaveAddr, SubAddr, pReadData, ReadLen):
		'Read bytes from I2C bus'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0 <= I2CIndex < 8, 'Channel index error!'
			assert 0 < ReadLen < 10230, 'Too much data'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_ReadBytes(c_int(DevType), c_int(DevIndex), c_int(I2CIndex), c_int(SlaveAddr), c_int(SubAddr), pReadData, c_ushort(ReadLen))

	# Read bytes in slave mode
	def VII_SlaveReadBytes(self, DevType, DevIndex, I2CIndex, pReadData, pReadLen):
		'Read bytes in slave mode'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0 <= I2CIndex < 8, 'Channel index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_SlaveReadBytes(c_int(DevType), c_int(DevIndex), c_int(I2CIndex), pReadData, pReadLen)

	# Write bytes in slave mode
	def VII_SlaveWriteBytes(self, DevType, DevIndex, I2CIndex, pWriteData, WriteLen):
		'Write bytes in slave mode'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0 <= I2CIndex < 8, 'Channel index error!'
			assert 0 < WriteLen < 10230, 'Too much data'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_SlaveWriteBytes(c_int(DevType),c_int(DevIndex),c_int(I2CIndex),pWriteData,c_ushort(WriteLen))

	# Query the remaining bytes in slave mode
	def VII_SlaveWriteRemain(self, DevType, DevIndex, I2CIndex, pRemainBytes):
		'Query the remaining bytes in slave mode'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
			assert 0 <= I2CIndex < 2, 'Channel index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_SlaveWriteRemain(c_int(DevType),c_int(DevIndex),c_int(I2CIndex),pRemainBytes)

	# Write user key data to adapter
	def VII_SetUserKey(self, DevType, DevIndex, pUserKey):
		'Write user key data to adapter'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_SetUserKey(c_int(DevType),c_int(DevIndex),pUserKey)

	# Check user key from adapter
	def VII_CheckUserKey(self, DevType, DevIndex, pUserKey):
		'Check user key from adapter'
		try:
			assert DevType == self.VII_USBI2C, 'Device type error!'
			assert DevIndex >= 0, 'Device index error!'
		except AssertionError as args:
			print('%s: %s'%(args.__class__.__name__, args))
			exit()
		return self.GinkgoLib.VII_CheckUserKey(c_int(DevType),c_int(DevIndex),pUserKey)


def main():
	# Create an GK_I2C instance (loads the driver library)
	i2c = GK_I2C()

	# Scan device
	nRet = i2c.VII_ScanDevice(1)
	if(nRet <= 0):
		print("No device connect!")
		exit()
	else:
		print("Connected device number is:"+repr(nRet))

	# Open device
	nRet = i2c.VII_OpenDevice(GK_I2C.VII_USBI2C, 0, 0)
	if(nRet != GK_I2C.ERR_SUCCESS):
		print("Open device error!")
		exit()
	else:
		print("Open device success!")

	# Initialize device
	I2C_InitConfig = GK_I2C.VII_INIT_CONFIG()
	# Master mode
	I2C_InitConfig.MasterMode = GK_I2C.VII_MASTER
	# Hardware control
	I2C_InitConfig.ControlMode = GK_I2C.VII_HCTL_MODE
	# 7-bit address mode
	I2C_InitConfig.AddrType = GK_I2C.VII_ADDR_7BIT
	# Sub address width->1byte
	I2C_InitConfig.SubAddrWidth = GK_I2C.VII_SUB_ADDR_1BYTE
	# Clock speed (in Hz)
	I2C_InitConfig.ClockSpeed = 400000
	nRet = i2c.VII_InitI2C(GK_I2C.VII_USBI2C, 0, 0, byref(I2C_InitConfig))
	if(nRet != GK_I2C.ERR_SUCCESS):
		print("Initialize device error!")
		exit()
	else:
		print("Initialize device success!")

	# Write 8 byte data to 0x08
	WriteData = (c_byte * 8)()
	for i in range(0, len(WriteData)):
		WriteData[i] = i
	nRet = i2c.VII_WriteBytes(GK_I2C.VII_USBI2C, 0, 0, 0xA0, 0x08, byref(WriteData), 8)
	if(nRet != GK_I2C.ERR_SUCCESS):
		print("Write data error! %d"%nRet)
		exit()
	else:
		print("Write data success!")

	# Delay to ensure write complete
	sleep(0.1)

	# Read data from 0x08
	ReadData = (c_byte * 8)()
	for i in range(0, len(ReadData)):
		ReadData[i] = 0
	nRet = i2c.VII_ReadBytes(GK_I2C.VII_USBI2C, 0, 0, 0xA0, 0x08, byref(ReadData), 8)
	if(nRet != GK_I2C.ERR_SUCCESS):
		print("Read data error! %d"%nRet)
		exit()
	else:
		print("Read data success!")
		print("Read Data(Hex):", end='')
		for i in range(0, len(ReadData)):
			print("%02X "%ReadData[i], end='')
		print("")

	# Close device
	nRet = i2c.VII_CloseDevice(GK_I2C.VII_USBI2C, 0)
	if(nRet != GK_I2C.ERR_SUCCESS):
		print("Close device error! %d"%nRet)
		exit()
	else:
		print("Close device success!")


if __name__ == "__main__":
	main()
