from collections import OrderedDict

# Read railways file
with open("railways.txt", "r", encoding="utf-8") as f:
    railways = f.read().splitlines()

# Base provinces (always included)
array = [12831, 4709]

# Provinces to exclude
remove = {4904, 13804}

# Extract railway endpoints
for line in railways:
    parts = line.split()
    if len(parts) < 3:
        continue

    try:
        start = int(parts[2])
        end = int(parts[-1])
        array.append(start)
        array.append(end)
    except ValueError:
        pass  # skip broken lines

# Remove duplicates while keeping order
array = list(OrderedDict.fromkeys(array))

# Write output file
with open("supply_nodes.txt", "w", encoding="utf-8") as f:
    for a in array:
        if a not in remove:
            f.write(f"1 {a}\n")

print("Done: supply_nodes.txt generated")