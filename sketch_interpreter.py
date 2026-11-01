
import os
import json
import math
import sys
from pathlib import Path

from google import genai
from PIL import Image

MODEL = "gemini-3.1-flash-lite"
OUTPUT_FILE = "sketch_design.json"


def extract_json(text):
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return json.loads(text)


def validate_design(design):
    errors = []

    if not isinstance(design, dict):
        return ["Design must be a JSON object."]

    if design.get("shape") != "box":
        errors.append("Only rectangular box-shaped components are supported.")

    for dimension in ["length", "width", "height"]:
        value = design.get(dimension)

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            errors.append(f"Invalid or missing dimension: {dimension}")

    features = design.get("features")

    if not isinstance(features, list):
        errors.append("Features must be a list.")
        return errors

    for i, feature in enumerate(features):
        number = i + 1

        if not isinstance(feature, dict):
            errors.append(f"Feature {number} is not an object.")
            continue

        feature_type = feature.get("type")

        if feature_type == "through_hole":
            values = [feature.get("diameter")]

        elif feature_type == "slot":
            values = [feature.get("length"), feature.get("width")]

            if feature.get("orientation") not in ["horizontal", "vertical"]:
                errors.append(f"Feature {number}: invalid slot orientation.")

        elif feature_type == "fillet":
            values = [feature.get("radius")]

        elif feature_type == "chamfer":
            values = [feature.get("distance")]

        else:
            errors.append(
                f"Feature {number}: unsupported feature type {feature_type}."
            )
            continue

        for value in values:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                errors.append(f"Feature {number} has an invalid dimension.")

        if feature_type in ["through_hole", "slot"]:
            position = feature.get("position")

            if not isinstance(position, dict):
                errors.append(f"Feature {number} has no valid position.")
            else:
                for axis in ["x", "y"]:
                    value = position.get(axis)

                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        errors.append(
                            f"Feature {number}: invalid {axis} position."
                        )

        if feature_type == "slot":
            length = feature.get("length")
            width = feature.get("width")

            if (
                isinstance(length, (int, float))
                and isinstance(width, (int, float))
                and width > length
            ):
                errors.append(f"Slot {number}: width cannot exceed length.")

    return errors


def main():
    print("=" * 55)
    print("             ATHENA - SKETCH TO CAD")
    print("=" * 55)

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("[ERROR] GEMINI_API_KEY environment variable not found.")
        return

    image_path = input("\nEnter the sketch image path: ").strip().strip('"')

    if not image_path:
        print("[ERROR] No image path supplied.")
        return

    image_path = Path(image_path)

    if not image_path.is_file():
        print("[ERROR] Image file not found.")
        return

    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as error:
        print("[ERROR] Could not open image:", error)
        return

    instruction = """
You are ATHENA, an AI mechanical engineering sketch interpreter.

Analyse the uploaded engineering sketch and convert it into a
structured CAD design.

FIRST VERSION SCOPE:
- Rectangular box-shaped plates or blocks.
- Through-holes.
- Horizontal and vertical through-slots.
- Basic fillets and chamfers.

Return ONLY one valid JSON object using this exact wrapper:

{
  "status": "ready",
  "missing_information": [],
  "design": {
    "shape": "box",
    "length": 100,
    "width": 60,
    "height": 10,
    "features": []
  }
}

If essential dimensions are missing, unreadable, ambiguous,
or cannot be established reliably, return:

{
  "status": "needs_clarification",
  "missing_information": [
    "Specify the plate thickness."
  ],
  "design": null
}
USER-PROVIDED INFORMATION:

The user has explicitly confirmed that the plate thickness is
10 mm. Set design.height = 10 even though thickness is not
shown in the uploaded image. This is a confirmed input, not
an inferred dimension.
ENGINEERING INTERPRETATION RULES:

1. All dimensions must be in millimetres.
2. Extract dimensions from the sketch. Do not invent dimensions.
3. Distinguish overall dimensions from feature dimensions.
4. For a rectangular plate, use:
   length = X dimension
   width = Y dimension
   height = thickness (Z dimension).
5. Use the centre of the rectangular plate as the origin.
6. Hole and slot positions must be relative to this centre.
7. Convert dimensions from edge references to centre coordinates
   only when the drawing provides enough information.
8. A circular feature on a plate may represent a through-hole.
9. Slots must have length, width, position and orientation.
10. Include every clearly identifiable supported feature.
11. Do not assume hidden features without evidence.
12. If a dimension cannot be read confidently, ask for clarification.
13. Do not infer exact dimensions from image pixel proportions.
14. If the drawing is not suitable for this first version,
    return needs_clarification and explain why.
15. Never include Markdown fences, comments or explanations
    outside the JSON object.

SUPPORTED FEATURE FORMATS:

Through-hole:
{
  "type": "through_hole",
  "diameter": 10,
  "position": {"x": 0, "y": 0}
}

Slot:
{
  "type": "slot",
  "length": 30,
  "width": 8,
  "position": {"x": 0, "y": 0},
  "orientation": "horizontal"
}

Fillet:
{
  "type": "fillet",
  "radius": 2
}

Chamfer:
{
  "type": "chamfer",
  "distance": 2
}

Return valid JSON only.
"""

    try:
        print("\n[1/4] Sending sketch to ATHENA Vision Engine...")

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=MODEL,
            contents=[instruction, image]
        )

        if not response.text:
            print("[ERROR] Gemini returned an empty response.")
            return

        result = extract_json(response.text)

    except Exception as error:
        print("\n[ERROR] Sketch interpretation failed.")
        print(error)
        return

    print("[2/4] Sketch interpretation received.")

    if result.get("status") != "ready":
        print("\n[CLARIFICATION REQUIRED]")
        for item in result.get("missing_information", []):
            print("-", item)

        print("\nNo CAD file was generated.")
        return

    design = result.get("design")

    print("[3/4] Checking extracted design structure...")

    errors = validate_design(design)

    if errors:
        print("\n[VALIDATION FAILED]")

        for error in errors:
            print("-", error)

        print("\nNo design file was saved.")
        return

    output_path = Path(OUTPUT_FILE)

    try:
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                design,
                file,
                indent=4,
                allow_nan=False
            )

    except Exception as error:
        print("[ERROR] Could not save design:", error)
        return

    print("[4/4] Design interpretation completed.")

    print("\n" + "=" * 55)
    print("          ATHENA SKETCH INTERPRETATION")
    print("=" * 55)

    print(json.dumps(design, indent=4))

    print("\n[PASS] Basic structure validation passed.")
    print("Saved as:", output_path.resolve())

    print("\nNOTE:")
    print("This is not yet the final CAD validation.")
    print("The existing engineering validator and EAGLE")
    print("clearance checker must still be run before CAD export.")


if __name__ == "__main__":
    main()
