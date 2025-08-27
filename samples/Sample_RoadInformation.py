from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
import time
import math
import pandas as pd

def GetRoad():
    global winRoadProxy
    prj = winRoadProxy.Project
    count = prj.RoadsCount
    df = pd.DataFrame(columns=['Name', 'Length', 'Distance','Pos X','Pos Z','Direction angle','Curvature','Height','Slope'])
    row = 0
    logProxy.logger.info("count={}".format(count))
    for i in range(count):
        road = prj.Road(i)
        name = road.Name
        roadLength = road.Length
        isLast = False
        dist = 0.0
        while dist <= roadLength:
            roadPos = road.GetPositionAt(dist);
            roadDir = road.GetDirectionAt(dist);
            angle = math.atan2(roadDir.X, -roadDir.Z);
            angle = angle * 180 / math.pi;
            if (angle < 0):
                angle += 360;

            curvature = road.GetCurvatureAt(dist);
            if (curvature == 0):
                strRadius = 'INF'
            else:
                strRadius = str(1 / curvature);

            slope = road.GetSlopeAt(dist) * 100;

            df.loc[row]=[name, roadLength, dist, roadPos.X, roadPos.Z, angle, strRadius, roadPos.Y, slope]
            row += 1
            if isLast:
                break
            dist += 150
            if dist >= roadLength:
                dist = roadLength
                isLast = True

        logProxy.logger.info(df)
        p = winRoadProxy.PythonPluginDirectory() + "/OutputRoadInformation_py" + str(i) + ".csv"
        df.to_csv(p)

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_RoadInformation'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        GetRoad()

        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
    finally:
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




