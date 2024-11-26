import httpx

url = "https://yktapp.nwpu.edu.cn/jfdt/charge/feeitem/getThirdData"


async def get_campus():
    data = {'feeitemid': '182', 'type': 'select', 'level': '0'}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=url,
            data=data
        )
        campus_all = response.json()['map']['data']
        msg = ""
        for i, campus in enumerate(campus_all):
            msg += str(i) + '  ' + campus['name'] + '\n'
        msg += '选择校区,如0或1'
        return msg, campus_all


async def get_building(campus):
    data = {'feeitemid': '182', 'type': 'select', 'level': '1', 'campus': campus}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=url,
            data=data
        )
        building_all = response.json()['map']['data']
        msg = ""
        count = 0
        msg_list = []
        for i, building in enumerate(building_all):
            count += 1
            msg += str(i) + '  ' + building['name'] + '\n'
            if count == 100:
                count = 0
                msg_list.append(msg)
                msg = ""
        msg += '选择楼栋,如0或1'
        msg_list.append(msg)
        return msg_list, building_all


async def get_room(campus, building):
    data = {'feeitemid': '182', 'type': 'select', 'level': '2', 'campus': campus, 'building': building}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=url,
            data=data
        )
        room_all = response.json()['map']['data']
        msg = ""
        count = 0
        msg_list = []
        for i, building in enumerate(room_all):
            count += 1
            msg += str(i) + '  ' + building['name'] + '\n'
            if count == 100:
                count = 0
                msg_list.append(msg)
                msg = ""
        msg += '选择房间,如0或1'
        msg_list.append(msg)
        return msg_list, room_all


async def get_electric_left(campus, building, room):
    data = {'feeitemid': '182', 'type': 'IEC', 'level': '3', 'campus': campus, 'building': building, 'room': room}
    async with httpx.AsyncClient() as client:
        response = await client.post(url=url, data=data)
        return float(response.json()['map']['showData']['当前剩余电量'])
