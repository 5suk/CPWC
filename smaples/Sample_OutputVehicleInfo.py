from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from VehicleInfo import DataclassVehicleInfo
import time
import datetime
import pandas as pd

def StrCarLights(carLights):
    state : str  =  ''
    if carLights.isLeftIndicatorOn:
        state = 'LeftIndicator/'
    if carLights.isRightIndicatorOn:
        state = state + 'RightIndicator/'
    if carLights.isBrakeLightOn:
        state = state + 'BrakeLight/'
    if carLights.isHighBeamOn:
        state = state + 'HighBeam/'
    if carLights.isLowBeamOn:
        state = state + 'LowBeam'
    return state

def GetVehicleInfomation():
    const = winRoadProxy.const
    mainCam = winRoadProxy.MainForm.MainCamera
    cameraSts = mainCam.MainCameraState
    eyework = cameraSts.eye

    traffic = winRoadProxy.SimulationCore.TrafficSimulation
    trafficList = traffic.GetTransientObjectsArround(100, eyework)
    count = trafficList.Count
    logProxy.logger.info("count={}".format(count))
    if count > 0:
        viList = []
        for i in range(count):
            obj = trafficList.Items(i)
            #logProxy.logger.info(obj)
            if obj is None:
                continue
            transientType = obj.TransientType
            if const._TransientCar == transientType :
                vi = DataclassVehicleInfo();
                vi.Timestamp = datetime.datetime.now()
                vi.ID = obj.ID
                vi.Description = obj.Description
                pos = obj.Position
                vi.Pos_X = pos.X
                vi.Pos_Y = pos.Y
                vi.Pos_Z = pos.Z
                vi.Yaw = obj.YawAngle
                vi.Pitch = obj.PitchAngle
                vi.Roll = obj.RollAngle
                direction =  obj.Direction
                vi.Dir_X = direction.X
                vi.Dir_Y = direction.Y
                vi.Dir_Z = direction.Z
                vi.BodyPitch = obj.BodyPitchAngle
                vi.BodyRoll = obj.BodyRollAngle
                vi.EngineRPM = obj.RPM
                speed = obj.SpeedVector(const._MeterPerSecond)
                vi.Speed_X = speed.X
                vi.Speed_Y = speed.Y
                vi.Speed_Z = speed.Z
                accel = obj.Acceleration
                vi.Acceleration_X = accel.X
                vi.Acceleration_Y = accel.Y
                vi.Acceleration_Z = accel.Z
                bRotSpeed = obj.BodyRotSpeed
                vi.BodyRotSpeed_X = bRotSpeed.X
                vi.BodyRotSpeed_Y = bRotSpeed.Y
                vi.BodyRotSpeed_Z = bRotSpeed.Z
                bRotAccel = obj.BodyRotAcceleration
                vi.BodyRotAccel_X = bRotAccel.X
                vi.BodyRotAccel_Y = bRotAccel.Y
                vi.BodyRotAccel_Z = bRotAccel.Z
                rotSpeed = obj.RotSpeed
                vi.RotSpeed_X = rotSpeed.X
                vi.RotSpeed_Y = rotSpeed.Y
                vi.RotSpeed_Z = rotSpeed.Z
                rotAccel = obj.RotAcceleration
                vi.RotAccel_X = rotAccel.X
                vi.RotAccel_Y = rotAccel.Y
                vi.RotAccel_Z = rotAccel.Z
                vi.DistTravelled = obj.DistanceTravelled
                vi.Steering = obj.Steering
                vi.Applied_steering = obj.AppliedSteering
                vi.Throttle = obj.Throttle
                vi.AppliedThrottle = obj.AppliedThrottle
                vi.Brake = obj.Brake
                vi.AppliedBrake = obj.AppliedBrake
                vi.Clutch = obj.Clutch
                vi.AppliedClutch = obj.AppliedClutch
                carLights = obj.CarLights
                vi.LightState = StrCarLights(carLights)
                intersection = obj.CurrentIntersection;
                if intersection is not None:
                    vi.Intersection = intersection.Name
                vi.AutomaticControl = 'Automatic' if obj.AutomaticControl else 'Manual'
                vi.Mass = obj.Mass
                curRoad = obj.CurrentRoad
                if curRoad is not None:
                    vi.currentRoad = curRoad.Name
                vi.DistAlongCurrentRoad = obj.DistanceAlongRoad
                lastRoad = obj.LatestRoad
                if lastRoad is not None:
                    vi.LatestRoad = lastRoad.Name
                vi.DistAlongLatestRoad = obj.DistanceAlongLatestRoad
                vi.LaneNumber = obj.LaneNumber
                vi.LaneWidth = obj.LaneWidth
                laneDir = obj.LaneDirection
                vi.LaneDir_X = laneDir.X
                vi.LaneDir_Y = laneDir.Y
                vi.LaneDir_Z = laneDir.Z
                vi.LaneCurvature = obj.LaneCurvature
                bodyDir = obj.BodyDirection
                vi.BodyDir_X = bodyDir.X
                vi.BodyDir_Y = bodyDir.Y
                vi.BodyDir_Z = bodyDir.Z
                vi.DistanceAlongPath = obj.DistanceAlongDrivePath
                curLane = obj.CurrentLane
                if curLane is not None:
                    if curLane.CurveType == const._cfRoad:
                        vi.LaneID = curLane.GetLaneID(vi.DistanceAlongPath, const._ldLane)
                vi.EngineOn = obj.EngineOn
                vi.SpeedInKmph = obj.Speed(const._KiloMeterPerHour)

                viList.append(vi)
                del vi

        if len(viList) > 0:
            df = pd.DataFrame(viList)
            logProxy.logger.info(df)
            df.to_csv(winRoadProxy.PythonPluginDirectory() + "/OutputVehicleInformations_py.csv", index = False)

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_OutputVehicleInfo'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        GetVehicleInfomation()

        elapsed_time = time.perf_counter_ns() - start
        logProxy.logger.info("Total:{}ms".format(elapsed_time/1000000))
        logProxy.logger.info('End '+ scriptName)
    finally:
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




