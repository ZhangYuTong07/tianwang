import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import random
import re
import hashlib
import os
from openai import OpenAI

# ========== 配置 ==========
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="天网演武", page_icon="⚔️", layout="wide")

# ========== 用户系统 ==========
USERS_DIR = "users"
if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_db_path(username):
    return os.path.join(USERS_DIR, f"{username}_history.db")

def init_user_db(username):
    db_path = get_user_db_path(username)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  question TEXT,
                  user_answer TEXT,
                  correct_answer TEXT,
                  is_correct INTEGER,
                  ai_feedback TEXT,
                  timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY,
                  password TEXT,
                  created_at TEXT)''')
    conn.commit()
    conn.close()

def register_user(username, password):
    db_path = get_user_db_path(username)
    if os.path.exists(db_path):
        return False
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  question TEXT, user_answer TEXT, correct_answer TEXT,
                  is_correct INTEGER, ai_feedback TEXT, timestamp TEXT)''')
    c.execute("INSERT INTO users VALUES (?, ?, ?)",
              (username, hash_password(password), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def check_login(username, password):
    db_path = get_user_db_path(username)
    if not os.path.exists(db_path):
        return False
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_password(password):
        return True
    return False

# ========== 数据操作（用户相关）==========
def save_record(username, question, user_answer, correct_answer, is_correct, ai_feedback):
    db_path = get_user_db_path(username)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO records (question, user_answer, correct_answer, is_correct, ai_feedback, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (question, user_answer, correct_answer, 1 if is_correct else 0, ai_feedback, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_records(username):
    db_path = get_user_db_path(username)
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM records ORDER BY id DESC", conn)
    conn.close()
    return df

def get_stats(username):
    df = get_records(username)
    if len(df) == 0:
        return 0, 0, 0
    total = len(df)
    correct = df['is_correct'].sum()
    rate = (correct / total * 100) if total > 0 else 0
    return total, correct, rate

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
    },
    "文件上传防御": {
        "question": "【Web安全 ⭐⭐】关于文件上传漏洞的防御，以下哪个最有效？\nA. 只检查扩展名\nB. 只检查MIME类型\nC. 禁用脚本执行+随机重命名\nD. 限制文件大小",
        "answer": "C",
        "difficulty": "⭐⭐",
        "category": "Web安全"
    },
    "CSRF原理": {
        "question": "【Web安全 ⭐⭐】关于CSRF攻击，哪个说法正确？\nA. 需要窃取Cookie\nB. 利用用户对网站的信任\nC. HTTPS可完全防御\nD. 属于服务端漏洞",
        "answer": "B",
        "difficulty": "⭐⭐",
        "category": "Web安全"
    },
    "DDoS防御": {
        "question": "【系统安全 ⭐】哪个是DDoS最有效的防御？\nA. 增加内存\nB. CDN+云清洗\nC. 关闭端口\nD. 改密码",
        "answer": "B",
        "difficulty": "⭐",
        "category": "系统安全"
    },
    "Linux提权": {
        "question": "【系统安全 ⭐⭐】Linux中检测sudo权限的命令？\nA. ls\nB. sudo -l\nC. cd\nD. pwd",
        "answer": "B",
        "difficulty": "⭐⭐",
        "category": "系统安全"
    },
    "子域名枚举": {
        "question": "【综合 ⭐】哪个工具用于子域名枚举？\nA. Nmap\nB. Dirb\nC. Sublist3r\nD. Hydra",
        "answer": "C",
        "difficulty": "⭐",
        "category": "综合"
    },
    "CTF编码": {
        "question": "【CTF ⭐⭐⭐】`ZmxhZ3tjdGZfZnVuXzEyM30=` 是什么编码？\nA. Base64\nB. Hex\nC. URL编码\nD. ROT13",
        "answer": "A",
        "difficulty": "⭐⭐⭐",
        "category": "综合"
    },
    "缓冲区溢出": {
        "question": "【系统安全 ⭐⭐⭐】缓冲区溢出原理是？\nA. 覆盖返回地址\nB. SQL拼接\nC. 诱导点击\nD. 窃取密码",
        "answer": "A",
        "difficulty": "⭐⭐⭐",
        "category": "系统安全"
    },
    "端口扫描": {
        "question": "【综合 ⭐】最常用的端口扫描工具？\nA. Nmap\nB. Burp Suite\nC. Wireshark\nD. Metasploit",
        "answer": "A",
        "difficulty": "⭐",
        "category": "综合"
    }
}

# ========== AI 解析 ==========
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

# ========== 侧边栏筛选 ==========
def get_filtered_questions(difficulty, category):
    filtered = {}
    for qid, qinfo in QUESTION_BANK.items():
        if difficulty != "全部" and qinfo["difficulty"] != difficulty:
            continue
        if category != "全部" and qinfo["category"] != category:
            continue
        filtered[qid] = qinfo
    return filtered

# ========== 登录页面 ==========
def login_page():
    st.title("⚔️ 天网演武")
    st.subheader("登录 / 注册")
    
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        username = st.text_input("用户名", key="login_user")
        password = st.text_input("密码", type="password", key="login_pwd")
        if st.button("登录"):
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                init_user_db(username)
                st.rerun()
            else:
                st.error("用户名或密码错误")
    
    with tab2:
        new_user = st.text_input("用户名", key="reg_user")
        new_pwd = st.text_input("密码", type="password", key="reg_pwd")
        confirm_pwd = st.text_input("确认密码", type="password")
        if st.button("注册"):
            if not new_user or not new_pwd:
                st.error("请填写完整")
            elif new_pwd != confirm_pwd:
                st.error("两次密码不一致")
            elif register_user(new_user, new_pwd):
                st.success("注册成功！请登录")
            else:
                st.error("用户名已存在")

# ========== 主应用 ==========
def main_app():
    username = st.session_state.username
    
    with st.sidebar:
        st.markdown(f"### ⚔️ 天网演武")
        st.markdown(f"👤 用户：**{username}**")
        if st.button("🚪 退出登录"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.current_question = None
            st.rerun()
        st.markdown("---")
        
        # 统计
        st.markdown("## 📊 答题统计")
        total, correct, rate = get_stats(username)
        col1, col2, col3 = st.columns(3)
        col1.metric("总答题", total)
        col2.metric("✅ 正确", correct)
        col3.metric("正确率", f"{rate:.0f}%")
        
        st.divider()
        
        # 历史记录
        st.markdown("## 📜 历史记录")
        df = get_records(username)
        if len(df) > 0:
            for _, row in df.head(10).iterrows():
                status = "✅" if row['is_correct'] else "❌"
                with st.expander(f"{status} {row['timestamp'][:16]}..."):
                    st.caption(f"题目：{row['question'][:50]}...")
                    st.caption(f"你的答案：{row['user_answer']} | 正确答案：{row['correct_answer']}")
        else:
            st.info("暂无记录")
        
        st.divider()
        
        # 错题本
        st.markdown("## 📖 错题本")
        if len(df) > 0:
            wrong_df = df[df['is_correct'] == 0]
            if len(wrong_df) > 0:
                st.warning(f"共 {len(wrong_df)} 道错题")
                for _, row in wrong_df.head(5).iterrows():
                    with st.expander(f"❌ {row['question'][:40]}..."):
                        st.caption(f"你的答案：{row['user_answer']}")
                        st.caption(f"正确答案：{row['correct_answer']}")
            else:
                st.success("暂无错题")
        
        st.divider()
        
        # 题库
        st.markdown("## 🎯 题库练习")
        difficulty = st.selectbox("难度", ["全部", "⭐", "⭐⭐", "⭐⭐⭐"])
        categories = ["全部"] + list(set(q["category"] for q in QUESTION_BANK.values()))
        category = st.selectbox("分类", categories)
        
        filtered = get_filtered_questions(difficulty, category)
        st.caption(f"共 {len(filtered)} 道题")
        
        if len(filtered) > 0:
            selected = st.selectbox("选择题目", list(filtered.keys()))
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📋 载入", use_container_width=True):
                    st.session_state.current_question = filtered[selected]["question"]
                    st.session_state.current_answer = filtered[selected]["answer"]
                    st.session_state.show_result = False
                    st.rerun()
            with col_b:
                if st.button("🎲 随机", use_container_width=True):
                    random_qid = random.choice(list(filtered.keys()))
                    st.session_state.current_question = filtered[random_qid]["question"]
                    st.session_state.current_answer = filtered[random_qid]["answer"]
                    st.session_state.show_result = False
                    st.rerun()
    
    # 主界面
    st.title("⚔️ 天网演武 — AI网络安全训练系统")
    st.caption("AI 智能解析 | 错题本 | 答题统计 | 多用户独立数据")
    
    # 显示题目
    if st.session_state.get("current_question") and not st.session_state.get("show_result", False):
        st.markdown(f"""
        <div style="background: #e8f4f8; border-left: 5px solid #1a3a5c; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
            <strong>📋 当前题目：</strong><br><br>
            {st.session_state.current_question}
        </div>
        """, unsafe_allow_html=True)
        st.caption("💡 请输入答案（例如：A 或 我选 A）")
    
    # 显示结果
    if st.session_state.get("show_result", False):
        if st.session_state.is_correct:
            st.success(f"✅ 正确！答案是 {st.session_state.current_answer}")
        else:
            st.error(f"❌ 错误！你选了 {st.session_state.user_answer}，正确答案是 {st.session_state.current_answer}")
        st.info(f"🤖 AI 解析：{st.session_state.ai_feedback}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡️ 下一题", use_container_width=True):
                st.session_state.show_result = False
                st.session_state.current_question = None
                st.rerun()
        with col2:
            if st.button("🔄 重新载入此题", use_container_width=True):
                st.session_state.show_result = False
                st.rerun()
    
    # 处理答案
    if not st.session_state.get("show_result", False) and st.session_state.get("current_question"):
        if prompt := st.chat_input("输入答案..."):
            match = re.search(r'([ABCD])', prompt.upper())
            if match:
                user_opt = match.group(1)
                is_correct = (user_opt == st.session_state.current_answer)
                
                with st.spinner("AI 正在分析..."):
                    ai_feedback = get_ai_feedback(
                        st.session_state.current_question,
                        user_opt,
                        st.session_state.current_answer,
                        is_correct
                    )
                
                save_record(username, st.session_state.current_question[:200],
                           user_opt, st.session_state.current_answer, is_correct, ai_feedback)
                
                st.session_state.user_answer = user_opt
                st.session_state.is_correct = is_correct
                st.session_state.ai_feedback = ai_feedback
                st.session_state.show_result = True
                st.rerun()
            else:
                st.error("请用 A/B/C/D 格式回答")
    
    elif not st.session_state.get("current_question"):
        st.info("👈 请从左侧选择题目开始练习")

# ========== 启动 ==========
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    if "current_question" not in st.session_state:
        st.session_state.current_question = None
        st.session_state.show_result = False
    main_app()
