
from collections import defaultdict
filePath = "/users/zhlin/eTran-priv/eTran/tcp_app/cpu_usage-no-isolation.log"

throughputMap=defaultdict(set)
latencyCpus=set()

with open(filePath, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith("throughput"):
            parts = line.split()
            pid=parts[1].split('=')[1].rstrip(',')
            tid=parts[2].split('=')[1].rstrip(',')
            cpu=parts[3].split('=')[1]
            throughputMap[(pid,tid)].add(cpu)
        elif line.startswith("latency"):
            parts = line.split()
            cpu=parts[1].split('=')[1]
            latencyCpus.add(cpu)

for key in sorted(throughputMap.keys()):
    pid, tid = key
    cpus = sorted(throughputMap[key])
    print(f"Throughput: pid={pid}, tid={tid}, cpus={','.join(cpus)}")
for cpu in sorted(latencyCpus):
    print(f"Latency: cpu={cpu}")