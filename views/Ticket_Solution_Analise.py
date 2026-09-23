import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob

# ==========================================
# PAGE CONFIGURATION & THEME
# ==========================================

# Blue-Green Theme CSS
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #F0F9FF; /* Light Blue-Green tint */
    }
    
    /* Header typography */
    h1, h2, h3, h4 {
        color: #0369A1; /* Deep Ocean Blue */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Dashboard Cards */
    .analysis-card {
        background-color: #FFFFFF;
        border-top: 4px solid #0D9488; /* Teal/Green border */
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    
    .kpi-title {
        color: #0F766E; /* Dark Teal */
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    
    .kpi-value {
        color: #0369A1; /* Ocean Blue */
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 5px;
    }
    
    /* Table Styling overrides */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    [data-testid="stSidebarNav"] ul li span { font-size: 1.1rem !important; font-weight: 600 !important; }

    /* Fix Header and Sidebar Toggle */
    header {background-color: transparent !important;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Make the sidebar toggle arrow clearly visible */
    [data-testid='collapsedControl'] {
        color: #0F766E !important;
        background-color: #F8FAFC !important;
        border: 2px solid #0F766E !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
    }


    /* Increase font sizes for filters */
    .stMultiSelect label, .stDateInput label, .stSelectbox label {
        font-size: 1.15rem !important;
        font-weight: 500 !important;
    }
    div[data-baseweb="select"] * {
        font-size: 1.05rem !important;
    }
    /* Attempt to scale dataframe */
    [data-testid="stDataFrame"] {
        font-size: 1.05rem !important;
    }
    .stMarkdown p, .stMarkdown li {
        font-size: 1.05rem !important;
    }

</style>
""", unsafe_allow_html=True)

# ==========================================
# DATA PROCESSING & UPLOAD LOGIC
# ==========================================
from google_sheets_helper import upload_ticket_data_to_gsheets, load_ticket_data_from_gsheets
import json

st.sidebar.markdown("### 📥 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload Excel File", type=["xlsx", "xls"])

METADATA_FILE = "upload_metadata.json"

if uploaded_file:
    with st.spinner("กำลังอัปโหลดข้อมูลขึ้น Google Sheets..."):
        try:
            preview = pd.read_excel(uploaded_file, header=None, nrows=20)
            header_idx = 0
            for i, row in preview.iterrows():
                if 'TicketID' in str(row.values) or 'Ticket ID' in str(row.values):
                    header_idx = i
                    break
            uploaded_file.seek(0)
            df_upload = pd.read_excel(uploaded_file, header=header_idx)
            upload_ticket_data_to_gsheets(df_upload)
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"filename": uploaded_file.name}, f)
            st.sidebar.success("อัปโหลดและอัปเดตข้อมูลสำเร็จ!")
            st.cache_data.clear()
        except Exception as e:
            st.sidebar.error(f"Error uploading: {e}")

@st.cache_data(ttl=300)
def load_data():
    try:
        df = load_ticket_data_from_gsheets()
        if df.empty:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading from Google Sheets: {e}")
        return pd.DataFrame()
        
    try:
        
        # Datetime conversion for CreateDate
        if 'CreateDate' in df.columns:
            df['CreateDate'] = pd.to_datetime(df['CreateDate'], errors='coerce')
        
        # Fill missing values for analysis columns
        text_cols = ['Solution/Defect LV 1', 'Solution/Defect LV 2', 'DescriptionOfProblem', 'SolutionForUser']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', 'Unknown')
                df[col] = df[col].fillna('Unknown')
                
        # Only keep rows that have actual defects mapped (ignore totally unknown ones if we want, but let's keep them and filter later)
        return df
    except Exception as e:
        st.error(f"Error parsing data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("ไม่พบไฟล์ข้อมูล กรุณาอัปโหลดไฟล์ Excel เพื่อเริ่มวิเคราะห์")
    st.stop()

# ==========================================
# SIDEBAR FILTERS
# ==========================================
st.sidebar.markdown("### 🔍 Filters")

if 'CreateDate' in df.columns:
    df['CreateDate_Day'] = df['CreateDate'].dt.date

if 'CreateDate_Day' in df.columns and not df['CreateDate_Day'].isna().all():
    min_d = df['CreateDate_Day'].min()
    max_d = df['CreateDate_Day'].max()
    date_range = st.sidebar.date_input("Date Range (Create Date)", [min_d, max_d], min_value=min_d, max_value=max_d)
else:
    date_range = []

def filter_multiselect(label, col_name, data):
    if col_name in data.columns:
        options = sorted(list(data[col_name].dropna().astype(str).unique()))
        selected = st.sidebar.multiselect(label, options=options)
        return selected
    return []

f_ticket_type = filter_multiselect("Ticket Type", "TicketType", df)
f_defect1 = filter_multiselect("Defect Level 1", "Solution/Defect LV 1", df)
f_defect2 = filter_multiselect("Defect Level 2", "Solution/Defect LV 2", df)

if len(date_range) == 2:
    df = df[(df['CreateDate_Day'] >= date_range[0]) & (df['CreateDate_Day'] <= date_range[1])]
if f_ticket_type: df = df[df['TicketType'].isin(f_ticket_type)]
if f_defect1: df = df[df['Solution/Defect LV 1'].isin(f_defect1)]
if f_defect2: df = df[df['Solution/Defect LV 2'].isin(f_defect2)]


# ==========================================
# HEADER
# ==========================================
st.markdown("<h2>💡 Deep Analytical Insights</h2>", unsafe_allow_html=True)

original_filename = "Google Sheets Database"
date_text = "N/A"
if not df.empty and 'CreateDate' in df.columns and not df['CreateDate'].isna().all():
    s_date = df['CreateDate'].dt.date.min().strftime('%d %b %Y')
    e_date = df['CreateDate'].dt.date.max().strftime('%d %b %Y')
    date_text = f"{s_date} - {e_date}"

st.markdown(f"<p style='color: #0F766E;'>ระบบวิเคราะห์เชิงลึก (Deep Analytics) | 📁 <b>{original_filename}</b> | 📅 <b>{date_text}</b></p>", unsafe_allow_html=True)

if df.empty:
    st.stop()

# ==========================================
# ANALYTICAL TABS
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Ticket Type (Incident vs Request)", 
    "2️⃣ Root Cause (Sustainable Fix)", 
    "3️⃣ Config Requests", 
    "4️⃣ Business Group Pain Points",
    "5️⃣ Channel Effectiveness"
])

with tab1:
    st.markdown("<h3>1️⃣ สัดส่วนประเภทงาน (Ticket Type Analysis)</h3>", unsafe_allow_html=True)
    st.markdown("เปรียบเทียบระหว่าง 'ปัญหาที่ระบบขัดข้อง' (Incident) กับ 'การขอให้ตั้งค่า/ขอข้อมูล' (Request)")
    if 'TicketType' in df.columns:
        type_df = df['TicketType'].fillna('Unknown').value_counts().reset_index()
        type_df.columns = ['TicketType', 'Count']
        
        c1, c2 = st.columns([1, 1])
        with c1:
            fig1 = px.pie(type_df, values='Count', names='TicketType', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
            st.markdown("**💡 ไอเดียเชิงบริหาร:**")
            if not type_df.empty:
                top_type = type_df.iloc[0]['TicketType']
                st.markdown(f"- งานส่วนใหญ่ของเราคือ **{top_type}**")
                if 'request' in top_type.lower():
                    st.markdown("- สะท้อนว่า User ต้องการความช่วยเหลือด้านการใช้งานหรือตั้งค่าเป็นหลัก ควรพิจารณาสร้าง **คู่มือแบบ Self-Service** หรือระบบ Automation เพื่อลดโหลดของทีม")
                else:
                    st.markdown("- สะท้อนว่าระบบมีความไม่เสถียร ควรนำข้อมูลไปหารือกับทีม Developer เพื่อเพิ่มความมั่นคงของระบบ")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if 'EffortTime' in df.columns:
                avg_effort = df.groupby('TicketType')['EffortTime'].mean().reset_index()
                fig_bar = px.bar(avg_effort, x='TicketType', y='EffortTime', title="Avg Effort Time by Type (Days)")
                st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.markdown("<h3>2️⃣ วิเคราะห์รากของปัญหาเพื่อการแก้ไขแบบยั่งยืน (Root Cause Analysis)</h3>", unsafe_allow_html=True)
    if 'Solution/Defect LV 1' in df.columns and 'Solution/Defect LV 2' in df.columns:
        valid_defects = df[~df['Solution/Defect LV 1'].str.contains('Unknown|-', case=False, regex=True, na=False)]
        
        if not valid_defects.empty:
            kb_df = valid_defects.groupby(['Solution/Defect LV 1', 'Solution/Defect LV 2']).size().reset_index(name='Count')
            fig_tree = px.treemap(kb_df, path=['Solution/Defect LV 1', 'Solution/Defect LV 2'], values='Count', color='Count', color_continuous_scale=['#e0f2fe', '#7dd3fc', '#38bdf8', '#0284c7', '#082f49'])
            st.plotly_chart(fig_tree, use_container_width=True)
            
            st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
            st.markdown("**💡 ไอเดียเชิงบริหาร:**")
            st.markdown("- กราฟด้านบนแสดงให้เห็นว่า **ระบบไหน/โมดูลไหน สร้างปัญหาซ้ำซากมากที่สุด**")
            top_lv1 = kb_df.groupby('Solution/Defect LV 1')['Count'].sum().idxmax()
            st.markdown(f"- แนะนำให้นำรายงานหมวดหมู่ **{top_lv1}** ไปประชุมร่วมกับทีม Developer หรือ Vendor เพื่อหาแนวทาง **แก้ไขที่ต้นเหตุ (Permanent Fix)** เพื่อที่ทีม GP จะได้ไม่ต้องมาตามแก้ปลายเหตุ (Workaround) อีกต่อไป")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("ไม่มีข้อมูล Defect ที่ระบุชัดเจน")

with tab3:
    st.markdown("<h3>3️⃣ วิเคราะห์การขอตั้งค่า (Config Request Patterns)</h3>", unsafe_allow_html=True)
    if 'TicketType' in df.columns and 'CategoryLevel1' in df.columns:
        req_df = df[df['TicketType'].astype(str).str.contains('Request|Service', case=False, na=False)]
        if not req_df.empty:
            cat_df = req_df['CategoryLevel1'].fillna('Unknown').value_counts().head(10).reset_index()
            cat_df.columns = ['Category', 'Count']
            
            fig_req = px.bar(cat_df, y='Category', x='Count', orientation='h', text_auto=True, color='Count', color_continuous_scale='Purples')
            st.plotly_chart(fig_req, use_container_width=True)
            
            st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
            st.markdown("**💡 ไอเดียเชิงบริหาร:**")
            top_req = cat_df.iloc[0]['Category'] if not cat_df.empty else ""
            st.markdown(f"- คำขอที่เสียเวลาทีมมากที่สุดคือ **{top_req}**")
            st.markdown("- หากการทำ Config เหล่านี้มีรูปแบบที่ตายตัว (Standardized) ควรพิจารณา: <br>1) พัฒนา Tool เล็กๆ ให้ User ทำได้เองแบบจำกัดสิทธิ์ <br>2) ทำ Script รันอัตโนมัติ", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("ไม่พบข้อมูลประเภท Request")

with tab4:
    st.markdown("<h3>4️⃣ เจาะจง Pain Point ของแต่ละ Business Group</h3>", unsafe_allow_html=True)
    if 'BusinessGroup' in df.columns and 'CategoryLevel1' in df.columns:
        bg_cat_df = df.groupby(['BusinessGroup', 'CategoryLevel1']).size().reset_index(name='Count')
        bg_cat_df = bg_cat_df[~bg_cat_df['BusinessGroup'].str.contains('Unknown|-', case=False, na=False)]
        
        if not bg_cat_df.empty:
            # Pivot for heatmap
            pivot = bg_cat_df.pivot(index='BusinessGroup', columns='CategoryLevel1', values='Count').fillna(0)
            fig_heat = px.imshow(pivot, aspect="auto", color_continuous_scale='Oranges', text_auto=True)
            st.plotly_chart(fig_heat, use_container_width=True)
            
            st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
            st.markdown("**💡 ไอเดียเชิงบริหาร:**")
            st.markdown("- **Heatmap (แผนที่ความร้อน)** สีที่เข้มที่สุดคือจุดที่เป็น Pain Point หนักที่สุดของแผนกนั้นๆ")
            st.markdown("- ควรนำข้อมูลนี้ไปใช้ **จัดทำคอร์ส Training เจาะจงเฉพาะแผนก** (เช่น แผนกบัญชีเจอปัญหาระบบ A บ่อย ก็จัดสอนแค่บัญชี) จะช่วยลดจำนวนตั๋วลงได้อย่างมีนัยสำคัญ")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("ไม่พบข้อมูล Business Group ที่ชัดเจน")

with tab5:
    st.markdown("<h3>5️⃣ ประสิทธิภาพการรับเรื่องตามช่องทาง (Channel Effectiveness)</h3>", unsafe_allow_html=True)
    if 'Channel' in df.columns:
        ch_df = df['Channel'].fillna('Unknown').value_counts().reset_index()
        ch_df.columns = ['Channel', 'Volume']
        
        c1, c2 = st.columns(2)
        with c1:
            fig_ch = px.bar(ch_df, x='Channel', y='Volume', text_auto=True, color='Volume', color_continuous_scale='Greens')
            st.plotly_chart(fig_ch, use_container_width=True)
            
        with c2:
            if 'EffortTime' in df.columns:
                ch_time = df.groupby('Channel')['EffortTime'].mean().reset_index()
                fig_time = px.bar(ch_time, x='Channel', y='EffortTime', title='Avg Effort Time (Days) by Channel', text_auto=True)
                st.plotly_chart(fig_time, use_container_width=True)
                
        st.markdown("<div class='analysis-card'>", unsafe_allow_html=True)
        st.markdown("**💡 ไอเดียเชิงบริหาร:**")
        st.markdown("- หากช่องทางที่มี Volume สูงสุด (เช่น โทรศัพท์) ใช้เวลาแก้ปัญหานานที่สุด อาจจะต้องพิจารณาเพิ่มคนตอบรับในช่องทางนั้น หรือบังคับให้ User ไปใช้ช่องทางที่เป็นระบบมากขึ้น (เช่น Portal) เพื่อให้ง่ายต่อการติดตามงาน")
        st.markdown("</div>", unsafe_allow_html=True)

