from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.runnables import RunnableParallel, RunnableLambda, RunnablePassthrough
from langchain_community.llms import HuggingFaceEndpoint


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



