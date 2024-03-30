import requests


url = "https://yktapp.nwpu.edu.cn/jfdt/charge/feeitem/getThirdData"
def get_campaus():
    data = {'feeitemid':'182','type':'select','level':'0'}
    response = requests.post(
        url=url,
        data=data
    )
    campaus_all = response.json()['map']['data']
    msg = ""
    for i, campaus in enumerate(campaus_all):
        msg += str(i) + '  ' + campaus['name'] + '\n'
    msg +=  '选择校区,如0或1'
    return msg,campaus_all

def get_building(campaus):
    data = {'feeitemid':'182','type':'select','level':'1','campaus':campaus}
    response = requests.post(
        url=url,
        data=data
    )
    building_all = response.json()['map']['data']
    msg = ""
    count = 0
    msg_list = []
    for i, building in enumerate(building_all):
        count += 1
        msg +=str(i) + '  ' + building['name'] + '\n'
        if count == 100:
            count = 0
            msg_list.append(msg)
            msg = ""
    msg +=  '选择楼栋,如0或1'
    msg_list.append(msg)
    return msg_list,building_all

def get_room(campaus,building):
    data = {'feeitemid':'182','type':'select','level':'2','campaus':campaus,'building':building}
    response = requests.post(
        url=url,
        data=data
    )
    room_all = response.json()['map']['data']
    msg = ""
    count = 0
    msg_list = []
    for i, building in enumerate(room_all):
        count += 1
        msg +=str(i) + '  ' + building['name'] + '\n'
        if count == 100:
            count = 0
            msg_list.append(msg)
            msg = ""
    msg +=  '选择房间,如0或1'
    msg_list.append(msg)
    return msg_list,room_all

def get_electric_left(campaus,building,room):
    data = {'feeitemid':'182','type':'IEC','level':'3','campaus':campaus,'building':building,'room':room }
    response = requests.post(
        url=url,
        data=data
    )
    return float(response.json()['map']['showData']['当前剩余电量'])
