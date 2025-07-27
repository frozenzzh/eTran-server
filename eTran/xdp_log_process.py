import sys
from collections import defaultdict

filePath = "/users/zhlin/eTran-priv/eTran/xdp.log"

# port ➜ list of (cpu, queue) tuples
port_map = defaultdict(list)

def extract_int(line: str, pos: int) -> tuple[int, int]:
    """从 line[pos] 开始提取连续数字，返回(值, 下一个位置)。"""
    n = 0
    while pos < len(line) and line[pos].isdigit():
        n = n * 10 + (ord(line[pos]) - 48)
        pos += 1
    return n, pos

with open(filePath, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:                          # 逐行处理，避免一次性读大文件
        # 找关键字的位置；若缺失则跳过
        p_cpu   = line.find("CPU=")
        if p_cpu == -1:
            continue
        p_queue = line.find("QUEUE=", p_cpu)
        p_port  = line.find("port=",  p_queue)
        if p_queue == -1 or p_port == -1:
            continue

        # 解析数字（不使用正则）
        cpu,   _ = extract_int(line, p_cpu   + 4)
        queue, _ = extract_int(line, p_queue + 6)
        port,  _ = extract_int(line, p_port  + 5)

        port_map[port].append((cpu, queue))

# 输出结果（按端口排序）
for port in sorted(port_map):
    pairs = ", ".join(f"({c},{q})" for c, q in port_map[port])
    print(f"port {port}: [{pairs}]")
