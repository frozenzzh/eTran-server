import os
from collections import defaultdict
from matplotlib import pyplot as plt
import time
import numpy as np

# msgSizeList=[4000,32000]
msgSizeList=[2000,4000,8000,16000,32000,64000,128000,256000,512000]
outstandingLargeList=[1]

msgSizeSmallList=[2,4,8,16,32,64,128,512]
outstandingSmallList=[64]

resultMulProc=[]
resultMulThread=[]

currNum=4

passwd="HRk3T7LWzE"
sleepTimeSec=60
topN=10#仅仅取前10个点的平均值

def runRemote(msgSize, outstanding):
    remote_cmds = [
        "cd /users/zhlin/eTran-priv/eTran/micro_kernel",
        f"sudo ./micro_kernel </dev/null >micro_kernel.txt 2>&1 &",
        "sleep 10",
        "cd /users/zhlin/eTran-priv/eTran/tcp_app"
    ]
    for i in range(currNum):
        remote_cmds.append(
            f"env ETRAN_PROTO=tcp ETRAN_NR_APP_THREADS=1 ETRAN_NR_NIC_QUEUES=1 "
            f"LD_PRELOAD=../shared_lib/libetran.so ./epoll_client "
            f"-i 10.10.1.1 -p {50000+i} -l {msgSize} -b {msgSize} -o {outstanding} >/users/zhlin/eTran-priv/batch_exp/{i}.txt &"
        )
        remote_cmds.append("sleep 3")
    full_remote_cmd = "\n".join(remote_cmds)
    os.system(f"sshpass -p '{passwd}' ssh -f zhlin@hp134.utah.cloudlab.us -p 22 '{full_remote_cmd}'")

def expClose():
    #client close
    remoteCmdsClose = [f"echo {passwd} | sudo -S killall epoll_client", f"echo {passwd} | sudo -S killall -s SIGINT micro_kernel"]
    fullRemoteCmdClose = " \n ".join(remoteCmdsClose)
    os.system(f"sshpass -p '{passwd}' ssh zhlin@hp134.utah.cloudlab.us -p 22 '{fullRemoteCmdClose}'")

    #server close
    os.system(f"echo {passwd} | sudo -S killall epoll_server")
    os.system(f"echo {passwd} | sudo -S killall -s SIGINT micro_kernel")
    
    time.sleep(10)

def runExpMulProc(msgSize, outstanding):
    #server端启动currNum个线程共享一个RXQ
    #server
    os.chdir(os.path.expanduser("~/eTran-priv/eTran/micro_kernel/"))
    os.system(f"sudo ./micro_kernel -Q 1 </dev/null >/users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/micro_kernel-mulProc.txt 2>&1 &")
    print("waiting 10s for micro_kernel to start...")
    time.sleep(10)

    print("launch micro_kernel succ on server in MulProc!")
    os.chdir(os.path.expanduser("~/eTran-priv/eTran/tcp_app"))
    for i in range(currNum):
        os.system(f"env ETRAN_PROTO=tcp ETRAN_NR_APP_THREADS=1 ETRAN_ALLOW_SHARED_QUEUES=1 ETRAN_NR_NIC_QUEUES=1 LD_PRELOAD=../shared_lib/libetran.so ./epoll_server -i 10.10.1.1 -p {50000+i} -l {msgSize} -b {msgSize} >/users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/{i}.txt &")
        os.system("sleep 3")
    time.sleep(10)
    print("launch epoll_server succ on server in MulProc!")
    #client
    runRemote(msgSize, outstanding)
    print("launch epoll_client succ on client in MulProc!")
    time.sleep(sleepTimeSec)

    expClose()
    print("close all processes on server and client in MulProc!")


def runExpMulThread(msgSize, outstanding):
    #server端启动currNum个线程共享一个RXQ
    #server
    os.chdir(os.path.expanduser("~/eTran-priv/eTran/micro_kernel/"))
    os.system(f"sudo ./micro_kernel </dev/null >/users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/micro_kernel-mulThread.txt 2>&1 &")
    time.sleep(10)
    os.chdir(os.path.expanduser("~/eTran-priv/eTran/tcp_app"))
    os.system(f"env ETRAN_PROTO=tcp ETRAN_NR_APP_THREADS={currNum} ETRAN_NR_NIC_QUEUES=1 LD_PRELOAD=../shared_lib/libetran.so ./epoll_server -i 10.10.1.1 -p 50000 -l {msgSize} -b {msgSize} -t {currNum} > /users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/serverMulThread.txt &")
    #client
    runRemote(msgSize, outstanding)

    time.sleep(sleepTimeSec)

    expClose()

def getMulProcData(msgSize, outstanding):
    timeValMap=defaultdict(float)
    #这里需要依照时间戳来统计
    for i in range(currNum):
        with open(f"/users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/{i}.txt", "r") as f:
            line=f.readline()
            while line:
                if line.strip():
                    fields= line.strip().split()
                    if "PID" in fields:
                        time=fields[0]
                        throughputStr=fields[4]
                        throughput=float(throughputStr.split('(')[1].split('/')[0])
                        timeValMap[time]+=throughput
                line=f.readline()
    top_items = sorted(timeValMap.items(), key=lambda item: item[1], reverse=True)[:topN]
    if top_items:
        ret = sum(val for _, val in top_items) / len(top_items)
    else:
        ret = 0.0
    return ret

def getMulThreadData(msgSize, outstanding):
    timeValMap=defaultdict(float)
    #这里需要依照时间戳来统计
    with open(f"/users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}/serverMulThread.txt", "r") as f:
       line=f.readline()
       while line:
           if line.strip():
               fields= line.strip().split()
               if "PID" in fields:
                   time=fields[0]
                   throughputStr=fields[4]
                   throughput=float(throughputStr.split('(')[1].split('/')[0])
                   timeValMap[time]+=throughput
           line=f.readline()
    top_items = sorted(timeValMap.items(), key=lambda item: item[1], reverse=True)[:topN]
    if top_items:
        ret = sum(val for _, val in top_items) / len(top_items)
    else:
        ret = 0.0
    return ret

def draw(msgSizeList, type):
    resultMulProc.sort(key=lambda x: x[0])
    resultMulThread.sort(key=lambda x: x[0])
    assert len(msgSizeList) == len(resultMulProc) == len(resultMulThread)
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
        fileName="large.pdf"
    elif type=="small":
        fileName="small.pdf"
    plt.savefig(fileName, bbox_inches='tight')
    plt.close()

def saveResults(msgSize, outstanding):
    throughputMulProc=getMulProcData(msgSize, outstanding)
    throughputMulThread=getMulThreadData(msgSize, outstanding)
    log_path = "/users/zhlin/eTran-priv/batch_exp/metrics.log"
    with open(log_path, "a", encoding="utf-8") as f:   # "a" 追加；改成 "w" 会覆盖
        print(
            f"msgSize={msgSize}, outstanding={outstanding}, "
            f"throughputMulProc={throughputMulProc}, throughputMulThread={throughputMulThread}",
            file=f
        )    
    resultMulProc.append((msgSize,throughputMulProc))
    resultMulThread.append((msgSize,throughputMulThread))

def runExp(msgSize, outstanding):
    os.system(f"mkdir /users/zhlin/eTran-priv/batch_exp/{msgSize}-{outstanding}")
    runExpMulProc(msgSize,outstanding)
    runExpMulThread(msgSize,outstanding)

def runAndProcess(msgSizeList,outstandingList,type):
    for msgSize in msgSizeList:
        for outstanding in outstandingList:
            print(f"run msgSize={msgSize}, outstanding={outstanding}")
            runExp(msgSize, outstanding)
            saveResults(msgSize,outstanding)
    draw(msgSizeList, type)

runAndProcess(msgSizeList, outstandingLargeList, "large")
# runAndProcess(msgSizeSmallList, outstandingSmallList, "small")