#!/usr/bin/env python3
import sys

FILES = [
    "/users/zhlin/eTran-priv/eTran/tcp_app/2.txt",
    "/users/zhlin/eTran-priv/eTran/tcp_app/3.txt",
    "/users/zhlin/eTran-priv/eTran/tcp_app/4.txt",
]
USAGE = "Usage: python3 avg_simple_lines.py [before|after] HH:MM:SS seconds"

def read_file(p):
    try: return open(p,"r",encoding="utf-8",errors="ignore").read().splitlines()
    except: return []

def get_in(line):
    k = line.find("In/Out(")
    if k < 0: return None
    k += len("In/Out(")
    s = line.find("/", k)
    if s < 0: return None
    try: return float(line[k:s].strip())
    except: return None

def find_anchors(lines_list, ts):
    tag = "[" + ts + "]"
    idxs = []
    for lines in lines_list:
        pos = -1
        for i, ln in enumerate(lines):
            if ln.startswith(tag): pos = i; break
        idxs.append(pos)
    return idxs

# 用法示例（before，向上取 secs 行；after 则向下含锚点 secs 行）
mode, ts, secs = sys.argv[1].lower(), sys.argv[2], int(sys.argv[3])
# mode, ts, secs = "before", "02:01:00", 60
L = [read_file(p) for p in FILES]
anchors = find_anchors(L, ts)  # 比如 [123, 123, 123] 或 [123, -1, 125]

sums, hits = 0.0, 0
for off in (range(1, secs+1) if mode=="before" else range(0, secs)):
    vals = []
    for f_i, lines in enumerate(L):
        a = anchors[f_i]
        if a < 0: continue
        j = a - off if mode=="before" else a + off
        if 0 <= j < len(lines):
            v = get_in(lines[j])
            if v is not None: vals.append(v)
    if vals:
        sums += sum(vals); hits += 1

print("No samples" if hits==0 else f"Avg In: {sums/hits:.6f} Gbps (seconds={hits})")
