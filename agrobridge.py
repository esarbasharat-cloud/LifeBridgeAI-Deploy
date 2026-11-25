import html
import json
import uuid

import streamlit as st
from datetime import date, datetime
from agro_live_scanner import render_live_scanner


def render_agrobridge(gemini_generate, student=None, query_all=None, execute=None):
    st.markdown("""
    <style>

/* AGROBRIDGE - PREMIUM BOTANICAL DESIGN SYSTEM */
 .agro-hero { position:relative; overflow:hidden; padding:46px 44px 42px; border:1px solid rgba(255,255,255,.16); border-radius:30px; background:radial-gradient(ellipse at 88% 8%,rgba(194,224,164,.22),transparent 32%),linear-gradient(125deg,#102c21 0%,#174832 55%,#286747 100%); color:#fff; margin:8px 0 28px; box-shadow:0 18px 48px rgba(22,59,39,.16); }
.agro-hero:after { content: "✳"; position:absolute; right:42px; top:-28px; color:rgba(235,247,222,.10); font-size:190px; line-height:1; pointer-events:none; }
.agro-eyebrow { color:#c8e5b6; font-size:.72rem; font-weight:750; letter-spacing:2.5px; text-transform:uppercase; margin-bottom:15px; }
.agro-hero h1 { color:#fff!important; font-size:clamp(2.2rem,4vw,3.15rem); font-weight:760; letter-spacing:-1.8px; margin:0 0 13px; line-height:1.08; }
.agro-hero p { color:#e2eee4!important; font-size:1.04rem; line-height:1.75; max-width:680px; margin:0; }
.agro-card { padding:24px; border:1px solid #e7ece4; border-radius:22px; background:rgba(255,255,255,.82); box-shadow:0 8px 28px rgba(31,58,39,.045); margin-bottom:18px; }
div[data-testid="stAppViewContainer"] { background:#f6f7f2; }
div[data-testid="stMainBlockContainer"] { padding-top:2rem; padding-bottom:3rem; max-width:1440px; }
h1,h2,h3 { letter-spacing:-.7px; }
h2 { color:#183d2b; font-weight:720; }
h3 { color:#234a35; font-weight:680; }
p, label, [data-testid="stCaptionContainer"] { color:#526458; }
.stTabs [data-baseweb="tab-list"] { gap:7px; padding:7px; border:1px solid #e6ebe3; border-radius:17px; background:#ecefe8; }
.stTabs [data-baseweb="tab"] { height:46px; padding:0 17px; border-radius:12px; color:#657468; font-size:.88rem; font-weight:650; transition:all .2s ease; }
.stTabs [data-baseweb="tab"]:hover { color:#214b34; background:rgba(255,255,255,.65); }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color:#17452f; background:#fff; box-shadow:0 2px 9px rgba(30,58,38,.09); }
.stTabs [data-baseweb="tab-highlight"] { background:transparent; }
.stTabs [data-baseweb="tab-panel"] { padding-top:27px; }
.stButton > button { min-height:47px; border:1px solid #dce5d9; border-radius:13px; background:#fff; color:#234a35; font-weight:680; transition:transform .18s ease,box-shadow .18s ease,background .18s ease; }
.stButton > button:hover { border-color:#7da487; background:#f6faf5; color:#17452f; box-shadow:0 7px 18px rgba(25,71,44,.10); transform:translateY(-1px); }
.stButton > button[kind="primary"] { background:linear-gradient(135deg,#174832,#286747); color:white; border:1px solid #174832; box-shadow:0 6px 16px rgba(23,72,50,.16); }
.stButton > button[kind="primary"]:hover { background:#245e40; color:white; box-shadow:0 9px 22px rgba(23,72,50,.22); }
[data-testid="stFileUploader"] section { border:1px dashed #b6cbb5; border-radius:18px; background:#f8faf6; padding:18px; }
[data-testid="stFileUploader"] section:hover { border-color:#548363; background:#f2f7f0; }
[data-testid="stCameraInput"] { border:1px solid #e5ebe2; border-radius:18px; padding:14px; background:#fff; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div,[data-testid="stMultiSelect"] [data-baseweb="select"] > div { border-radius:12px; border-color:#dfe6dc; background:#fff; min-height:44px; }
[data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input,[data-testid="stDateInput"] input { border:1px solid #dfe6dc; border-radius:12px; background:#fff; }
[data-testid="stTextArea"] textarea:focus,[data-testid="stTextInput"] input:focus { border-color:#659274; box-shadow:0 0 0 3px rgba(76,131,91,.10); }
[data-testid="stAlert"] { border-radius:15px; border:1px solid #e6ebe3; }
[data-testid="stImage"] img { border-radius:17px; }
[data-testid="stMetric"] { padding:17px 19px; border:1px solid #e7ece4; border-radius:17px; background:#fff; box-shadow:0 5px 18px rgba(31,58,39,.035); }
[data-testid="stExpander"] { border:1px solid #e5ebe2; border-radius:15px; background:rgba(255,255,255,.8); }
@media(max-width:760px) { .agro-hero { padding:30px 24px; border-radius:22px; } .agro-hero:after { right:8px; top:0; font-size:105px; } .stTabs [data-baseweb="tab-list"] { gap:3px; overflow-x:auto; } .stTabs [data-baseweb="tab"] { padding:0 10px; font-size:.78rem; } }
@media(prefers-reduced-motion:no-preference) { .agro-hero { animation:agroReveal .65s ease both; } @keyframes agroReveal { from { opacity:0; transform:translateY(9px); } to { opacity:1; transform:translateY(0); } } }
    [data-testid=stSegmentedControl] { animation: agroControlIn .45s ease both; }
    [data-testid=stSegmentedControl] [role=radiogroup] { display:flex; flex-wrap:wrap; gap:6px; padding:6px; border:1px solid #dfe8dc; border-radius:18px; background:#e9eee7; }
    [data-testid=stSegmentedControl] [role=radio] { min-height:40px; padding:9px 15px; border:1px solid transparent; border-radius:13px; color:#526458; font-weight:650; transition:all .22s ease; }
    [data-testid=stSegmentedControl] [role=radio][aria-checked=true] { color:#fff; background:linear-gradient(135deg,#174832,#286747); border-color:#174832; box-shadow:0 4px 12px rgba(23,72,50,.16); }
    [data-testid=stSegmentedControl] [role=radio]:hover { transform:translateY(-1px); background:#fff; color:#174832; }
    @keyframes agroControlIn { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:translateY(0); } }

/* PREMIUM DEPTH & MOTION */
@media (prefers-reduced-motion: no-preference) {
  [data-testid=stVerticalBlockBorderWrapper] {
    position:relative; overflow:hidden; border-radius:22px !important;
    border:1px solid rgba(222,233,220,.95) !important;
    background:linear-gradient(145deg,rgba(255,255,255,.98),rgba(247,250,245,.96)) !important;
    box-shadow:0 2px 5px rgba(24,55,35,.025),0 8px 22px rgba(24,55,35,.055),0 18px 38px rgba(24,55,35,.045),inset 0 1px 0 rgba(255,255,255,.95) !important;
    transition:transform .32s cubic-bezier(.2,.7,.2,1),box-shadow .32s ease,border-color .32s ease !important;
    animation:agroCardEntrance .55s cubic-bezier(.2,.7,.2,1) both;
  }
  [data-testid=stVerticalBlockBorderWrapper]:hover {
    transform:translateY(-5px) scale(1.006);
    border-color:#c4d7c2 !important;
    box-shadow:0 4px 9px rgba(24,55,35,.04),0 14px 30px rgba(24,55,35,.09),0 28px 55px rgba(24,55,35,.075),inset 0 1px 0 rgba(255,255,255,1) !important;
  }
  [data-testid=stVerticalBlockBorderWrapper]:active { transform:translateY(-1px) scale(.998); }
  [data-testid=stVerticalBlockBorderWrapper]::before {
    content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none;
    background:linear-gradient(125deg,rgba(255,255,255,.5),transparent 35%,transparent 72%,rgba(218,237,215,.16));
    opacity:.55; transition:opacity .3s ease;
  }
  [data-testid=stVerticalBlockBorderWrapper]:hover::before { opacity:1; }
  [data-testid=stMetric] {
    border:1px solid #e3ebe1 !important; border-radius:19px !important;
    background:linear-gradient(150deg,#fff 0%,#f8faf7 100%) !important;
    box-shadow:0 3px 7px rgba(25,58,39,.035),0 10px 25px rgba(25,58,39,.055),inset 0 1px 0 #fff !important;
    transition:transform .28s ease,box-shadow .28s ease,border-color .28s ease !important;
    animation:agroCardEntrance .6s ease both;
  }
  [data-testid=stMetric]:hover { transform:translateY(-4px); border-color:#c6d8c4 !important; box-shadow:0 7px 15px rgba(25,58,39,.055),0 17px 32px rgba(25,58,39,.075) !important; }
  [data-testid=stImage] img { transition:transform .45s cubic-bezier(.2,.7,.2,1),box-shadow .35s ease; box-shadow:0 6px 22px rgba(23,48,32,.09); }
  [data-testid=stImage] img:hover { transform:scale(1.012); box-shadow:0 12px 32px rgba(23,48,32,.13); }
  [data-testid=stFileUploader] section,[data-testid=stCameraInput] { transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease,background .25s ease !important; box-shadow:inset 0 1px 0 rgba(255,255,255,.8),0 5px 16px rgba(25,58,39,.035); }
  [data-testid=stFileUploader] section:hover,[data-testid=stCameraInput]:hover { transform:translateY(-2px); box-shadow:0 8px 22px rgba(25,58,39,.065); }
  .stButton > button { box-shadow:0 2px 5px rgba(25,58,39,.025),0 5px 13px rgba(25,58,39,.04); }
  @keyframes agroCardEntrance { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
}
@media(prefers-reduced-motion:reduce) {
  [data-testid=stVerticalBlockBorderWrapper],[data-testid=stMetric],[data-testid=stImage] img { animation:none !important; transition:none !important; transform:none !important; }
}

/* AGRO TRUE 3D SURFACES */
@media (prefers-reduced-motion: no-preference) {
  [data-testid=stVerticalBlockBorderWrapper] {
    perspective:1200px; transform-style:preserve-3d;
    border:1px solid #dce8dc !important; border-radius:24px !important;
    background:linear-gradient(155deg,#ffffff 0%,#fbfdfb 38%,#f1f6f0 100%) !important;
    box-shadow:0 1px 0 #fff inset,0 -1px 0 rgba(206,220,205,.4) inset,0 3px 0 #e8efe7,0 5px 0 #e1eae0,0 8px 0 #d8e4d7,0 12px 24px rgba(27,57,37,.09),0 24px 48px rgba(27,57,37,.055) !important;
    transform:translateZ(0) rotateX(0deg); transform-style:preserve-3d;
    transition:transform .42s cubic-bezier(.2,.7,.2,1),box-shadow .42s ease,border-color .3s ease !important;
  }
  [data-testid=stVerticalBlockBorderWrapper] > div { transform:translateZ(8px); }
  [data-testid=stVerticalBlockBorderWrapper]::before {
    content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none; z-index:0;
    background:linear-gradient(135deg,rgba(255,255,255,.88) 0%,rgba(255,255,255,.16) 26%,transparent 55%,rgba(207,226,204,.24) 100%);
    box-shadow:inset 0 1px 0 rgba(255,255,255,.95),inset 1px 0 0 rgba(255,255,255,.6);
  }
  [data-testid=stVerticalBlockBorderWrapper]:hover {
    transform:perspective(1200px) translateY(-8px) rotateX(2deg) rotateY(-.7deg) scale(1.008) !important;
    border-color:#b9d0b8 !important;
    box-shadow:0 1px 0 #fff inset,0 -1px 0 #d5e2d4 inset,0 4px 0 #e2ece0,0 7px 0 #d5e3d4,0 11px 0 #cbdcc9,0 18px 35px rgba(24,56,36,.14),0 35px 65px rgba(24,56,36,.10) !important;
  }
  [data-testid=stVerticalBlockBorderWrapper]:active { transform:perspective(1200px) translateY(-2px) scale(.998) !important; }
  [data-testid=stMetric] {
    transform-style:preserve-3d; border:1px solid #dce8dc !important; border-radius:21px !important;
    background:linear-gradient(145deg,#fff 0%,#f5f9f4 100%) !important;
    box-shadow:0 1px 0 #fff inset,0 3px 0 #e4ede3,0 6px 0 #d8e5d7,0 10px 23px rgba(26,57,37,.075) !important;
    transition:transform .35s ease,box-shadow .35s ease !important;
  }
  [data-testid=stMetric]:hover { transform:translateY(-6px) rotateX(3deg) !important; box-shadow:0 1px 0 #fff inset,0 4px 0 #e0eae0,0 8px 0 #d2e0d1,0 16px 32px rgba(26,57,37,.12) !important; }
}
@media(prefers-reduced-motion:reduce) {
  [data-testid=stVerticalBlockBorderWrapper],[data-testid=stMetric] { transition:none !important; transform:none !important; }
}

/* AGROBRIDGE - LEARNING STUDIO MOTION */
@media (prefers-reduced-motion: no-preference) {
.st-key-agro_leaf_photo_card,.st-key-agro_crop_details_card,.st-key-agro_symptoms_card,.st-key-agro_field_notes_card {
 position:relative !important; isolation:isolate; overflow:visible !important;
 transform:translateY(0); transform-style:flat;
 border:1px solid rgba(255,255,255,.9) !important;
 border-radius:25px !important;
 background:linear-gradient(145deg,#ffffff 0%,#fbfdf9 50%,#f3f7f1 100%) !important;
 box-shadow:0 2px 5px rgba(28,60,39,.04),0 6px 18px rgba(28,60,39,.055) !important;
 transition:transform .26s ease,box-shadow .26s ease,border-color .26s ease !important;
}
.st-key-agro_leaf_photo_card:hover,.st-key-agro_crop_details_card:hover,.st-key-agro_symptoms_card:hover,.st-key-agro_field_notes_card:hover {
 transform:translateY(-5px) !important;
 border-color:#c8d8ca !important;
 box-shadow:0 15px 32px rgba(35,75,54,.11) !important;
}
}
@media(prefers-reduced-motion:reduce) {
.st-key-agro_leaf_photo_card,.st-key-agro_crop_details_card,.st-key-agro_symptoms_card,.st-key-agro_field_notes_card {animation:none!important;transition:none!important;transform:none!important}
}

/* PREMIUM ASSESSMENT RESULT SURFACES */
.st-key-agro_assessment_result_card,.st-key-agro_latest_assessment_card {
 padding:26px 28px !important;
 margin:18px 0 24px !important;
 border:1px solid #dfe9dc !important;
 border-radius:24px !important;
 background:linear-gradient(145deg,#ffffff 0%,#fbfdf9 58%,#f2f7ef 100%) !important;
 box-shadow:0 3px 8px rgba(27,59,37,.035),0 12px 30px rgba(27,59,37,.065),inset 0 1px 0 rgba(255,255,255,.95) !important;
}
.st-key-agro_assessment_result_card h3,.st-key-agro_latest_assessment_card h3 {
 color:#1d5035 !important;
 font-weight:760 !important;
 letter-spacing:-.6px !important;
 padding-bottom:12px !important;
 margin-bottom:17px !important;
 border-bottom:1px solid #e7eee4 !important;
}
.st-key-agro_assessment_result_card p,.st-key-agro_latest_assessment_card p {
 color:#46594b;
 line-height:1.8;
}
@media(max-width:760px) {
 .st-key-agro_assessment_result_card,.st-key-agro_latest_assessment_card {padding:19px 17px !important;border-radius:19px !important}
}

.agro-chat-row { display:flex; width:100%; margin:14px 0; }
.agro-chat-user { justify-content:flex-end; }
.agro-chat-assistant { justify-content:flex-start; }
.agro-chat-bubble { max-width:min(78%,680px); padding:15px 19px; border-radius:19px; font-size:.96rem; line-height:1.7; overflow-wrap:anywhere; box-shadow:0 5px 16px rgba(25,55,35,.055); }
.agro-user-bubble { color:#fff; background:linear-gradient(135deg,#174832,#286747); border:1px solid #245c3e; border-bottom-right-radius:6px; }
.agro-assistant-bubble { color:#294333; background:linear-gradient(145deg,#fff,#f4f8f2); border:1px solid #e0e9de; border-bottom-left-radius:6px; }
.agro-chat-label { font-size:.66rem; font-weight:800; letter-spacing:1.25px; margin-bottom:6px; opacity:.78; }
[data-testid="stChatInput"] { width:100% !important; max-width:900px !important; margin-left:auto !important; margin-right:auto !important; }
[data-testid="stBottom"] { background:transparent !important; }\n[data-testid="stBottom"] > div { max-width:900px !important; margin-left:auto !important; margin-right:auto !important; background:transparent !important; box-shadow:none !important; }\n[data-testid="stChatInput"] { width:100% !important; max-width:900px !important; background:#fff !important; border:0 !important; outline:0 !important; box-shadow:none !important; border-radius:18px !important; padding:4px 8px !important; }\n[data-testid="stBottom"] [data-testid="stChatInput"] > div { background:#fff !important; border-radius:16px !important; }
[data-testid="stChatInput"] textarea { background:transparent !important; color:#294333 !important; border:0 !important; outline:0 !important; box-shadow:none !important; border-radius:0 !important; opacity:1 !important; }
[data-testid="stChatInput"] { background:#fff !important; border:0 !important; outline:0 !important; box-shadow:none !important; }
.agro-user-bubble, .agro-user-bubble * { color:#fff !important; }
.st-key-agro_chat_panel { border-radius:24px !important; }
@media(max-width:600px) { .agro-chat-bubble { max-width:91%; padding:12px 14px; } }
\n</style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="agro-hero">        <div class="agro-eyebrow">SMART AGRICULTURE • PLANT HEALTH</div>        <h1>🌱 AgroBridge</h1>        <p>Helping farmers understand their crops with accessible, AI-assisted plant-health insights and practical crop-care guidance.</p>    </div>
    """, unsafe_allow_html=True)

    st.caption(
        "Agricultural assistance is informational. "
        "AI suggestions are not confirmed diagnoses."
    )

    pending_assessment = st.session_state.get("agro_pending_assessment")

    if pending_assessment:
        st.session_state.agro_assessment_id = pending_assessment["assessment_id"]
        st.session_state.agro_assessment = pending_assessment["report"]
        st.session_state.agro_original_assessment = pending_assessment["report"]
        st.session_state.agro_assessment_image = (
            bytes(pending_assessment["image_data"])
            if pending_assessment.get("image_data") is not None else None
        )
        st.session_state.agro_assessment_mime = pending_assessment.get("image_mime") or "image/jpeg"
        st.session_state.agro_assessment_crop = pending_assessment.get("crop") or ""
        st.session_state.agro_assessment_details = pending_assessment.get("details") or ""

        try:
            st.session_state.agro_assessment_symptoms = json.loads(
                pending_assessment.get("symptoms_json") or "[]"
            )
        except (TypeError, ValueError):
            st.session_state.agro_assessment_symptoms = []

        try:
            st.session_state.agro_chat_history = json.loads(
                pending_assessment.get("chat_json") or "[]"
            )
        except (TypeError, ValueError):
            st.session_state.agro_chat_history = []

        st.session_state.agro_assessment_saved = True
        st.session_state.agro_navigation = "Leaf Analysis"
        del st.session_state["agro_pending_assessment"]

    active_section = st.segmented_control(
        'AgroBridge navigation',
        [
            'Leaf Analysis',
            'Live Plant Scanner',
            'Health Reports',
            'Crop Monitoring',
            'Treatment Guidance',
        ],
        selection_mode='single',
        default='Leaf Analysis',
        key='agro_navigation',
        label_visibility='collapsed',
        width='stretch',
        wrap=True,
    )

    if active_section == 'Leaf Analysis':
        st.markdown("### Plant health assessment")
        st.caption("Start with a clear leaf photograph, then add crop and symptom details.")
        photo_col, crop_col = st.columns([1.15, 0.85], gap="large")

        with photo_col:
            with st.container(border=True, key="agro_leaf_photo_card"):
                st.markdown("#### 01 · Leaf photograph")
                st.caption("Add a clear photograph of the affected plant leaf.")
                photo_source = st.segmented_control(
                    'Choose how to add a leaf photo',
                    ['Upload an existing photo', 'Take a photo with camera'],
                    selection_mode='single',
                    default='Upload an existing photo',
                    key='agro_photo_source',
                    label_visibility='collapsed',
                    width='stretch',
                    wrap=True,
                )
                if photo_source == "Upload an existing photo":
                    image_input = st.file_uploader("Upload a leaf photograph", type=["jpg", "jpeg", "png", "webp", "jfif"], key="agro_leaf_upload")
                else:
                    image_input = st.camera_input("Take a leaf photograph", key="agro_camera")
                if image_input:
                    st.image(image_input, caption="Leaf image for assessment", use_container_width=True)

        with crop_col:
            with st.container(border=True, key="agro_crop_details_card"):
                st.markdown("#### 02 · Crop details")
                st.caption("Choose the crop or let AgroBridge suggest its identity from the image.")
                crop = st.selectbox("Crop", ["Select crop", "Tomato", "Potato", "Rice", "Wheat", "Cotton", "Maize", "Chilli", "Auto-identify from image", "Other"], key="agro_crop")
                st.info("A clear, well-lit photograph helps improve visual observations.")

        with st.container(border=True, key="agro_symptoms_card"):
            st.markdown("#### 03 · Visible symptoms")
            st.caption("Select all observations that apply. Leave blank if you are unsure.")
            symptoms = st.multiselect("Observed symptoms", ["Yellowing", "Brown spots", "Dark spots", "White powder-like patches", "Curling leaves", "Wilting", "Dry edges", "Holes in leaves", "Unusual growth", "Other / unsure"], key="agro_symptoms")

        with st.container(border=True, key="agro_field_notes_card"):
            st.markdown("#### 04 · Additional field observations")
            st.caption("A little context can help explain what may be happening.")
            additional_details = st.text_area("Additional observations", placeholder="When did it start? Which leaves are affected? Has the weather been unusually wet or hot?", key="agro_details")

        if st.button("Generate Observation Assessment",
                     key="agro_assess", use_container_width=True, type="primary"):
            if crop == "Select crop" or (crop == "Auto-identify from image" and image_input is None):
                st.warning("Please select a crop.")
            elif not symptoms and not additional_details.strip() and image_input is None:
                st.warning("Please describe at least one observation.")
            else:
                prompt = f"""
You are AgroBridge, an educational crop-health assistant.

Crop selection: {crop}
If a photograph is attached, inspect it for plant identity and visible leaf symptoms.
If Auto-identify from image is selected, suggest the most likely plant or crop and explain the visual clues.
Observed symptoms: {", ".join(symptoms) if symptoms else "Not selected"}
Additional observations: {additional_details or "None"}

Provide an educational assessment using this structure:

1. Observation Summary
2. Possible Causes (rank cautiously, do not claim certainty)
3. What information is still missing
4. Low-risk immediate care and observation steps
5. When to contact a local agricultural expert

Assess visible features in the photograph when one is provided.
Give a cautious possible issue, confidence level, and alternative explanations.
If the image is unclear, say that identification is uncertain.
Never present a visual assessment as a confirmed diagnosis.
Do not prescribe pesticide products, dosages, mixtures,
or chemical application instructions.
Use simple, practical language.
"""
                try:
                    with st.spinner("Preparing assessment..."):
                        for attempt in range(3):
                            try:
                                if image_input is not None:
                                    result = gemini_generate(prompt, temperature=0.2, image_bytes=image_input.getvalue(), mime_type=("image/jpeg" if image_input.name.lower().endswith(".jfif") or image_input.type in ("image/jfif", "image/pjpeg") else image_input.type or "image/jpeg"))
                                else:
                                    result = gemini_generate(prompt, temperature=0.2)
                                break
                            except Exception as retry_exc:
                                error_text = str(retry_exc).lower()
                                temporary_error = any(code in error_text for code in ("429", "500", "502", "503", "504", "unavailable", "resource_exhausted"))
                                if not temporary_error or attempt == 2:
                                    raise
                                wait_seconds = 2 * (attempt + 1)
                                st.info(f"Gemini is temporarily busy. Retrying in {wait_seconds} seconds (attempt {attempt + 2} of 3)...")
                                import time
                                time.sleep(wait_seconds)
                    st.session_state.agro_assessment = result
                    st.session_state.agro_original_assessment = result
                    st.session_state.agro_chat_history = []
                    st.session_state.agro_assessment_image = image_input.getvalue() if image_input is not None else None
                    st.session_state.agro_assessment_mime = ("image/jpeg" if image_input.name.lower().endswith(".jfif") or image_input.type in ("image/jfif", "image/pjpeg") else image_input.type or "image/jpeg") if image_input is not None else None
                    st.session_state.agro_assessment_crop = crop
                    st.session_state.agro_assessment_symptoms = list(symptoms)
                    st.session_state.agro_assessment_details = additional_details
                    assessment_id = uuid.uuid4().hex
                    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
                    image_bytes = image_input.getvalue() if image_input is not None else None
                    image_mime = ("image/jpeg" if image_input.name.lower().endswith(".jfif") or image_input.type in ("image/jfif", "image/pjpeg") else image_input.type or "image/jpeg") if image_input is not None else "image/jpeg"

                    st.session_state.agro_assessment_id = assessment_id
                    st.session_state.agro_assessment_saved = False

                    owner_id = student["student_id"] if student is not None else None
                    if owner_id and execute:
                        try:
                            execute(
                                "INSERT INTO agro_assessments (assessment_id, student_id, title, crop, symptoms_json, details, report, image_data, image_mime, chat_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    assessment_id,
                                    owner_id,
                                    crop if crop not in ("Select crop", "Other", "Auto-identify from image") else "Plant Assessment",
                                    crop,
                                    json.dumps(list(symptoms), ensure_ascii=False),
                                    additional_details,
                                    result,
                                    image_bytes,
                                    image_mime,
                                    "[]",
                                    created_at,
                                    created_at,
                                ),
                            )
                            st.session_state.agro_assessment_saved = True
                        except Exception as save_exc:
                            st.warning(f"Assessment is available in this session, but could not be saved: {save_exc}")

                except Exception as exc:
                    st.error(f"Assessment failed: {exc}")

        if st.session_state.get("agro_assessment"):
            with st.container(key="agro_assessment_result_card"):
                st.markdown("### 🌿 Plant Health Assessment")
                st.markdown(st.session_state.agro_assessment)

            st.markdown("### 💬 Continue with AgroBridge")
            st.caption("Your plant assessment stays separate. Continue the conversation below.")

            with st.container(key="agro_chat_panel", border=True):
                history = st.session_state.get("agro_chat_history", [])

                if not history:
                    st.markdown("**AgroBridge**")
                    st.caption("I'm here to help you understand your plant observations. What would you like to ask?")

                for chat_item in history:
                    message_text = html.escape(str(chat_item["content"])).replace("\\n", "<br>")
                    if chat_item["role"] == "user":
                        st.markdown(
                            '<div class="agro-chat-row agro-chat-user"><div class="agro-chat-bubble agro-user-bubble"><div class="agro-chat-label">YOU</div>'
                            + message_text + '</div></div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            '<div class="agro-chat-row agro-chat-assistant"><div class="agro-chat-bubble agro-assistant-bubble"><div class="agro-chat-label">AGROBRIDGE</div>'
                            + message_text + '</div></div>',
                            unsafe_allow_html=True
                        )

                chat_message = st.chat_input("Message AgroBridge...", key="agro_chat_input", width=900)

            if chat_message:
                history = st.session_state.setdefault("agro_chat_history", [])
                history.append({"role": "user", "content": chat_message})

                conversation_context = "\\n".join(
                    ("Farmer" if item["role"] == "user" else "AgroBridge") + ": " + item["content"]
                    for item in history
                )

                chat_prompt = (
                    "You are AgroBridge, a helpful conversational educational crop-health assistant. "
                    "Respond naturally and directly to the farmer's latest message. "
                    "Original crop: " + str(st.session_state.get("agro_assessment_crop", "Unknown")) + "\\n"
                    + "Original symptoms: " + ", ".join(st.session_state.get("agro_assessment_symptoms", [])) + "\\n"
                    + "Original field observations: " + str(st.session_state.get("agro_assessment_details", "None")) + "\\n"
                    + "Original assessment: " + str(st.session_state.get("agro_original_assessment", "")) + "\\n"
                    + "Conversation so far:\\n" + conversation_context + "\\n\\n"
                    + "Answer the latest message specifically. Remember earlier messages and avoid repeating questions. "
                    "Be friendly, clear and concise. Treat image-based observations as uncertain. "
                    "Never claim a confirmed diagnosis or predict future disease. "
                    "Never prescribe pesticide products, dosages, mixtures or chemical application instructions."
                )

                try:
                    with st.spinner("AgroBridge is thinking..."):
                        saved_image = st.session_state.get("agro_assessment_image")
                        if saved_image:
                            reply = gemini_generate(
                                chat_prompt,
                                temperature=0.3,
                                image_bytes=saved_image,
                                mime_type=st.session_state.get("agro_assessment_mime") or "image/jpeg"
                            )
                        else:
                            reply = gemini_generate(chat_prompt, temperature=0.3)

                    history.append({"role": "assistant", "content": reply})

                    assessment_id = st.session_state.get("agro_assessment_id")
                    owner_id = student["student_id"] if student is not None else None

                    if (
                        st.session_state.get("agro_assessment_saved")
                        and assessment_id
                        and owner_id
                        and execute
                    ):
                        try:
                            execute(
                                "UPDATE agro_assessments SET chat_json=?, updated_at=? WHERE assessment_id=? AND student_id=?",
                                (
                                    json.dumps(history, ensure_ascii=False),
                                    datetime.now().astimezone().isoformat(timespec="seconds"),
                                    assessment_id,
                                    owner_id,
                                ),
                            )
                        except Exception as save_exc:
                            st.warning(f"Reply received, but chat history could not be saved: {save_exc}")

                    st.rerun()

                except Exception as chat_exc:
                    history.pop()
                    st.error(f"AgroBridge could not respond: {chat_exc}")

    elif active_section == 'Live Plant Scanner':
        render_live_scanner(gemini_generate)

    elif active_section == 'Health Reports':
        st.subheader("Recent Assessments")
        st.caption("Your saved plant assessments, reports and conversations.")

        if student is None:
            st.info("Sign in to save and revisit your assessments. You can still explore AgroBridge as a guest.")
        elif query_all is None:
            st.warning("Assessment history is temporarily unavailable.")
        else:
            records = query_all(
                "SELECT assessment_id, title, crop, symptoms_json, details, report, image_data, image_mime, chat_json, created_at, updated_at FROM agro_assessments WHERE student_id=? ORDER BY updated_at DESC",
                (student["student_id"],),
            )

            if not records:
                st.info("Your saved assessments will appear here after you complete your first plant assessment.")
            else:
                for saved_record in records:
                    record = dict(saved_record)

                    with st.container(border=True):
                        image_col, details_col, action_col = st.columns([1, 4, 1])

                        with image_col:
                            if record.get("image_data") is not None:
                                st.image(bytes(record["image_data"]), width=100)
                            else:
                                st.markdown("🌿")

                        with details_col:
                            st.markdown("**" + str(record.get("title") or "Plant Assessment") + "**")
                            st.caption(
                                str(record.get("crop") or "Crop not specified")
                                + " · "
                                + str(record.get("created_at") or "").replace("T", " ")
                            )

                        with action_col:
                            if st.button(
                                "Open",
                                key="agro_open_" + record["assessment_id"],
                                use_container_width=True,
                            ):
                                st.session_state.agro_pending_assessment = record
                                st.rerun()

    elif active_section == 'Crop Monitoring':
        st.subheader("Crop Monitoring")
        st.write("Keep track of crop conditions over time.")
        st.date_input("Observation date", value=date.today(),
                     key="agro_monitor_date")
        st.selectbox(
            "Growth stage",
            ["Unknown", "Seedling", "Vegetative", "Flowering",
             "Fruiting", "Harvest"],
            key="agro_growth_stage"
        )
        st.text_area(
            "Field notes",
            placeholder="Record weather, soil appearance, irrigation, "
                       "plant growth or changes...",
            key="agro_monitor_notes"
        )
        st.info("Persistent monitoring history is planned for the next phase.")

    elif active_section == 'Treatment Guidance':
        st.subheader("Treatment Guidance")
        st.write(
            "Explore safe, general crop-care practices "
            "based on your crop and observations."
        )
        st.markdown("""
        - Check whether symptoms are spreading.
        - Avoid unnecessary disturbance of affected plants.
        - Keep notes of recent weather and watering.
        - Avoid applying unknown treatments.
        - Seek advice from a local agriculture expert when symptoms
          are severe or the cause is unclear.
        """)
        st.caption(
            "Specific treatment recommendations require verified, "
            "crop-specific information."
        )
