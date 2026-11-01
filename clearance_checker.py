
import json
import math
import sys

# ============================================================
# EAGLE: GEOMETRIC CLEARANCE ANALYSIS ENGINE
# ============================================================

print("=" * 60)
print(" EAGLE - GEOMETRIC CLEARANCE ANALYSIS ENGINE")
print("=" * 60)


# ============================================================
# 1. LOAD DESIGN
# ============================================================

try:
    with open("design.json", "r", encoding="utf-8") as file:
        design = json.load(file)

except Exception as e:
    print("[ERROR] Could not load design.json:", e)
    sys.exit(1)


if design.get("shape") != "box":
    print("[ERROR] Initial clearance engine supports box-shaped plates only.")
    sys.exit(1)


length = design.get("length")
width = design.get("width")
features = design.get("features", [])


def valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


if (
    not valid_number(length)
    or not valid_number(width)
    or length <= 0
    or width <= 0
):
    print("[ERROR] Invalid plate dimensions.")
    sys.exit(1)

if not isinstance(features, list):
    print("[ERROR] Features must be a list.")
    sys.exit(1)


# ============================================================
# 2. GET REQUIRED CLEARANCE
# ============================================================

try:
    minimum_clearance = float(
        input("\nEnter required minimum clearance (mm): ")
    )

    if not math.isfinite(minimum_clearance) or minimum_clearance < 0:
        raise ValueError("Clearance must be a finite non-negative number.")

except ValueError as e:
    print("[ERROR]", e)
    sys.exit(1)


# ============================================================
# 3. CONVERT FEATURES INTO GEOMETRIC REPRESENTATIONS
# ============================================================

holes = []
slots = []
errors = []

for index, feature in enumerate(features):

    if not isinstance(feature, dict):
        errors.append(f"Feature {index + 1} is not a valid object.")
        continue

    feature_type = feature.get("type")

    position = feature.get(
        "position",
        {"x": 0, "y": 0}
    )

    if not isinstance(position, dict):
        errors.append(f"Feature {index + 1} has invalid position.")
        continue

    x = position.get("x", 0)
    y = position.get("y", 0)

    if not valid_number(x) or not valid_number(y):
        errors.append(f"Feature {index + 1} has invalid coordinates.")
        continue

    if feature_type == "through_hole":

        diameter = feature.get("diameter")

        if not valid_number(diameter) or diameter <= 0:
            errors.append(f"Hole {index + 1} has invalid diameter.")
            continue

        holes.append({
            "name": f"Hole {index + 1}",
            "x": x,
            "y": y,
            "radius": diameter / 2
        })

    elif feature_type == "slot":

        slot_length = feature.get("length")
        slot_width = feature.get("width")
        orientation = feature.get(
            "orientation",
            "horizontal"
        )

        if (
            not valid_number(slot_length)
            or not valid_number(slot_width)
            or slot_length <= 0
            or slot_width <= 0
            or slot_width > slot_length
        ):
            errors.append(f"Slot {index + 1} has invalid dimensions.")
            continue

        if orientation not in ["horizontal", "vertical"]:
            errors.append(f"Slot {index + 1} has invalid orientation.")
            continue

        radius = slot_width / 2
        half_centerline = (slot_length - slot_width) / 2

        if orientation == "horizontal":
            p1 = (x - half_centerline, y)
            p2 = (x + half_centerline, y)
        else:
            p1 = (x, y - half_centerline)
            p2 = (x, y + half_centerline)

        slots.append({
            "name": f"Slot {len(slots) + 1}",
            "x": x,
            "y": y,
            "radius": radius,
            "p1": p1,
            "p2": p2,
            "length": slot_length,
            "width": slot_width,
            "orientation": orientation
        })


# ============================================================
# 4. GEOMETRY CALCULATION FUNCTIONS
# ============================================================

def distance(p1, p2):
    return math.hypot(
        p2[0] - p1[0],
        p2[1] - p1[1]
    )


def point_to_segment_distance(point, a, b):

    px, py = point
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    length_squared = dx**2 + dy**2

    if length_squared == 0:
        return distance(point, a)

    t = (
        (px - ax) * dx
        + (py - ay) * dy
    ) / length_squared

    t = max(0, min(1, t))

    closest = (
        ax + t * dx,
        ay + t * dy
    )

    return distance(point, closest)


def segments_intersect(a, b, c, d):

    def cross(p, q, r):
        return (
            (q[0] - p[0]) * (r[1] - p[1])
            - (q[1] - p[1]) * (r[0] - p[0])
        )

    def on_segment(p, q, r):
        return (
            min(p[0], r[0]) - 1e-9
            <= q[0]
            <= max(p[0], r[0]) + 1e-9
            and
            min(p[1], r[1]) - 1e-9
            <= q[1]
            <= max(p[1], r[1]) + 1e-9
        )

    o1 = cross(a, b, c)
    o2 = cross(a, b, d)
    o3 = cross(c, d, a)
    o4 = cross(c, d, b)

    if (
        ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0))
        and
        ((o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0))
    ):
        return True

    if abs(o1) < 1e-9 and on_segment(a, c, b):
        return True

    if abs(o2) < 1e-9 and on_segment(a, d, b):
        return True

    if abs(o3) < 1e-9 and on_segment(c, a, d):
        return True

    if abs(o4) < 1e-9 and on_segment(c, b, d):
        return True

    return False


def segment_to_segment_distance(a, b, c, d):

    if segments_intersect(a, b, c, d):
        return 0.0

    return min(
        point_to_segment_distance(a, c, d),
        point_to_segment_distance(b, c, d),
        point_to_segment_distance(c, a, b),
        point_to_segment_distance(d, a, b)
    )


# ============================================================
# 5. HOLE-TO-HOLE CLEARANCE
# ============================================================

results = []

for i in range(len(holes)):

    for j in range(i + 1, len(holes)):

        h1 = holes[i]
        h2 = holes[j]

        center_distance = distance(
            (h1["x"], h1["y"]),
            (h2["x"], h2["y"])
        )

        clearance = (
            center_distance
            - h1["radius"]
            - h2["radius"]
        )

        results.append({
            "pair": f'{h1["name"]} - {h2["name"]}',
            "clearance": clearance,
            "category": "Hole-to-hole"
        })


# ============================================================
# 6. HOLE-TO-SLOT CLEARANCE
# ============================================================

for hole in holes:

    for slot in slots:

        centerline_distance = point_to_segment_distance(
            (hole["x"], hole["y"]),
            slot["p1"],
            slot["p2"]
        )

        clearance = (
            centerline_distance
            - hole["radius"]
            - slot["radius"]
        )

        results.append({
            "pair": f'{hole["name"]} - {slot["name"]}',
            "clearance": clearance,
            "category": "Hole-to-slot"
        })


# ============================================================
# 7. SLOT-TO-SLOT CLEARANCE
# ============================================================

for i in range(len(slots)):

    for j in range(i + 1, len(slots)):

        s1 = slots[i]
        s2 = slots[j]

        centerline_distance = segment_to_segment_distance(
            s1["p1"],
            s1["p2"],
            s2["p1"],
            s2["p2"]
        )

        clearance = (
            centerline_distance
            - s1["radius"]
            - s2["radius"]
        )

        results.append({
            "pair": f'{s1["name"]} - {s2["name"]}',
            "clearance": clearance,
            "category": "Slot-to-slot"
        })


# ============================================================
# 8. FEATURE-TO-PLATE EDGE CLEARANCE
# ============================================================

half_length = length / 2
half_width = width / 2


def check_edge_clearance(
    name,
    center_x,
    center_y,
    half_x,
    half_y
):

    edge_distances = {
        "Left edge": (center_x - half_x) + half_length,
        "Right edge": half_length - (center_x + half_x),
        "Bottom edge": (center_y - half_y) + half_width,
        "Top edge": half_width - (center_y + half_y)
    }

    for edge_name, clearance in edge_distances.items():

        results.append({
            "pair": f"{name} - {edge_name}",
            "clearance": clearance,
            "category": "Feature-to-edge"
        })

for hole in holes:

    r = hole["radius"]

    check_edge_clearance(
        hole["name"],
        hole["x"],
        hole["y"],
        r,
        r
    )


for slot in slots:

    if slot["orientation"] == "horizontal":
        half_x = slot["length"] / 2
        half_y = slot["width"] / 2
    else:
        half_x = slot["width"] / 2
        half_y = slot["length"] / 2

    check_edge_clearance(
        slot["name"],
        slot["x"],
        slot["y"],
        half_x,
        half_y
    )


# ============================================================
# 9. DISPLAY ENGINEERING REPORT
# ============================================================

print()
print("=" * 60)
print(" GEOMETRIC CLEARANCE ANALYSIS REPORT")
print("=" * 60)

print(f"\nPlate dimensions: {length} x {width} mm")
print(f"Minimum required clearance: {minimum_clearance} mm")

print(f"\nHoles analysed: {len(holes)}")
print(f"Slots analysed: {len(slots)}")

if errors:

    print("\n[ERROR] Invalid features detected:")

    for error in errors:
        print("-", error)

    print("\nAnalysis stopped. Correct the input design first.")
    sys.exit(1)


if not holes and not slots:
    print("\nNo holes or slots found. Nothing to analyse.")
    sys.exit(0)


violations = []

print("\n" + "-" * 60)
print(" FEATURE CLEARANCE RESULTS")
print("-" * 60)

if not results:
    print("No feature pairs available for comparison.")

for result in results:

    clearance = result["clearance"]

    if clearance < 0:
        status = "INTERFERENCE"
        violations.append(result)

    elif clearance < minimum_clearance:
        status = "INSUFFICIENT CLEARANCE"
        violations.append(result)

    else:
        status = "PASS"

    print(f"\n{result['category']}")
    print(f"Pair: {result['pair']}")
    print(f"Calculated clearance: {clearance:.3f} mm")
    print(f"Required clearance: {minimum_clearance:.3f} mm")
    print(f"Status: {status}")


# ============================================================
# 10. FINAL RESULT
# ============================================================

print()
print("=" * 60)
print(" FINAL ENGINEERING ASSESSMENT")
print("=" * 60)

print(f"\nTotal checks: {len(results)}")
print(f"Violations: {len(violations)}")
print(f"Passed checks: {len(results) - len(violations)}")

if violations:

    print("\n[FAIL] DESIGN HAS CLEARANCE VIOLATIONS.")

    print("\nRecommended review:")

    for violation in violations:
        print(
            f"- {violation['pair']}: "
            f"{violation['clearance']:.3f} mm"
        )

else:

    print("\n[PASS] ALL CHECKED CLEARANCES SATISFY THE REQUIREMENT.")

print()
print("=" * 60)
print(" EAGLE ANALYSIS COMPLETE")
print("=" * 60)
