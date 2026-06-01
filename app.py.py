import streamlit as st
import os
from groq import Groq

st.set_page_config(page_title="Anchorpoint Navigator", page_icon="⚓")
st.title("Anchorpoint AI Navigator")
st.caption("Diagnosing operational gaps. Stewarding certainty.")

# Get API key from Streamlit secrets (you'll set this on the cloud)
api_key = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=api_key)

# Load your knowledge file (must be uploaded to GitHub alongside this script)
with open("Anchorpoint_AI_Knowledge.txt", "r") as f:
    system_content = f.read()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": system_content + "\n\nRemember: You are a Navigator. Lead with questions."}
    ]

# Display previous messages
for msg in st.session_state.messages[1:]:
    st.chat_message(msg["role"]).write(msg["content"])

# Chat input
if prompt := st.chat_input("Describe an operational process or challenge..."):
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.spinner("Diagnosing..."):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=st.session_state.messages,
            temperature=0.7,
            max_tokens=500
        )
        reply = response.choices[0].message.content
        st.chat_message("assistant").write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})