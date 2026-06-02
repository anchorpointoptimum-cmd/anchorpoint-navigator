import streamlit as st
import uuid
from groq import Groq

st.set_page_config(page_title="Anchorpoint Navigator", page_icon="⚓")
st.title("Anchorpoint AI Navigator")
st.caption("Diagnosing operational gaps. Stewarding certainty.")

# Intro message (once per session)
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
    
    st.markdown("""
    ***
    **💡 Tips:**
    - Add context like *"The manager is often away on Mondays"* in your answers
    - Click **✏️** next to any of your messages to edit and re-diagnose
    ***
    """)
    
    st.session_state.intro_shown = True

# API and knowledge file
api_key = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=api_key)

with open("Anchorpoint_AI_Knowledge.txt", "r") as f:
    system_content = f.read()

# Initialize conversation
if "conversation" not in st.session_state:
    st.session_state.conversation = [
        {
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": system_content + "\n\nRemember: You are a Navigator. Lead with questions.",
            "parent_id": None
        }
    ]

# Edit state
if "editing_message_id" not in st.session_state:
    st.session_state.editing_message_id = None

def regenerate_from_message(message_id):
    """Delete all messages after the given ID and regenerate assistant responses."""
    idx = None
    for i, msg in enumerate(st.session_state.conversation):
        if msg["id"] == message_id:
            idx = i
            break
    if idx is not None:
        # Truncate
        st.session_state.conversation = st.session_state.conversation[:idx+1]
        # Regenerate
        api_messages = []
        for msg in st.session_state.conversation:
            if msg["role"] != "system":
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        with st.spinner("Re‑diagnosing..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": st.session_state.conversation[0]["content"]}] + api_messages,
                temperature=0.7,
                max_tokens=500
            )
            new_reply = response.choices[0].message.content
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": new_reply,
                "parent_id": message_id
            }
            st.session_state.conversation.append(assistant_msg)
        st.rerun()

# Display conversation (skip system message)
for msg in st.session_state.conversation[1:]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "user":
            col1, col2 = st.columns([10, 1])
            with col2:
                if st.button("✏️", key=f"edit_{msg['id']}"):
                    st.session_state.editing_message_id = msg["id"]
                    st.rerun()

# Edit modal
if st.session_state.editing_message_id:
    msg_to_edit = next((m for m in st.session_state.conversation if m["id"] == st.session_state.editing_message_id), None)
    if msg_to_edit:
        with st.form(key="edit_form"):
            edited_content = st.text_area("Edit your message:", value=msg_to_edit["content"])
            if st.form_submit_button("Save and regenerate"):
                msg_to_edit["content"] = edited_content
                regenerate_from_message(msg_to_edit["id"])
                st.session_state.editing_message_id = None
                st.rerun()
        if st.button("Cancel"):
            st.session_state.editing_message_id = None
            st.rerun()

# Chat input (if not editing)
if not st.session_state.editing_message_id:
    if prompt := st.chat_input("Describe an operational process or challenge..."):
        # Add user message
        user_msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": prompt,
            "parent_id": st.session_state.conversation[-1]["id"]
        }
        st.session_state.conversation.append(user_msg)
        
        # Prepare API call
        api_messages = []
        for msg in st.session_state.conversation:
            if msg["role"] != "system":
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        
        with st.spinner("Diagnosing..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": st.session_state.conversation[0]["content"]}] + api_messages,
                temperature=0.7,
                max_tokens=500
            )
            reply = response.choices[0].message.content
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": reply,
                "parent_id": user_msg["id"]
            }
            st.session_state.conversation.append(assistant_msg)
        st.rerun()

# Summary button (appears after enough exchanges)
assistant_count = len([m for m in st.session_state.conversation if m["role"] == "assistant"])
if assistant_count >= 3 and "summary_generated" not in st.session_state:
    st.divider()
    if st.button("📋 Generate Summary"):
        conversation_text = ""
        for msg in st.session_state.conversation[1:]:
            conversation_text += f"{msg['role'].upper()}: {msg['content']}\n\n"
        with st.spinner("Generating summary..."):
            summary_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Generate a brief operational gap summary with: Gap Type, Key Insight, Suggested First Step, Relevant Asset."},
                    {"role": "user", "content": f"Conversation:\n{conversation_text}"}
                ],
                temperature=0.3,
                max_tokens=300
            )
            summary = summary_response.choices[0].message.content
            st.session_state.generated_summary = summary
            st.session_state.summary_generated = True
            st.rerun()

if "generated_summary" in st.session_state:
    st.success("Summary generated!")
    st.markdown(st.session_state.generated_summary)
    st.caption("📸 Screenshot to share")
    
    # New conversation button
    if st.button("🔄 Start New Conversation"):
        st.session_state.clear()
        st.rerun()
