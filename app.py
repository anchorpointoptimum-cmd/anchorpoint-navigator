import streamlit as st
import os
from groq import Groq

st.set_page_config(page_title="Anchorpoint Navigator", page_icon="⚓")
st.title("Anchorpoint AI Navigator")
st.caption("Diagnosing operational gaps. Stewarding certainty.")

# Step 1: Intro message
if "intro_shown" not in st.session_state:
    intro_message = """**How this works:**

I'll ask you 3–5 diagnostic questions about an operational process or challenge you're facing.

At the end, I'll give you a one‑page summary you can screenshot or share:
- The gap type we identified
- A key insight from our conversation
- A suggested first governance step

No jargon. No rushed solutions. Just clarity.

Ready? Describe your process or challenge below."""
    
    st.info(intro_message)
    
    # Step 2: Tip for adding context
    st.markdown("""
    ***
    **💡 Tip:** You can add helpful context to any answer, like:
    - *"The store manager is often away on Mondays"*
    - *"This happens mostly during night shifts"*
    - *"We've tried fixing this before but it didn't stick"*
    
    Just type your context in the same message as your answer.
    ***
    """)
    
    st.session_state.intro_shown = True

# API and knowledge file setup
api_key = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=api_key)

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

# Step 3: End-of-conversation summary
if len(st.session_state.messages) >= 8:
    if "summary_generated" not in st.session_state:
        st.divider()
        st.markdown("### 📋 Ready for your operational summary?")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Generate Summary", key="generate_summary"):
                conversation_text = ""
                for msg in st.session_state.messages[1:]:
                    conversation_text += f"{msg['role'].upper()}: {msg['content']}\n\n"
                
                with st.spinner("Generating your operational summary..."):
                    summary_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": """You are Anchorpoint's summary engine. Based on the conversation, generate a brief, clear summary with exactly these sections:

**Gap Type:** [E/K/SC/CD/WE] – [full name]

**Key Insight:** [one sentence capturing the core issue]

**Suggested First Step:** [one actionable governance step, from the 90-Day Lift Framework]

**Relevant Anchorpoint Asset:** [e.g., Nigerian Process Library – WhatsApp Approvals, GAS metrics, etc.]

Keep it short. No fluff. Use bullet points where helpful."""},
                            {"role": "user", "content": f"Conversation:\n{conversation_text}\n\nGenerate summary."}
                        ],
                        temperature=0.3,
                        max_tokens=300
                    )
                    summary = summary_response.choices[0].message.content
                    st.session_state.generated_summary = summary
                    st.session_state.summary_generated = True
                    st.rerun()
        
        with col2:
            if st.button("🔁 Continue Diagnosis", key="continue_diagnosis"):
                st.session_state.summary_skipped = True
                st.rerun()
        
        if "generated_summary" in st.session_state:
            st.success("✅ Summary generated!")
            st.markdown(st.session_state.generated_summary)
            st.caption("📸 Screenshot this summary to share with your team.")
            
            if st.button("🔄 Start New Conversation"):
                st.session_state.messages = [
                    {"role": "system", "content": system_content + "\n\nRemember: You are a Navigator. Lead with questions."}
                ]
                st.session_state.summary_generated = False
                st.session_state.summary_skipped = False
                st.rerun()

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
