from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import time

def GetRequiredVehicleDistance(speedKmPerHour):
    if speedKmPerHour > 100:
        distance = 112
    elif speedKmPerHour > 80:
        distance = 76
    elif speedKmPerHour > 50:
        distance = 32
    elif speedKmPerHour > 30:
        distance = 14
    else:
        distance = 10
    return distance

class MyVehcleHandler(HandlerBase):
    def OnBeforeCalculateMovement(self, dTimeInSeconds, proxy):
        if proxy is None:
            return
        proxyCar = com.Dispatch(proxy)
        frontCar = proxyCar.DriverAheadInTraffic(const._primaryPath)
        if frontCar is not None:
            if frontCar.TransientType == const._TransientCar:
                if frontCar.ID != 0 :
                    logProxy.logger.info("A front car exists.")
                    logProxy.logger.info("frontCar Name={}".format(frontCar.Name)+", ID={}".format(frontCar.ID))
                    vPos = proxyCar.Position
                    cPos = frontCar.Position
                    currentDistance = Distance(vPos, cPos)
                    carSpeed = proxyCar.Speed(const._KiloMeterPerHour)
                    requiredDistance = GetRequiredVehicleDistance(carSpeed)
                    logProxy.logger.info("#speed={}".format(carSpeed))
                    logProxy.logger.info("#required distance between vehicles ={}".format(requiredDistance))
                    logProxy.logger.info("#current distance between vehicles ={}".format(currentDistance))
                    global assistReset
                    if abs(currentDistance) < requiredDistance :
                        logProxy.logger.info("Narrow distance!")
                        assistReset = True
                        proxyCar.Throttle = 0.0
                        proxyCar.Brake = 1
                        logProxy.logger.info("Brake={}".format(proxyCar.Brake))   
                        winRoadProxy.SimulationCore.SetUserVariable(0, 1)
                        winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(0, 1)
                    else:
                        logProxy.logger.info("Appropriate distance.")
                        if assistReset :
                            assistReset = False
                            logProxy.logger.info("Reset.")
                            proxyCar.Throttle = 0.5
                            proxyCar.Brake = 0
                            winRoadProxy.SimulationCore.SetUserVariable(0, 0)
                            winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(0, 0)
                else:
                    logProxy.logger.info("No front car exists.")    
            else:
                logProxy.logger.info("No front car exists.")
        else:
            logProxy.logger.info("No front car exists.")

def InitUserVariables():
    winRoadProxy.SimulationCore.SetUserVariable(0, 0)

def InitPythonScriptUserFlg():
    for i in range(9):
        winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(i, 0)

def main():
    try:
        start = time.perf_counter_ns()
        
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        
        global const
        const = winRoadProxy.const
        
        scriptName = 'Sample_BrakeAssist'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        InitUserVariables()
        InitPythonScriptUserFlg()

        global assistReset
        assistReset = False
        global EventList
        EventList = []
        
        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
        driver = traffic.Driver
        if driver is not None:
            myCar = driver.CurrentCar
            if myCar is not None:
                SetCallbackHandlers(EventList, myCar, MyVehcleHandler)
                loopFlg = True
                winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
                while loopFlg:
                    time.sleep(0.005)
                    loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun
                    if loopFlg == False:
                        logProxy.logger.info("loopFlg={}".format(loopFlg))
                        logProxy.logger.info("Script close")
                winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
            else :
                logProxy.logger.info("no driver")
    finally:
        if EventList is not None:
            CloseCallbackEvent(EventList)
        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
        logProxy.killLogger()
        traffic = None
        winRoadProxy.SimulationCore.SetUserVariable(0, 0)
        winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(0, 0)
        del winRoadProxy


if __name__ == '__main__':
    main()



