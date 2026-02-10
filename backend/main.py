import os
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from operator import itemgetter

# LangChain
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from langchain_groq import ChatGroq

load_dotenv()

# ---------------- APP ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["content-type"],
)

# ---------------- GLOBAL STATE ----------------
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

retriever = None
store = {}

llm = ChatGroq(
    temperature=0.1,
    model="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY"),
)

# ---------------- PROMPTS ----------------
rewrite_prompt = ChatPromptTemplate.from_template(
    """Based on chat history and the question, rephrase the question to be self-contained.

Chat History:
{chat_history}

Question:
{question}

Standalone Search Query:"""
)

rewrite_chain = (
    rewrite_prompt
    | llm.with_config(temperature=0.0)
    | StrOutputParser()
)

answer_prompt = ChatPromptTemplate.from_template(
    """You are a helpful document analyser.

Use the context to answer accurately.
Organise the response neatly using bullet points or numbering where helpful.

Chat History:
{chat_history}

Context:
{context}

Question:
{question}

Answer:"""
)

# ---------------- HELPERS ----------------
def get_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# ---------------- MODELS ----------------
class ChatRequest(BaseModel):
    message: str
    session_id: str

# ---------------- ENDPOINTS ----------------
@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    global retriever

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, file.filename)

        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        loader = UnstructuredPDFLoader(temp_path)
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1750,
            chunk_overlap=350,
        )
        chunks = splitter.split_documents(docs)

        retriever = FAISS.from_documents(
            chunks, embeddings
        ).as_retriever(search_kwargs={"k": 3})

    return {
        "status": "success",
        "message": "document indexed successfully"
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    if not retriever:
        return {
            "reply": "Please upload a document first."
        }

    base_chain = (
    {
            "context": (
                RunnableLambda(
                    lambda x: rewrite_chain.invoke({
                        "question": x["question"],
                        "chat_history": x["chat_history"],
                    })
                )
                | retriever
                | format_docs
            ),
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        }
        | answer_prompt
        | llm
        | StrOutputParser()
    )

    rag_chain = RunnableWithMessageHistory(
        base_chain,
        get_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

    response = rag_chain.invoke(
        {"question": request.message},
        config={"configurable": {"session_id": request.session_id}},
    )

    return {"reply": response}


@app.post("/clear")
async def clear_data():
    global retriever, store
    
    # Reset the FAISS retriever
    retriever = None
    
    # Clear all chat histories in the session store
    store.clear()
    
    return {
        "status": "success", 
        "message": "Vector database and chat history have been cleared."
    }





# ---------------- RUN ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
