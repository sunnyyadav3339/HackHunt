from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# loading the hackathon data 
loader = CSVLoader(
    file_path="data.csv",
    source_column="name"  # This will be shown as the source in metadata
)

documents = loader.load()

# indexing and chunking 

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
split_docs = text_splitter.split_documents(documents)


# Generating the embeddings and storing them in vectorstore

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = FAISS.from_documents(split_docs, embedding_model)
vectorstore.save_local("hackathon_faiss_index")


# retrieving the relevant docs 
vectorstore = FAISS.load_local("hackathon_faiss_index", embedding_model, allow_dangerous_deserialization=True)

retriever = vectorstore.as_retriever(search_kwargs={"k": 5})  


# Generating the response
llm = ChatOllama(model="llama3.2")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

prompt = PromptTemplate.from_template("""
Answer the following question based on the context below.
If the answer cannot be found in the context, answer based on your knowledge.

Context:
{context}

Question:
{question}
""")

parallel_chain = RunnableParallel({
    "context": retriever | format_docs,
    "question": RunnablePassthrough()
})

main_chain = parallel_chain | prompt | llm | StrOutputParser()


print("🤖 Ask me anything about upcoming hackathons! (type 'exit' to quit)\n")

while True:
    user_query = input("🟢 You: ")
    if user_query.lower() in ["exit", "quit"]:
        print("👋 Chat ended.")
        break

    try:
        response = main_chain.invoke(user_query)
        print(f"🤖 Bot: {response}\n")
    except Exception as e:
        print(f"⚠️ Error: {e}\n")

