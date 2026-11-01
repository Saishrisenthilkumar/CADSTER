
from google import genai
import os
import json
import subprocess
import sys
import math

# ============================================================
# AI-ASSISTED CAD DESIGN GENERATOR
# ============================================================

print("==========================================")
print("     AI-ASSISTED CAD DESIGN GENERATOR")
print("==========================================")

# ============================================================
# 1. CREATE GEMINI CLIENT
# ============================================================

try:
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"]
    )

except KeyError:
    print()
    print("[ERROR] GEMINI_API_KEY environment variable not found.")
    print("Please set your Gemini API key first.")
    sys.exit(1)

# ============================================================
# 2. GET USER REQUEST
# ============================================================

prompt = input(
    "\nDescribe the CAD model you want:\n"
)

if not prompt.strip():
    print("[ERROR] No design description entered.")
    sys.exit(1)

print()
print("Sending request to Gemini...")

# ============================================================
# 3. ENGINEERING CAD PROMPT
# ============================================================

instruction = f"""
You are an engineering CAD design assistant.

Convert the user's natural-language CAD request into a
structured JSON object for a CadQuery CAD generator.

USER REQUEST:
{prompt}

Return ONLY valid JSON.
Do not use Markdown code fences.
Do not add explanations.

============================================================
SUPPORTED BASE SHAPES
============================================================

BOX:
{{
    "shape": "box",
    "length": 100,
    "width": 60,
    "height": 10,
    "features": []
}}

CYLINDER:
{{
    "shape": "cylinder",
    "radius": 30,
    "height": 60,
    "features": []
}}

CONE:
{{
    "shape": "cone",
    "radius": 30,
    "height": 60,
    "features": []
}}

The numbers above are examples, not default dimensions.
Use the dimensions requested by the user.

============================================================
SUPPORTED FEATURES
============================================================

1. THROUGH-HOLE

{{
    "type": "through_hole",
    "diameter": 10,
    "position": {{
        "x": 0,
        "y": 0
    }}
}}

2. FILLET

{{
    "type": "fillet",
    "radius": 2
}}

3. CHAMFER

{{
    "type": "chamfer",
    "distance": 2
}}

4. THROUGH-SLOT

{{
    "type": "slot",
    "length": 30,
    "width": 8,
    "position": {{
        "x": -25,
        "y": 0
    }},
    "orientation": "horizontal"
}}

============================================================
SLOT RULES
============================================================

1. Slots are through-slots cut completely through the
   model in the vertical Z direction.

2. Slot length is the overall end-to-end length, including
   the rounded ends.

3. Slot width is the diameter of the rounded ends.

4. Slot width must not exceed slot length.

5. Slot length and width must be positive.

6. Orientation must be either:
   "horizontal"
   "vertical"

7. Horizontal slots extend along the X direction.
   Vertical slots extend along the Y direction.

8. The position x and y specify the slot centre relative
   to the centre of the base footprint.

9. Multiple slots are allowed. Each slot must be a
   separate feature object.

10. Slots are supported on boxes and cylinders only.
    Do not generate slot features for cones.

11. Keep every slot fully inside the base footprint.

12. For a box:
    x ranges from -length/2 to +length/2.
    y ranges from -width/2 to +width/2.
    Include the entire slot outline when checking fit.

13. For a cylinder, keep the entire rounded slot outline
    inside the circular footprint.

14. If the user specifies symmetric slots, calculate
    their positions correctly.

15. Do not invent extra slots or dimensions that the user
    did not request.

============================================================
ENGINEERING RULES
============================================================

1. All dimensions must be in millimetres.

2. Preserve explicitly specified dimensions.

3. Use numerical values only for dimensions.
   Do not include units inside numerical values.

4. Every hole and every slot must be a separate object.

5. Multiple through-holes are allowed.

6. Through-hole positions represent their centres.

7. For a centred box, the origin is x = 0, y = 0.

8. Do not place holes or slots outside the base geometry.

9. Hole diameter must be positive and smaller than the
   surrounding geometry.

10. Fillet radius must be positive.

11. Chamfer distance must be positive.

12. Fillets and chamfers apply to the main outer geometry
    in the current CAD generator.

13. Do not invent unnecessary features.

14. Use an empty features list if no features are requested.

15. Keep the features in this order:
    - Fillets and chamfers
    - Through-holes
    - Through-slots

16. If multiple features are requested, include all of them.

17. Output one valid JSON object matching the schemas above.

18. Never include comments or explanations in the JSON.

============================================================
USER REQUEST
============================================================

{prompt}
"""

# ============================================================
# 4. SEND REQUEST TO GEMINI
# ============================================================

try:
    interaction = client.interactions.create(
        model="gemini-3.1-flash-lite",
        input=instruction
    )

except Exception as e:
    print()
    print("[ERROR] Gemini request failed.")
    print()
    print(str(e))
    print()
    print("If this is a quota error, wait for the")
    print("Gemini API quota to reset and try again.")
    sys.exit(1)

print()
print("Response received!")

# ============================================================
# 5. GET GEMINI RESPONSE
# ============================================================

try:
    response_text = interaction.output_text.strip()

except Exception:
    print("[ERROR] Gemini returned no usable response.")
    sys.exit(1)

# Remove accidental Markdown code fences.

if response_text.startswith("```"):
    lines = response_text.splitlines()

    if lines and lines[0].startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    response_text = "\n".join(lines).strip()

# ============================================================
# 6. CONVERT JSON
# ============================================================

try:
    design = json.loads(response_text)

except json.JSONDecodeError:
    print()
    print("[ERROR] Gemini did not return valid JSON.")
    print()
    print("Gemini response:")
    print(response_text)
    sys.exit(1)

if not isinstance(design, dict):
    print("[ERROR] Gemini response must be a JSON object.")
    sys.exit(1)

# ============================================================
# 7. BASIC RESPONSE CHECK
# ============================================================

if design.get("shape") not in ["box", "cylinder", "cone"]:
    print("[ERROR] Gemini returned an unsupported base shape.")
    print("Supported shapes: box, cylinder, cone.")
    sys.exit(1)

features = design.get("features", [])

if not isinstance(features, list):
    print("[ERROR] The features field must be a list.")
    sys.exit(1)

# Avoid saving malformed numeric JSON values such as NaN or Infinity.
def reject_nonfinite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite number found in design JSON.")

    if isinstance(value, dict):
        for item in value.values():
            reject_nonfinite(item)

    elif isinstance(value, list):
        for item in value:
            reject_nonfinite(item)


try:
    reject_nonfinite(design)

except ValueError as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

# ============================================================
# 8. SAVE DESIGN JSON
# ============================================================

try:
    with open(
        "design.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            design,
            file,
            indent=4,
            allow_nan=False
        )

except Exception as e:
    print()
    print("[ERROR] Could not save design.json")
    print(str(e))
    sys.exit(1)

print()
print("==========================================")
print("       CAD DESIGN JSON GENERATED")
print("==========================================")
print(json.dumps(design, indent=4))
print()
print("Saved successfully as: design.json")

# ============================================================
# 9. RUN ENGINEERING VALIDATOR
# ============================================================

print()
print("==========================================")
print("       ENGINEERING VALIDATION")
print("==========================================")
print()
print("Running engineering validation...")

try:
    validator = subprocess.run(
        [
            sys.executable,
            "validator.py"
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

except Exception as e:
    print("[ERROR] Could not start validator.py")
    print(str(e))
    sys.exit(1)

if validator.stdout:
    print(validator.stdout)

if validator.returncode != 0:
    print()
    print("==========================================")
    print("       CAD GENERATION STOPPED")
    print("==========================================")
    print()
    print("The design failed engineering validation.")

    if validator.stderr:
        print()
        print("Validator error:")
        print(validator.stderr)

    print()
    print("Correct the design request and try again.")
    sys.exit(1)

# ============================================================
# 10. RUN EAGLE GEOMETRIC CLEARANCE ANALYSIS
# ============================================================

print()
print("==========================================")
print("       EAGLE CLEARANCE ANALYSIS")
print("==========================================")

# The current EAGLE version supports box-shaped plates only.
# Preserve the existing cylinder/cone workflow without claiming
# that those shapes have been clearance-checked.
eagle_applicable = (
    design.get("shape") == "box"
    and any(
        isinstance(feature, dict)
        and feature.get("type") in ["through_hole", "slot"]
        for feature in features
    )
)

if eagle_applicable:
    try:
        minimum_clearance = float(
            input("\nEnter required minimum clearance (mm): ")
        )
        if not math.isfinite(minimum_clearance) or minimum_clearance < 0:
            raise ValueError("Clearance must be a finite non-negative number.")
    except ValueError as e:
        print("[ERROR]", e)
        sys.exit(1)

    print()
    print("Running EAGLE geometric clearance analysis...")

    try:
        eagle = subprocess.run(
            [sys.executable, "clearance_checker.py"],
            input=f"{minimum_clearance}\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print("[ERROR] Could not start clearance_checker.py")
        print(str(e))
        sys.exit(1)

    if eagle.stdout:
        print(eagle.stdout)

    if eagle.stderr:
        print("EAGLE error output:")
        print(eagle.stderr)

    # The current standalone checker prints this exact failure
    # marker when it detects interference/insufficient clearance.
    eagle_failed = (
        eagle.returncode != 0
        or "[FAIL] DESIGN HAS CLEARANCE VIOLATIONS." in (eagle.stdout or "")
    )

    if eagle_failed:
        print()
        print("==========================================")
        print("       CAD GENERATION BLOCKED")
        print("==========================================")
        print("EAGLE detected clearance violations.")
        print("Resolve the geometry and submit the design again.")
        sys.exit(2)

    if "[PASS] ALL CHECKED CLEARANCES SATISFY THE REQUIREMENT." not in (eagle.stdout or ""):
        print("[ERROR] EAGLE did not produce a confirmed PASS result.")
        print("CAD generation has been stopped for safety.")
        sys.exit(2)

    print("[EAGLE] Clearance analysis passed.")

else:
    if design.get("shape") != "box":
        print("[EAGLE] Skipped: current clearance engine supports box plates only.")
    else:
        print("[EAGLE] Skipped: no holes or slots require clearance analysis.")

# ============================================================
# 11. VALIDATION AND CLEARANCE PASSED
# ============================================================

print()
print("==========================================")
print("       ENGINEERING CHECKS PASSED")
print("==========================================")
print()
print("Design validator: PASS")
if eagle_applicable:
    print("EAGLE clearance analysis: PASS")
else:
    print("EAGLE clearance analysis: NOT APPLICABLE")
print("Sending design to CAD generator...")

# ============================================================
# (This section is retained as the CAD hand-off.)
# ============================================================

print()
print("==========================================")
print("       VALIDATION PASSED")
print("==========================================")
print()
print("Design approved.")
print("Sending design to CAD generator...")

# ============================================================
# 12. RUN CAD GENERATOR
# ============================================================

try:
    cad = subprocess.run(
        [
            sys.executable,
            "cad_generator.py"
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

except Exception as e:
    print("[ERROR] Could not start cad_generator.py")
    print(str(e))
    sys.exit(1)

if cad.stdout:
    print(cad.stdout)

# ============================================================
# 13. CHECK CAD GENERATION
# ============================================================

output_file = os.path.join(
    "outputs",
    "generated_model.step"
)

if cad.returncode != 0:
    print()
    print("==========================================")
    print("       CAD GENERATION FAILED")
    print("==========================================")

    if cad.stderr:
        print()
        print("CAD generator error:")
        print(cad.stderr)

    sys.exit(1)

# ============================================================
# 14. VERIFY STEP FILE
# ============================================================

if not os.path.exists(output_file):
    print()
    print("==========================================")
    print("       CAD GENERATION FAILED")
    print("==========================================")
    print()
    print("The STEP file could not be found.")
    print("Expected:", output_file)
    sys.exit(1)

if os.path.getsize(output_file) == 0:
    print("[ERROR] STEP file exists but is empty.")
    sys.exit(1)

# ============================================================
# 15. FINAL SUCCESS
# ============================================================

print()
print("==========================================")
print("      AI CAD GENERATION COMPLETE")
print("==========================================")
print()
print("Pipeline:")
print("Natural Language")
print("       -> Gemini AI")
print("       -> design.json")
print("       -> Engineering Validator")
print("       -> EAGLE Clearance Engine (when applicable)")
print("       -> CadQuery")
print("       -> STEP")
print()
print("STEP file:")
print(output_file)
print()
print("==========================================")
print("             SUCCESS")
print("==========================================")
