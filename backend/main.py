import os
import shutil
import tempfile # Added for secure temporary handling
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# LangChain Imports
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from operator import itemgetter

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = None
retriever = None
store = {}

llm = ChatGroq(
    temperature=0.1,
    model="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# --- Logic Chains ---
rewrite_prompt = ChatPromptTemplate.from_template(
    "Based on chat history and the question, rephrase the question to be self-contained for resume search.\n\nChat History:\n{chat_history}\n\nQuestion: {question}\n\nStandalone Search Query:"
)
rewrite_chain = rewrite_prompt | llm.with_config(temperature=0.0) | StrOutputParser()

prompt = ChatPromptTemplate.from_template(
    "You are a helpful resume analyst. Use the context to answer accurately.\n\nChat History: {chat_history}\nContext: {context}\nQuestion: {question}\nAnswer:"
)

def get_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

class ChatRequest(BaseModel):
    message: str
    session_id: str

# --- Endpoints ---

@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    global vectorstore, retriever
    
    # tempfile.TemporaryDirectory creates a secure folder outside your project
    # that is automatically deleted when the 'with' block ends.
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        # Write the uploaded content to the temp folder
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Load and Index (Text extraction happens here)
        loader = UnstructuredPDFLoader(temp_file_path)
        docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1750, chunk_overlap=350)
        chunks = text_splitter.split_documents(docs)
        
        # Create vectorstore in memory
        vectorstore = FAISS.from_documents(chunks, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        
    # At this point, the temp_dir and the file inside it are DELETED from the disk.
    return {"status": "success", "message": "Content extracted and indexed. File deleted."}

@app.post("/chat")
async def chat(request: ChatRequest):
    global retriever
    if not retriever:
        return {"reply": "I don't have any resume data yet. Please upload a file first!"}

    base_chain = (
        {
            "context": (
                RunnablePassthrough() 
                | RunnableLambda(lambda x: rewrite_chain.invoke({
                    "question": x["question"], 
                    "chat_history": x["chat_history"]
                })) 
                | retriever 
                | format_docs
            ),
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        }
        | prompt | llm | StrOutputParser()
    )

    rag_chain = RunnableWithMessageHistory(
        base_chain,
        get_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

    config = {"configurable": {"session_id": request.session_id}}
    response = rag_chain.invoke({"question": request.message}, config)
    
    return {"reply": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)