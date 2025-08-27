from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
import time
import win32com.client as com
import math
import pandas as pd

class RibbonButtonHandler:
    def SetCOMEventClass(self, events):
        self.events = events
    def OnIsExistEventHandler(self, funcname):
        try:
            func = getattr(self.events, funcname)
        except AttributeError:
            return False
        return True
    def OnClick(self):
        print("OnClick")
        
class RibbonButtonHandler1(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simScreenSetting = com.Dispatch('UCwinRoad.F8COMSimulationScreenSettingType')
        simScreenSetting.settingType = const._WindowSize
        simScreenSetting.Yaw   = math.radians(0.1)
        simScreenSetting.Pitch = math.radians(0.2)
        simScreenSetting.Roll  = math.radians(0.3)
        simScreenSetting.settingWindowSize.fovVertical = math.radians(45.0)
        simScreenSetting.settingWindowSize.fovHorizontal = 0.0 # This will be calculated from window size.
        simScreenSetting.settingWindowSize.frustumShiftX = 0.01
        simScreenSetting.settingWindowSize.frustumShiftY = 0.02
        simScreenSetting.settingWindowSize.screenDistance = 1.0
        mainSimScreen = winRoadProxy.MainForm.MainSimulationScreen 
        mainSimScreen.Settings = simScreenSetting

class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simScreenSetting = com.Dispatch('UCwinRoad.F8COMSimulationScreenSettingType')
        simScreenSetting.settingType = const._PhysicalScreen
        simScreenSetting.Yaw   = math.radians(0.2)
        simScreenSetting.Pitch = math.radians(0.3)
        simScreenSetting.Roll  = math.radians(0.4)
        simScreenSetting.settingPhysicalScreen.Height = 1.0
        simScreenSetting.settingPhysicalScreen.Width  = 1.6
        simScreenSetting.settingPhysicalScreen.Position = AsF8COMdVec3(0, 0, 1)
        mainSimScreen = winRoadProxy.MainForm.MainSimulationScreen 
        mainSimScreen.Settings = simScreenSetting

class RibbonButtonHandler3(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simScreenSetting = com.Dispatch('UCwinRoad.F8COMSimulationScreenSettingType')
        simScreenSetting.settingType = const._DirectFov
        simScreenSetting.Yaw   = math.radians(0.3)
        simScreenSetting.Pitch = math.radians(0.4)
        simScreenSetting.Roll  = math.radians(0.5)
        simScreenSetting.settingDirectFov.fovTop    = math.radians( 25.0)
        simScreenSetting.settingDirectFov.fovBottom = math.radians(-20.0)
        simScreenSetting.settingDirectFov.fovLeft   = math.radians( 30.0)
        simScreenSetting.settingDirectFov.fovRight  = math.radians(-35.0)
        mainSimScreen = winRoadProxy.MainForm.MainSimulationScreen 
        mainSimScreen.Settings = simScreenSetting

class RibbonButtonHandler4(RibbonButtonHandler):
    
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        settings = winRoadProxy.MainForm.MainSimulationScreen.Settings 
        settingType = settings.settingType 
        
        listSettingType = ['Window size','Physical screen','Direct Fov']
        list = [[
            listSettingType[settingType], 
            math.degrees(settings.Yaw), 
            math.degrees(settings.Pitch), 
            math.degrees(settings.Roll)
        ]]
        df = pd.DataFrame(list, index=['Value'], columns=['Setting Type', 'Yaw angle(deg.)', 'Pitch angle(deg.)','Roll angle(deg.)'])

        if settingType == const._WindowSize:
            listWindowSize = [[
                math.degrees(settings.settingWindowSize.fovHorizontal), 
                math.degrees(settings.settingWindowSize.fovVertical), 
                settings.settingWindowSize.frustumShiftX * 100,
                settings.settingWindowSize.frustumShiftY * 100, 
                settings.settingWindowSize.screenDistance
            ]]
            df_WindowSize = pd.DataFrame(listWindowSize, index=['Value'], columns=['H FOV(deg.)', 'V FOV(deg.)', 'Frustum shift X(%)','Frustum shift Y(%)', 'Screen distance(m)'])
            df = pd.concat([df,df_WindowSize], axis=1)
        elif settingType == const._PhysicalScreen:
            listPhysical = [[
                settings.settingPhysicalScreen.Height,
                settings.settingPhysicalScreen.Width,
                settings.settingPhysicalScreen.Position.X,
                settings.settingPhysicalScreen.Position.Y,
                settings.settingPhysicalScreen.Position.Z
            ]]
            df_PhysicalScreen = pd.DataFrame(listPhysical, index=['Value'], columns=['Height(m)', 'Width(m)', 'Position X(m)','Position Y(m)', 'Position Z(m)'])
            df = pd.concat([df,df_PhysicalScreen], axis=1)
        elif settingType == const._DirectFov:
            listDirectFov = [[
                math.degrees(settings.settingDirectFov.fovTop),   
                math.degrees(settings.settingDirectFov.fovBottom),
                math.degrees(settings.settingDirectFov.fovLeft),  
                math.degrees(settings.settingDirectFov.fovRight) 
            ]]
            df_DirectFov = pd.DataFrame(listDirectFov, index=['Value'], columns=['Top FOV(deg.)', 'Bottom FOV(deg.)', 'Left FOV(deg.)','Right FOV(deg.)'])
            df = pd.concat([df,df_DirectFov], axis=1)
        else:
            pass
        
        p = winRoadProxy.PythonPluginDirectory() + "/OutputSimulationScreen" + ".csv"
        df.to_csv(p)


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

    def MakeRibbonUI(self):
        mainForm = winRoadProxy.MainForm
        # Menu
        self.ribbonMenu = mainForm.MainRibbonMenu
        # Tab
        self.ribbonTab = self.MakeRibbonTab(self.ribbonMenu, 'PythonAPISamples', 'Python API Samples')
        # Group
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'GroupMainSimScreenOp', 'Simulation Screen operation')
        # Panel
        self.ribbonPanel1 = self.MakeRibbonPanel(self.ribbonGroup, 'PanelMainSimScreenOp1', '')
        self.ribbonPanel2 = self.MakeRibbonPanel(self.ribbonGroup, 'PanelMainSimScreenOp2', '')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonPanel1, 'ButtonMainSimScreenOp1', 'Setting 1', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonPanel1, 'ButtonMainSimScreenOp2', 'Setting 2', RibbonButtonHandler2)
        self.ribbonButton3 = self.MakeRibbonButton(self.ribbonPanel2, 'ButtonMainSimScreenOp3', 'Setting 3', RibbonButtonHandler3)
        self.ribbonButton4 = self.MakeRibbonButton(self.ribbonPanel2, 'ButtonMainSimScreenOp4', 'Setting 4', RibbonButtonHandler4)

        self.ribbonButton2.Top = self.ribbonButton1.Top + self.ribbonButton1.Height + 6
        self.ribbonButton4.Top = self.ribbonButton3.Top + self.ribbonButton3.Height + 6
        self.ribbonPanel1.Width = self.ribbonButton1.Width + 6
        self.ribbonPanel1.Height = self.ribbonButton1.Height * 2 + 6
        self.ribbonPanel2.Width = self.ribbonButton3.Width + 6
        self.ribbonPanel2.Height = self.ribbonButton3.Height * 2 + 6

    def KillRibbonUI(self):
        self.CloseCallbackEvent()
        self.DeleteControlFromParent(self.ribbonButton1, self.ribbonPanel1)
        self.DeleteControlFromParent(self.ribbonButton2, self.ribbonPanel1)
        self.DeleteControlFromParent(self.ribbonButton3, self.ribbonPanel2)
        self.DeleteControlFromParent(self.ribbonButton4, self.ribbonPanel2)
        self.DeleteControlFromParent(self.ribbonPanel1, self.ribbonGroup)
        self.DeleteControlFromParent(self.ribbonPanel2, self.ribbonGroup)
        self.ribbonTab.DeleteGroup(self.ribbonGroup)
        self.ribbonGroup = None
        if self.ribbonTab.RibbonGroupsCount == 0 :
            self.ribbonMenu.DeleteTab(self.ribbonTab)
        self.ribbonTab = None
        self.ribbonMenu = None

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_SimulationScreen'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        ribbon = RibbonUI()
        ribbon.MakeRibbonUI()

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
        ribbon.KillRibbonUI()
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




