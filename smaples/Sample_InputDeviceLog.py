from UCwinRoadCOM import *
from LoggerProxy import LoggerProxy
from UCwinRoadUtils import *
from CallbackHandlers import *
import time
import win32com.client as com
       
class MainFormHandler1(HandlerBase):
    def OnJoystickButtonDown(self, button):
        logProxy.logger.info("Joystick button={}".format(button))

    def OnKeyDown(self, key, Shift):
        logProxy.logger.info("Key={}".format(key))

class MainOpenGLHandler1(HandlerBase):
    def OnOpenGLMouseDown(self, button, Shift, X, Y):
        if button == const._MouseButtonLeft:
            strlog = 'left'
        elif button == const._MouseButtonRight:
            strlog = 'right'
        elif button == const._MouseButtonMiddle:
            strlog = 'middle'
        else :
            strlog = 'unknown'
        logProxy.logger.info("button={}".format(strlog))
        dShift = com.Dispatch(Shift)
        logProxy.logger.info("isShiftDown={}".format(dShift.isShiftDown))
        logProxy.logger.info("isAltDown={}".format(dShift.isAltDown))
        logProxy.logger.info("isCtrlDown={}".format(dShift.isCtrlDown))
        logProxy.logger.info("isLeftDown={}".format(dShift.isLeftDown))
        logProxy.logger.info("isRightDown={}".format(dShift.isRightDown))
        logProxy.logger.info("isMiddleDown={}".format(dShift.isMiddleDown))
        logProxy.logger.info("isDouble={}".format(dShift.isDouble))

def main():
    try:
        start = time.perf_counter_ns()
        global winRoadProxy
        winRoadProxy = UCwinRoadComProxy()
        global const
        const = winRoadProxy.const

        scriptName = 'Sample_InputDeviceLog'
        global logProxy
        logfilepath = winRoadProxy.PythonPluginDirectory() + scriptName + '.log'
        logProxy = LoggerProxy(scriptName, logfilepath)
        logProxy.logger.info('Start '+ scriptName)

        global EventList
        EventList = []
        SetCallbackHandlers(EventList, winRoadProxy.MainForm, MainFormHandler1)
        SetCallbackHandlers(EventList, winRoadProxy.MainForm.MainOpenGL, MainOpenGLHandler1)

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
        logProxy.killLogger()
        del winRoadProxy

if __name__ == '__main__':
    main()

# ここまで




