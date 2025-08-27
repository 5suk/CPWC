from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
import time
import win32com.client as com
import math

class TransientInstanceHandler:
    def SetCOMEventClass(self, events):
        self.events = events
    def OnIsExistEventHandler(self, funcname):
        try:
            func = getattr(self.events, funcname)
        except AttributeError:
            return False
        return True

    def OnBeforeCalculateMovement(self, dTimeInSeconds, proxy):
        instance = com.Dispatch(proxy)
        logProxy.logger.info("ID={}".format(instance.ID))
        if instance.TransientType == const._TransientCar:
            instance.EngineOn = True
            global aTime
            aTime = aTime + dTimeInSeconds
            steer = math.cos(math.pi * aTime);
            instance.Steering = steer
            logProxy.logger.info("steer={}".format(instance.Steering))
            instance.Throttle = 0.5
            instance.Brake = 0.0
            instance.Clutch = 0.0
            #
            Position = instance.Position
            instance.PositionInTraffic = Position

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_OverrideCarInput'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        global traffic
        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
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
            global EventList
            EventList = []
            SetCallbackHandlers(EventList, car, TransientInstanceHandler)
            global aTime
            aTime = 0
            v1 = car.IsSetCallbackOnDoMovement()
            v2 = car.IsSetCallbackOnCalculateMovement()
            logProxy.logger.info("IsSetCallbackOnDoMovement={}".format(v1))
            logProxy.logger.info("IsSetCallbackOnCalculateMovement={}".format(v2))
        else:
            print('No driving car')
            loopFlg = False

        # Event Loop
        loopFlg = True
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
        while loopFlg:
            time.sleep(0.005)
            #loopFlg = winRoadProxy.ApplicationServices.PythonScriptUserFlg(0)
            loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun
            if loopFlg == False:
                logProxy.logger.info("loopFlg={}".format(loopFlg))
                logProxy.logger.info("Script close")
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg

    finally:
        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
        if EventList is not None:
            CloseCallbackEvent(EventList)
        logProxy.killLogger()
        del winRoadProxy


if __name__ == "__main__":
    main()

