from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import time
import win32com.client as com
import pandas as pd
from OpenGL.GLUT import *
from OpenGL.GL import *
from UCwinRoadOpenGL import *

p_speed = 0
SPEED_METER_MAX = 140
EventList = []

class TransientInstanceHandler(HandlerBase):
    def OnAfterCalculateMovement(self, dTimeInSeconds, proxy):
        proxyCar = com.Dispatch(proxy)
        if proxyCar.TransientType == const._TransientCar:
            if saveCarID == proxyCar.ID :
                global p_speed
                p_speed = proxyCar.Speed(const._KiloMeterPerHour)

class VirtualDisplayEventHandler2D(HandlerBase):
    
    def OnDirectDraw(self):
        OpenGLSample.DrawBack(1.0, 1.0, 1.0, 0.5)
        p = 0.0
        global p_speed
        if (p_speed > 0) and (p_speed <= SPEED_METER_MAX) :
            p = p_speed / SPEED_METER_MAX
        OpenGLSample.DrawLine(0, 0, p, p, 10)
        OpenGLSample.DrawQUADS(0.5)

class VirtualDisplayEventHandler3D(HandlerBase):
    
    def OnDirectDraw(self):
        OpenGLSample.DrawBack(0.0, 1.0, 1.0, 0.5)
        p = 0.0
        global p_speed
        if (p_speed > 0) and (p_speed <= SPEED_METER_MAX) :
            p = p_speed / SPEED_METER_MAX
        OpenGLSample.DrawLine(0, 0, p, p, 10)
        OpenGLSample.DrawQUADS(0.5)
        
class RibbonButtonHandler1(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('Start DirectDraw')
        global EventList
        vdList = winRoadProxy.VirtualDisplaysPlugin.GetVirtualDisplays()
        vdCount = vdList.Count
        # Set callback to VirtualDisplay
        for i in range(vdCount):
            VD = vdList.Items(i)
            logProxy.logger.info("VirtualDisplay Name={}".format(VD.Name))
            if VD.VirtualDisplayType == const._vd2DOverlay:
                SetCallbackHandlers(EventList, VD, VirtualDisplayEventHandler2D)
            elif VD.VirtualDisplayType == const._vd3DObject:
                SetCallbackHandlers(EventList, VD, VirtualDisplayEventHandler3D)

        # Set callback to CarInstance
        global saveCarID
        traffic = winRoadProxy.ApplicationServices.SimulationCore.TrafficSimulation
        driver = traffic.Driver
        if driver is not None:
            car = driver.CurrentCar
            if car is not None:
                logProxy.logger.info("car.ID={}".format(car.ID))
                saveCarID = car.ID
                SetCallbackHandlers(EventList, car, TransientInstanceHandler)
        else :
            logProxy.logger.info("no driver")


class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('Stop DirectDraw')
        global EventList
        CloseCallbackEvent(EventList)

class RibbonUI:
    def __init__(self) -> None:
        self.EventList = []

    def MakeRibbonTab(self, Parent, partsName, caption):
        if Parent is not None:
            tab = Parent.GetTabByName(partsName)
            if tab is None:
                tab = Parent.CreateTab(partsName, 10000)
                tab.Caption = caption
            return tab

    def MakeRibbonGroup(self, Parent, partsName, caption):
        if Parent is not None:
            group = Parent.GetGroupByName(partsName)
            if group is None:
                group = Parent.CreateGroup(partsName, 100)
                group.Caption = caption
            return group
    
    def MakeRibbonPanel(self, Parent, partsName, caption):
        if Parent is not None:
            panel = Parent.GetControlByName(partsName)
            if panel is None:
                panel = Parent.CreatePanel(partsName)    
            return panel
    
    def SetCallbackEvent(self, button, handler):
        if button is not None:
            isValue = button.IsSetCallbackOnClick()
        if isValue == False :
            Event = com.WithEvents(button, handler)
            Event.SetCOMEventClass(Event)
            button.RegisterEventHandlers()
            self.EventList.append(Event)
            return Event

    def MakeRibbonButton(self, Parent, partsName, caption, handler):
        if Parent is not None:
            button = Parent.GetControlByName(partsName)
            if button is None:
                button = Parent.CreateButton(partsName)
                button.Caption = caption
                self.SetCallbackEvent(button, handler)
            return button

    def DeleteControlFromParent(self, child, Parent):
        if child is not None:
            child.UnRegisterEventHandlers()
            if Parent is not None:
                Parent.DeleteControl(child)
            child = None

    def CloseCallbackEvent(self):
        if self.EventList is not None:
            for Event in self.EventList:
                Event.close()
            self.EventList.clear()

    def MakeRibbonUI(self):
        mainForm = winRoadProxy.MainForm
        # Menu
        self.ribbonMenu = mainForm.MainRibbonMenu
        # Tab
        self.ribbonTab = self.MakeRibbonTab(self.ribbonMenu, 'PythonAPISamples', 'Python API Samples')
        # Group
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'VirtualDisplay', 'VirtualDisplay')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonGroup, 'Button1', 'Start', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonGroup, 'Button2', 'Stop', RibbonButtonHandler2)
        self.ribbonButton1.Width = 150
        self.ribbonButton2.Width = 150

    def KillRibbonUI(self):
        self.DeleteControlFromParent(self.ribbonButton1, self.ribbonGroup)
        self.DeleteControlFromParent(self.ribbonButton2, self.ribbonGroup)
        self.ribbonTab.DeleteGroup(self.ribbonGroup)
        self.ribbonGroup = None
        if self.ribbonTab.RibbonGroupsCount == 0 :
            self.ribbonMenu.DeleteTab(self.ribbonTab)
        self.ribbonTab = None
        self.ribbonMenu = None
        self.CloseCallbackEvent()

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_VirtualDisplay'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        ribbon = RibbonUI()
        ribbon.MakeRibbonUI()

        global OpenGLSample
        OpenGLSample = OpenGLSamples()

        global EventList

        # Event Loop
        loopFlg = True
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
        while loopFlg:
            #pythoncom.PumpWaitingMessages()
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
        ribbon.KillRibbonUI()
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




