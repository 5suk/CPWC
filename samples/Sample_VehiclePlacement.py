from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
import win32com.client as com
import time

def PlaceVehicle():
    global winRoadProxy
    prj = winRoadProxy.Project
    const = winRoadProxy.const
    modelcount = prj.ThreeDModelsCount
    found = False
    for i in range(modelcount):
        vehicleModel = prj.ThreeDModel(i)
        if vehicleModel.ModelType == const._VehicleModel :
            found = True
            break

    if (not found) and (vehicleModel is None) :
        logProxy.logger.info('Vehicle is not found.')
        exit

    global road
    count = prj.RoadsCount
    for i in range(count):
        road = prj.Road(i)
        if road is not None:
            if road.Name == "Nihondaira Park Way":
                logProxy.logger.info("Road.name:{}".format(road.Name))
                traffic = winRoadProxy.SimulationCore.TrafficSimulation
                # AddNewVheicle 1
                vptype = com.DispatchEx('UCwinRoad.F8COMVehiclePlacementType')
                vptype.IsForward = True
                vptype.Lane = 1
                vptype.Distance = 40.0
                traffic.AddNewVehicle(vehicleModel, road, vptype)
                # AddNewVheicle 2
                vptype2 = com.DispatchEx('UCwinRoad.F8COMVehiclePlacementType')
                vptype2.IsForward = False
                vptype2.Lane = 1
                vptype2.Distance = 1900
                traffic.AddNewVehicle(vehicleModel, road, vptype2)
    if road is None :
        logProxy.logger.info('Road is not found.')

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_VehiclePlacement'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        PlaceVehicle()

        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
    finally:
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




