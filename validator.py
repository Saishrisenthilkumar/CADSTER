
import json
import math
import sys

print("==========================================")
print("        CAD DESIGN VALIDATOR")
print("==========================================")

# ============================================================
# 1. LOAD DESIGN
# ============================================================

try:
    with open("design.json", "r") as file:
        design = json.load(file)

except FileNotFoundError:
    print("[ERROR] design.json not found.")
    sys.exit(1)

except json.JSONDecodeError as e:
    print("[ERROR] design.json contains invalid JSON.")
    print(e)
    sys.exit(1)

if not isinstance(design, dict):
    print("[ERROR] Design must be a JSON object.")
    sys.exit(1)

errors = []
warnings = []

# ============================================================
# 2. BASIC STRUCTURE VALIDATION
# ============================================================

print()
print("Running engineering validation...")
print()

if "shape" not in design:
    errors.append("Missing required field: shape")

shape = design.get("shape")

supported_shapes = ["box", "cylinder", "cone"]

if shape not in supported_shapes:
    errors.append(f"Unsupported shape: {shape}")

# ============================================================
# 3. DIMENSION VALIDATION
# ============================================================

def check_positive_number(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        errors.append(f"{name} must be a finite number.")
        return False

    if value <= 0:
        errors.append(f"{name} must be greater than zero.")
        return False

    return True


if shape == "box":

    for dimension in ["length", "width", "height"]:

        if dimension not in design:
            errors.append(f"Box is missing dimension: {dimension}")
        else:
            check_positive_number(design[dimension], dimension)


elif shape in ["cylinder", "cone"]:

    if "radius" not in design:
        errors.append(f"{shape.capitalize()} is missing radius.")
    else:
        check_positive_number(design["radius"], "radius")

    if "height" not in design:
        errors.append(f"{shape.capitalize()} is missing height.")
    else:
        check_positive_number(design["height"], "height")


# ============================================================
# 4. GET FEATURES
# ============================================================

features = design.get("features", [])

if not isinstance(features, list):
    errors.append("features must be a list.")
    features = []

# ============================================================
# 5. FEATURE VALIDATION
# ============================================================

for index, feature in enumerate(features):

    feature_number = index + 1

    if not isinstance(feature, dict):
        errors.append(
            f"Feature {feature_number} is not a valid object."
        )
        continue

    feature_type = feature.get("type")

    # --------------------------------------------------------
    # THROUGH-HOLE
    # --------------------------------------------------------

    if feature_type == "through_hole":

        diameter = feature.get("diameter")

        if not check_positive_number(
            diameter,
            f"Through-hole {feature_number} diameter"
        ):
            continue

        position = feature.get(
            "position",
            {"x": 0, "y": 0}
        )

        if not isinstance(position, dict):
            errors.append(
                f"Through-hole {feature_number} has invalid position."
            )
            continue

        x = position.get("x", 0)
        y = position.get("y", 0)

        position_valid = (
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and math.isfinite(x)
            and isinstance(y, (int, float))
            and not isinstance(y, bool)
            and math.isfinite(y)
        )

        if not position_valid:
            errors.append(
                f"Through-hole {feature_number} positions "
                "must be finite numbers."
            )
            continue

        # Check hole fit for a box.
        if shape == "box":

            length = design.get("length", 0)
            width = design.get("width", 0)

            if (
                isinstance(length, (int, float))
                and not isinstance(length, bool)
                and math.isfinite(length)
                and length > 0
                and abs(x) + diameter / 2 > length / 2
            ):
                errors.append(
                    f"Through-hole {feature_number} extends "
                    "outside the box length."
                )

            if (
                isinstance(width, (int, float))
                and not isinstance(width, bool)
                and math.isfinite(width)
                and width > 0
                and abs(y) + diameter / 2 > width / 2
            ):
                errors.append(
                    f"Through-hole {feature_number} extends "
                    "outside the box width."
                )

        # Check hole fit for a cylinder.
        elif shape == "cylinder":

            radius = design.get("radius", 0)

            if (
                isinstance(radius, (int, float))
                and not isinstance(radius, bool)
                and math.isfinite(radius)
                and radius > 0
            ):
                distance = math.sqrt(x ** 2 + y ** 2)

                if distance + diameter / 2 > radius:
                    errors.append(
                        f"Through-hole {feature_number} does not "
                        "fit inside the cylinder."
                    )

    # --------------------------------------------------------
    # THROUGH-SLOT
    # --------------------------------------------------------

    elif feature_type == "slot":

        slot_length = feature.get("length")
        slot_width = feature.get("width")

        length_valid = check_positive_number(
            slot_length,
            f"Slot {feature_number} length"
        )

        width_valid = check_positive_number(
            slot_width,
            f"Slot {feature_number} width"
        )

        if (
            length_valid
            and width_valid
            and slot_width > slot_length
        ):
            errors.append(
                f"Slot {feature_number} width cannot exceed length."
            )

        orientation = feature.get("orientation", "horizontal")

        if not isinstance(orientation, str):
            errors.append(
                f"Slot {feature_number} orientation must be text."
            )
            orientation = ""

        orientation = orientation.lower()

        if orientation not in ["horizontal", "vertical"]:
            errors.append(
                f"Slot {feature_number} orientation must be "
                "horizontal or vertical."
            )

        position = feature.get(
            "position",
            {"x": 0, "y": 0}
        )

        if not isinstance(position, dict):
            errors.append(
                f"Slot {feature_number} has invalid position."
            )
            continue

        x = position.get("x", 0)
        y = position.get("y", 0)

        position_valid = (
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and math.isfinite(x)
            and isinstance(y, (int, float))
            and not isinstance(y, bool)
            and math.isfinite(y)
        )

        if not position_valid:
            errors.append(
                f"Slot {feature_number} positions must be "
                "finite numbers."
            )
            continue

        if not (length_valid and width_valid):
            continue

        if slot_width > slot_length:
            continue

        if orientation not in ["horizontal", "vertical"]:
            continue

        # A rounded-end slot has a straight centreline
        # of length (slot_length - slot_width).
        end_offset = (slot_length - slot_width) / 2

        if orientation == "horizontal":
            half_x = slot_length / 2
            half_y = slot_width / 2
        else:
            half_x = slot_width / 2
            half_y = slot_length / 2

        # Check slot fit inside a rectangular box.
        if shape == "box":

            box_length = design.get("length", 0)
            box_width = design.get("width", 0)

            dimensions_valid = (
                isinstance(box_length, (int, float))
                and not isinstance(box_length, bool)
                and math.isfinite(box_length)
                and box_length > 0
                and isinstance(box_width, (int, float))
                and not isinstance(box_width, bool)
                and math.isfinite(box_width)
                and box_width > 0
            )

            if dimensions_valid and (
                abs(x) + half_x > box_length / 2
                or abs(y) + half_y > box_width / 2
            ):
                errors.append(
                    f"Slot {feature_number} extends outside "
                    "the box footprint."
                )

        # Conservative fit check for a cylindrical footprint.
        elif shape == "cylinder":

            radius = design.get("radius", 0)

            radius_valid = (
                isinstance(radius, (int, float))
                and not isinstance(radius, bool)
                and math.isfinite(radius)
                and radius > 0
            )

            if radius_valid:

                if orientation == "horizontal":
                    farthest_x = abs(x) + end_offset
                    farthest_y = abs(y)
                else:
                    farthest_x = abs(x)
                    farthest_y = abs(y) + end_offset

                farthest_distance = (
                    math.sqrt(farthest_x ** 2 + farthest_y ** 2)
                    + slot_width / 2
                )

                if farthest_distance > radius:
                    errors.append(
                        f"Slot {feature_number} may extend outside "
                        "the cylinder footprint."
                    )

        elif shape == "cone":

            errors.append(
                f"Slot {feature_number}: through-slots on cones "
                "are not supported in this version."
            )

    # --------------------------------------------------------
    # FILLET
    # --------------------------------------------------------

    elif feature_type == "fillet":

        radius = feature.get("radius")

        if check_positive_number(
            radius,
            f"Fillet {feature_number} radius"
        ):

            if shape == "box":

                dimensions = [
                    design.get("length"),
                    design.get("width"),
                    design.get("height")
                ]

                if all(
                    isinstance(d, (int, float))
                    and not isinstance(d, bool)
                    and math.isfinite(d)
                    and d > 0
                    for d in dimensions
                ):

                    smallest_dimension = min(dimensions)

                    if radius >= smallest_dimension / 2:
                        errors.append(
                            f"Fillet radius {radius} mm is too large "
                            "for the box geometry."
                        )

            elif shape == "cylinder":

                cylinder_radius = design.get("radius", 0)

                if (
                    isinstance(cylinder_radius, (int, float))
                    and not isinstance(cylinder_radius, bool)
                    and math.isfinite(cylinder_radius)
                    and cylinder_radius > 0
                    and radius >= cylinder_radius
                ):
                    errors.append(
                        f"Fillet radius {radius} mm is too large "
                        "for the cylinder."
                    )

    # --------------------------------------------------------
    # CHAMFER
    # --------------------------------------------------------

    elif feature_type == "chamfer":

        distance = feature.get("distance")

        if check_positive_number(
            distance,
            f"Chamfer {feature_number} distance"
        ):

            if shape == "box":

                dimensions = [
                    design.get("length"),
                    design.get("width"),
                    design.get("height")
                ]

                if all(
                    isinstance(d, (int, float))
                    and not isinstance(d, bool)
                    and math.isfinite(d)
                    and d > 0
                    for d in dimensions
                ):

                    smallest_dimension = min(dimensions)

                    if distance >= smallest_dimension / 2:
                        errors.append(
                            f"Chamfer distance {distance} mm "
                            "is too large for the box."
                        )

    # --------------------------------------------------------
    # UNKNOWN FEATURE
    # --------------------------------------------------------

    else:

        errors.append(
            f"Unsupported feature type: {feature_type}"
        )


# ============================================================
# 6. ADDITIONAL CYLINDER HOLE CHECK
# ============================================================

for index, feature in enumerate(features):

    if (
        isinstance(feature, dict)
        and feature.get("type") == "through_hole"
    ):

        diameter = feature.get("diameter")
        radius = design.get("radius", 0)

        if (
            shape == "cylinder"
            and isinstance(diameter, (int, float))
            and not isinstance(diameter, bool)
            and math.isfinite(diameter)
            and isinstance(radius, (int, float))
            and not isinstance(radius, bool)
            and math.isfinite(radius)
            and radius > 0
            and diameter >= 2 * radius
        ):
            errors.append(
                f"Through-hole {index + 1} diameter is too large "
                "for the cylinder."
            )


# ============================================================
# 7. DISPLAY VALIDATION RESULT
# ============================================================

print()
print("==========================================")
print("        VALIDATION RESULT")
print("==========================================")

if errors:

    print()
    print("[FAILED] DESIGN VALIDATION FAILED")
    print("------------------------------------------")
    print("Validation errors:")

    for error in errors:
        print(f"- {error}")

    print()
    print("CAD GENERATION STOPPED")
    print("Please correct the design and try again.")

    sys.exit(1)


# ============================================================
# 8. SUCCESS
# ============================================================

print()
print("[OK] DESIGN VALIDATION PASSED")
print("------------------------------------------")
print("No validation errors found.")
print("Design is ready for the CAD generator.")


# ============================================================
# 9. DISPLAY DESIGN SUMMARY
# ============================================================

print()
print("DESIGN SUMMARY")
print("------------------------------------------")

print(f"Shape: {shape}")

if shape == "box":
    print(
        f"Dimensions: {design.get('length')} x "
        f"{design.get('width')} x "
        f"{design.get('height')} mm"
    )

elif shape == "cylinder":
    print(f"Radius: {design.get('radius')} mm")
    print(f"Height: {design.get('height')} mm")

elif shape == "cone":
    print(f"Base Radius: {design.get('radius')} mm")
    print(f"Height: {design.get('height')} mm")

print(f"Features: {len(features)}")
print("------------------------------------------")

for feature in features:

    if not isinstance(feature, dict):
        continue

    feature_type = feature.get("type")

    if feature_type == "through_hole":

        position = feature.get(
            "position",
            {"x": 0, "y": 0}
        )

        print(
            f"- Through-hole: diameter {feature.get('diameter')} mm "
            f"at ({position.get('x', 0)}, {position.get('y', 0)}) mm"
        )

    elif feature_type == "fillet":
        print(f"- Fillet: {feature.get('radius')} mm")

    elif feature_type == "chamfer":
        print(f"- Chamfer: {feature.get('distance')} mm")

    elif feature_type == "slot":

        position = feature.get(
            "position",
            {"x": 0, "y": 0}
        )

        print(
            f"- Through-slot: {feature.get('length')} x "
            f"{feature.get('width')} mm, "
            f"{feature.get('orientation', 'horizontal')}, "
            f"at ({position.get('x', 0)}, {position.get('y', 0)}) mm"
        )

print()
print("==========================================")
print("       VALIDATION COMPLETE")
print("==========================================")
