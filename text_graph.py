from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from typing import  Annotated
import operator
from pinecone import Pinecone
from openai import OpenAI
from langgraph.graph import START, END, StateGraph
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

import streamlit as st
import os

os.environ["LANGCHAIN_TRACING_V2"] = st.secrets["LANGCHAIN_TRACING_V2"]
os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]
os.environ["LANGCHAIN_ENDPOINT"] = st.secrets["LANGCHAIN_ENDPOINT"]
os.environ["LANGCHAIN_PROJECT"] = st.secrets["LANGCHAIN_PROJECT"]
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["PINECONE_API_KEY"]= st.secrets["PINECONE_API_KEY"]
os.environ["INDEX_HOST"]= st.secrets["INDEX_HOST"]

# constants
TEXT_MODEL = "text-embedding-ada-002"
NAMESPACE_KEY = "Keya"
ANSWER_INSTRUCTIONS = """ You are an expert nutritionist for IBD patients.

You are an expert being answered based on given context.

You goal is to answer a question posed by the user.

Use the folowing guidenlines to answer user questions.

1. First check whether user is asking a question or greeting.

2. If it is a greeting, please greet appropriately.

3. If not please answer the question using below guidelines.

To answer question, use this context:

{context}

When answering questions, follow these guidelines:

1. Use only the information provided in the context.

2. Do not introduce external information or make assumptions beyond what is explicitly stated in the context.
"""

# set the openai model
llm = ChatOpenAI(model="gpt-4o", temperature=0)
# create client
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# pinecone setup
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(host=os.environ["INDEX_HOST"])

# this is be default has the messages and add_messages reducers (different from colab)
class BotState(MessagesState):
    context: Annotated[list, operator.add]
    answer: str

def get_openai_embeddings(text: str) -> list[float]:
    response = client.embeddings.create(input=f"{text}", model=TEXT_MODEL)

    return response.data[0].embedding


# function query similar chunks
def query_response(query_embedding, k = 2, namespace_ = NAMESPACE_KEY):
    query_response = index.query(
        namespace=namespace_,
        vector=query_embedding,
        top_k=k,
        include_values=False,
        include_metadata=True,
    )

    return query_response

def content_extractor(similar_data):
    top_values = similar_data["matches"]
    # get the text out
    text_content = [sub_content["metadata"]["text"] for sub_content in top_values]
    return " ".join(text_content)


def get_similar_context(question: str):
    # get the query embeddings
    quer_embed_data = get_openai_embeddings(question)

    # query the similar chunks
    similar_chunks = query_response(quer_embed_data)

    # extract the similar text data
    similar_content = content_extractor(similar_chunks)

    return similar_content

def semantic_search(state: BotState):
    question = state["messages"]

    # get the most similar context
    similar_context = get_similar_context(question)

    return {"context": [similar_context]}


def answer_generator(state: BotState, config: RunnableConfig):
    searched_context = state["context"]
    messages = state["messages"]

    # generate the prompt as a system message
    system_message_prompt = [SystemMessage(ANSWER_INSTRUCTIONS.format(context = searched_context ))]
    # invoke the llm
    answer = llm.invoke(system_message_prompt + messages, config)

    return {"answer": answer}

# add nodes and edges
helper_builder = StateGraph(BotState)
helper_builder.add_node("pinecone_retriever", semantic_search)
helper_builder.add_node("answer_generator", answer_generator)

# build graph
helper_builder.add_edge(START, "pinecone_retriever")
helper_builder.add_edge("pinecone_retriever", "answer_generator")
helper_builder.add_edge("answer_generator", END)

# compile the graph
helper_graph = helper_builder.compile()

async def graph_streamer(question_messages: list):
    # configurations
    node_to_stream = 'answer_generator'
    model_config = {"configurable": {"thread_id": "1"}}
    #input_message = HumanMessage(content=question)
    # streaming tokens
    async for event in helper_graph.astream_events({"messages": question_messages}, model_config, version="v2"):
        # Get chat model tokens from a particular node
        #print(event)
        if event["event"] == "on_chat_model_stream" and event['metadata'].get('langgraph_node','') == node_to_stream:
            data = event["data"]
            yield data["chunk"].content