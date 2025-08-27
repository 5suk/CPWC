import win32com.client as com
import platform
import os

dir = com.gencache.GetGeneratePath()
print('Cache directory:', dir)
os_name = platform.system()
if os_name == 'Windows' :
    os.system('explorer.exe "%s"' % dir)
