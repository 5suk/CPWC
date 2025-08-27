from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
import time
import win32com.client as com

def CoordinateConvert(x, y):
    # Convert
    srcVec2 = com.Dispatch('UCwinRoad.F8COMdVec2')
    dstVec2 = com.Dispatch('UCwinRoad.F8COMdVec2')
    convRes = com.Dispatch('UCwinRoad.F8COMHcsConvertResultType')
    srcVec2.X = x
    srcVec2.Y = y

    hConverter = winRoadProxy.CoordinateConverter.HorizontalCoordinateConvertor
    hConverter.Convert(const._hcLocal_XY, const._hcWGS84_LonLat, srcVec2, dstVec2, convRes);
    logProxy.logger.info("Local(src.X:{}".format(srcVec2.X)+",src.Y:{})".format(srcVec2.Y))
    logProxy.logger.info("WGS84(dst.X:{}".format(dstVec2.X)+",dst.Y:{})".format(dstVec2.Y))
    logProxy.logger.info("Res  (isSuccess:{}".format(convRes.isSuccess)+",isOutOfCS:{}".format(convRes.isOutOfCS)+",isBadArray:{})".format(convRes.isBadArray))
    logProxy.logger.info('==========================================')

def CoordinateConvertArray():
    # ConvertArray
    lIn = [[0] * 2 for i in range(4)]
    lOut = [[0] * 2 for i in range(4)]
    convRes = com.DispatchEx('UCwinRoad.F8COMHcsConvertResultType')
    lIn[0] = (0, 0)
    lIn[1] = (1000, 0)
    lIn[2] = (0, 1000)
    lIn[3] = (1000, 1000)

    hConverter = winRoadProxy.CoordinateConverter.HorizontalCoordinateConvertor
    hConverter.ConvertArray(const._hcLocal_XY, const._hcWGS84_LonLat, lIn, lOut, convRes);
    ret, lOut, convRes = hConverter.ConvertArray(const._hcLocal_XY, const._hcWGS84_LonLat, lIn, lOut, convRes);
    for i in range(0, len(lIn)) :
        logProxy.logger.info("Local{}".format(lIn[i]) + "=>" + "WGS84{}".format(lOut[i]))
    logProxy.logger.info("Res  (isSuccess:{}".format(convRes.isSuccess)+",isOutOfCS:{}".format(convRes.isOutOfCS)+",isBadArray:{})".format(convRes.isBadArray))
    logProxy.logger.info('==========================================')

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_CoordinateConvertion'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        CoordinateConvert(500,500)
        CoordinateConvertArray()

    finally:
        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




