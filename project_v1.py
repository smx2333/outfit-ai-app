import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import os
import time

# --- CONFIGURATION ---
st.set_page_config(
    page_title="OutfitAI: Powered by Gemini",
    page_icon="👗",
    layout="wide"
)

# --- SIDEBAR: API KEY & USER PROFILE ---
with st.sidebar:
    st.title("⚙️ Settings")
    # Securely accepting the API Key
    api_key = st.text_input("Enter Google Gemini API Key", type="password")

    # --- MODEL SELECTION (FIX FOR 404 & 429 ERRORS) ---
    available_models = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # Fetch models dynamically
            all_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]
            # Custom Sort: Prioritize 'flash' models (better rate limits) over 'pro' or 'experimental'
            available_models = sorted(all_models, key=lambda x: 0 if 'flash' in x else (1 if 'pro' in x else 2))
        except Exception as e:
            st.error(f"Key Error: {e}")

    # Default fallback if list fails
    if not available_models:
        available_models = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro-vision"]

    selected_model_name = st.selectbox(
        "Select AI Model",
        available_models,
        index=0 if available_models else 0,
        help="Tip: Select a 'flash' model (e.g., gemini-1.5-flash) for faster speed and fewer 'Quota Exceeded' errors."
    )

    st.divider()

    st.title("👤 User Profile")
    gender = st.selectbox("Gender Preference", ["Female", "Male", "Non-binary"])
    skin_tone = st.select_slider(
        "Skin Tone",
        options=["Fair", "Light", "Medium", "Tan", "Deep"],
        value="Medium"
    )
    body_type = st.selectbox("Body Shape", ["Hourglass", "Pear", "Rectangle", "Inverted Triangle", "Athletic"])


# --- GEMINI AI BACKEND ---
class GeminiStylist:
    def __init__(self, api_key, model_name):
        if not api_key:
            st.error("Please enter an API Key in the sidebar to proceed.")
            st.stop()

        genai.configure(api_key=api_key)
        # Use the user-selected model
        self.model = genai.GenerativeModel(model_name)

    def analyze_image(self, image):
        """
        Sends the uploaded image to Gemini Vision to detect the clothing item.
        Includes retry logic for 429 Rate Limit errors.
        """
        prompt = """
        Analyze this image of a clothing item. 
        Return ONLY a JSON object (no markdown, no extra text) with the following keys:
        - "category": (e.g., Top, Bottom, Dress, Shoe)
        - "color": (e.g., Navy Blue, Beige)
        - "style": (e.g., Casual, Formal, Bohemian, Streetwear)
        - "description": (A short visual description of the texture and fit)
        """

        retries = 3
        for attempt in range(retries):
            try:
                response = self.model.generate_content([prompt, image])
                # Clean up response to ensure valid JSON
                clean_text = response.text.strip().replace("```json", "").replace("```", "")
                return json.loads(clean_text)

            except Exception as e:
                error_msg = str(e)
                # Check for Rate Limit (429)
                if "429" in error_msg:
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)  # Wait 1s, then 2s
                        continue
                    else:
                        st.error("Quota Exceeded (429): You are sending requests too fast or using a restricted model.")
                        st.info("Tip: Switch to a 'flash' model in the sidebar.")
                        return None
                else:
                    st.error(f"AI Vision Error: {e}")
                    st.info(
                        f"Tip: The model '{self.model.model_name}' failed. Try selecting a different model in the sidebar settings.")
                    return None

    def generate_advice(self, user_item, context, user_profile):
        """
        Sends the item data + user context to Gemini to get styling advice.
        """
        # Construct a detailed prompt for the 'Explainable AI' part
        prompt = f"""
        You are an expert fashion stylist.

        **USER PROFILE:**
        - Gender: {user_profile['gender']}
        - Skin Tone: {user_profile['skin_tone']} (Consider color theory)
        - Body Type: {user_profile['body_type']} (Consider silhouette)

        **THE ITEM:**
        - Category: {user_item['category']}
        - Color: {user_item['color']}
        - Style: {user_item['style']}
        - Description: {user_item['description']}

        **THE SCENARIO:**
        - Occasion: {context['occasion']}
        - Weather: {context['weather']}

        **YOUR TASK:**
        1. Recommend 2 specific items to pair with this (e.g., "Pair with white linen trousers...").
        2. Explain WHY this works (Color Theory & Silhouette).
        3. Give a specific styling tip (e.g., "Tuck it in", "Roll sleeves").

        Keep the tone encouraging, stylish, and concise.
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Sorry, I couldn't generate advice right now. Error: {e}"


# --- MAIN UI ---
st.title("✨ OutfitAI: Your Personal Stylist")
st.caption("Powered by Google Gemini")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Upload & Context")
    uploaded_file = st.file_uploader("Upload a photo of your cloth", type=['jpg', 'png', 'jpeg'])

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Your Item", use_container_width=True)

    st.divider()

    occasion = st.selectbox("Occasion",
                            ["Casual Day Out", "Date Night", "Job Interview", "Wedding Guest", "Gym/Active"])
    weather = st.selectbox("Weather", ["Sunny & Hot", "Mild/Spring", "Cold/Rainy", "Freezing"])

    generate_btn = st.button("✨ Get Styling Advice", type="primary", use_container_width=True)

with col2:
    if generate_btn and uploaded_file and api_key:
        # Initialize AI with SELECTED MODEL
        stylist = GeminiStylist(api_key, selected_model_name)

        with st.status("Consulting the AI Stylist...", expanded=True) as status:

            # Step 1: Vision Analysis
            st.write(f"👁️ Analyzing with {selected_model_name}...")
            item_data = stylist.analyze_image(image)

            if item_data:
                st.write(f"✅ Detected: **{item_data['color']} {item_data['style']} {item_data['category']}**")

                # Step 2: Reasoning & Advice
                st.write("🧠 Generating style recommendations...")
                user_profile = {"gender": gender, "skin_tone": skin_tone, "body_type": body_type}
                context = {"occasion": occasion, "weather": weather}

                advice = stylist.generate_advice(item_data, context, user_profile)

                status.update(label="Styling Complete!", state="complete", expanded=False)

                # Display Results
                st.subheader("Your Styled Look")
                st.markdown(advice)