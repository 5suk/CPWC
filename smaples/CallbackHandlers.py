import pythoncom

# This class has the necessary functions to define a handler class. 
# Use this class by inheritance when creating user-defined handler classes.
class HandlerBase:
    def SetCOMEventClass(self, events):
        self.events = events
    def OnIsExistEventHandler(self, funcname):
        try:
            func = getattr(self.events, funcname)
        except AttributeError:
            return False
        return True

# Below is a template for event interface handler classes.
# Please define and use a class that defines only the necessary functions.
# If you define functions in the handler class, 
# the callback function will be called even if there is no processing, which increases the processing load.
# Therefore, define only the functions you need.
class ApplicationServicesHandler(HandlerBase):
    def OnPluginAbleMenus(self, enable):
        pass
    def OnErrorOrWarning(self, errorType, errorCode, errorMessage):
        pass
    def OnNewProject(self):
        pass
    def OnBeforeSaveProject(self, name):
        pass
    def OnAfterSaveProject(self):
        pass
    def OnCloseProjectQuery(self, allow=pythoncom.Missing):
        pass
    def OnBeforeDestroyProject(self):
        pass
    def OnAfterLoadProject(self):
        pass

class MainOpenGLHandler(HandlerBase):
    def OnOpenGLBeforePaint(self, mode):
        pass
    def OnOpenGLAfterDrawScene(self):
        pass
    def OnOpenGLAfterPaint(self):
        pass
    def OnOpenGLMouseEnter(self):
        pass
    def OnOpenGLMouseLeave(self):
        pass
    def OnOpenGLMouseUp(self, button, Shift, X, Y):
        pass
    def OnOpenGLMouseDown(self, button, Shift, X, Y):
        pass
    def OnOpenGLMouseMove(self, Shift, X, Y):
        pass
    def OnOpenGLMouseWheel(self, Shift, wheelDelta, MousePos, Handled):
        pass

class MainFormHandler(HandlerBase):
    def OnNavigationModeChange(self):
        pass
    def OnMoveModeChange(self):
        pass
    def OnModelClick(self, instance, command):
        pass
    def OnJoystickMove(self, X, Y, Z, rX, rY, rZ, throttle, clutch):
        pass
    def OnJoystickButtonDown(self, button):
        pass
    def OnJoystickButtonUp(self, button):
        pass
    def OnJoystickHat(self, Angle):
        pass
    def OnKeyUp(self, key, Shift):
        pass
    def OnKeyDown(self, key, Shift):
        pass

class RibbonButtonHandler(HandlerBase):
    def OnClick(self):
        pass

class RibbonCheckBoxHandler(HandlerBase):
    def OnClick(self):
        pass

class RibbonEditHandler(HandlerBase):
    def OnChange(self):
        pass

class SimulationCoreProxyHandler(HandlerBase):
    def OnApplyContext(self, context):
        pass
    def OnStartEnvironment(self):
        pass
    def OnStartEvent(self, Event):
        pass
    def OnStartScenario(self, scenario):
        pass
    def OnStartScript(self):
        pass
    def OnStopEnvironment(self):
        pass
    def OnStopEvent(self, Event):
        pass
    def OnStopScenario(self, scenario, runningScenarioCount):
        pass
    def OnStopScript(self):
        pass

class TrafficSimulationHandler(HandlerBase):
    def OnTrafficSimulationStatusChanged(self):
        pass
    def OnBeforeInitializeDriving(self, driverData):
        pass
    def OnSimulationStartDrivingCar(self, aVehicle):
        pass
    def OnSimulationStopDrivingCar(self, aVehicle):
        pass
    def OnTransientWorldBeforeMove(self, dTimeInSeconds):
        pass
    def OnTransientWorldAfterMove(self, dTimeInSeconds):
        pass
    def OnTransientWorldMove(self, dTimeInSeconds):
        pass
    def OnNewTransientObject(self, newTransient):
        pass
    def OnTransientObjectDeleted(self, deletedTransient):
        pass
    def OnCacheSimulationData(self, dTimeInSeconds):
        pass

class TransientInstanceHandler(HandlerBase):
    def OnBeforeCalculateMovement(self, dTimeInSeconds, proxy):
        pass
    def OnAfterCalculateMovement(self, dTimeInSeconds, proxy):
        pass
    def OnBeforeDoMovement(self, dTimeInSeconds, proxy):
        pass
    def OnAfterDoMovement(self, dTimeInSeconds, proxy):
        pass
    def OnBeforeDestruction(self, proxy):
        pass
    def OnCalculateMovement(self, dTimeInSeconds, proxy):
        pass
    def OnDoMovement(self, dTimeInSeconds, proxy):
        pass

class ObjectProxyHandler(HandlerBase):
    def OnBeforeDestruction(self, proxy):
        pass