
import streamlit as st
import subprocess
import sys
import os
import json
import shutil
import tempfile
from pathlib import Path


# ============================================================
# CADSTER - AI-POWERED CAD GENERATOR
# ============================================================

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="CADSTER | AI CAD Generator",
    page_icon="⚙️",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "design": None,
    "step_file": None,
    "logs": {},
    "mode": "Text Prompt",
    "active_mode": None,
    "review_json": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# Clear old results when switching input modes
current_mode = st.session_state.mode

if st.session_state.active_mode != current_mode:
    st.session_state.design = None
    st.session_state.step_file = None
    st.session_state.logs = {}
    st.session_state.review_json = ""
    st.session_state.active_mode = current_mode


# ============================================================
# STYLING
# ============================================================

st.markdown("""
<style>
.stApp {
    background: #10141c;
    color: #e8edf5;
}

section[data-testid="stSidebar"] {
    background: #171e29;
}

h1, h2, h3 {
    color: #edf3fb;
}

.subtitle {
    color: #8b9bb1;
    letter-spacing: 3px;
    font-size: 12px;
}

div.stButton > button {
    background: #00b8a9;
    color: #07151a;
    border: none;
    border-radius: 8px;
    font-weight: 700;
    min-height: 42px;
}

div.stButton > button:hover {
    background: #36d6c7;
    color: #07151a;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.title("⚙️ CADSTER")

st.markdown(
    '<p class="subtitle">AI-POWERED ENGINEERING CAD GENERATION</p>',
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("CADSTER")
    st.caption("Design Workspace")
    st.divider()

    st.markdown("### WORKFLOW")

    workflow = [
        "01  Design Input",
        "02  AI Interpretation",
        "03  Design Review",
        "04  Engineering Validation",
        "05  CAD Generation",
        "06  STEP Export"
    ]

    for item in workflow:
        st.write("◉  " + item)

    st.divider()

    st.markdown("### SYSTEM STATUS")

    if os.getenv("GEMINI_API_KEY"):
        st.success("Gemini AI configured")
    else:
        st.error("Gemini API key missing")

    backend_files = [
        "validator.py",
        "clearance_checker.py",
        "cad_generator.py"
    ]

    for filename in backend_files:
        if (ROOT / filename).exists():
            st.success(filename + " available")
        else:
            st.error(filename + " missing")


# ============================================================
# INPUT MODE
# ============================================================

st.header("01 | Create Your CAD Model")

mode = st.radio(
    "Choose your input method",
    ["Text Prompt", "Drawing Upload"],
    horizontal=True,
    key="mode"
)


# ============================================================
# COMMON FUNCTIONS
# ============================================================

def copy_backend(work):

    files = [
        "validator.py",
        "clearance_checker.py",
        "cad_generator.py"
    ]

    for name in files:

        source = ROOT / name

        if not source.exists():
            raise FileNotFoundError(f"{name} not found")

        shutil.copy2(source, work / name)

    (work / "outputs").mkdir(exist_ok=True)


def run_command(work, script, input_text=None, timeout=180):

    result = subprocess.run(
        [sys.executable, script],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=work,
        timeout=timeout
    )

    output = result.stdout or ""

    if result.stderr:
        output += "\n\n--- STDERR ---\n" + result.stderr

    return result, output


def run_drawing_pipeline(work, clearance):

    logs = {}

    # --------------------------------------------------------
    # 1. DESIGN VALIDATION
    # --------------------------------------------------------

    result, output = run_command(
        work,
        "validator.py",
        timeout=60
    )

    logs["Design Validation"] = output

    if (
        result.returncode != 0
        or "DESIGN VALIDATION PASSED" not in output
    ):
        raise RuntimeError(
            "Design validation failed. Check the execution logs."
        )

    # --------------------------------------------------------
    # 2. EAGLE CLEARANCE ANALYSIS
    # --------------------------------------------------------

    design = json.loads(
        (work / "design.json").read_text(encoding="utf-8")
    )

    eagle_applicable = (
        design.get("shape") == "box"
        and any(
            isinstance(feature, dict)
            and feature.get("type") in ["through_hole", "slot"]
            for feature in design.get("features", [])
        )
    )

    if eagle_applicable:

        result, output = run_command(
            work,
            "clearance_checker.py",
            input_text=f"{clearance}\n",
            timeout=60
        )

        logs["EAGLE Clearance Analysis"] = output

        if (
            result.returncode != 0
            or "[PASS] ALL CHECKED CLEARANCES SATISFY THE REQUIREMENT."
            not in output
        ):
            raise RuntimeError(
                "EAGLE clearance validation failed. "
                "Review the clearance report."
            )

    else:

        logs["EAGLE Clearance Analysis"] = (
            "Not applicable for this geometry or feature set."
        )

    # --------------------------------------------------------
    # 3. CAD GENERATION
    # --------------------------------------------------------

    result, output = run_command(
        work,
        "cad_generator.py",
        timeout=180
    )

    logs["CAD Generation"] = output

    step = work / "outputs" / "generated_model.step"

    if (
        result.returncode != 0
        or not step.exists()
        or step.stat().st_size == 0
    ):
        raise RuntimeError(
            "CAD generation or STEP export failed."
        )

    return logs, step.read_bytes()


# ============================================================
# TEXT PROMPT MODE
# ============================================================

if mode == "Text Prompt":

    st.markdown("### Describe your component")

    prompt = st.text_area(
        "Design description",
        placeholder=(
            "Example: I need a rectangular mounting plate "
            "with four holes near the corners and two slots "
            "in the centre. The plate should be 200 x 120 x 12 mm."
        ),
        height=140
    )

    clearance = st.number_input(
        "Minimum required clearance (mm)",
        min_value=0.1,
        value=5.0,
        step=0.5
    )

    if st.button(
        "Generate CAD Model",
        use_container_width=True,
        disabled=not prompt.strip()
    ):

        if not os.getenv("GEMINI_API_KEY"):

            st.error("GEMINI_API_KEY is not configured.")

        else:

            try:

                with st.spinner(
                    "CADSTER is interpreting and generating your design..."
                ):

                    with tempfile.TemporaryDirectory() as temp:

                        work = Path(temp)

                        copy_backend(work)

                        shutil.copy2(
                            ROOT / "gemini_test.py",
                            work / "gemini_test.py"
                        )

                        result, output = run_command(
                            work,
                            "gemini_test.py",
                            input_text=f"{prompt.strip()}\n{clearance}\n",
                            timeout=300
                        )

                        st.session_state.logs = {
                            "Complete Text-to-CAD Pipeline": output
                        }

                        step = (
                            work
                            / "outputs"
                            / "generated_model.step"
                        )

                        if (
                            result.returncode != 0
                            or not step.exists()
                            or step.stat().st_size == 0
                        ):

                            raise RuntimeError(
                                "Text-to-CAD pipeline failed. "
                                "Inspect the execution log below."
                            )

                        st.session_state.design = json.loads(
                            (work / "design.json").read_text(
                                encoding="utf-8"
                            )
                        )

                        st.session_state.step_file = step.read_bytes()

                st.success("CAD model generated successfully!")

            except subprocess.TimeoutExpired:

                st.error(
                    "The CAD generation process timed out. "
                    "Try again or check the backend."
                )

            except Exception as error:

                st.error(f"Text-to-CAD Error: {error}")


# ============================================================
# DRAWING UPLOAD MODE
# ============================================================

elif mode == "Drawing Upload":

    st.markdown("### Upload your engineering drawing")

    uploaded = st.file_uploader(
        "Choose an engineering drawing",
        type=["png", "jpg", "jpeg"]
    )

    thickness = st.number_input(
        "Plate thickness (mm)",
        min_value=0.1,
        value=10.0,
        step=0.5
    )

    clearance = st.number_input(
        "Minimum required clearance (mm)",
        min_value=0.1,
        value=5.0,
        step=0.5,
        key="drawing_clearance"
    )

    if uploaded is not None:

        st.image(
            uploaded,
            caption="Uploaded Engineering Drawing",
            use_container_width=True
        )

    if st.button(
        "Interpret & Generate CAD",
        use_container_width=True,
        disabled=uploaded is None
    ):

        if not os.getenv("GEMINI_API_KEY"):

            st.error("GEMINI_API_KEY is not configured.")

        else:

            try:

                with st.spinner(
                    "CADSTER Vision is interpreting your drawing..."
                ):

                    with tempfile.TemporaryDirectory() as temp:

                        work = Path(temp)

                        # Copy backend files
                        copy_backend(work)

                        shutil.copy2(
                            ROOT / "sketch_interpreter.py",
                            work / "sketch_interpreter.py"
                        )

                        # Save uploaded image
                        image_path = work / uploaded.name

                        image_path.write_bytes(
                            uploaded.getvalue()
                        )

                        # ------------------------------------------------
                        # UPDATE CONFIRMED THICKNESS IN COPY OF INTERPRETER
                        # ------------------------------------------------

                        interpreter_path = (
                            work / "sketch_interpreter.py"
                        )

                        source = interpreter_path.read_text(
                            encoding="utf-8"
                        )

                        old_instruction = (
                            "The user has explicitly confirmed that the plate thickness is\n"
                            "10 mm. Set design.height = 10 even though thickness is not\n"
                            "shown in the uploaded image. This is a confirmed input, not\n"
                            "an inferred dimension."
                        )

                        new_instruction = (
                            "The user has explicitly confirmed that the plate thickness is\n"
                            f"{thickness} mm. Set design.height = {thickness} even though thickness is not\n"
                            "shown in the uploaded image. This is a confirmed input, not\n"
                            "an inferred dimension."
                        )

                        if old_instruction in source:

                            source = source.replace(
                                old_instruction,
                                new_instruction
                            )

                        interpreter_path.write_text(
                            source,
                            encoding="utf-8"
                        )

                        # ------------------------------------------------
                        # RUN GEMINI VISION INTERPRETER
                        # ------------------------------------------------

                        result, output = run_command(
                            work,
                            "sketch_interpreter.py",
                            input_text=str(image_path) + "\n",
                            timeout=180
                        )

                        logs = {
                            "AI Drawing Interpretation": output
                        }

                        design_path = (
                            work / "sketch_design.json"
                        )

                        # ------------------------------------------------
                        # SHOW ACTUAL BACKEND ERROR
                        # ------------------------------------------------

                        if (
                            result.returncode != 0
                            or not design_path.exists()
                        ):

                            st.session_state.logs = logs

                            st.error(
                                "Drawing interpretation failed."
                            )

                            st.write(
                                "Process return code:",
                                result.returncode
                            )

                            st.subheader("Actual backend output")

                            st.code(
                                output
                                or "No output received from sketch_interpreter.py"
                            )

                            st.stop()

                        # ------------------------------------------------
                        # READ INTERPRETED DESIGN
                        # ------------------------------------------------

                        interpreted = json.loads(
                            design_path.read_text(
                                encoding="utf-8"
                            )
                        )

                        if interpreted.get("status") != "ready":

                            st.session_state.logs = logs

                            st.warning(
                                "Additional information required:"
                            )

                            st.write(
                                interpreted.get(
                                    "missing_information",
                                    []
                                )
                            )

                            st.stop()

                        # Save design for review
                        st.session_state.design = interpreted["design"]

                        st.session_state.step_file = None

                        st.session_state.logs = logs

                        st.session_state.review_json = json.dumps(
                            interpreted["design"],
                            indent=4
                        )

                st.success(
                    "Drawing interpreted successfully! "
                    "Review the extracted design below."
                )

            except subprocess.TimeoutExpired:

                st.error(
                    "Drawing interpretation timed out. "
                    "Check your Gemini API response and try again."
                )

            except Exception as error:

                st.error(
                    f"Drawing interpretation error: {error}"
                )


# ============================================================
# DESIGN REVIEW
# ============================================================

if st.session_state.design:

    st.divider()

    st.header("02 | Design Review")

    design = st.session_state.design

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Length / Diameter",
        str(
            design.get(
                "length",
                design.get("radius", "-")
            )
        )
    )

    col2.metric(
        "Width",
        str(design.get("width", "-"))
    )

    col3.metric(
        "Height",
        f'{design.get("height", "-")} mm'
    )

    st.markdown("### Extracted Design JSON")

    edited = st.text_area(
        "Review or correct the design parameters",
        height=300,
        key="review_json"
    )

    st.caption(
        "Review the dimensions and feature coordinates carefully. "
        "AI interpretation may require manual correction."
    )

    clearance_value = (
        st.session_state.get("drawing_clearance", 5.0)
        if mode == "Drawing Upload"
        else 5.0
    )

    if (
        mode == "Drawing Upload"
        and st.button(
            "Run Engineering Validation & Generate STEP",
            use_container_width=True
        )
    ):

        try:

            corrected = json.loads(edited)

            with st.spinner(
                "Running validator, EAGLE and CadQuery..."
            ):

                with tempfile.TemporaryDirectory() as temp:

                    work = Path(temp)

                    copy_backend(work)

                    (work / "design.json").write_text(
                        json.dumps(corrected, indent=4),
                        encoding="utf-8"
                    )

                    logs, step_bytes = run_drawing_pipeline(
                        work,
                        clearance_value
                    )

                    st.session_state.logs.update(logs)

                    st.session_state.design = corrected

                    st.session_state.step_file = step_bytes

            st.success(
                "Engineering validation passed. STEP generated!"
            )

        except json.JSONDecodeError as error:

            st.error(
                f"Invalid JSON. Please correct the design parameters: {error}"
            )

        except Exception as error:

            st.session_state.step_file = None

            st.error(
                f"Engineering pipeline failed: {error}"
            )


# ============================================================
# EXECUTION RESULTS
# ============================================================

if st.session_state.logs:

    st.divider()

    st.header("03 | Execution Results")

    for name, log in st.session_state.logs.items():

        with st.expander(name, expanded=False):

            st.code(
                log or "No output recorded."
            )


# ============================================================
# STEP EXPORT
# ============================================================

if st.session_state.step_file:

    st.divider()

    st.header("04 | CAD Model Export")

    st.success("STEP model generated successfully.")

    st.download_button(
        "⬇ Download STEP Model",
        data=st.session_state.step_file,
        file_name="CADSTER_generated_model.step",
        mime="application/octet-stream",
        use_container_width=True
    )

    st.caption(
        "Open the downloaded STEP file in SolidWorks "
        "or another STEP-compatible CAD application."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CADSTER | AI-assisted engineering design automation | Prototype"
)
