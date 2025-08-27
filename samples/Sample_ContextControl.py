from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import MainOpenGLHandler,MainFormHandler,RibbonButtonHandler
import time
import win32com.client as com
       
class RibbonButtonHandler1(RibbonButtonHandler):
    def OnClick(self):
        prj = winRoadProxy.Project
        context = None
        if (prj.ContextsCount >= 1):
            context = prj.Context(0)
            winRoadProxy.SimulationCore.ApplyContext(context)        

class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        prj = winRoadProxy.Project
        context = None
        if (prj.ContextsCount >= 2):
            context = prj.Context(1)
            winRoadProxy.SimulationCore.ApplyContext(context)        

class RibbonUI:
    def __init__(self) -> None:
        self.EventList = []
        self.isLogging = False
        self.ribbonButton1 = None
        self.ribbonButton2 = None
        
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
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'GroupApplyContext1', 'Context')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonApplyContext1', 'Apply 1st', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonApplyContext2', 'Apply 2nd', RibbonButtonHandler2)

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

        scriptName = 'Sample_ContextControl'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        global ribbon
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




