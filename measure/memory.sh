#!/usr/bin/env bash
# Records the memory of every running container once per second, while the benchmark runs.
# Run it in a second terminal, on the laptop (not in a container), from the project folder:
#     bash measure/memory.sh
# Stop it with Ctrl+C when the benchmark is done: it prints the peak of each container.
# Every sample is also saved in measure/results/memory.csv.
OUT=measure/results/memory.csv
mkdir -p measure/results
echo "time,container,mem_usage,cpu" > "$OUT"

# called on Ctrl+C: highest memory value seen for each container, converted to MiB
summary() {
  echo
  echo "Peak memory per container (MiB):"
  python3 - "$OUT" <<'PY'
import csv, re, sys
units = {"B": 1/2**20, "KiB": 1/1024, "kB": 1/1024, "MiB": 1, "MB": 1, "GiB": 1024, "GB": 1024}
peak = {}
for row in csv.DictReader(open(sys.argv[1])):
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", row["mem_usage"].split("/")[0].strip())
    if m:
        v = float(m.group(1)) * units.get(m.group(2), 1)
        peak[row["container"]] = max(peak.get(row["container"], 0), v)
for name, v in sorted(peak.items()):
    print(f"  {name:40s} {v:8.1f}")
PY
  exit 0
}
trap summary INT

while true; do
  docker stats --no-stream --format "{{.Name}},{{.MemUsage}},{{.CPUPerc}}" \
    | sed "s/^/$(date +%H:%M:%S),/" >> "$OUT"
  sleep 1
done
