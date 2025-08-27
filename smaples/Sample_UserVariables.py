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
        simulation = winRoadProxy.SimulationCore
        var1 = simulation.ClearUserVariables()

class RibbonButtonHandler2(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simulation = winRoadProxy.SimulationCore
        varIndex = 1
        var1 = simulation.UserVariable(varIndex)
        var1+=1
        simulation.SetUserVariable(varIndex, var1)

class RibbonButtonHandler3(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simulation = winRoadProxy.SimulationCore
        userV = simulation.GetUserVariables()
        vlist = list(userV)
        count = len(vlist)
        for i in range(count):
            vlist[i] = i
        simulation.SetUserVariables(vlist)

class RibbonButtonHandler4(RibbonButtonHandler):
    def OnClick(self):
        logProxy.logger.info('')
        global const
        global winRoadProxy
        simulation = winRoadProxy.SimulationCore
        userV = simulation.GetUserVariables()
        vlist = list(userV)
        for i,x in enumerate(vlist):
            logProxy.logger.info("var[{}]".format(i)+" = {}".format(x))
            #print(i,x)
            
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
        self.ribbonGroup = self.MakeRibbonGroup(self.ribbonTab, 'GroupUserVariable1', 'User variables')
        # Panel
        self.ribbonPanel1 = self.MakeRibbonPanel(self.ribbonGroup, 'PanelMainCameraOp1', '')
        self.ribbonPanel2 = self.MakeRibbonPanel(self.ribbonGroup, 'PanelMainCameraOp2', '')
        # Button
        self.ribbonButton1 = self.MakeRibbonButton(self.ribbonPanel1, 'ButtonUserVariable1', 'Reset', RibbonButtonHandler1)
        self.ribbonButton2 = self.MakeRibbonButton(self.ribbonPanel1, 'ButtonUserVariable2', 'Var1++', RibbonButtonHandler2)
        self.ribbonButton3 = self.MakeRibbonButton(self.ribbonPanel2, 'ButtonUserVariable3', 'Set All', RibbonButtonHandler3)
        self.ribbonButton4 = self.MakeRibbonButton(self.ribbonPanel2, 'ButtonUserVariable4', 'Show', RibbonButtonHandler4)

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

        scriptName = 'Sample_UserVariables'
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




