import chainlit as cl
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os

main_chain = None
vectorstore = None
retriever = None

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

async def setup_rag_chain():
    global main_chain, vectorstore, retriever
    
    try:
        if os.path.exists("hackathon_faiss_index"):
            
            # Load embeddings
            embedding_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            
            # Load vectorstore
            vectorstore = FAISS.load_local(
                "hackathon_faiss_index", 
                embedding_model, 
                allow_dangerous_deserialization=True
            )
            
        else:
            
            if not os.path.exists("data.csv"):
                await cl.Message(
                    content="❌ Error: 'data.csv' file not found. Please ensure the CSV file is in the same directory as this script."
                ).send()
                return False
            
            # Load CSV data
            loader = CSVLoader(
                file_path="data.csv",
                source_column="name"
            )
            documents = loader.load()
            
            # Split documents
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
            )
            split_docs = text_splitter.split_documents(documents)
            
            # Create embeddings
            embedding_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            
            # Create and save vectorstore
            vectorstore = FAISS.from_documents(split_docs, embedding_model)
            vectorstore.save_local("hackathon_faiss_index")
        
        # Setup retriever
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        
        # Setup LLM
        llm = ChatOllama(model="llama3.2")
        
        # Create prompt template
        prompt = PromptTemplate.from_template("""
Answer the following question based on the context below.
If the answer cannot be found in the context, answer based on your knowledge.

Context:
{context}

Question:
{question}
""")
        
        # Create the chain
        parallel_chain = RunnableParallel({
            "context": retriever | format_docs,
            "question": RunnablePassthrough()
        })
        
        main_chain = parallel_chain | prompt | llm | StrOutputParser()
        return True
        
    except Exception as e:
        await cl.Message(content=f"❌ Error initializing RAG system: {str(e)}").send()
        return False

@cl.on_chat_start
async def start():
    await cl.Message(content="🤖 Welcome to the HackHunt!").send()
    
    success = await setup_rag_chain()
    
    if success:
        await cl.Message(
            content="🚀 I'm ready to answer questions about upcoming hackathons! Ask me anything!"
        ).send()
    else:
        await cl.Message(
            content="Sorry but I'm sleeping..."
        ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    global main_chain
    
    if main_chain is None:
        await cl.Message(
            content="System not initialized. Please refresh the page and try again."
        ).send()
        return
    
    thinking_msg = cl.Message(content="Preparing response...")
    await thinking_msg.send()
    
    try:
        response = await main_chain.ainvoke(message.content)
        
        thinking_msg.content = f"🤖 **Answer:**\n\n{response}"
        await thinking_msg.update()
        
    
    except Exception as e:
        thinking_msg.content = f"❌ Error processing your question: {str(e)}"
        await thinking_msg.update()


@cl.on_stop
def stop():
    """Cleanup when chat stops"""
    print("Chat session ended")
