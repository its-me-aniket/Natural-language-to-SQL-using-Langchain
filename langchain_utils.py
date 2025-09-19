# langchain_utils.py
import os
import csv
import json
from typing import Any, Dict, List

from dotenv import load_dotenv
load_dotenv()

from langchain_community.utilities.sql_database import SQLDatabase
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI  # hypothetical Gemini wrapper

from prompts import SQL_GENERATION_PROMPT, FINAL_ANSWER_PROMPT

# Environment variables
DB_URI = os.getenv("DB_URI")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not DB_URI:
    raise RuntimeError("DB_URI is not set. Put it in your .env")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is not set. Put it in your .env")

# Module-level cache
_db_instance = None
_table_info = None

def build_db() -> SQLDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = SQLDatabase.from_uri(DB_URI)
    return _db_instance

def load_table_details_csv(path: str = "table_details.csv") -> str:
    global _table_info
    if _table_info is None:
        items = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    t = (r.get("Table") or r.get("table") or "").strip()
                    d = (r.get("Description") or r.get("description") or "").strip()
                    if t:
                        items.append(f"- {t}: {d}")
        except FileNotFoundError:
            pass
        _table_info = "\n".join(items)
    return _table_info

# Memory for conversation
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# LangChain LLM wrapper for Gemini
llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, api_key=GOOGLE_API_KEY)

# Prompt template for SQL generation
sql_prompt = PromptTemplate(
    template=SQL_GENERATION_PROMPT,
    input_variables=["table_info", "input"]
)

# Prompt template for final answer
final_answer_prompt = PromptTemplate(
    template=FINAL_ANSWER_PROMPT,
    input_variables=["question", "query", "result"]
)

# Toolkit + Agent setup
def get_agent():
    db = build_db()
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=False,
        memory=memory
    )
    return agent

def handle_question(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Main helper: generate SQL, execute, and produce final answer using agent.
    Returns dict with 'query', 'result', 'answer'.
    """
    table_info = load_table_details_csv()
    agent = get_agent()

    # Include recent history for context
    history_text = ""
    if history:
        last = history[-6:]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last])
        question_with_context = f"Conversation history:\n{history_text}\n\nUser question: {question}"
    else:
        question_with_context = question

    # Run agent (returns final answer including SQL execution)
    agent_output = agent.run(question_with_context)

    # Attempt to extract SQL from agent output (if any)
    import re
    match = re.search(r"(select|show|with|describe|explain).*", agent_output, re.IGNORECASE | re.DOTALL)
    sql_query = match.group(0).strip() if match else "N/A"

    # Execute SQL separately to get structured rows (optional, for Streamlit table)
    try:
        rows = build_db().run(sql_query) if sql_query != "N/A" else []
        if not isinstance(rows, list):
            rows = list(rows)
    except Exception as e:
        rows = [{"__error__": str(e)}]

    return {
        "query": sql_query,
        "result": rows,
        "answer": agent_output
    }
