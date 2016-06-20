# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------

from __future__ import division


#--------------------
# System wide imports
# -------------------

import datetime

# ---------------
# Twisted imports
# ---------------

from twisted.trial    import unittest
from twisted.test     import proto_helpers
from twisted.internet import task, error
from twisted.logger   import Logger, LogLevel
from twisted.internet.defer import inlineCallbacks


#--------------
# local imports
# -------------

from ..base   import EMAProtocol, EMAProtocolFactory
from ...logger import setLogLevel


class TestEMAProtocol1(unittest.TestCase):

    BULK_DUMP = [
        '(CAP 001 982 10150 09329 0000 0000 009 04140 +183 653 +112 0000 000 0000 230 M0300)',
        '(CAP 001 931 10144 09324 0000 0000 008 03518 +176 628 +110 0000 000 0000 224 m0300)',
        '(00:59:56 25/05/2016)',
        '(CAP 001 999 10151 09328 0000 0000 009 04360 +176 692 +112 0000 000 0004 230 M0301)',
        '(CAP 001 954 10145 09323 0000 0000 008 03619 +168 652 +110 0000 000 0000 224 m0301)',
        '(01:59:56 25/05/2016)',
        '(CAP 001 989 10166 09327 0000 0000 009 04757 +117 506 +011 0000 000 0004 177 M0302)',
        '(CAP 001 953 10160 09319 0000 0000 008 04157 +109 479 +009 0000 000 0000 171 m0302)',
        '(02:59:56 03/04/2016)',
        '(CAP 001 996 10164 09323 0000 0000 009 04757 +110 523 +013 0000 000 0000 177 M0303)',
        '(CAO 001 965 10158 09318 0000 0000 008 04185 +105 501 +010 0000 000 0000 171 m0303)',
        '(03:59:51 03/04/2016)',
        '(CAX 001 977 11115 09592 0000 0000 009 04231 +052 560 -031 0000 000 0000 295 M0304)',
        '(CAV 001 903 11107 09584 0000 0000 008 04033 +046 537 -034 0000 000 0000 289 m0304)',
        '(04:59:56 16/01/2016)',
        '(CAV 001 982 11128 09596 0000 0000 009 04469 +047 605 -031 0000 000 0004 295 M0305)',
        '(CAU 001 963 11109 09585 0000 0000 008 03960 +032 550 -038 0000 000 0000 289 m0305)',
        '(05:59:56 16/01/2016)',
        '(CAP 001 999 10205 09377 0000 0000 105 04260 +200 577 +088 0000 000 0000 106 M0306)',
        '(CAO 001 995 10183 09365 0000 0000 008 03969 +170 486 +078 0000 000 0000 100 m0306)',
        '(02:31:26 24/05/2016)',
        '(CAP 001 999 10160 09368 0000 0000 148 30359 +291 386 +136 0000 000 0000 330 M0307)',
        '(CAO 001 960 10133 09339 0000 0000 008 03515 +268 316 +091 0000 000 0000 230 m0307)',
        '(20:52:51 10/06/2016)',
        '(CAP 001 999 10166 09364 0000 0000 161 30294 +269 359 +105 0000 000 0004 241 M0308)',
        '(CAO 001 943 10158 09361 0000 0000 008 30087 +254 338 +083 0000 000 0000 171 m0308)',
        '(23:27:35 13/06/2016)',
        '(CAR 001 999 10119 09302 0000 0000 224 53585 +193 569 +094 0000 000 0014 289 M0309)',
        '(CAO 001 999 10097 09283 0000 0000 133 42126 +180 504 +080 0000 000 0000 000 m0309)',
        '(09:59:55 15/06/2016)',
        '(CAT 001 999 10119 09302 0000 0000 249 52398 +192 563 +093 0000 000 0014 348 M0310)',
        '(CAR 001 999 10098 09284 0000 0000 008 51306 +180 486 +077 0000 000 0000 059 m0310)',
        '(10:59:55 15/06/2016)',
        '(CAU 001 999 10118 09304 0000 0000 037 53576 +199 504 +082 0000 000 0019 277 M0311)',
        '(CAS 001 983 10085 09274 0000 0000 008 51760 +187 444 +072 0000 000 0000 088 m0311)',
        '(11:59:55 15/06/2016)',
        '(CAT 001 999 10115 09301 0000 0000 065 54473 +207 468 +080 0000 000 0023 318 M0312)',
        '(CAS 001 999 10083 09274 0000 0000 011 51793 +193 395 +064 0000 000 0000 088 m0312)',
        '(12:59:55 15/06/2016)',
        '(CAT 001 999 10113 09299 0000 0000 060 54474 +205 430 +069 0000 000 0028 336 M0313)',
        '(CAS 001 999 10071 09263 0000 0000 008 51631 +194 388 +055 0000 000 0000 000 m0313)',
        '(13:59:55 15/06/2016)',
        '(CAS 001 999 10098 09287 0000 0000 028 52911 +207 436 +074 0000 000 0028 324 M0314)',
        '(CAS 001 962 10075 09266 0000 0000 008 51428 +200 392 +062 0000 000 0000 041 m0314)',
        '(14:59:55 15/06/2016)',
        '(CAS 001 999 10099 09289 0000 0000 025 52780 +206 446 +077 0000 000 0038 360 M0315)',
        '(CAR 001 942 10073 09264 0000 0000 008 51005 +199 410 +069 0000 000 0000 023 m0315)',
        '(15:59:55 15/06/2016)',
        '(CAS 001 999 10095 09284 0000 0000 029 52123 +203 428 +072 0000 000 0052 360 M0316)',
        '(CAR 001 944 10074 09264 0000 0000 008 51151 +196 393 +057 0000 000 0000 000 m0316)',
        '(16:59:55 15/06/2016)',
        '(CAR 001 999 10302 09488 0000 0000 023 51782 +198 526 +084 0000 000 0028 295 M0317)',
        '(CAR 001 999 10079 09268 0000 0000 008 48914 +182 412 +062 0000 000 0000 023 m0317)',
        '(17:59:55 15/06/2016)',
        '(CAR 001 999 10098 09284 0000 0000 015 51399 +200 526 +091 0000 000 0014 206 M0318)',
        '(CAR 001 927 10081 09271 0000 0000 008 44053 +183 485 +081 0000 000 0000 188 m0318)',
        '(18:59:55 15/06/2016)',
        '(CAQ 001 999 10110 09292 0000 0000 009 30385 +175 543 +081 0000 000 0000 194 M0319)',
        '(CAQ 001 965 10104 09285 0000 0000 008 30025 +171 526 +076 0000 000 0000 188 m0319)',
        '(20:15:22 15/06/2016)',
        '(CAQ 001 999 10114 09296 0000 0000 009 30027 +177 624 +095 0000 000 0004 200 M0320)',
        '(CAQ 001 981 10108 09289 0000 0000 008 07036 +165 517 +075 0000 000 0000 188 m0320)',
        '(20:59:55 15/06/2016)',
        '(CAQ 001 999 10118 09299 0000 0000 009 30010 +181 532 +084 0000 000 0004 200 M0321)',
        '(CAQ 001 898 10109 09292 0000 0000 008 03601 +170 497 +065 0000 000 0000 194 m0321)',
        '(21:59:55 15/06/2016)',
        '(CAQ 001 940 10151 09335 0000 0000 009 04883 +197 574 +106 0000 000 0004 230 M0322)',
        '(CAP 001 926 10145 09329 0000 0000 008 03809 +191 543 +101 0000 000 0000 206 m0322)',
        '(22:59:56 24/05/2016)',
        '(CAQ 001 946 10151 09334 0000 0000 009 04161 +191 628 +111 0000 000 0004 230 M0323)',
        '(CAP 001 928 10146 09327 0000 0000 008 03419 +183 574 +105 0000 000 0000 224 m0323)',
        '(23:59:56 24/05/2016)',
    ]


    RESULT =   [
        [
            ['Closed', 'Closed', 8.0, 0.1, 98.2, 932.9000000000001, 1015.0, 0.0, 0, 0.9, 4.14, 18.3, 65.3, 11.200000000000001, 0.0, 0, 230, 300], 
            ['Closed', 'Closed', 8.0, 0.1, 93.10000000000001, 932.4000000000001, 1014.4000000000001, 0.0, 0, 0.8, 3.5180000000000002, 17.6, 62.800000000000004, 11.0, 0.0, 0, 224, 300], 
            datetime.datetime(2016, 5, 25, 0, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 99.9, 932.8000000000001, 1015.1, 0.0, 0, 0.9, 4.36, 17.6, 69.2, 11.200000000000001, 0.4, 0, 230, 301], 
            ['Closed', 'Closed', 8.0, 0.1, 95.4, 932.3000000000001, 1014.5, 0.0, 0, 0.8, 3.619, 16.8, 65.2, 11.0, 0.0, 0, 224, 301], 
            datetime.datetime(2016, 5, 25, 1, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 98.9, 932.7, 1016.6, 0.0, 0, 0.9, 4.757, 11.700000000000001, 50.6, 1.1, 0.4, 0, 177, 302], 
            ['Closed', 'Closed', 8.0, 0.1, 95.30000000000001, 931.9000000000001, 1016.0, 0.0, 0, 0.8, 4.157, 10.9, 47.900000000000006, 0.9, 0.0, 0, 171, 302], 
            datetime.datetime(2016, 4, 3, 2, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 99.60000000000001, 932.3000000000001, 1016.4000000000001, 0.0, 0, 0.9, 4.757, 11.0, 52.300000000000004, 1.3, 0.0, 0, 177, 303], 
            ['Closed', 'Closed', 7.9, 0.1, 96.5, 931.8000000000001, 1015.8000000000001, 0.0, 0, 0.8, 4.1850000000000005, 10.5, 50.1, 1.0, 0.0, 0, 171, 303], 
            datetime.datetime(2016, 4, 3, 3, 59, 51)
        ], 
        [
            ['Closed', 'Closed', 8.8, 0.1, 97.7, 959.2, 1111.5, 0.0, 0, 0.9, 4.231, 5.2, 56.0, -3.1, 0.0, 0, 295, 304], 
            ['Closed', 'Closed', 8.6, 0.1, 90.30000000000001, 958.4000000000001, 1110.7, 0.0, 0, 0.8, 4.033, 4.6000000000000005, 53.7, -3.4000000000000004, 0.0, 0, 289, 304], 
            datetime.datetime(2016, 1, 16, 4, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.6, 0.1, 98.2, 959.6, 1112.8, 0.0, 0, 0.9, 4.469, 4.7, 60.5, -3.1, 0.4, 0, 295, 305], 
            ['Closed', 'Closed', 8.5, 0.1, 96.30000000000001, 958.5, 1110.9, 0.0, 0, 0.8, 3.96, 3.2, 55.0, -3.8000000000000003, 0.0, 0, 289, 305], 
            datetime.datetime(2016, 1, 16, 5, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 99.9, 937.7, 1020.5, 0.0, 0, 10.5, 4.26, 20.0, 57.7, 8.8, 0.0, 0, 106, 306], 
            ['Closed', 'Closed', 7.9, 0.1, 99.5, 936.5, 1018.3000000000001, 0.0, 0, 0.8, 3.969, 17.0, 48.6, 7.800000000000001, 0.0, 0, 100, 306], 
            datetime.datetime(2016, 5, 24, 2, 31, 26)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 99.9, 936.8000000000001, 1016.0, 0.0, 0, 14.8, 359.0, 29.1, 38.6, 13.600000000000001, 0.0, 0, 330, 307], 
            ['Closed', 'Closed', 7.9, 0.1, 96.0, 933.9000000000001, 1013.3000000000001, 0.0, 0, 0.8, 3.515, 26.8, 31.6, 9.1, 0.0, 0, 230, 307], 
            datetime.datetime(2016, 6, 10, 20, 52, 51)
        ], 
        [
            ['Closed', 'Closed', 8.0, 0.1, 99.9, 936.4000000000001, 1016.6, 0.0, 0, 16.1, 294.0, 26.900000000000002, 35.9, 10.5, 0.4, 0, 241, 308], 
            ['Closed', 'Closed', 7.9, 0.1, 94.30000000000001, 936.1, 1015.8000000000001, 0.0, 0, 0.8, 87.0, 25.400000000000002, 33.800000000000004, 8.3, 0.0, 0, 171, 308], 
            datetime.datetime(2016, 6, 13, 23, 27, 35)
        ], 
        [
            ['Closed', 'Closed', 8.200000000000001, 0.1, 99.9, 930.2, 1011.9000000000001, 0.0, 0, 22.400000000000002, 358500.0, 19.3, 56.900000000000006, 9.4, 1.4000000000000001, 0, 289, 309], 
            ['Closed', 'Closed', 7.9, 0.1, 99.9, 928.3000000000001, 1009.7, 0.0, 0, 13.3, 21260.0, 18.0, 50.400000000000006, 8.0, 0.0, 0, 0, 309], 
            datetime.datetime(2016, 6, 15, 9, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.4, 0.1, 99.9, 930.2, 1011.9000000000001, 0.0, 0, 24.900000000000002, 239800.0, 19.200000000000003, 56.300000000000004, 9.3, 1.4000000000000001, 0, 348, 310], 
            ['Closed', 'Closed', 8.200000000000001, 0.1, 99.9, 928.4000000000001, 1009.8000000000001, 0.0, 0, 0.8, 130600.0, 18.0, 48.6, 7.7, 0.0, 0, 59, 310], 
            datetime.datetime(2016, 6, 15, 10, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.5, 0.1, 99.9, 930.4000000000001, 1011.8000000000001, 0.0, 0, 3.7, 357600.0, 19.900000000000002, 50.400000000000006, 8.200000000000001, 1.9000000000000001, 0, 277, 311], 
            ['Closed', 'Closed', 8.3, 0.1, 98.30000000000001, 927.4000000000001, 1008.5, 0.0, 0, 0.8, 176000.0, 18.7, 44.400000000000006, 7.2, 0.0, 0, 88, 311], 
            datetime.datetime(2016, 6, 15, 11, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.4, 0.1, 99.9, 930.1, 1011.5, 0.0, 0, 6.5, 447300.0, 20.700000000000003, 46.800000000000004, 8.0, 2.3000000000000003, 0, 318, 312],
            ['Closed', 'Closed', 8.3, 0.1, 99.9, 927.4000000000001, 1008.3000000000001, 0.0, 0, 1.1, 179300.0, 19.3, 39.5, 6.4, 0.0, 0, 88, 312], 
            datetime.datetime(2016, 6, 15, 12, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.4, 0.1, 99.9, 929.9000000000001, 1011.3000000000001, 0.0, 0, 6.0, 447400.0, 20.5, 43.0, 6.9, 2.8000000000000003, 0, 336, 313], 
            ['Closed', 'Closed', 8.3, 0.1, 99.9, 926.3000000000001, 1007.1, 0.0, 0, 0.8, 163100.0, 19.400000000000002, 38.800000000000004, 5.5, 0.0, 0, 0, 313], 
            datetime.datetime(2016, 6, 15, 13, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.3, 0.1, 99.9, 928.7, 1009.8000000000001, 0.0, 0, 2.8000000000000003, 291100.0, 20.700000000000003, 43.6, 7.4, 2.8000000000000003, 0, 324, 314], 
            ['Closed', 'Closed', 8.3, 0.1, 96.2, 926.6, 1007.5, 0.0, 0, 0.8, 142800.0, 20.0, 39.2, 6.2, 0.0, 0, 41, 314], 
            datetime.datetime(2016, 6, 15, 14, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.3, 0.1, 99.9, 928.9000000000001, 1009.9000000000001, 0.0, 0, 2.5, 278000.0, 20.6, 44.6, 7.7, 3.8000000000000003, 0, 360, 315], 
            ['Closed', 'Closed', 8.200000000000001, 0.1, 94.2, 926.4000000000001, 1007.3000000000001, 0.0, 0, 0.8, 100500.0, 19.900000000000002, 41.0, 6.9, 0.0, 0, 23, 315], 
            datetime.datetime(2016, 6, 15, 15, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.3, 0.1, 99.9, 928.4000000000001, 1009.5, 0.0, 0, 2.9000000000000004, 212300.0, 20.3, 42.800000000000004, 7.2, 5.2, 0, 360, 316], 
            ['Closed', 'Closed', 8.200000000000001, 0.1, 94.4, 926.4000000000001, 1007.4000000000001, 0.0, 0, 0.8, 115100.0, 19.6, 39.300000000000004, 5.7, 0.0, 0, 0, 316], 
            datetime.datetime(2016, 6, 15, 16, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.200000000000001, 0.1, 99.9, 948.8000000000001, 1030.2, 0.0, 0, 2.3000000000000003, 178200.0, 19.8, 52.6, 8.4, 2.8000000000000003, 0, 295, 317], 
            ['Closed', 'Closed', 8.200000000000001, 0.1, 99.9, 926.8000000000001, 1007.9000000000001, 0.0, 0, 0.8, 89140.0, 18.2, 41.2, 6.2, 0.0, 0, 23, 317], 
            datetime.datetime(2016, 6, 15, 17, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.200000000000001, 0.1, 99.9, 928.4000000000001, 1009.8000000000001, 0.0, 0, 1.5, 139900.0, 20.0, 52.6, 9.1, 1.4000000000000001, 0, 206, 318], 
            ['Closed', 'Closed', 8.200000000000001, 0.1, 92.7, 927.1, 1008.1, 0.0, 0, 0.8, 40530.0, 18.3, 48.5, 8.1, 0.0, 0, 188, 318], 
            datetime.datetime(2016, 6, 15, 18, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.1, 0.1, 99.9, 929.2, 1011.0, 0.0, 0, 0.9, 385.0, 17.5, 54.300000000000004, 8.1, 0.0, 0, 194, 319], 
            ['Closed', 'Closed', 8.1, 0.1, 96.5, 928.5, 1010.4000000000001, 0.0, 0, 0.8, 25.0, 17.1, 52.6, 7.6000000000000005, 0.0, 0, 188, 319], 
            datetime.datetime(2016, 6, 15, 20, 15, 22)
        ], 
        [
            ['Closed', 'Closed', 8.1, 0.1, 99.9, 929.6, 1011.4000000000001, 0.0, 0, 0.9, 27.0, 17.7, 62.400000000000006, 9.5, 0.4, 0, 200, 320], 
            ['Closed', 'Closed', 8.1, 0.1, 98.10000000000001, 928.9000000000001, 1010.8000000000001, 0.0, 0, 0.8, 7.0360000000000005, 16.5, 51.7, 7.5, 0.0, 0, 188, 320], 
            datetime.datetime(2016, 6, 15, 20, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.1, 0.1, 99.9, 929.9000000000001, 1011.8000000000001, 0.0, 0, 0.9, 10.0, 18.1, 53.2, 8.4, 0.4, 0, 200, 321], 
            ['Closed', 'Closed', 8.1, 0.1, 89.80000000000001, 929.2, 1010.9000000000001, 0.0, 0, 0.8, 3.601, 17.0, 49.7, 6.5, 0.0, 0, 194, 321], 
            datetime.datetime(2016, 6, 15, 21, 59, 55)
        ], 
        [
            ['Closed', 'Closed', 8.1, 0.1, 94.0, 933.5, 1015.1, 0.0, 0, 0.9, 4.883, 19.700000000000003, 57.400000000000006, 10.600000000000001, 0.4, 0, 230, 322], 
            ['Closed', 'Closed', 8.0, 0.1, 92.60000000000001, 932.9000000000001, 1014.5, 0.0, 0, 0.8, 3.809, 19.1, 54.300000000000004, 10.100000000000001, 0.0, 0, 206, 322], 
            datetime.datetime(2016, 5, 24, 22, 59, 56)
        ], 
        [
            ['Closed', 'Closed', 8.1, 0.1, 94.60000000000001, 933.4000000000001, 1015.1, 0.0, 0, 0.9, 4.1610000000000005, 19.1, 62.800000000000004, 11.100000000000001, 0.4, 0, 230, 323], 
            ['Closed', 'Closed', 8.0, 0.1, 92.80000000000001, 932.7, 1014.6, 0.0, 0, 0.8, 3.419, 18.3, 57.400000000000006, 10.5, 0.0, 0, 224, 323], 
            datetime.datetime(2016, 5, 24, 23, 59, 56)
        ]
    ]


    def setUp(self):
        setLogLevel(namespace='serial', levelStr='debug')
        setLogLevel(namespace='protoc', levelStr='debug')
        self.transport = proto_helpers.StringTransport()
        #self.clock     = task.Clock()
        self.factory   = EMAProtocolFactory()
        self.protocol  = self.factory.buildProtocol(0)
        self.transport.protocol = self.protocol
        #EMAProtocol.callLater   = self.clock.callLater
        self.protocol.makeConnection(self.transport)
       
   
    # --------------
    # EMA Bulk Dumps
    # --------------

    def test_getDailyMinMaxDump(self, nretries=0):
        d = self.protocol.getDailyMinMaxDump()
        self.assertEqual(self.transport.value(), '(@H0300)')
        self.transport.clear()
        for data in self.BULK_DUMP:
            self.protocol.dataReceived(data)
        d.addCallback(self.assertEqual, self.RESULT)
        return d