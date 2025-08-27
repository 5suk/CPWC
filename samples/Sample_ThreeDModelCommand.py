from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
import time
import win32com.client as com

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
        proj = winRoadProxy.Project
        count = proj.ThreeDModelInstancesCount
        for i in range(0, count):
            modelInst = proj.ThreeDModelInstance(i)
            #if modelInst.Name == 'SCX700':
            commandValues = [0] * 2
            modelInst.ActivateCommand('right', commandValues)
        winRoadProxy.MainForm.MainOpenGL.Changed()

class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        proj = winRoadProxy.Project
        count = proj.ThreeDModelInstancesCount
        for i in range(0, count):
            modelInst = proj.ThreeDModelInstance(i)
            #if modelInst.Name == 'SCX700':
            commandValues = [0] * 2
            modelInst.DeactivateCommand('right')
        winRoadProxy.MainForm.MainOpenGL.Changed()

class RibbonButtonHandler3(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        proj = winRoadProxy.Project
        count = proj.ThreeDModelInstancesCount
        for i in range(0, count):
            modelInst = proj.ThreeDModelInstance(i)
            #if modelInst.Name == 'SCX700':
            commandValues = [0] * 2
            modelInst.ActivateCommand('* RESET *', commandValues)
        winRoadProxy.MainForm.MainOpenGL.Changed()

            
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
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'GroupThreeDModelCommand', '3D Model Command')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonActivateCommand', 'Activate', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonDeactivateCommand', 'Deactivate', RibbonButtonHandler2)
        self.ribbonButton3 = self.MakeRibbonButton(self.ribbonGroup, 'ButtonResetCommand', 'Reset', RibbonButtonHandler3)

    def KillRibbonUI(self):
        self.CloseCallbackEvent()
        self.DeleteControlFromParent(self.ribbonButton1, self.ribbonGroup)
        self.DeleteControlFromParent(self.ribbonButton2, self.ribbonGroup)
        self.DeleteControlFromParent(self.ribbonButton3, self.ribbonGroup)
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

        scriptName = 'Sample_ThreeDModelCommand'
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




