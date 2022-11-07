#!/usr/bin/python3
# -*-coding:utf-8 -*-
"""
Create time: 2022/09/26
Author: Kayla Lin
"""
# thought:
"""
For read COMTRADE file and get the peak in data
NOTICE: if you don't understand COMTRAD file,
    PLEASE refer to comtrade standard 1999.
    All of page infos are according to ENGLISH VERSION.
    Additionally, there are some information in comtrade/reference/ folder,
    please have a look.

1. read the CFG files to get the config structure -> Comtrade.read_cfg()
2. read the DAT files to get the data -> obj Comtrade

3. find the waves before faluts in a feeder -> recrusive
    not sort -> obj Comtrade
4. export information to csv file -> just formatting?

Requirements:
1. the full data on newest date
2. ABCN and fault information
3. device name , which feeder, feeder breaker

Therefore, the functions will be: 
1. find every latest cfg and dat files in a folder
2. for every folder, find every latest paired files
3. get the data and save to csv

"""


# set path
from gc import set_debug
from pathlib import Path, PurePath


# to read binary data
import re
import struct

from datetime import date, datetime

# this path is setting for test
folderPath = str(
    PurePath(
        Path().cwd(),
        "data",
        "xingYa",
        "COMTRADE",
        "MCB1",
    )
)


class Comtrade:
    def __init__(self, folderPath: str, filename: str):
        self.cfg_file = PurePath(folderPath, f"{filename}.CFG")
        self.dat_file = PurePath(folderPath, f"{filename}.DAT")

    def show_error(self):
        # if error, show this error.
        # maybe set a golbal error package for modual?
        pass

    def read_cfg(self):
        cfg_lines = []
        with open(self.cfg_file) as cfg_obj:
            lines = cfg_obj.readlines()
            for l in lines:
                l = l.rstrip()
                l = l.split(",")
                cfg_lines.append(l)
        # check the cfg file is binary or not. If not, return
        file_format = cfg_lines[-2][0]
        if file_format != "BINARY":
            return {"Message": "DAT NOT a binary file."}

        """
        Please refer to p17-21 in comtrade_standard_1999(ENG ver)
        for data def
        """
        # find the number of analog channels
        analog_channel_num = int(re.findall("\d+", cfg_lines[1][1])[0])
        # find the number of status channels
        # the calculation (x+15)/16 is for transform binary
        status_channel_num = int((int(re.findall("\d+", cfg_lines[1][2])[0]) + 15) / 16)
        # last sample number at sample rate = points in a wave
        wave_points = int(cfg_lines[-5][-1])
        start_time = cfg_lines[-4]
        trigger_time = cfg_lines[-3]
        """
        [-4] = time start; [-3] = time trigger
        """

        ana_infos = {}
        for i in range(analog_channel_num):
            info_dict = {
                i: {
                    # An = analog
                    "An": int(cfg_lines[i + 2][0]),
                    # ch-id = channel identifier
                    "ch-id": int(cfg_lines[i + 2][0]),
                    # ph = phase
                    "ph": cfg_lines[i + 2][2],
                    # ccbm = circuit component being monitored
                    "ccbm": cfg_lines[i + 2][3],
                    # uu = unit
                    "uu": cfg_lines[i + 2][4],
                    # a = channel mutiplier
                    "a": float(cfg_lines[i + 2][5]),
                    # b = channel offset adder ; f(x)= a*data+b
                    "b": float(cfg_lines[i + 2][6]),
                    # channel time skew from start of sample period.(optional)
                    "skew": float(cfg_lines[i + 2][7]),
                    # lower limit of possible data value range
                    "min": int(cfg_lines[i + 2][8]),
                    # upper limit of possible data value range
                    "max": int(cfg_lines[i + 2][9]),
                    # the channel voltage or current transformer ratio primary factor
                    "primary": float(cfg_lines[i + 2][10]),
                    # the channel voltage or current transformer ratio secondary factor
                    "secondary": float(cfg_lines[i + 2][11]),
                    # the primary or secondary data scaling identifier
                    "ps": cfg_lines[i + 2][12],
                    "ana_data": [],
                    "pri_data": [],
                    "start_time": cfg_lines[-4],
                    "trigger_time": cfg_lines[-3],
                }
            }
            ana_infos.update(info_dict)
        return (
            ana_infos,
            analog_channel_num,
            status_channel_num,
            wave_points,
            start_time,
            trigger_time,
        )

    def read_dat(self):
        ana_infos = self.read_cfg()[0]
        analog_channel_num = self.read_cfg()[1]
        status_channel_num = self.read_cfg()[2]
        wave_points = self.read_cfg()[3]
        start_time = self.read_cfg()[4]
        packed_datas = []
        data = {"start_time": start_time, "index": {}}

        # II = index + timestamp; < = little-endian; "h"=analog; "H" = status
        pack_format = "<II" + "h" * analog_channel_num + "H" * status_channel_num

        """
        Please refer to COMTRADE STANDARD 1999 p25 for
        the following formula of dataframe_lenth
        """
        dataframe_lenth = 4 + 4 + 2 * analog_channel_num + 2 * status_channel_num

        with open(self.dat_file, "rb") as dat_obj:
            for i in range(wave_points):
                recv_buf = dat_obj.read(dataframe_lenth)
                if len(recv_buf) != dataframe_lenth:
                    return {"Message": "Please check dataframe."}
                else:
                    packed_datas.append(recv_buf)
        # read data
        for i in range(wave_points):
            n_stuct = struct.Struct(pack_format)
            n_unpacked_data = n_stuct.unpack(packed_datas[i])
            for j in range(analog_channel_num):
                ana_infos[j]["ana_data"].append(n_unpacked_data[2 + j])
        # transform to primary value : a*{data}+b
        for i in range(wave_points):
            for j in range(analog_channel_num):
                ana_infos[j]["pri_data"].append(
                    (
                        ana_infos[j]["ana_data"][i] * ana_infos[j]["a"]
                        + ana_infos[j]["b"]
                    )
                )
        data["index"].update(ana_infos)
        return data

    def get_time_interval(self):
        # start_time means a device detected something may start to be wrong,
        # trigger_time means a device detected wrong information happened.
        """
        thoughts:
        1. (trigger_time - start_time)/point_number = time_interval of one point
        2. get start_time, time_interval
        """
        from datetime import datetime

        start_time = " ".join(self.read_cfg()[4])
        trigger_time = " ".join(self.read_cfg()[5])
        time_format = "%d/%m/%Y %H:%M:%S.%f"
        # orginal format example: '06/01/2022 14:19:32.461840'
        start_time = datetime.strptime(start_time, time_format)
        trigger_time = datetime.strptime(trigger_time, time_format)

        time_interval = (trigger_time - start_time) / 1600  # how long take 1 point

        return start_time, time_interval

    def draw_current_plot(self, plot_filename):
        # draw a current plot in a comtrade file
        # including phase A, phase B, phase C, and phase N
        import matplotlib.pyplot as plt

        phaseA_index = 0
        phaseB_index = 1
        phaseC_index = 2
        phaseN_index = 3

        a = self.read_dat()["index"][phaseA_index]["pri_data"]
        b = self.read_dat()["index"][phaseB_index]["pri_data"]
        c = self.read_dat()["index"][phaseC_index]["pri_data"]
        d = self.read_dat()["index"][phaseN_index]["pri_data"]

        ylim = max([max(map(abs, value)) for value in zip(a, b, c, d)])

        fig, axs = plt.subplots(4, sharex=True, sharey=True)
        fig.suptitle("IL (unit=A)")
        # set plot points
        axs[0].plot(a, linewidth=1)
        axs[1].plot(b, linewidth=1)
        axs[2].plot(c, linewidth=1)
        axs[3].plot(d, linewidth=1)
        # set plot ylabel
        axs[0].set_ylabel("PhaseA")
        axs[1].set_ylabel("PhaseB")
        axs[2].set_ylabel("PhaseC")
        axs[3].set_ylabel("PhaseN")

        plt.ylim([-ylim, ylim])

        plt.savefig(
            PurePath(Path().cwd(), f"{plot_filename}.svg"),
            dpi="figure",
            format="svg",
            metadata=None,
            bbox_inches=None,
            pad_inches=0.1,
            facecolor="white",
            edgecolor="auto",
            backend=None,
        )
        plt.show()


def set_path():
    """
    for set script path and data path
    """
    script_path = Path().cwd()
    data_path = str(PurePath(Path().cwd(), "data", "xingYa", "COMTRADE", "MCB1"))
    return script_path, data_path


def iterate_files(folderPath: str):
    # retrieve all datas in target folder
    """
    Get the folder path, if there are CFG files,
    read the DAT files, add them to list and return (Due to the filename is the same)
    """
    # list file name in the target folder
    p = Path(folderPath).glob("**/*")
    cfgFileName = [
        str(x).split(".")[0] for x in p if x.is_file() and str(x)[-3:] == "CFG"
    ]
    dataList = [Comtrade(name).read_dat() for name in cfgFileName]

    return dataList


def retrieve_total_points(folderPath: str, index, point=0):
    # retrieve total points in a folder
    dataList = iterate_files(folderPath)
    total_wave_points = []
    for data in dataList:
        for points in data["index"][index]["pri_data"][point:]:
            total_wave_points.append(points)
    return total_wave_points


def find_latest_record(folderPath: str):
    """
    find the latest xml desc record in a folder,
    and get the lastes COMTRADE filename
    """

    from pathlib import Path

    p = Path(folderPath).glob("**/*")
    xmlFileName = [str(x) for x in p if x.is_file() and str(x)[-3:] == "xml"]
    latest_desc_file = sorted(xmlFileName, reverse=True)[0]

    # open the xml dexc and return the DAT&CFG file name
    import defusedxml.ElementTree as Xet  # read xml
    import xmltodict  # extract xml to dict

    if Path(latest_desc_file).exists() and str(latest_desc_file)[-3:] == "xml":
        xmlparse = Xet.parse(latest_desc_file)
        root = xmlparse.getroot()
        toString = Xet.tostring(root, encoding="UTF-8", method="xml")
        xmlDict = xmltodict.parse(toString)

    latest_filename = str(xmlDict["Recording"]["Files"]["File"][0]).split(".")[0]
    return latest_filename


def draw_save_folder_plot(folderPath):
    import matplotlib.pyplot as plt

    IL1A = retrieve_total_points(folderPath, 0)
    IL2B = retrieve_total_points(folderPath, 1)
    IL3C = retrieve_total_points(folderPath, 2)
    IL4N = retrieve_total_points(folderPath, 3)
    fig, axs = plt.subplots(3, sharex=True, sharey=True)
    fig.suptitle("IL (unit=A)")
    axs[0].plot(IL1A, linewidth=1)
    axs[1].plot(IL2B, linewidth=1)
    axs[2].plot(IL3C, linewidth=1)
    axs[3].plot(IL4N, linewidth=1)

    p = Path().cwd()

    plt.savefig(
        p + "test",
        dpi="figure",
        format="svg",
        metadata=None,
        bbox_inches=None,
        pad_inches=0.1,
        facecolor="white",
        edgecolor="auto",
        backend=None,
    )
    plt.show()


def get_data_point(folderPath, index):

    filename = find_latest_record(folderPath)
    data = Comtrade(folderPath, filename).read_dat()
    return data["index"][index]["pri_data"]


def get_data_time(folderPath):

    filename = find_latest_record(folderPath)
    data = Comtrade(folderPath, filename).read_dat()
    return (data["start_time"],)


def find_max(folderPath, num):
    # thought
    """
    how can I know the max value?
    it is not a maximum in all data, but a maximal in a period

    what is the values we want?

    ways to get max value:
    1. read all (time, point) and get max values
    2. create a generater,
        2.1 just select a maxixum in every file
        2.2 when a value > previous one and > or equal to the next one, save it

    """
    dataList = iterate_files(folderPath)
    maxPoint = [max(i) for i in dataList]
    return maxPoint


def find_waveform():
    pass


def format_date():
    # thought
    """
    change date format to required format
    ori_format: [dd/mm/yyyy, hh:mm:ss.ssssss]
    aim_format: yyyy/mm/dd, hh:mm:ss.ssssss
    """
    pass


def transform_data(folderPath, filename):
    """
    to transform data format to write csv
    """

    ILA = get_data_point(folderPath, 0)
    ILB = get_data_point(folderPath, 1)
    ILC = get_data_point(folderPath, 2)
    ILN = get_data_point(folderPath, 3)
    start_time = Comtrade(folderPath, filename).get_data_before_trigger_time()[0]
    interval = Comtrade(folderPath, filename).get_data_before_trigger_time()[1]
    data_list = []
    datetime_str_format = "%Y-%m-%d %H:%M:%S.%f"
    for IL in zip(ILA, ILB, ILC, ILN):
        tmp_row = [
            "XingYa",
            "MCB1",
            start_time.strftime(datetime_str_format),
            IL[0],
            IL[1],
            IL[2],
            IL[3],
        ]
        data_list.append(tmp_row)
        start_time += interval
    return data_list


def export_csv(folderPath, filename):
    import csv

    header = [
        "Substation",
        "Device",
        "Record_time",
        "ILA",
        "ILB",
        "ILC",
        "ILN",
    ]

    from datetime import date

    today = date.today().strftime("%Y%m%d")
    data = transform_data(folderPath, filename)
    with open(f"{folderPath}/test_{today}.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(data)


def main():
    pass


if __name__ == "__main__":
    main()
