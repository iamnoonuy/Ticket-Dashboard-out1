import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import json


st.markdown("""
<style>
    .stApp { background-color: #FAFAF9; }
    h1, h2, h3, h4 { color: #1C1917; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .card { background-color: #FFFFFF; border: 1px solid #E7E5E4; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }
    .kpi-title { color: #57534E; font-size: 14px; font-weight: 500; text-transform: uppercase; margin-bottom: 5px; }
    .kpi-value { color: #0C4A6E; font-size: 32px; font-weight: 700; margin-bottom: 5px; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    /* Fix Header and Sidebar Toggle */
    header {background-color: transparent !important;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid='collapsedControl'] {
        color: #0F766E !important;
        background-color: #F8FAFC !important;
        border: 2px solid #0F766E !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
    }
    [data-testid="stSidebarNav"] ul li span { font-size: 1.1rem !important; font-weight: 600 !important; }

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

from google_sheets_helper import load_ticket_data_from_gsheets, load_ticket_notes, save_ticket_notes
from io import BytesIO
METADATA_FILE = "upload_metadata.json"

# DATA LOADING FROM GSHEETS
@st.cache_data(ttl=300)
def load_data():
    try:
        df = load_ticket_data_from_gsheets()
        if df.empty:
            return pd.DataFrame(), "Unknown"
        return df, "Google Sheets Database"
    except Exception as e:
        st.error(f"Error loading from Google Sheets: {e}")
        return pd.DataFrame(), "Unknown"

raw_df, fallback_filename = load_data()

if not raw_df.empty:
    raw_df['IsOpen'] = ~raw_df['Status'].str.contains('Complete|Closed|Resolve|Reject|Cancel|Close', case=False, na=False)
    raw_df = raw_df[raw_df['IsOpen'] == True]

if raw_df.empty:
    st.warning("ไม่พบไฟล์ข้อมูล กรุณาอัปโหลดไฟล์ Excel ในหน้า Ticket Management ก่อน")
    st.stop()

# OUTSTANDING TRANSFORMATION
# Filter for Accept, Acknowledge
if 'Status' in raw_df.columns:
    df = raw_df[raw_df['Status'].astype(str).str.contains('Accept|Acknowledge', case=False, na=False)].copy()
else:
    df = pd.DataFrame()

if df.empty:
    st.info("ไม่มีงาน Outstanding (Status: Accept, Acknowledge) ในขณะนี้")
    st.stop()

# Convert dates
for col in ['CreateDate', 'StartSLADate', 'EndSLADate']:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

current_time = pd.Timestamp.now()

# Create requested columns map
out_df = pd.DataFrame()
out_df['Ticket Type'] = df.get('TicketType', 'Unknown')
out_df['Ticket No.'] = df.get('TicketID', 'Unknown')
out_df['Status'] = df.get('Status', 'Unknown')

# Load Notes from GSheets
notes_df = load_ticket_notes()
if not notes_df.empty and 'TicketID' in notes_df.columns:
    notes_df['TicketID'] = notes_df['TicketID'].astype(str).str.replace(r'\.0$', '', regex=True)
    notes_df = notes_df.drop_duplicates(subset=['TicketID'], keep='last')
    notes_dict = dict(zip(notes_df['TicketID'], notes_df['Note Status'].astype(str)))
    out_df['Note Status'] = out_df['Ticket No.'].astype(str).str.replace(r'\.0$', '', regex=True).map(notes_dict).fillna('')
else:
    out_df['Note Status'] = ''

out_df['Parent ID 1'] = df.get('CategoryLevel1', 'Unknown')
out_df['Child ID 2'] = df.get('CategoryLevel2', 'Unknown')
out_df['Name Staff'] = df.get('ResponseBy', 'Unknown')

if 'CreateDate' in df.columns:
    out_df['Ageing day'] = (current_time - df['CreateDate']).dt.days
else:
    out_df['Ageing day'] = 0

bg = df.get('BusinessGroup', '').fillna('')
cat1 = df.get('CategoryLevel1', '').fillna('')
out_df['Case - (Duration)-Problem'] = bg + " => " + cat1

out_df['Duration(Days)'] = df.get('EffortTime', 0)
out_df['Create Date/Time'] = df.get('CreateDate', '')
out_df['Details'] = df.get('DescriptionOfProblem', '')
out_df['Solution for IT'] = df.get('SolutionForIT', '')

def eval_sla(row):
    end_sla = row.get('EndSLADate')
    if pd.isna(end_sla): return 'Unknown'
    if current_time > end_sla: return 'Over SLA'
    if (end_sla - current_time).total_seconds() <= 86400: return 'Near SLA'
    return 'Within SLA'

out_df['SLA Rank'] = df.apply(eval_sla, axis=1) if 'EndSLADate' in df.columns else 'Unknown'
out_df['Start SLA date'] = df.get('StartSLADate', '')
out_df['SLA Due'] = df.get('EndSLADate', '')
out_df['Actual SLA'] = df.get('SLAStatus', '')
out_df['Count of status case'] = 1

# ==========================================
# SIDEBAR FILTERS
# ==========================================
st.sidebar.markdown("### 🔍 Filters")
def filter_multiselect(label, col_name, data):
    if col_name in data.columns:
        options = sorted(list(data[col_name].dropna().astype(str).unique()))
        return st.sidebar.multiselect(label, options=options)
    return []

f_category = filter_multiselect("Category (Level 1)", "Parent ID 1", out_df)
f_assignee = filter_multiselect("Assignee (Response By)", "Name Staff", out_df)

if f_category: out_df = out_df[out_df['Parent ID 1'].isin(f_category)]
if f_assignee: out_df = out_df[out_df['Name Staff'].isin(f_assignee)]

# ==========================================
# HEADER
# ==========================================
original_filename = fallback_filename
if os.path.exists(METADATA_FILE):
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
            original_filename = meta.get("filename", fallback_filename)
    except: pass

st.markdown("<h2>🔥 Outstanding Tickets Dashboard</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='color: #57534E;'>ข้อมูลงานค้าง (Accept/Acknowledge) | 📁 <b>{original_filename}</b></p>", unsafe_allow_html=True)

# KPIs
k1, k2, k3 = st.columns(3)
k1.markdown(f"<div class='card'><div class='kpi-title'>Total Outstanding</div><div class='kpi-value'>{len(out_df)}</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='card'><div class='kpi-title'>Avg Ageing (Days)</div><div class='kpi-value'>{out_df['Ageing day'].mean():.1f}</div></div>", unsafe_allow_html=True)
over_sla = len(out_df[out_df['SLA Rank'] == 'Over SLA'])
k3.markdown(f"<div class='card'><div class='kpi-title'>Over SLA</div><div class='kpi-value' style='color: #EF4444;'>{over_sla}</div></div>", unsafe_allow_html=True)

# CHARTS
c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    st.markdown("<div class='card'><h4>📊 Category (Level 1)</h4>", unsafe_allow_html=True)
    cat_df = out_df['Parent ID 1'].fillna('Unknown').value_counts().head(10).reset_index()
    cat_df.columns = ['Category', 'Count']
    fig1 = px.bar(cat_df, y='Category', x='Count', orientation='h', text_auto=True, color='Count', color_continuous_scale='Blues')
    st.plotly_chart(fig1, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='card'><h4>👤 Assignee Workload</h4>", unsafe_allow_html=True)
    staff_df = out_df['Name Staff'].fillna('Unknown').value_counts().head(10).reset_index()
    staff_df.columns = ['Name', 'Count']
    fig2 = px.bar(staff_df, y='Name', x='Count', orientation='h', text_auto=True, color='Count', color_continuous_scale='Oranges')
    st.plotly_chart(fig2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c3:
    st.markdown("<div class='card'><h4>🚨 Over SLA Days by Category</h4>", unsafe_allow_html=True)
    over_df = out_df[out_df['SLA Rank'] == 'Over SLA']
    if not over_df.empty:
        sla_days_df = over_df.groupby('Parent ID 1')['Ageing day'].sum().reset_index().sort_values('Ageing day', ascending=False).head(10)
        fig3 = px.bar(sla_days_df, x='Parent ID 1', y='Ageing day', text_auto=True, color='Ageing day', color_continuous_scale='Reds')
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("🎉 ไม่มีงานที่ Over SLA")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<h3>📋 Outstanding Ticket Details (Editable)</h3>", unsafe_allow_html=True)
st.markdown("💬 **คำแนะนำ:** คุณสามารถดับเบิ้ลคลิกที่ช่อง `Note Status` เพื่อพิมพ์อัปเดตสถานะงานได้เลย ข้อมูลจะถูกบันทึกอัตโนมัติลง Google Sheets")

# Column configuration for Data Editor
column_config = {
    "Note Status": st.column_config.TextColumn("Note Status ✏️", width="large", required=False),
    "Ticket Type": st.column_config.TextColumn("Ticket Type", disabled=True),
    "Ticket No.": st.column_config.TextColumn("Ticket No.", disabled=True),
    "Status": st.column_config.TextColumn("Status", disabled=True),
    "Parent ID 1": st.column_config.TextColumn("Parent ID 1", disabled=True),
    "Child ID 2": st.column_config.TextColumn("Child ID 2", disabled=True),
    "Name Staff": st.column_config.TextColumn("Name Staff", disabled=True),
    "Ageing day": st.column_config.NumberColumn("Ageing day", disabled=True),
    "Case - (Duration)-Problem": st.column_config.TextColumn("Case - (Duration)-Problem", disabled=True),
    "Duration(Days)": st.column_config.NumberColumn("Duration(Days)", disabled=True),
    "Create Date/Time": st.column_config.TextColumn("Create Date/Time", disabled=True),
    "Details": st.column_config.TextColumn("Details", disabled=True),
    "Solution for IT": st.column_config.TextColumn("Solution for IT", disabled=True),
    "SLA Rank": st.column_config.TextColumn("SLA Rank", disabled=True),
    "Start SLA date": st.column_config.TextColumn("Start SLA date", disabled=True),
    "SLA Due": st.column_config.TextColumn("SLA Due", disabled=True),
    "Actual SLA": st.column_config.TextColumn("Actual SLA", disabled=True),
    "Count of status case": st.column_config.NumberColumn("Count", disabled=True)
}

def highlight_note(s):
    return ['background-color: #E0F2FE' if s.name == 'Note Status' else '' for i in s]

st.markdown("<div class='card'>", unsafe_allow_html=True)
styled_df = out_df.style.apply(highlight_note).set_properties(**{'font-size': '14px'})
edited_df = st.data_editor(styled_df, column_config=column_config, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)

# Detect changes and save
if not edited_df.equals(out_df):
    diff = edited_df[edited_df['Note Status'] != out_df['Note Status']]
    if not diff.empty:
        current_notes_df = load_ticket_notes()
        for _, row in diff.iterrows():
            t_id = str(row['Ticket No.']).replace('.0', '')
            note = str(row['Note Status'])
            
            if not current_notes_df.empty and 'TicketID' in current_notes_df.columns:
                current_notes_df['TicketID'] = current_notes_df['TicketID'].astype(str).str.replace(r'\.0$', '', regex=True)
                
            if not current_notes_df.empty and 'TicketID' in current_notes_df.columns and t_id in current_notes_df['TicketID'].values:
                current_notes_df.loc[current_notes_df['TicketID'] == t_id, 'Note Status'] = note
                current_notes_df.loc[current_notes_df['TicketID'] == t_id, 'UpdatedTime'] = str(pd.Timestamp.now())
            else:
                new_row = pd.DataFrame([{"TicketID": t_id, "Note Status": note, "UpdatedBy": "User", "UpdatedTime": str(pd.Timestamp.now())}])
                current_notes_df = pd.concat([current_notes_df, new_row], ignore_index=True)
                
        save_ticket_notes(current_notes_df)
        st.success("✅ บันทึก Note Status เรียบร้อยแล้ว!")
        
# Add Download Button
st.markdown("<br>", unsafe_allow_html=True)
import datetime
today_str = datetime.datetime.now().strftime("%Y-%m-%d")

excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    edited_df.to_excel(writer, index=False, sheet_name='Outstanding')

st.download_button(
    label="📥 Export Outstanding Tickets (Excel)",
    data=excel_buffer.getvalue(),
    file_name=f"outstanding_{today_str}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
