from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import time
import win32com.client as com
import pandas as pd

class GazeTrackingEventHandler(HandlerBase):
    def OnGazeDataUpdated(self):
        global winRoadProxy
        gazeData = winRoadProxy.GazeTrackingPlugin.CurrentGazeData
        if gazeData is not None:
            list = [
                ToStrF8COMdVec3(gazeData.absEyePosition).split(',')[0],
                ToStrF8COMdVec3(gazeData.absEyePosition).split(',')[1],
                ToStrF8COMdVec3(gazeData.absEyePosition).split(',')[2],
                ToStrF8COMdVec3(gazeData.absHeadPosition).split(',')[0], 
                ToStrF8COMdVec3(gazeData.absHeadPosition).split(',')[1], 
                ToStrF8COMdVec3(gazeData.absHeadPosition).split(',')[2], 
                ToStrF8COMdVec3(gazeData.absEyeDirection).split(',')[0],
                ToStrF8COMdVec3(gazeData.absEyeDirection).split(',')[1],
                ToStrF8COMdVec3(gazeData.absEyeDirection).split(',')[2],
                ToStrF8COMdVec3(gazeData.absHeadDirection).split(',')[0], 
                ToStrF8COMdVec3(gazeData.absHeadDirection).split(',')[1], 
                ToStrF8COMdVec3(gazeData.absHeadDirection).split(',')[2], 
                gazeData.measurementReliability, 
                ToStrF8COMdVec3(gazeData.rawEyePosition).split(',')[0], 
                ToStrF8COMdVec3(gazeData.rawEyePosition).split(',')[1], 
                ToStrF8COMdVec3(gazeData.rawEyePosition).split(',')[2], 
                ToStrF8COMdVec3(gazeData.rawEyeDirection).split(',')[0],
                ToStrF8COMdVec3(gazeData.rawEyeDirection).split(',')[1],
                ToStrF8COMdVec3(gazeData.rawEyeDirection).split(',')[2],
                ToStrF8COMdVec3(gazeData.rawHeadPosition).split(',')[0],
                ToStrF8COMdVec3(gazeData.rawHeadPosition).split(',')[1],
                ToStrF8COMdVec3(gazeData.rawHeadPosition).split(',')[2],
                ToStrF8COMdVec3(gazeData.rawHeadDirection).split(',')[0],
                ToStrF8COMdVec3(gazeData.rawHeadDirection).split(',')[1],
                ToStrF8COMdVec3(gazeData.rawHeadDirection).split(',')[2],
                gazeData.rawMeasurementReliability,
                gazeData.Time 
            ]
            global gazeDatalist
            gazeDatalist.append(list)
            logProxy.logger.info(list)
        
class RibbonButtonHandler1(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        sendData = com.Dispatch('UCwinRoad.F8COMApiGazeTrackingDataType')
        sendData.rawEyePosition.X = 0.01;
        sendData.rawEyePosition.Y = 0.02;
        sendData.rawEyePosition.Z = 0.03;
        sendData.rawEyeDirection.X = 0.04;
        sendData.rawEyeDirection.Y = 0.05;
        sendData.rawEyeDirection.Z = -1.00;
        sendData.rawHeadPosition.X = 0.07;
        sendData.rawHeadPosition.Y = 0.08;
        sendData.rawHeadPosition.Z = 0.09;
        sendData.rawHeadDirection.X = 0.01;
        sendData.rawHeadDirection.Y = 0.02;
        sendData.rawHeadDirection.Z = -1.00;
        sendData.rawMeasurementReliability = 0.123;
        winRoadProxy.GazeTrackingPlugin.PushGazeData(sendData, float('NaN'))

class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global gazeDatalist
        df = pd.DataFrame(gazeDatalist,  
                        columns=[
                                'Absolute eye position(X)', 
                                'Absolute eye position(Y)', 
                                'Absolute eye position(Z)', 
                                'Absolute head position(X)', 
                                'Absolute head position(Y)', 
                                'Absolute head position(Z)', 
                                'Absolute eye direction(X)', 
                                'Absolute eye direction(Y)', 
                                'Absolute eye direction(Z)', 
                                'Absolute head direction(X)', 
                                'Absolute head direction(Y)', 
                                'Absolute head direction(Z)', 
                                'Measurement reliability', 
                                'Raw eye position(X)', 
                                'Raw eye position(Y)', 
                                'Raw eye position(Z)', 
                                'Raw eye direction(X)', 
                                'Raw eye direction(Y)', 
                                'Raw eye direction(Z)', 
                                'Raw head position(X)', 
                                'Raw head position(Y)', 
                                'Raw head position(Z)', 
                                'Raw head direction(X)',
                                'Raw head direction(Y)',
                                'Raw head direction(Z)',
                                'Raw measurement reliability',
                                'Time'])
        p = winRoadProxy.PythonPluginDirectory() + "/OutputGazeTrackReceive.csv"
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
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'GroupGazeTrackReceive', 'Gaze data received')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonSendGazeData', 'Send gaze data', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonShowGazeData', 'Output gaze data', RibbonButtonHandler2)
        self.ribbonButton1.Width = 150
        self.ribbonButton2.Width = 150

    def KillRibbonUI(self):
        self.CloseCallbackEvent()
        self.DeleteControlFromParent(self.ribbonButton1, self.ribbonGroup)
        self.DeleteControlFromParent(self.ribbonButton2, self.ribbonGroup)
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

        scriptName = 'Sample_GazeTrackReceive'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        ribbon = RibbonUI()
        ribbon.MakeRibbonUI()

        global gazeDatalist
        gazeDatalist = [[]]

        global EventList
        EventList = []
        SetCallbackHandlers(EventList, winRoadProxy.GazeTrackingPlugin, GazeTrackingEventHandler)

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
        CloseCallbackEvent(EventList)
        ribbon.KillRibbonUI()
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




