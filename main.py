import streamlit as st
import random
import math
import bleach
from owlready2 import get_ontology, sync_reasoner
from streamlit_confetti import confetti

# ---------------------------------------------------------------
# 1. Load the ontology created in Protégé
# ---------------------------------------------------------------
onto = get_ontology("AreaShapes.owl").load()
with onto:
    sync_reasoner()  # Run HermiT at startup to prepare all 20 SWRL rules

# ---------------------------------------------------------------
# 2. Student model – mastery for the 6 shapes
# ---------------------------------------------------------------
if "student" not in st.session_state:
    st.session_state.student = {
        "mastery": {
            "Rectangle": 0.5, "Square": 0.5, "Triangle": 0.5,
            "Parallelogram": 0.5, "Trapezium": 0.5, "Circle": 0.5
        }
    }

# ---------------------------------------------------------------
# 3. Choose student's weakest shape
# ---------------------------------------------------------------
def choose_shape():
    mastery = st.session_state.student["mastery"]
    weights = [1 / (mastery[shape] + 0.01) for shape in mastery]  # Lower mastery = higher chance
    return random.choices(list(mastery.keys()), weights=weights)[0]

# ---------------------------------------------------------------
# 4. Generate random problem with units
# ---------------------------------------------------------------
def generate_problem():
    shape = choose_shape()
    units = ["cm", "m"]
    unit = random.choice(units)
    scale = 100 if unit == "m" else 1
    
    if shape in ["Rectangle", "Square"]:
        length = random.randint(4, 15) * scale
        width = length if shape == "Square" else random.randint(3, 12) * scale
        question = f"**{shape}**<br>Length = {length/scale} {unit}<br>Width = {width/scale} {unit}"
        params = {"length": length/scale, "width": width/scale}
        
    elif shape == "Triangle":
        base = random.randint(5, 15) * scale
        height = random.randint(4, 12) * scale
        question = f"**Triangle**<br>Base = {base/scale} {unit}<br>Height = {height/scale} {unit}"
        params = {"base": base/scale, "height": height/scale}
        
    elif shape == "Circle":
        radius = round(random.uniform(2, 10) * scale / 10, 1)
        question = f"**Circle**<br>Radius = {radius} {unit}"
        params = {"radius": radius}
        
    elif shape == "Parallelogram":
        base = random.randint(6, 14) * scale
        height = random.randint(4, 10) * scale
        question = f"**Parallelogram**<br>Base = {base/scale} {unit}<br>Height = {height/scale} {unit}"
        params = {"base": base/scale, "height": height/scale}
        
    else:  # Trapezium
        a = random.randint(5, 12) * scale
        b = random.randint(8, 15) * scale
        h = random.randint(4, 10) * scale
        question = f"**Trapezium**<br>Parallel sides = {a/scale} {unit} and {b/scale} {unit}<br>Height = {h/scale} {unit}"
        params = {"a": a/scale, "b": b/scale, "h": h/scale}
    
    st.session_state.current = {
        "shape": shape,
        "params": params,
        "question": question,
        "unit": unit + "²"  # Expected correct unit for answer
    }
    return question

# ---------------------------------------------------------------
# 5. Calculate correct numerical value
# ---------------------------------------------------------------
def correct_answer():
    p = st.session_state.current["params"]
    s = st.session_state.current["shape"]
    if s in ["Rectangle", "Square", "Parallelogram"]:
        return p.get("length", p.get("base", p.get("a", 0))) * p.get("width", p.get("height", p.get("h", 0)))
    if s == "Triangle":
        return round(0.5 * p["base"] * p["height"], 2)
    if s == "Circle":
        return round(math.pi * p["radius"]**2, 2)
    return round(0.5 * (p["a"] + p["b"]) * p["h"], 2)

# ---------------------------------------------------------------
# 6. Three-level hint system
# ---------------------------------------------------------------
def give_hint(level):
    shape = st.session_state.current["shape"]
    if level == 1:
        st.info("Hint: What measurements do you need for this shape?")
    elif level == 2:
        hints = {
            "Triangle": "Remember to multiply by ½",
            "Circle": "Use π and square the radius",
            "Trapezium": "Add the two parallel sides first"
        }
        st.warning(hints.get(shape, "Think carefully about the formula"))
    else:
        st.success(f"Worked example: The area is {correct_answer()} {st.session_state.current['unit']}")

# ---------------------------------------------------------------
# 7. Main User Interface
# ---------------------------------------------------------------
st.set_page_config(page_title="AreaTutor", layout="centered")
st.markdown("<h1 style='text-align:center; color:#1E90FF;'>AreaTutor</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; font-size:18px;'>Primary Mathematics – Area of 2D Shapes with Units</p>", unsafe_allow_html=True)

# Generate problem if not already done
if "question" not in st.session_state:
    st.session_state.question = generate_problem()

# Display the problem
st.markdown(f"<h3>{st.session_state.current['question']}</h3>", unsafe_allow_html=True)
st.latex(r"\Large \text{What is the area?}")

# Input fields
col1, col2 = st.columns([3, 1])
answer = col1.number_input("Answer", step=0.1, format="%.2f", key="ans_input")
selected_unit = col2.selectbox("Unit", ["cm²", "m²"])

# Check answer button
if st.button("Check Answer", type="primary", use_container_width=True):
    clean_answer = bleach.clean(str(answer))  # Security sanitisation
    
    # Create temporary StudentAnswer individual in ontology
    with onto:
        temp_answer = onto.StudentAnswer(f"answer_{random.randint(1000,9999)}")
        temp_answer.hasValue = [float(clean_answer)]
        temp_answer.hasUnit = [selected_unit]
        temp_answer.concernsShape = [onto.search_one(iri=f"*{st.session_state.current['shape']}")]
        sync_reasoner()  # Fires all 20 SWRL rules – detects misconceptions

    # Check value + unit
    correct_value = abs(float(clean_answer) - correct_answer()) < 0.2
    correct_unit = selected_unit == st.session_state.current["unit"]
    
    if correct_value and correct_unit:
        st.balloons()  # Celebration animation
        confetti()     # Confetti explosion
        st.success("Correct! Well done!")
        # Increase mastery
        current_shape = st.session_state.current["shape"]
        st.session_state.student["mastery"][current_shape] = min(1.0, st.session_state.student["mastery"][current_shape] + 0.18)
    else:
        # Check SWRL-diagnosed misconception
        mistakes = list(temp_answer.triggersMisconception)
        if mistakes:
            st.error(f"Common mistake: {mistakes[0].name.replace('_', ' ')}")
        else:
            reason = []
            if not correct_value: reason.append("wrong number")
            if not correct_unit: reason.append("wrong unit")
            st.error(f"Incorrect – {' and '.join(reason)}")
        # Decrease mastery
        current_shape = st.session_state.current["shape"]
        st.session_state.student["mastery"][current_shape] *= 0.88

    # Next problem button
    if st.button("Next Problem"):
        del st.session_state.question
        st.rerun()

# Hint buttons
c1, c2, c3 = st.columns(3)
if c1.button("Hint 1"): give_hint(1)
if c2.button("Hint 2"): give_hint(2)
if c3.button("Full Example"): give_hint(3)

# Mastery dashboard in sidebar
st.sidebar.header("Your Mastery")
for shape, mastery in st.session_state.student["mastery"].items():
    st.sidebar.progress(mastery, text=f"{shape}: {int(mastery*100)}%")