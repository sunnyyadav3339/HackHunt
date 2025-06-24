from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.runnables import RunnableParallel, RunnableLambda, RunnablePassthrough
from langchain_community.llms import HuggingFaceEndpoint


import os
os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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"


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


llm = HuggingFaceEndpoint(
    repo_id="tiiuae/falcon-7b-instruct",
    task="text-generation",
)



prompt = PromptTemplate.from_template("""
You are a helpful assistant that answers questions about hackathons.
Use the context below to answer the question. If the context is not helpful or insufficient, use your own knowledge.
Context:
{context}
Question:
{question}
Answer in a clear and friendly tone:
""".strip())

output_parser = StrOutputParser()

def format_docs(docs):
    return "\n\n".join([doc.page_content for doc in docs])

# Fix: Extract question and pass to retriever
question_to_context = RunnableLambda(lambda x: x["question"]) | retriever | RunnableLambda(format_docs)

# Parallel chain
parallel_chain = RunnableParallel({
    "context": question_to_context,
    "question": RunnableLambda(lambda x: x["question"])
})

rag_chain = (
    parallel_chain
    | prompt
    | llm
    | output_parser
)


query = "Any AI hackathons in July?"

response = rag_chain.invoke({"question": query})
print("🤖", response)
