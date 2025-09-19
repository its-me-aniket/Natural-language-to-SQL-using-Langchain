# app.py
import streamlit as st
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()
from langchain_utils import handle_question

st.set_page_config(page_title="NL → SQL (Gemini)", page_icon="🧠", layout="wide")
st.title("NL → SQL — Gemini + MySQL (conversational)")

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Settings")
    st.write("Secrets loaded from .env (local).")
    if st.button("Clear chat history"):
        st.session_state.history = []
        st.success("Cleared conversation history.")

# Display chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input
user_input = st.chat_input("Ask a question about your database...")
if user_input:
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.spinner("Generating SQL and executing..."):
        try:
            out = handle_question(user_input, st.session_state.history)
        except Exception as e:
            out = {
                "query": "",
                "result": [{"__error__": str(e)}],
                "answer": f"Error: {str(e)}"
            }

    # Show assistant response
    with st.chat_message("assistant"):
        st.write("Generated SQL (run against DB):")
        with st.expander("SQL"):
            st.code(out["query"], language="sql")

        st.write("Result summary:")
        try:
            df = pd.DataFrame(out["result"])
            st.dataframe(df)
        except Exception:
            st.write(out["result"])

        st.write("Assistant answer:")
        st.markdown(out["answer"])

    # Add assistant response to history
    st.session_state.history.append({"role": "assistant", "content": out["answer"]})
