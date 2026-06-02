import streamlit as st
import os
import uuid
import sqlite3
import json
from datetime import datetime
from groq import Groq

st.set_page_config(page_title="Anchorpoint Navigator", page_icon="⚓")
st.title("Anchorpoint AI Navigator")
st.caption("Diagnosing operational gaps. Stewarding certainty.")

# --- Database setup ---
def init_db():
    conn = sqlite3.connect('conversations.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (session_id TEXT PRIMARY KEY, created_at TIMESTAMP, last_active TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, 
                  parent_id TEXT, timestamp TIMESTAMP, FOREIGN KEY(session_id) REFERENCES sessions(session_id))''')
    conn.commit()
    conn.close()

def get_or_create_session():
    # Check URL parameter for session_id
    query_params = st.query_params
    session_id = query_params.get("session", None)
    
    if session_id:
        # Verify session exists in DB
        conn = sqlite3.connect('conversations.db')
        c = conn.cursor()
        c.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
        if c.fetchone():
            # Update last_active
            c.execute("UPDATE sessions SET last_active = ? WHERE session_id = ?", 
                     (datetime.now(), session_id))
            conn.commit()
            conn.close()
            return session_id
        conn.close()
    
    # Check local storage via JavaScript
    if "session_id" not in st.session_state:
        # Generate new session
        new_session = str(uuid.uuid4())
        st.session_state.session_id = new_session
        conn = sqlite3.connect('conversations.db')
        c = conn.cursor()
        c.execute("INSERT INTO sessions (session_id, created_at, last_active) VALUES (?, ?, ?)",
                 (new_session, datetime.now(), datetime.now()))
        conn.commit()
        conn.close()
        # Set URL parameter
        st.query_params["session"] = new_session
        return new_session
    else:
        return st.session_state.session_id

def save_message(message_id, session_id, role, content, parent_id):
    conn = sqlite3.connect('conversations.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO messages (id, session_id, role, content, parent_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
             (message_id, session_id, role, content, parent_id, datetime.now()))
    conn.commit()
    conn.close()

def load_conversation(session_id):
    conn = sqlite3.connect('conversations.db')
    c = conn.cursor()
    c.execute("SELECT id, role, content, parent_id FROM messages WHERE session_id = ? ORDER BY timestamp", (session_id,))
    rows = c.fetchall()
    conn.close()
    
    conversation = []
    for row in rows:
        conversation.append({
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "parent_id": row[3]
        })
    return conversation

# Initialize DB
init_db()

# Get or create session
session_id = get_or_create_session()

# Show intro message only once per session
if "intro_shown" not in st.session_state:
    intro_message = """**How this works:**

I'll ask you 3–5 diagnostic questions about an operational process or challenge you're facing.

At the end, I'll give you a one‑page summary you can screenshot or share:
- The gap type we identified
- A key insight from our conversation
- A suggested first governance step

No jargon. No rushed solutions. Just clarity.

**✨ New in v2:** Your conversation is saved automatically. Share this link to continue the same conversation on another device:
`https://anchorpoint-navigator.streamlit.app/?session=`""" + session_id

    st.info(intro_message)
    
    st.markdown("""
    ***
    **💡 Tips:**
    - Add context like *"The manager is often away on Mondays"* in your answers
    - Click **✏️** next to any of your messages to edit and re-diagnose
    - Bookmark this page to return to this conversation later
    ***
    """)
    
    st.session_state.intro_shown = True

# API and knowledge file setup
api_key = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=api_key)

with open("Anchorpoint_AI_Knowledge.txt", "r") as f:
    system_content = f.read()

# Load existing conversation from DB
if "conversation_loaded" not in st.session_state:
    db_conversation = load_conversation(session_id)
    if db_conversation:
        # Add system message at the beginning
        system_msg = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": system_content + "\n\nRemember: You are a Navigator. Lead with questions.",
            "parent_id": None
        }
        st.session_state.conversation = [system_msg] + db_conversation
    else:
        st.session_state.conversation = [
            {
                "id": str(uuid.uuid4()),
                "role": "system",
                "content": system_content + "\n\nRemember: You are a Navigator. Lead with questions.",
                "parent_id": None
            }
        ]
    st.session_state.conversation_loaded = True

# Track edit state
if "editing_message_id" not in st.session_state:
    st.session_state.editing_message_id = None

def regenerate_from_message(message_id):
    """Delete all messages after the given message ID and regenerate responses."""
    idx = None
    for i, msg in enumerate(st.session_state.conversation):
        if msg["id"] == message_id:
            idx = i
            break
    
    if idx is not None:
        # Keep messages up to and including the edited message
        st.session_state.conversation = st.session_state.conversation[:idx + 1]
        
        # Delete from database
        conn = sqlite3.connect('conversations.db')
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ? AND timestamp > (SELECT timestamp FROM messages WHERE id = ?)",
                 (session_id, message_id))
        conn.commit()
        conn.close()
        
        # Regenerate responses from this point
        conversation_for_api = []
        for msg in st.session_state.conversation:
            conversation_for_api.append({"role": msg["role"], "content": msg["content"]})
        
        with st.spinner("Re‑diagnosing..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=conversation_for_api,
                temperature=0.7,
                max_tokens=500
            )
            new_reply = response.choices[0].message.content
            
            # Add assistant's new response
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": new_reply,
                "parent_id": message_id
            }
            st.session_state.conversation.append(assistant_msg)
            save_message(assistant_msg["id"], session_id, assistant_msg["role"], 
                        assistant_msg["content"], assistant_msg["parent_id"])
        
        st.rerun()

# Display conversation (skip system message)
for msg in st.session_state.conversation[1:]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        
        # Show edit button for user messages only
        if msg["role"] == "user":
            col1, col2 = st.columns([10, 1])
            with col2:
                if st.button("✏️", key=f"edit_{msg['id']}"):
                    st.session_state.editing_message_id = msg["id"]
                    st.rerun()

# Edit modal
if st.session_state.editing_message_id:
    msg_to_edit = None
    for msg in st.session_state.conversation:
        if msg["id"] == st.session_state.editing_message_id:
            msg_to_edit = msg
            break
    
    if msg_to_edit:
        with st.form(key="edit_form"):
            edited_content = st.text_area("Edit your message:", value=msg_to_edit["content"])
            submitted = st.form_submit_button("Save and regenerate")
            
            if submitted:
                # Update the message content
                msg_to_edit["content"] = edited_content
                save_message(msg_to_edit["id"], session_id, msg_to_edit["role"], 
                           edited_content, msg_to_edit["parent_id"])
                # Regenerate from this point
                regenerate_from_message(msg_to_edit["id"])
                st.session_state.editing_message_id = None
                st.rerun()
        
        if st.button("Cancel"):
            st.session_state.editing_message_id = None
            st.rerun()

# Chat input (only show if not editing)
if not st.session_state.editing_message_id:
    if prompt := st.chat_input("Describe an operational process or challenge..."):
        # Add user message
        user_msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": prompt,
            "parent_id": st.session_state.conversation[-1]["id"] if st.session_state.conversation else None
        }
        st.session_state.conversation.append(user_msg)
        save_message(user_msg["id"], session_id, user_msg["role"], user_msg["content"], user_msg["parent_id"])
        
        # Prepare API messages (linear, from root to latest)
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
            
            # Add assistant message
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": reply,
                "parent_id": user_msg["id"]
            }
            st.session_state.conversation.append(assistant_msg)
            save_message(assistant_msg["id"], session_id, assistant_msg["role"], 
                        assistant_msg["content"], assistant_msg["parent_id"])
        
        st.rerun()

# New conversation button
if len(st.session_state.conversation) > 1:
    st.sidebar.divider()
    if st.sidebar.button("🆕 Start New Conversation"):
        # Create new session
        new_session = str(uuid.uuid4())
        st.query_params["session"] = new_session
        st.session_state.clear()
        st.rerun()
    
    # Show current session ID for sharing
    st.sidebar.caption(f"Session ID: `{session_id[:8]}...`")
    st.sidebar.caption("Share this link to continue the same conversation:")
    st.sidebar.code(f"{st.get_option('server.baseUrlPath')}?session={session_id}")

# End-of-conversation summary
if len([m for m in st.session_state.conversation if m["role"] == "assistant"]) >= 3:
    if "summary_generated" not in st.session_state:
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
