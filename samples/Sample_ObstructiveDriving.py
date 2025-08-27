from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import math
import time

SEARCH_AROUND_RADIUS = 50 # m
ELAPSED_TIME_MILISECOND = 2000 # ms

class VehicleControl:
    def __init__(self, instance, ID):
        self.instance = instance
        self.ID = ID
        self.count = 0
        self.time = 0.0
        self.Event = None

    def __del__(self):
        self.DeleteCallbackEvent()
        if self.instance is not None:
            self.instance = None
        if self.Event is not None:
            self.Event = None

    def SetCallbackHandler(self, handler):
        if self.instance is not None:
            if self.Event is None:
                self.Event = com.WithEvents(self.instance, handler)
                self.Event.SetCOMEventClass(self.Event)
                self.instance.RegisterEventHandlers()
    
    def DeleteCallbackEvent(self):
        if self.instance is not None:
            self.instance.UnRegisterEventHandlers()
        if self.Event is not None:
            self.Event.close()
            self.Event = None

class TransientInstanceHandler(HandlerBase):
    SteerTime = 0
    BrakeTime = 0
    toggle = True
    def OnBeforeCalculateMovement(self, dTimeInSeconds, proxy):
        if proxy is None:
            return
        proxyCar = com.Dispatch(proxy)
        logProxy.logger.info("ID={}".format(proxyCar.ID))
        if proxyCar.TransientType == const._TransientCar:
            global aTime
            aTime = aTime + dTimeInSeconds
            if self.toggle :
                steer = 0.1 * math.cos(math.pi * aTime)
                proxyCar.Steering = steer
                logProxy.logger.info("steer={}".format(steer))
                proxyCar.Throttle = 0.5
                proxyCar.Brake = 0.0
                proxyCar.Clutch = 0.0
                self.SteerTime = aTime
            else:            
                proxyCar.Steering = 0.0
                proxyCar.Throttle = 0.0
                proxyCar.Brake = 1.0
                logProxy.logger.info("Brake={}".format(proxyCar.Brake))
                self.BrakeTime = aTime
            
            if (abs(self.SteerTime - self.BrakeTime) > 1):
                self.toggle = not self.toggle

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

def CheckVehicleAround(radius, car, tick):
    if car is None:
        return
    if car.CurrentRoad is None:
        return
    if car.CurrentLane is None:
        return
    currentRoad = car.CurrentRoad
    currentLane = car.CurrentLane
    carPos = car.Position
    logProxy.logger.info("radius={}".format(radius)+", carPos.X={}".format(carPos.X)+",Y={}".format(carPos.Y)+"Z={}".format(carPos.Z))
    traffic = winRoadProxy.SimulationCore.TrafficSimulation
    trafficList = traffic.GetTransientVehiclesArround(radius, carPos)
    count = trafficList.Count
    logProxy.logger.info("vehicle count={}".format(count))
    global frontVehcle
    resetFlg = True
    nearestVehcle = None
    nearestDistance = 1000
    workvehcleList = []
    for i in range(count):
        logProxy.logger.info("i={}".format(i))
        vehcle = trafficList.Items(i)
        if vehcle is None:
            logProxy.logger.info("vehcle is None")
            continue
        logProxy.logger.info("Name={}".format(vehcle.Name)+", ID={}".format(vehcle.ID))
        transientType = vehcle.TransientType
        if const._TransientCar == transientType :
            if car.ID == vehcle.ID :
                logProxy.logger.info("This is my vehcle!! Name={}".format(vehcle.Name)+", ID={}".format(vehcle.ID))
            else:                    
                workvehcleList.append(vehcle)
                vCurrentRoad = vehcle.CurrentRoad
                vCurrentLane = vehcle.CurrentLane
                if vCurrentRoad is not None:
                    if vCurrentRoad.IsSameAs(currentRoad):
                        if vCurrentLane is not None:
                            if vCurrentLane.IsSameAs(currentLane):
                                logProxy.logger.info("CurrentRoad.Name={}".format(vCurrentRoad.Name))
                                vPos = vehcle.Position
                                cPos = car.Position
                                currentDistance = Distance(vPos, cPos)
                                if nearestDistance > currentDistance:
                                    nearestDistance = currentDistance
                                    nearestVehcle = vehcle
                            else:
                                logProxy.logger.info("False : vCurrentLane.IsSameAs")   
                        else:
                            logProxy.logger.info("vCurrentLane is None")        
                    else:
                        logProxy.logger.info("False : vCurrentRoad.IsSameAs")        
                else:
                    logProxy.logger.info("vCurrentRoad is None")    
        else:
            logProxy.logger.info("vehcle is not _TransientCar")

    if nearestVehcle is not None:
        if currentLane.IsForward == True:
            myVehcleIsBehind = True if nearestDistance > 0 else False
        else:
            myVehcleIsBehind = False if nearestDistance > 0 else True       
        logProxy.logger.info("myVehcleIsBehind={}".format(myVehcleIsBehind))
        if myVehcleIsBehind :
            carSpeed = car.Speed(const._KiloMeterPerHour)
            requiredDistance = GetRequiredVehicleDistance(carSpeed)
            logProxy.logger.info("#speed={}".format(carSpeed))
            logProxy.logger.info("#required distance between vehicles ={}".format(requiredDistance))
            logProxy.logger.info("#current distance between vehicles ={}".format(nearestDistance))
            if abs(nearestDistance) < requiredDistance :
                resetFlg = False
                if frontVehcle is None:
                    frontVehcle = VehicleControl(nearestVehcle, nearestVehcle.ID)
                    logProxy.logger.info("[1]Create frontVehcle.ID={}".format(frontVehcle.ID))
                else:
                    frontVehcle.time += tick
                    logProxy.logger.info("frontVehcle.time={}".format(frontVehcle.time))
                    if frontVehcle.time > ELAPSED_TIME_MILISECOND :
                        frontVehcle.SetCallbackHandler(TransientInstanceHandler)
                        logProxy.logger.info("[2]Start frontVehcle.ID={}".format(frontVehcle.ID))
                        winRoadProxy.SimulationCore.SetUserVariable(0, 1)
                        winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(1, 1)

    if resetFlg :
        if frontVehcle is not None:
            logProxy.logger.info("[3]Stop frontVehcle.ID={}".format(frontVehcle.ID))
            frontVehcle.Steering = 0
            frontVehcle.Throttle = 0.5
            frontVehcle.Brake = 0.0
            frontVehcle.Clutch = 0.0
            frontVehcle.DeleteCallbackEvent()
            frontVehcle = None
            winRoadProxy.SimulationCore.SetUserVariable(0, 0)
            winRoadProxy.ApplicationServices.SetPythonScriptUserFlg(1, 0)
            InitPythonScriptUserFlg()
        nearestVehcle = None

    if frontVehcle is not None:
        findFlg = False
        for wv in workvehcleList:
            if frontVehcle.ID == wv.ID:
                findFlg = True
                break 
        if not findFlg :
            logProxy.logger.info("[4]Stop frontVehcle.ID={}".format(frontVehcle.ID))
            frontVehcle.DeleteCallbackEvent()
            frontVehcle = None
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
        scriptName = 'Sample_ObstructiveDriving'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        InitPythonScriptUserFlg()
        global traffic
        global car
        global frontVehcle
        frontVehcle = None
        global aTime
        aTime = 0
        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
        driver = traffic.Driver
        if driver is not None:
            car = driver.CurrentCar
            if car is not None:
                logProxy.logger.info("car.ID={}".format(car.ID))
                # Event Loop
                loopFlg = True
                winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
                pre = time.perf_counter_ns()
                while loopFlg:
                    time.sleep(0.005)
                    loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun
                    now = time.perf_counter_ns()
                    tick = now - pre
                    pre = now
                    
                    CheckVehicleAround(SEARCH_AROUND_RADIUS, car, tick/1000000)
                    
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
        del winRoadProxy

if __name__ == '__main__':
    main()




