import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import random
import re
from openai import OpenAI

# ========== 配置 ==========
# 从 Streamlit Secrets 读取 API Key
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="天网演武", page_icon="⚔️", layout="wide")

# ========== 数据库 ==========
def init_db():
    conn = sqlite3.connect('tianwang_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  question TEXT,
                  user_answer TEXT,
                  correct_answer TEXT,
                  is_correct INTEGER,
                  ai_feedback TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def save_record(question, user_answer, correct_answer, is_correct, ai_feedback):
    try:
        conn = sqlite3.connect('tianwang_history.db')
        c = conn.cursor()
        c.execute("INSERT INTO records (question, user_answer, correct_answer, is_correct, ai_feedback, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                  (question, user_answer, correct_answer, 1 if is_correct else 0, ai_feedback, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

def get_records():
    try:
        conn = sqlite3.connect('tianwang_history.db')
        df = pd.read_sql_query("SELECT * FROM records ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def get_stats():
    df = get_records()
    if len(df) == 0:
        return 0, 0, 0
    total = len(df)
    correct = df['is_correct'].sum()
    rate = (correct / total * 100) if total > 0 else 0
    return total, correct, rate

init_db()

# ========== 题库 ==========
QUESTION_BANK = {
    "SQL注入基础": {
        "question": "【Web安全 ⭐】以下哪个SQL注入语句可以绕过登录检查？\nA. ' OR '1'='1\nB. '; DROP TABLE users; --\nC. ' UNION SELECT password FROM users --\nD. ' AND 1=1",
        "answer": "A",
        "difficulty": "⭐",
        "category": "Web安全"
    },
    "XSS存储型": {
        "question": "【Web安全 ⭐】以下哪个属于存储型XSS？\nA. URL参数中插入<script>\nB. 留言板中插入<script>\nC. HTTP Referer中插入<script>\nD. User-Agent中插入<script>",
        "answer": "B",
        "difficulty": "⭐",
        "category": "Web安全"
    }
}

def get_ai_feedback(question, user_answer, correct_answer, is_correct):
    try:
        prompt = f"题目：{question}\n用户选择了：{user_answer}\n正确答案是：{correct_answer}\n用户{'正确' if is_correct else '错误'}。\n请用2-3句话给出解析。"
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        return response.choices[0].message.content
    except:
        return "解析生成失败。"

def get_filtered_questions(difficulty, category):
    filtered = {}
    for qid, qinfo in QUESTION_BANK.items():
        if difficulty != "全部" and qinfo["difficulty"] != difficulty:
            continue
        if category != "全部" and qinfo["category"] != category:
            continue
        filtered[qid] = qinfo
    return filtered

if "current_question" not in st.session_state:
    st.session_state.current_question = None
    st.session_state.show_result = False

with st.sidebar:
    st.markdown("### ⚔️ 天网演武")
    total, correct, rate = get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("总答题", total)
    col2.metric("正确", correct)
    col3.metric("正确率", f"{rate:.0f}%")
    st.divider()
    difficulty = st.selectbox("难度", ["全部", "⭐", "⭐⭐", "⭐⭐⭐"])
    categories = ["全部"] + list(set(q["category"] for q in QUESTION_BANK.values()))
    category = st.selectbox("分类", categories)
    filtered = get_filtered_questions(difficulty, category)
    if len(filtered) > 0:
        selected = st.selectbox("选择题目", list(filtered.keys()))
        if st.button("载入题目"):
            st.session_state.current_question = filtered[selected]["question"]
            st.session_state.current_answer = filtered[selected]["answer"]
            st.session_state.show_result = False
            st.rerun()

st.title("⚔️ 天网演武 — AI网络安全训练系统")

if st.session_state.current_question and not st.session_state.show_result:
    st.markdown(f"**当前题目：**\n\n{st.session_state.current_question}")
    st.caption("请输入答案（例如：A）")

if st.session_state.show_result:
    if st.session_state.is_correct:
        st.success(f"正确！答案是 {st.session_state.current_answer}")
    else:
        st.error(f"错误！你选了 {st.session_state.user_answer}，正确答案是 {st.session_state.current_answer}")
    st.info(f"AI解析：{st.session_state.ai_feedback}")
    if st.button("下一题"):
        st.session_state.show_result = False
        st.session_state.current_question = None
        st.rerun()

if not st.session_state.show_result and st.session_state.current_question:
    if prompt := st.chat_input("输入答案..."):
        match = re.search(r'([ABCD])', prompt.upper())
        if match:
            user_opt = match.group(1)
            is_correct = (user_opt == st.session_state.current_answer)
            with st.spinner("AI分析中..."):
                ai_feedback = get_ai_feedback(st.session_state.current_question, user_opt, st.session_state.current_answer, is_correct)
            save_record(st.session_state.current_question[:200], user_opt, st.session_state.current_answer, is_correct, ai_feedback)
            st.session_state.user_answer = user_opt
            st.session_state.is_correct = is_correct
            st.session_state.ai_feedback = ai_feedback
            st.session_state.show_result = True
            st.rerun()
        else:
            st.error("请用 A/B/C/D 格式回答")

if not st.session_state.current_question:
    st.info("请从左侧选择题目开始练习")
