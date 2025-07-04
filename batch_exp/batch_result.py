import os
from collections import defaultdict
from matplotlib import pyplot as plt
import time
import numpy as np
from typing import Dict, List, Tuple

msgSizeList=[]


currNum=4

topN=5#仅仅取前10个点的平均值

thresh=0.05

def getProcAvg(msgSize):
    time_vals:Dict[str, List[float]] = defaultdict(list)
    #这里需要依照时间戳来统计
    for i in range(currNum):
        with open(f"/users/zhlin/eTran-priv/batch_exp/{msgSize}-1/{i}.txt", "r") as f:
            line=f.readline()
            while line:
                if line.strip():
                    fields= line.strip().split()
                    if "PID" in fields:
                        time=fields[0]
                        throughputStr=fields[4]
                        throughput=float(throughputStr.split('(')[1].split('/')[0])
                        if (throughput > thresh):
                            time_vals[time].append(throughput)
                line=f.readline()
    time_avg: List[Tuple[str, float]] = [
        (ts, sum(vals) / len(vals)) for ts, vals in time_vals.items() if vals
    ]
    top_items = sorted(time_avg, key=lambda x: x[1], reverse=True)[:topN]

    if top_items:
        return sum(val for _, val in top_items) / len(top_items)
    return 0.0

def getThreadAvg(msgSize):
    timeVals=[]
    #这里需要依照时间戳来统计
    with open(f"/users/zhlin/eTran-priv/batch_exp/{msgSize}-1/serverMulThread.txt", "r") as f:
        line=f.readline()
        while line:
            if line.strip():
                fields= line.strip().split()
                if "PID" in fields:
                    vals=[]
                    for i in range(currNum):
                        newline=f.readline()
                        if newline.strip():
                            newline_fields=newline.strip().split()
                            throughputStr=newline_fields[1]
                            throughput=float(throughputStr.split('(')[1].split('/')[0])
                            if throughput > thresh:
                               vals.append(throughput)
                    if vals: timeVals.append(sum(vals) / len(vals))
            line=f.readline()
    # print("timeVals for msgSize", msgSize, ":", timeVals)
    top_items = sorted(timeVals,reverse=True)[:topN]
    if top_items:
        ret = sum(top_items) / len(top_items)
    else:
        ret = 0.0
    return ret

def draw(msgSizeList, type, resultMulProc, resultMulThread):
    assert len(msgSizeList) == len(resultMulProc) == len(resultMulThread)
    if (type=='avg'):
        print("Results for Multi-Process:")
        print(resultMulProc)
        print("Results for Multi-Thread:")
        print(resultMulThread)
    sizeLabels=[]
    for msgSize in msgSizeList:
        if msgSize >= 1_000_000:
            sizeLabels.append(f"{int(msgSize / 1_000_000)}M")
        elif msgSize >= 1000:
            sizeLabels.append(f"{int(msgSize / 1000)}K")
        else:
            sizeLabels.append(str(msgSize))
    plt.figure(figsize=(6,4))
    xRay=np.arange(len(msgSizeList))
    
    plt.plot(xRay, resultMulProc, "o--", color="blue", label="shared RXQ mul-proc")
    plt.plot(xRay, resultMulThread, "s--", color="red", label="mul-thread")

    # 设置坐标轴
    plt.xticks(xRay, sizeLabels, rotation=45)
    plt.xlabel("Size (Bytes)")
    plt.ylabel("Throughput (Gbps)")

    # 网格线 & 图例
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()
    if type=="large":
        fileName="/users/zhlin/eTran-priv/batch_exp/large.pdf"
    elif type=="small":
        fileName="/users/zhlin/eTran-priv/batch_exp/small.pdf"
    elif type=="avg":
        fileName="/users/zhlin/eTran-priv/batch_exp/avg.pdf"
    plt.savefig(fileName, bbox_inches='tight')
    plt.close()


def drawAll():
    resultMulProc=[]
    resultMulThread=[]
    with open("/users/zhlin/eTran-priv/batch_exp/metrics.log", "r") as f:
        for i in range(9):
            line=f.readline()
            fields=line.strip().split(" ")
            msgSize=int(fields[0].split("=")[1].replace(",",""))
            throughputMulProc=float(fields[2].split("=")[1].replace(",",""))
            throughputMulThread=float(fields[3].split("=")[1].replace(",",""))
            msgSizeList.append(msgSize)
            resultMulProc.append(throughputMulProc)
            resultMulThread.append(throughputMulThread)
    draw(msgSizeList, "large", resultMulProc, resultMulThread)

def drawAvg():
    mulProcAvgList=[]
    mulThreadAvgList=[]
    for msgSize in msgSizeList:
        procAvg = getProcAvg(msgSize)
        threadAvg = getThreadAvg(msgSize)
        mulProcAvgList.append(procAvg)
        mulThreadAvgList.append(threadAvg)
    draw(msgSizeList, "avg", mulProcAvgList, mulThreadAvgList)

drawAll()
drawAvg()