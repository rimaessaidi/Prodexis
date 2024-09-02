import os
import sqlite3
import openai
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

# Define your prompt template
general_system_template = r"""
You are a virtual assistant with access to a wide range of products data. Your goal is to provide helpful and positive answers to users. Be friendly, polite, and helpful in all interactions.
---
{context}
---
"""
general_user_template = "Question: ```{question}```"
messages = [
    SystemMessagePromptTemplate.from_template(general_system_template),
    HumanMessagePromptTemplate.from_template(general_user_template),
]
qa_prompt = ChatPromptTemplate.from_messages(messages)

conversation_chain = None

def get_vectorstore_from_db():
    try:
        # Connect to SQLite database
        connection = sqlite3.connect('apps/db.sqlite3')
        cursor = connection.cursor()
        
        # Fetch product information along with related data
        query = """
            SELECT p.title, p.category, p.product_link, p.current_price, p.old_price, p.discount, p.image_url, 
                   u.username, pr.name AS project_name
            FROM products p
            LEFT JOIN project_product pp ON p.id = pp.product_id
            LEFT JOIN projects pr ON pp.project_id = pr.id
            LEFT JOIN project_user pu ON pr.id = pu.project_id
            LEFT JOIN users u ON pu.user_id = u.id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        connection.close()

        # Create text chunks from the DB data
        text_chunks = [
            f"Title: {row[0]}, Category: {row[1]}, Current Price: {row[3]}, Old Price: {row[4]}, Discount: {row[5]}%, Product Link: {row[2]}, User: {row[7]}, Project: {row[8]}"
            for row in rows
        ]

        # Create FAISS vector store
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
        
        return vectorstore
    except Exception as e:
        print(f"An error occurred while retrieving the vectorstore: {e}")
        return None

def initialize_conversation_chain():
    global conversation_chain
    vectorstore = get_vectorstore_from_db()
    if vectorstore is None:
        print("Failed to initialize vectorstore. Conversation chain cannot be created.")
        return
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_type="similarity"),
        memory=memory,
        combine_docs_chain_kwargs={"prompt": qa_prompt},
        verbose=True,
    )

def get_chatbot_response(user_input):
    global conversation_chain
    if conversation_chain is None:
        initialize_conversation_chain()
        print("chatting...")
    if conversation_chain is None:
        return "Error: Unable to generate response. Please try again later."
    
    response = conversation_chain({"question": user_input})
    return response.get('answer', "No answer found.")

