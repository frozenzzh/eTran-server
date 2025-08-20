
from collections import defaultdict
filePath = "/users/zhlin/eTran-priv/eTran/tcp_app/cpu_usage.log"

throughputMap=defaultdict(set)
latencyCpus=set()

with open(filePath, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith("throughput"):
            parts = line.split()
            port=parts[1].split('=')[1].rstrip(',')
            cpu=parts[2].split('=')[1]
            throughputMap[port].add(cpu)
        elif line.startswith("latency"):
            parts = line.split()
            cpu=parts[1].split('=')[1]
            latencyCpus.add(cpu)

for key in sorted(throughputMap.keys()):
    port = key
    cpus = sorted(throughputMap[key])
    print(f"Throughput: port={port}, cpus={','.join(cpus)}")
for cpu in sorted(latencyCpus):
    print(f"Latency: cpu={cpu}")