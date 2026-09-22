import streamlit as st
import json
import os
import hashlib
import importlib.util

# ==========================================
# SYSTEM CONFIGURATION
# ==========================================
st.set_page_config(page_title="Ticket Dashboard", page_icon="🎫", layout="wide")

ENABLE_LOGIN = True  # เปลี่ยนเป็น False หากต้องการปิดระบบ Login
USERS_FILE = "users.json"

# ==========================================
# AUTHENTICATION LOGIC
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

from google_sheets_helper import load_users_from_gsheets, save_users_to_gsheets

def load_users():
    users = load_users_from_gsheets()
    if not users:
        # Create default admin
        default_users = {
            "admin": {
                "password": hash_password("admin123"),
                "role": "admin",
                "allowed_pages": ["🎟️ Ticket Management", "🔥 Outstanding Ticket", "💡 Ticket Solution-Analise", "⚙️ Admin Panel"]
            }
        }
        save_users_to_gsheets(default_users)
        return default_users
    return users

def save_users(users_dict):
    save_users_to_gsheets(users_dict)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'allowed_pages' not in st.session_state:
    st.session_state.allowed_pages = []

users = load_users()

# Login Screen
if ENABLE_LOGIN and not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #0F766E;'>🔐 System Login</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if user_input in users:
                    if users[user_input]["password"] == hash_password(pass_input):
                        st.session_state.logged_in = True
                        st.session_state.username = user_input
                        st.session_state.role = users[user_input]["role"]
                        st.session_state.allowed_pages = users[user_input]["allowed_pages"]
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")
                else:
                    st.error("ไม่พบ Username นี้")
    st.stop()

# If login is disabled, grant full access
if not ENABLE_LOGIN:
    st.session_state.username = "Guest"
    st.session_state.role = "admin"
    st.session_state.allowed_pages = ["🎟️ Ticket Management", "🔥 Outstanding Ticket", "💡 Ticket Solution-Analise", "⚙️ Admin Panel"]

# ==========================================
# SIDEBAR NAVIGATION (DYNAMIC)
# ==========================================
st.sidebar.markdown(f"### 👤 Welcome, {st.session_state.username}")
if ENABLE_LOGIN:
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 Menu")

# Pages Dictionary
PAGE_FILES = {
    "🎟️ Ticket Management": "views/Ticket_Management.py",
    "🔥 Outstanding Ticket": "views/Outstanding_Ticket.py",
    "💡 Ticket Solution-Analise": "views/Ticket_Solution_Analise.py",
    "⚙️ Admin Panel": "admin_panel"
}

# Filter menu based on user's allowed pages
available_pages = [p for p in PAGE_FILES.keys() if p in st.session_state.allowed_pages]

if not available_pages:
    st.warning("คุณยังไม่ได้รับสิทธิ์ให้เข้าถึงหน้าใดๆ กรุณาติดต่อ Admin")
    st.stop()

selection = st.sidebar.radio("Go to", available_pages, label_visibility="collapsed")

# ==========================================
# RENDER SELECTED PAGE
# ==========================================
if selection == "⚙️ Admin Panel":
    st.markdown("<h2>⚙️ Admin Panel (User Management)</h2>", unsafe_allow_html=True)
    if st.session_state.role != "admin":
        st.error("Access Denied: เฉพาะ Admin เท่านั้นที่สามารถเข้าหน้านี้ได้")
        st.stop()
        
    st.markdown("จัดการบัญชีผู้ใช้งาน สิทธิ์ และการเข้าถึงหน้าเว็บต่างๆ")
    
    # Create new user form
    with st.expander("➕ สร้างผู้ใช้งานใหม่", expanded=False):
        with st.form("new_user_form"):
            new_user = st.text_input("Username ใหม่")
            new_pass = st.text_input("Password", type="password")
            new_role = st.selectbox("สิทธิ์ (Role)", ["user", "manager", "admin"])
            
            st.markdown("**เลือกหน้าที่อนุญาตให้เข้าถึง:**")
            col1, col2 = st.columns(2)
            c1 = col1.checkbox("🎟️ Ticket Management", value=True)
            c2 = col1.checkbox("🔥 Outstanding Ticket", value=False)
            c3 = col2.checkbox("💡 Ticket Solution-Analise", value=False)
            c4 = col2.checkbox("⚙️ Admin Panel", value=False)
            
            if st.form_submit_button("บันทึกผู้ใช้ใหม่"):
                if new_user in users:
                    st.error("Username นี้มีอยู่แล้ว!")
                elif not new_user or not new_pass:
                    st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
                else:
                    allowed = []
                    if c1: allowed.append("🎟️ Ticket Management")
                    if c2: allowed.append("🔥 Outstanding Ticket")
                    if c3: allowed.append("💡 Ticket Solution-Analise")
                    if c4: allowed.append("⚙️ Admin Panel")
                    
                    users[new_user] = {
                        "password": hash_password(new_pass),
                        "role": new_role,
                        "allowed_pages": allowed
                    }
                    save_users(users)
                    st.success(f"สร้างผู้ใช้งาน {new_user} สำเร็จ!")
                    st.rerun()
                    
    # Edit existing users
    st.markdown("### 👥 รายชื่อผู้ใช้งานในระบบ")
    for u_name, u_data in users.items():
        with st.expander(f"👤 {u_name} (Role: {u_data['role']})"):
            u_role = st.selectbox(f"Role", ["user", "manager", "admin"], index=["user", "manager", "admin"].index(u_data['role']), key=f"role_{u_name}")
            
            st.markdown("**หน้าที่เข้าถึงได้:**")
            u_c1 = st.checkbox("🎟️ Ticket Management", value="🎟️ Ticket Management" in u_data['allowed_pages'], key=f"c1_{u_name}")
            u_c2 = st.checkbox("🔥 Outstanding Ticket", value="🔥 Outstanding Ticket" in u_data['allowed_pages'], key=f"c2_{u_name}")
            u_c3 = st.checkbox("💡 Ticket Solution-Analise", value="💡 Ticket Solution-Analise" in u_data['allowed_pages'], key=f"c3_{u_name}")
            u_c4 = st.checkbox("⚙️ Admin Panel", value="⚙️ Admin Panel" in u_data['allowed_pages'], key=f"c4_{u_name}")
            
            new_pwd = st.text_input("เปลี่ยนรหัสผ่าน (เว้นว่างไว้ถ้าไม่ต้องการเปลี่ยน)", type="password", key=f"pwd_{u_name}")
            
            col_save, col_del = st.columns([1, 1])
            if col_save.button("💾 บันทึกการเปลี่ยนแปลง", key=f"save_{u_name}"):
                u_allowed = []
                if u_c1: u_allowed.append("🎟️ Ticket Management")
                if u_c2: u_allowed.append("🔥 Outstanding Ticket")
                if u_c3: u_allowed.append("💡 Ticket Solution-Analise")
                if u_c4: u_allowed.append("⚙️ Admin Panel")
                
                users[u_name]["role"] = u_role
                users[u_name]["allowed_pages"] = u_allowed
                if new_pwd:
                    users[u_name]["password"] = hash_password(new_pwd)
                save_users(users)
                
                # If editing self, update session state
                if u_name == st.session_state.username:
                    st.session_state.role = u_role
                    st.session_state.allowed_pages = u_allowed
                    
                st.success("บันทึกสำเร็จ!")
                st.rerun()
                
            if u_name != "admin": # Prevent deleting default admin
                if col_del.button("🗑️ ลบผู้ใช้งาน", key=f"del_{u_name}"):
                    del users[u_name]
                    save_users(users)
                    st.success("ลบสำเร็จ!")
                    st.rerun()

else:
    # Run the selected python file dynamically
    file_path = PAGE_FILES[selection]
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        # Execute the view script within the current namespace
        exec(code, globals())
    else:
        st.error(f"ไม่พบไฟล์: {file_path}")
