from io import BytesIO
import json
import math
import struct
import wave
from threading import Lock
from time import monotonic
import os

import truststore
truststore.inject_into_ssl()
import requests

import streamlit as st
from PIL import Image
from streamlit_webrtc import VideoProcessorBase, WebRtcMode, webrtc_streamer


def _identify_with_plantnet(image_bytes):
    api_key = os.getenv("PLANTNET_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PLANTNET_API_KEY is missing from the environment.")

    try:
        response = requests.post(
            "https://my-api.plantnet.org/v2/identify/all",
            params={"api-key": api_key},
            files={"images": ("agrobridge-frame.jpg", image_bytes, "image/jpeg")},
            data={"organs": "auto"},
            timeout=45,
        )
        if not response.ok:
            detail = " ".join(response.text.split())[:300]
            raise RuntimeError(
                f"Pl@ntNet HTTP {response.status_code}: {detail or 'No error details supplied.'}"
            )
        payload = response.json()
    except requests.exceptions.RequestException:
        raise RuntimeError(
            "Could not connect to Pl@ntNet. Check your internet connection."
        ) from None
    except ValueError:
        raise RuntimeError("Pl@ntNet returned an unreadable response.") from None

    candidates = []
    for item in payload.get("results", [])[:5]:
        species = item.get("species") or {}
        scientific_name = species.get("scientificNameWithoutAuthor") or "Unknown"
        common_names = species.get("commonNames") or []
        score = item.get("score", 0)

        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score = 0.0

        candidates.append({
            "scientific_name": str(scientific_name),
            "common_names": [str(name) for name in common_names[:3]],
            "score": score,
        })

    return candidates


def _create_alert_tone():
    sample_rate = 22050
    duration = 0.42
    frequency = 880
    total = int(sample_rate * duration)
    frames = bytearray()

    for i in range(total):
        envelope = min(1.0, i / (sample_rate * 0.02),
                       (total - i) / (sample_rate * 0.04))
        sample = int(
            10000 * envelope *
            math.sin(2 * math.pi * frequency * i / sample_rate)
        )
        frames.extend(struct.pack("<h", sample))

    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(bytes(frames))

    return buffer.getvalue()


_ALERT_AUDIO = _create_alert_tone()


class PlantFrameProcessor(VideoProcessorBase):
    def __init__(self):
        self._lock = Lock()
        self._latest_frame = None
        self._frame_id = 0
        self._last_encode_time = 0.0

    def recv(self, frame):
        try:
            now = monotonic()
            if now - self._last_encode_time < 1.0:
                return frame

            image = Image.fromarray(frame.to_ndarray(format="rgb24"))
            image.thumbnail((960, 960))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=65)
            encoded = buffer.getvalue()

            with self._lock:
                self._latest_frame = encoded
                self._frame_id += 1
                self._last_encode_time = now
        except Exception:
            pass
        return frame

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame, self._frame_id


def render_live_scanner(gemini_generate):
    st.subheader("Live Plant Scanner")
    st.write(
        "Keep a leaf in view. AgroBridge periodically inspects "
        "the camera feed and updates its observations automatically."
    )

    crop = st.selectbox(
        "Choose the crop",
        ["Auto-identify from image", "Tomato", "Potato", "Rice", "Wheat", "Cotton", "Maize", "Chilli", "Other"],
        key="agro_live_crop"
    )

    enable_scanner = st.checkbox(
        "Enable Live Camera Scanning",
        value=False,
        key="agro_live_scanner_enabled"
    )

    if not enable_scanner:
        st.info("The camera is off. Enable scanning when you are ready.")
        return

    st.checkbox(
        "Enable sound alerts",
        value=False,
        key="agro_live_sound_enabled"
    )

    ctx = webrtc_streamer(
        key="agro_live_scanner_webrtc",
        mode=WebRtcMode.SENDRECV,
        video_processor_factory=PlantFrameProcessor,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True
    )

    st.caption("Allow camera permission when your browser prompts you.")

    if not ctx.state.playing:
        st.info("Start the camera to begin automatic plant observation.")
        return

    processor_for_id = ctx.video_processor
    if st.button("Identify Plant with Pl@ntNet", key="agro_plantnet_identify"):
        if processor_for_id is None:
            st.warning("The camera processor is not ready yet.")
        else:
            captured_bytes, captured_id = processor_for_id.get_latest_frame()
            if not captured_bytes:
                st.warning("Waiting for a clear camera frame. Try again in a moment.")
            else:
                try:
                    with st.spinner("Identifying the plant with Pl@ntNet..."):
                        matches = _identify_with_plantnet(captured_bytes)
                    st.session_state["agro_plantnet_result"] = {
                        "frame_id": captured_id,
                        "candidates": matches,
                    }
                except Exception as exc:
                    st.error(f"Plant identification unavailable: {exc}")

    latest_result = st.session_state.get("agro_plantnet_result")
    if latest_result:
        st.markdown("#### Latest Pl@ntNet plant matches")
        st.caption(
            f"Based on camera frame {latest_result.get('frame_id', 'unknown')}. "
            "This is a tentative identification."
        )
        matches = latest_result.get("candidates", [])
        if not matches:
            st.info("Pl@ntNet did not return a plant match for this frame.")
        else:
            for index, match in enumerate(matches, start=1):
                common = ", ".join(match["common_names"]) or "No common name supplied"
                st.write(
                    f"{index}. **{common}** — {match['scientific_name']} "
                    f"({match['score']:.1%} similarity)"
                )
            st.caption(
                "Similarity scores are not guaranteed probabilities or confirmed identifications."
            )

    @st.fragment(run_every="12s")
    def automatic_observation():
        processor = ctx.video_processor
        if processor is None:
            st.info("Waiting for the camera feed...")
            return

        frame_bytes, frame_id = processor.get_latest_frame()
        if not frame_bytes:
            st.info("Waiting for the first camera frame...")
            return

        previous_id = st.session_state.get("agro_live_last_frame_id", -1)
        if frame_id == previous_id:
            st.caption("Waiting for a fresh camera frame...")
            return

        st.session_state.agro_live_last_frame_id = frame_id

        plantnet_context = "No Pl@ntNet reference is available."
        plantnet_result = st.session_state.get("agro_plantnet_result")
        if plantnet_result:
            matches = plantnet_result.get("candidates", [])
            if matches:
                plantnet_context = (
                    "Tentative matches from an earlier manually selected camera frame: "
                    + "; ".join(
                        f"{item['scientific_name']} ({item['score']:.1%} similarity)"
                        for item in matches
                    )
                )

        prompt = f"""You are AgroBridge, an educational plant-health observation assistant.
Farmer crop selection: {crop}
Optional Pl@ntNet context: {plantnet_context}
Treat Pl@ntNet matches as tentative reference information, not confirmed identity.
Assess visible plant-health symptoms independently of plant identification.
Inspect the attached live camera frame carefully.

Return ONLY one valid JSON object with these exact keys:
{{
  "plant_identification": "Likely plant or uncertain",
  "visible_observations": "What is visibly observed",
  "severity": "healthy, caution, high_concern, or uncertain",
  "alert_reason": "Short reason for a warning, or empty string",
  "possible_causes": "Possible explanations, clearly marked as uncertain",
  "safe_next_steps": "Practical, safe next steps"
}}

Severity rules:
- healthy: no obvious concerning symptoms visible.
- caution: a visible sign that deserves monitoring, but is not clearly severe.
- high_concern: clearly concerning visible symptoms that deserve prompt expert inspection.
- uncertain: image is unclear, plant is not visible, or evidence is insufficient.

Do not diagnose a confirmed disease from an image.
Do not claim to predict future disease or guarantee disease-free crops.
Do not infer actual soil nutrient levels from a photograph.
Do not prescribe pesticides, dosages, mixtures, or chemical application instructions.
If uncertain, use severity uncertain and do not trigger a disease warning.
Use simple, concise language. Ensure the JSON is valid."""

        try:
            with st.spinner("Observing the latest camera frame..."):
                result = gemini_generate(
                    prompt,
                    temperature=0.2,
                    max_output_tokens=700,
                    image_bytes=frame_bytes,
                    mime_type="image/jpeg"
                )

            response_text = str(result).strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[-1]
                if response_text.endswith("```"):
                    response_text = response_text[:-3].strip()

            json_start = response_text.find("{")
            json_end = response_text.rfind("}")
            if json_start < 0 or json_end <= json_start:
                raise ValueError("The AI response did not contain valid JSON.")

            observation = json.loads(response_text[json_start:json_end + 1])
            if not isinstance(observation, dict):
                raise ValueError("Unexpected AI response format.")

            severity = str(observation.get("severity", "uncertain")).lower()
            if severity not in {"healthy", "caution", "high_concern", "uncertain"}:
                severity = "uncertain"

            st.markdown("#### Latest plant observation")
            st.markdown(
                f"**Plant identification:** "
                f"{observation.get('plant_identification', 'Uncertain')}"
            )
            st.markdown(
                f"**Visible observations:** "
                f"{observation.get('visible_observations', 'Not provided')}"
            )

            if severity == "healthy":
                st.success("No obvious warning signs detected in this frame.")
            elif severity == "caution":
                st.warning("CAUTION — Visible symptoms need monitoring.")
            elif severity == "high_concern":
                st.error("HIGH CONCERN — Prompt expert inspection is recommended.")
            else:
                st.info("UNCERTAIN — The image does not provide enough evidence for a reliable warning.")

            if observation.get("alert_reason"):
                st.markdown(f"**Warning reason:** {observation['alert_reason']}")

            st.markdown(
                f"**Possible causes:** "
                f"{observation.get('possible_causes', 'Not established')}"
            )
            st.markdown(
                f"**Safe next steps:** "
                f"{observation.get('safe_next_steps', 'Inspect the plant again in clear lighting.')}"
            )

            sound_enabled = st.session_state.get("agro_live_sound_enabled", False)
            if severity in {"caution", "high_concern"}:
                signature = (
                    severity + "|" +
                    str(observation.get("alert_reason", "")).strip().lower()
                )
                now = monotonic()
                previous_signature = st.session_state.get(
                    "agro_live_last_alert_signature", ""
                )
                previous_time = st.session_state.get(
                    "agro_live_last_alert_time", 0.0
                )

                if signature != previous_signature or now - previous_time >= 180:
                    st.markdown("**<span style='color:#B45309'>Audible warning generated</span>**", unsafe_allow_html=True)
                    st.audio(
                        _ALERT_AUDIO,
                        format="audio/wav",
                        autoplay=bool(sound_enabled)
                    )
                    st.session_state.agro_live_last_alert_signature = signature
                    st.session_state.agro_live_last_alert_time = now

            st.caption(
                "AI-assisted visual observation, not a confirmed diagnosis. "
                "Frames are sampled periodically, not analysed continuously."
            )

        except Exception as exc:
            st.error(f"Live observation failed: {exc}")
            st.info("No automatic disease alert was triggered because the observation could not be reliably classified.")

    automatic_observation()
