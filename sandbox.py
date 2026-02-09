from langchain_community.vectorstores import FAISS #for storing embedded chunks
from langchain_huggingface import HuggingFaceEmbeddings #for embedding the chunks and query
from langchain_community.document_loaders import UnstructuredPDFLoader #extracting texts from pdf
from langchain_core.prompts import ChatPromptTemplate #crafting prompt
from langchain_core.output_parsers import StrOutputParser #extracts the text content from a chat model response (like AIMessage) and returns it as a plain string
from langchain_groq import ChatGroq #used for LLM
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter #chunking
from dotenv import load_dotenv
import os
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from operator import itemgetter


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

# Load → Split → Embed → FAISS (your existing code, cleaned up)
loader = UnstructuredPDFLoader(r"c:\Users\booong\Downloads\Resume.pdf")
docs = loader.load()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1750, chunk_overlap=350)
chunks = text_splitter.split_documents(docs)

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = FAISS.from_documents(chunks, embeddings)  # Simpler: pass Documents directly

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# RAG Chain with Groq LLM
llm = ChatGroq(
    temperature=0.1,
    model="llama-3.3-70b-versatile",  # Or "mixtral-8x7b-32768"
    groq_api_key=api_key
)


rewrite_prompt = ChatPromptTemplate.from_template("""
Based on chat history and the question, rephrase the question to be self-contained and specific for resume search.

Chat History:
{chat_history}

Question: {question}

Standalone Search Query:""")


rewrite_chain = (
    rewrite_prompt 
    | llm.with_config(temperature=0.0)  # Deterministic rewrites
    | StrOutputParser()
)


prompt = ChatPromptTemplate.from_template("""
You are a helpful resume analyst. Use the following resume sections to answer questions accurately.
Only use info from the context. Be concise and specific.

Chat History: 
{chat_history}

Context: {context}

Question: {question}

Answer:""")

# History store and getter
store: dict[str, ChatMessageHistory] = {}

def get_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# Full RAG chain: Retrieve → Format → LLM → Parse
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Base chain (takes question str, outputs answer str)
base_chain = (
    {
        "context": (
            RunnablePassthrough()  # Pass all inputs (question + chat_history)
            | RunnableLambda(lambda x: rewrite_chain.invoke({
                "question": x["question"], 
                "chat_history": x["chat_history"]
            }))  # Rewrite question using history → "Years of Python?" → "How many years Python experience?"
            | retriever      # Now search with rewritten query!
            | format_docs
        ),
        "question": itemgetter("question"),    # Original for final answer
        "chat_history": itemgetter("chat_history"),  # For conversation flow
    }
    | prompt
    | llm
    | StrOutputParser()
)

# Add memory wrapper
rag_chain = RunnableWithMessageHistory(
    base_chain,
    get_history,
    input_messages_key="question",
    history_messages_key="chat_history",
)


config = {"configurable":{"session_id":"resume_session"}}
print("=== Resume Analyst ===")
print("Loaded resume from: c:\\Users\\booong\\Downloads\\Resume.pdf")

while True:
    query = input("You: ").strip()
    # ...
    if query:
        print("Analyst: ", end="", flush=True)
        response = rag_chain.invoke({"question":query},config)  # Pass config!
        print(response)
