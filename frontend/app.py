import streamlit as st
import requests
import uuid

# --- CONFIGURATION ---
BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="DocuMind AI", page_icon="📄")

# Initialize session state for chat history and session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- INITIALIZE EXTRA STATE ---
if "active_doc" not in st.session_state:
    st.session_state.active_doc = None
# We use a 'file_uploader_key' to force the widget to reset
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- SIDEBAR: Document Upload & Management ---
with st.sidebar:
    st.title("Settings")
    
    # Show active document status
    if st.session_state.active_doc:
        st.info(f"📁 **Active:** {st.session_state.active_doc}")
    else:
        st.warning("No document indexed.")

    # File uploader with a dynamic key
    uploaded_file = st.file_uploader(
        "Upload a PDF", 
        type="pdf", 
        key=f"pdf_uploader_{st.session_state.uploader_key}"
    )
    
    if st.button("Index Document"):
        if uploaded_file:
            with st.spinner("Processing document..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(f"{BASE_URL}/upload", files=files)
                
                if response.status_code == 200:
                    # 1. Update the active document name
                    st.session_state.active_doc = uploaded_file.name
                    
                    # --- ADD THIS LINE TO CLEAR MESSAGES ---
                    st.session_state.messages = [] 
                    
                    # 2. Increment key to "reset" the file_uploader widget
                    st.session_state.uploader_key += 1
                    st.success("Document indexed and chat cleared!")
                    st.rerun() 
                else:
                    st.error("Upload failed.")
        else:
            st.warning("Please select a file first.")

    st.markdown("---")
    
    if st.button("Clear Conversation & Index", type="secondary"):
        response = requests.post(f"{BASE_URL}/clear")
        if response.status_code == 200:
            st.session_state.messages = []
            st.session_state.active_doc = None
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

# --- MAIN CHAT INTERFACE ---
st.title("📄 DocuMind AI")
st.caption("Chat with your documents in real-time")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask something about your document..."):
    # Add user message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call FastAPI backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            payload = {
                "message": prompt,
                "session_id": st.session_state.session_id
            }
            try:
                response = requests.post(f"{BASE_URL}/chat", json=payload)
                if response.status_code == 200:
                    answer = response.json().get("reply")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error("Backend error. Make sure the document is uploaded.")
            except Exception as e:
                st.error(f"Connection failed: {e}")