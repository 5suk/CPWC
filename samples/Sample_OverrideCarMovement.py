from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import time
import win32com.client as com
import math
import pandas as pd


class TransientInstanceHandler(HandlerBase):
    def OnDoMovement(self, dTimeInSeconds, proxy):
        proxyCar = com.Dispatch(proxy)
        logProxy.logger.info("dTimeInSeconds={}".format(dTimeInSeconds))
        logProxy.logger.info("instance.ID={}".format(proxyCar.ID))
        logProxy.logger.info("TransientType={}".format(proxyCar.TransientType))
        if proxyCar.TransientType == const._TransientCar:
            if saveCarID == proxyCar.ID :
                global aTime
                aTime = aTime + dTimeInSeconds
                Position = proxyCar.Position
                x = 4900.0 + 10.0 * aTime
                z = 4997.0 + math.sin(math.pi * aTime)
                y = 560.0
                proxyCar.PositionInTraffic = SetF8COMdVec3(Position, x, y, z)
                z = 10.0
                x = math.cos(math.pi * aTime)
                y = 0.0
                yaw = math.atan2(z, x)
                proxyCar.SetSpeed(const._MeterPerSecond, 10.0)
                proxyCar.YawAngle = yaw
                proxyCar.PitchAngle = 0.0
                proxyCar.RollAngle = 0.0
                proxyCar.BodyPitchAngle = 0.0
                proxyCar.BodyRollAngle = 0.0
                len = math.sqrt(x * x + y * y + z * z)
                x = x / len
                y = y / len
                z = z / len
                dir = proxyCar.Direction
                proxyCar.Direction = SetF8COMdVec3(dir, x, y, z)
                bodyDir = proxyCar.BodyDirection
                proxyCar.BodyDirection = SetF8COMdVec3(bodyDir, x, y, z)
                proxyCar.RPM = 3000.0

                lightState = proxyCar.CarLights
                lightState.isLeftIndicatorOn = (x > 0)
                lightState.isRightIndicatorOn = (x < 0)
                lightState.isBrakeLightOn = True
                proxyCar.CarLights = lightState


class TrafficSimulationHandler(HandlerBase):
    def OnTransientObjectDeleted(self, deletedTransient):
        dDeletedTransient = com.Dispatch(deletedTransient)
        logProxy.logger.info(dDeletedTransient)
        logProxy.logger.info("dDeletedTransient.Name={}".format(dDeletedTransient.Name))
        logProxy.logger.info("dDeletedTransient.ID={}".format(dDeletedTransient.ID))
        if saveCarID == dDeletedTransient.ID :
            dDeletedTransient.UnRegisterEventHandlers()
            if dDeletedTransient.IsSetCallbackOnDoMovement() :
                dDeletedTransient.UnsetCallbackOnDoMovement()
                logProxy.logger.info('UnsetCallbackOnDoMovement!!')

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_OverrideCarMovement'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
        
        global EventList
        EventList = []
        SetCallbackHandlers(EventList, traffic, TrafficSimulationHandler)

        driver = traffic.Driver
        global car
        if driver is not None:
            car = driver.CurrentCar
            if car is not None:
                logProxy.logger.info("car.ID={}".format(car.ID))
        else :
            logProxy.logger.info("no driver")
        logProxy.logger.info(car)

        if car is not None:
            global aTime
            aTime = 0
            global saveCarID
            saveCarID = car.ID
            SetCallbackHandlers(EventList, car, TransientInstanceHandler)
        else:
            print('No driving car')
            loopFlg = False

        # Event Loop
        loopFlg = True
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
        while loopFlg:
            time.sleep(0.005)
            loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun
            if loopFlg == False:
                logProxy.logger.info("loopFlg={}".format(loopFlg))
                logProxy.logger.info("Script close")
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg

    finally:
        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
        CloseCallbackEvent(EventList)
        logProxy.killLogger()
        traffic = None
        del winRoadProxy

if __name__ == '__main__':
    main()

