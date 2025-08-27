from tkinter import messagebox 
import platform
import os

cwd = os.getcwd()
print('Current directory:', cwd)
os_name = platform.system()
if os_name == 'Windows' :
    os.system('explorer.exe "%s"' % cwd)
