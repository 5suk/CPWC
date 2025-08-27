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

def CheckVehicleAround(proxyCar, dTimeInMilliSec):
    if proxyCar is None:
        return
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
                global resetFlg
                global elapsedtime
                diagnosis = abs(currentDistance) < requiredDistance
                if diagnosis :
                    logProxy.logger.info("Narrow distance!")
                    resetFlg = True
                    logProxy.logger.info("Brake={}".format(proxyCar.Brake))   
                    winRoadProxy.SimulationCore.SetUserVariable(0, 1)
                    winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(2, 1)
                    elapsedtime = elapsedtime + dTimeInMilliSec
                    logProxy.logger.info("###############elapsedtime ={}".format(elapsedtime))
                else:
                    logProxy.logger.info("Appropriate distance.")
                    elapsedtime = 0
                    if resetFlg :
                        resetFlg = False
                        logProxy.logger.info("Reset.")
                        winRoadProxy.SimulationCore.SetUserVariable(0, 0)
                        winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(2, 0)

                winRoadProxy.SimulationCore.SetUserVariable(1, diagnosis)           #Diagnosic result 0:OK,1:NG
                winRoadProxy.SimulationCore.SetUserVariable(2, elapsedtime)         #elapsed time(ms)
                winRoadProxy.SimulationCore.SetUserVariable(3, carSpeed)            #Speed(km/h)
                winRoadProxy.SimulationCore.SetUserVariable(4, requiredDistance)    #required distance between vehicles(m)
                winRoadProxy.SimulationCore.SetUserVariable(5, currentDistance)     #current distance(m)
                winRoadProxy.SimulationCore.SetUserVariable(6, frontCar.ID)         #nearest vehcle ID
            else:
                logProxy.logger.info("No front car exists.")    
        else:
            logProxy.logger.info("No front car exists.")
    else:
        logProxy.logger.info("No front car exists.")    

def InitUserVariables():
    winRoadProxy.SimulationCore.SetUserVariable(0, 0)
    winRoadProxy.SimulationCore.SetUserVariable(1, -1)
    winRoadProxy.SimulationCore.SetUserVariable(2, -1) 
    winRoadProxy.SimulationCore.SetUserVariable(3, -1) 
    winRoadProxy.SimulationCore.SetUserVariable(4, -1) 
    winRoadProxy.SimulationCore.SetUserVariable(5, -1) 
    winRoadProxy.SimulationCore.SetUserVariable(6, -1) 

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
        scriptName = 'Sample_DiagnosisDriving'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        InitUserVariables()
        InitPythonScriptUserFlg()

        global resetFlg
        resetFlg = False
        global elapsedtime
        elapsedtime = 0
        global traffic
        global car
        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
        driver = traffic.Driver
        if driver is not None:
            car = driver.CurrentCar
            if car is not None:
                logProxy.logger.info("car.ID={}".format(car.ID))
                loopFlg = True
                winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
                pre = time.perf_counter_ns()
                while loopFlg:
                    time.sleep(0.005)
                    loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun

                    now = time.perf_counter_ns()
                    tick = now - pre
                    pre = now
                    CheckVehicleAround(car, tick/1000000)

                    if loopFlg == False:
                        logProxy.logger.info("loopFlg={}".format(loopFlg))
                        logProxy.logger.info("Script close")
                winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
            else :
                logProxy.logger.info("no driver")
    finally:
        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
        logProxy.killLogger()
        traffic = None
        winRoadProxy.SimulationCore.SetUserVariable(0, 0)
        InitPythonScriptUserFlg()
        del winRoadProxy

if __name__ == '__main__':
    main()




