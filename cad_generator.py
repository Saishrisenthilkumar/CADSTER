
import json
import cadquery as cq
import sys
import os

# ==========================================
# 1. Read design specification
# ==========================================

with open("design.json", "r") as file:
    design = json.load(file)

shape = design["shape"]

# ==========================================
# 2. Create base shape
# ==========================================

if shape == "box":

    length = design["length"]
    width = design["width"]
    height = design["height"]

    model = cq.Workplane("XY").box(length, width, height)

elif shape == "cylinder":

    radius = design["radius"]
    height = design["height"]

    model = cq.Workplane("XY").cylinder(height, radius)

elif shape == "cone":

    radius = design["radius"]
    height = design["height"]

    cone = cq.Solid.makeCone(radius, 0, height)
    model = cq.Workplane("XY").add(cone)

else:
    raise ValueError(f"Unsupported shape: {shape}")

# Z-position of the bottom face of the base shape.
# Boxes and cylinders are centred around Z=0.
# Cones extend from Z=0 to Z=height.

if shape in ["box", "cylinder"]:
    bottom_z = -height / 2
else:
    bottom_z = 0

# ==========================================
# 3. Separate feature types
# ==========================================

features = design.get("features", [])

edge_features = []
hole_features = []
slot_features = []

for feature in features:

    feature_type = feature["type"]

    if feature_type in ["fillet", "chamfer"]:
        edge_features.append(feature)

    elif feature_type == "through_hole":
        hole_features.append(feature)

    elif feature_type == "slot":
        slot_features.append(feature)

    else:
        print(f"Warning: Unsupported feature: {feature_type}")

# ==========================================
# 4. Apply fillet / chamfer
# ==========================================

for feature in edge_features:

    if feature["type"] == "fillet":

        radius = feature["radius"]
        print(f"Applying fillet: {radius} mm")

        try:
            model = model.edges().fillet(radius)
        except Exception as e:
            print(f"WARNING: Fillet failed: {e}")

    elif feature["type"] == "chamfer":

        distance = feature["distance"]
        print(f"Applying chamfer: {distance} mm")

        try:
            model = model.edges().chamfer(distance)
        except Exception as e:
            print(f"WARNING: Chamfer failed: {e}")

# ==========================================
# 5. Apply through-holes
# ==========================================

for feature in hole_features:

    diameter = feature["diameter"]

    position = feature.get(
        "position",
        {"x": 0, "y": 0}
    )

    x = position.get("x", 0)
    y = position.get("y", 0)

    print(
        f"Creating hole: diameter {diameter} mm "
        f"at ({x}, {y})"
    )

    hole = (
        cq.Workplane("XY")
        .center(x, y)
        .cylinder(height + 2, diameter / 2)
        .translate((0, 0, -1))
    )

    model = model.cut(hole)

# ==========================================
# 6. Apply through-slots
# ==========================================

for feature in slot_features:

    slot_length = feature["length"]
    slot_width = feature["width"]

    position = feature.get(
        "position",
        {"x": 0, "y": 0}
    )

    x = position.get("x", 0)
    y = position.get("y", 0)

    orientation = feature.get("orientation", "horizontal").lower()

    if slot_length <= 0 or slot_width <= 0:
        raise ValueError("Slot length and width must be positive.")

    if slot_width > slot_length:
        raise ValueError("Slot width cannot exceed slot length.")

    if orientation == "horizontal":
        angle = 0

    elif orientation == "vertical":
        angle = 90

    else:
        raise ValueError(
            f"Unsupported slot orientation: {orientation}. "
            "Use horizontal or vertical."
        )

    print(
        f"Creating through-slot: "
        f"{slot_length} x {slot_width} mm, "
        f"{orientation}, at ({x}, {y})"
    )

    # Create a 2D rounded-end slot and extrude it
    # completely through the base shape.

    slot_cutter = (
        cq.Workplane("XY")
        .center(x, y)
        .slot2D(slot_length, slot_width, angle=angle)
        .extrude(height + 2)
        .translate((0, 0, bottom_z - 1))
    )

    model = model.cut(slot_cutter)

# ==========================================
# 7. Export STEP
# ==========================================

os.makedirs("outputs", exist_ok=True)

cq.exporters.export(
    model,
    "outputs/generated_model.step"
)

# ==========================================
# 8. Display information
# ==========================================

print()
print("==========================================")
print("CAD MODEL GENERATED SUCCESSFULLY!")
print("==========================================")
print(f"Shape: {shape}")

if shape == "box":
    print(f"Dimensions: {length} x {width} x {height} mm")

elif shape == "cylinder":
    print(f"Radius: {radius} mm")
    print(f"Height: {height} mm")

elif shape == "cone":
    print(f"Base Radius: {radius} mm")
    print(f"Height: {height} mm")

if features:

    print()
    print("Features:")

    for feature in features:

        feature_type = feature["type"]

        if feature_type == "through_hole":

            position = feature.get(
                "position",
                {"x": 0, "y": 0}
            )

            print(
                f"- Through-hole: diameter "
                f"{feature['diameter']} mm at "
                f"({position.get('x', 0)}, "
                f"{position.get('y', 0)}) mm"
            )

        elif feature_type == "fillet":
            print(f"- Fillet: {feature['radius']} mm")

        elif feature_type == "chamfer":
            print(f"- Chamfer: {feature['distance']} mm")

        elif feature_type == "slot":

            position = feature.get(
                "position",
                {"x": 0, "y": 0}
            )

            print(
                f"- Through-slot: "
                f"{feature['length']} x {feature['width']} mm, "
                f"{feature.get('orientation', 'horizontal')}, "
                f"at ({position.get('x', 0)}, "
                f"{position.get('y', 0)}) mm"
            )

else:
    print("Features: None")

print()
print("Output: outputs/generated_model.step")
print("==========================================")

# Preserve the existing Windows shutdown workaround.
sys.stdout.flush()
os._exit(0)
