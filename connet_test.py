import win32com.client

try:
    ucwin = win32com.client.Dispatch("UcwinRoad.UcwinRoadCom_1723")
    print("UC-win/Road 연결 성공!")
    print(dir(ucwin))

except Exception as e:
    print("연결 실패:", e)