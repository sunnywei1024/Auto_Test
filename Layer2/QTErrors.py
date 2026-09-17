#!/usr/bin/env python  
# -*- coding: utf-8 -*-

""" 
@version: v1.0 
@author: BaiLi,modified by Jiangwei.li
@license: Apache Licence  
@contact: BaiLi@queentest.com 
@site: http://www.queentest.com/index.html 
@software: Examples for all QT11xx DAQ cards 
@file: QTErrors.py 
@time: 2017/5/17 19:29 
"""

RES_SUCCESS                                      = 0x00000000
RES_ALREADY_OPEN                                 = 0x00000001
RES_OPEN_FAILURE                                 = 0x80000000
RES_RESET_FAILURE                                = 0x80000001
RES_IOCTL_READREG_FAILURE                        = 0x80000002
RES_IOCTL_WRITEREG_FAILURE                       = 0x80000003
RES_IOCTL_CREATE_INTERRUPT_EVENT_FAILURE         = 0x80000004
RES_IOCTL_MAP_MEMORY_FAILURE                     = 0x80000005
RES_IOCTL_UNMAPADDR_FAILURE                      = 0x80000006
RES_DMATX_LEN_LARGER_MAX                         = 0x80000007
RES_DMA_LEN_IS_ZERO                              = 0x80000008
RES_DMA_LENGTH_128BYTE_ALIGNMENT_ERR             = 0x80000009
RES_DMA_LENGTH_ALIGNMENT_ERROR                   = 0x8000000a
RES_DMA_BUF_UNALLOC                              = 0x8000000b
RES_DATA_READY_TIMEOUT                           = 0x8000000c
RES_DMA_TIMEOUT                                  = 0x8000000d
RES_DMARX_LEN_LARGER_MAX                         = 0x8000000e
RES_FPGABUF_READY_FOR_DMARX_TIMEOUT              = 0x8000000f
RES_STREAM_MODE_ENABLE_TX_ALREADY                = 0x80000010
RES_STREAM_MODE_ENABLE_RX_ALREADY                = 0x80000011
RES_STREAM_MODE_THREAD_TX_FALSE                  = 0x80000012
RES_STREAM_MODE_THREAD_RX_FALSE                  = 0x80000013
RES_WAITFOR_STREAM_DMA_DONE_EVENT_TIMEOUT_TX     = 0x80000014
RES_WAITFOR_STREAM_DMA_DONE_EVENT_TIMEOUT_RX     = 0x80000015
RES_WAITFOR_STREAM_DMA_APP_DONE_EVENT_TIMEOUT_TX = 0x80000016
RES_WAITFOR_STREAM_DMA_APP_DONE_EVENT_TIMEOUT_RX = 0x80000017
RES_DMA_TX_OVER                                  = 0x80000018
RES_DMA_RX_OVER                                  = 0x80000019
RES_CREATE_OR_OPEN_CNF_FAILURE                   = 0x8000001a
RES_READ_CNF_FAILURE                             = 0x8000001b
RES_CNF_IS_EMPTY                                 = 0x8000001c
RES_CNF_IS_LARGER                                = 0x8000001d
RES_SET_BATCH_REGS_WRITEREG_FAILURE              = 0x8000001e
RES_SET_BATCH_REGS_READREG_FAILURE               = 0x8000001f
RES_AUTO_SET_MAILBOX_REG_TIMEOUT                 = 0x80000020
RES_MAILBOX_SETPARAM_TIMEOUT                     = 0x80000021
RES_MAILBOX_GETPARAM_TIMEOUT                     = 0x80000022
RES_MBCMD_CNT_LARGER_THAN_MAXLEN                 = 0x80000023
RES_READ_SETUP_FROM_ARRY_BY_INDEX_FALSE          = 0x80000024
RES_MONITORTXINT_WAIT_FAILED                     = 0x80000025
RES_NOT_TX_INT                                   = 0x80000026
RES_IO_DELAY_CAL_SET_74_FALSE                    = 0x80000027
RES_ERROR_UNKNOWN                                = 0x80000028
RES_ERROR_BAD_PARAMETER                          = 0x80000029
RES_ERROR_NOT_ENOUGH_RESOURCE                    = 0x8000002a
RES_ERROR_UNSUPPORTED                            = 0x8000002b
RES_ERROR_UNEXPECTED                             = 0x8000002c
RES_ERROR_FILE_NOT_FOUND                         = 0x8000002d
RES_ERROR_IODELAY_NO_EYE                         = 0x8000002e
RES_ERROR_CLOCK_FREQ_ILLEGAL                     = 0x8000002f
RES_ERROR_BOARD_EXCEPTION                        = 0x80000030
RES_CALIB_TIMEOUT                                = 0x80000031
RES_MBCMD_TIMEOUT                                = 0x80000032
RES_MBCMD_FAILED                                 = 0x80000033
RES_STORE_DATA_BUZY                              = 0x80000034
RES_ERROR_NO_RANGE_SET                           = 0x80000035
RES_ERROR_NOT_VALID_RANGE                        = 0x80000036
RES_ERROR_NOT_VALID_CHNIDX                       = 0x80000037
RES_ERROR_VFIFO_IS_FULL                          = 0x80000038
RES_ERROR_VFIFO_IS_EMPTY                         = 0x80000039
RES_ERROR_VFIFO_EXCEPTION                        = 0x8000003a
RES_NOT_ENOUGH_DATA_IN_VFIFO                     = 0x8000003b
RES_ERROR_ALLOC_BUF                              = 0x8000003c
RES_ERROR_PRETRIGLEN_ILLEGAL                     = 0x8000003d
RES_ERROR_FLASH_OUT_BLOCK                        = 0x8000003e
RES_ERROR_PRODUCT_INFO_UNDEF                     = 0x8000003f

