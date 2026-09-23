import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from datetime import datetime, timedelta

# ==========================================
# PAGE CONFIGURATION & THEME
# ==========================================

# Semantic Colors
C_BREACH = "#EF4444" # Red
C_NEAR = "#F59E0B"   # Orange/Amber
C_OPEN = "#3B82F6"   # Blue
C_RESOLVED = "#10B981" # Green
C_COORD = "#8B5CF6"  # Purple

# Additional vibrant palette for charts
VIBRANT_PALETTE = px.colors.qualitative.Prism

# Custom CSS for Clean & Soft Light Theme
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #F8FAFC;
    }
    
    /* Hide native styling components */
    
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
        margin-top: 10px;
        margin-left: 10px;
    }
    [data-testid='stSidebarCollapseButton'] {
        color: #0F766E !important;
    }

    
    /* Sidebar Nav styling for larger text */
    [data-testid="stSidebarNav"] ul li span {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F1F5F9;
        border-right: 1px solid #E2E8F0;
    }
    
    /* KPI Cards & Chart Containers */
    .dashboard-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    
    .kpi-title {
        color: #64748B;
        font-size: 14px;
        font-weight: 500;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    
    .kpi-value {
        color: #0F172A;
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 5px;
    }
    
    /* Header typography */
    h1, h2, h3, h4 {
        color: #0F172A;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F8FAFC;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        border-bottom: 2px solid #3B82F6;
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
st.sidebar.markdown("### ⚙️ Data Upload & Settings")
uploaded_file = st.sidebar.file_uploader("Upload Ticket Excel Data", type=["xlsx", "xls"])

LATEST_UPLOAD = "latest_uploaded_data.xlsx"

import json
METADATA_FILE = "upload_metadata.json"

from google_sheets_helper import upload_ticket_data_to_gsheets, load_ticket_data_from_gsheets

# Save newly uploaded file to GSheets
if uploaded_file:
    with st.spinner("กำลังอัปโหลดข้อมูลขึ้น Google Sheets..."):
        try:
            # Auto-detect header
            preview = pd.read_excel(uploaded_file, header=None, nrows=20)
            header_idx = 0
            for i, row in preview.iterrows():
                if 'TicketID' in str(row.values) or 'Ticket ID' in str(row.values):
                    header_idx = i
                    break
            
            # Reset pointer
            uploaded_file.seek(0)
            df_upload = pd.read_excel(uploaded_file, header=header_idx)
            
            # Upload to GSheets
            upload_ticket_data_to_gsheets(df_upload)
            
            # Save metadata locally just for name display
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"filename": uploaded_file.name}, f)
                
            st.sidebar.success("อัปโหลดขึ้น Google Sheets สำเร็จ!")
            st.cache_data.clear() # Clear cache to fetch new data
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
        
        # Datetime conversion
        for col in ['CreateDate', 'FinishDate', 'UpdateDate', 'EndSLADate']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                
        # Fill missing values
        text_cols = ['Status', 'Priority', 'ResponseBy', 'Requester', 'CategoryLevel1', 'Solution/Defect LV 1', 'DescriptionOfProblem', 'SolutionForUser']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', 'Unknown')
                df[col] = df[col].fillna('Unknown')
                
        # [Disabled] Filter by Team GP Account&Finance
        # team_file_path = 'Team GP Account&Finance.xlsx'
        # if os.path.exists(team_file_path) and 'ResponseBy' in df.columns:
        #     team_df = pd.read_excel(team_file_path)
        #     if 'รายชื่อทีม' in team_df.columns:
        #         team_names_clean = team_df['รายชื่อทีม'].dropna().astype(str).str.replace('^คุณ', '', regex=True).str.strip().tolist()
        #         team_names_raw = team_df['รายชื่อทีม'].dropna().astype(str).str.strip().tolist()
        #         allowed_names = set(team_names_clean + team_names_raw)
        #         df = df[df['ResponseBy'].isin(allowed_names)]
                
        # SLA Calculation Logic
        current_time = pd.Timestamp.now()
        if 'UpdateDate' in df.columns and not df['UpdateDate'].isna().all():
            current_time = df['UpdateDate'].max()
            
        def eval_sla(row):
            status = str(row.get('Status', ''))
            is_closed = 'Complete' in status or 'Closed' in status or 'Resolve' in status or 'Cancel' in status or 'Reject' in status
            end_sla = row.get('EndSLADate')
            finish = row.get('FinishDate')
            
            if pd.isna(end_sla):
                return 'Within SLA' 
                
            if is_closed:
                if not pd.isna(finish) and finish > end_sla:
                    return 'SLA Breached'
                return 'Within SLA'
            else:
                if current_time > end_sla:
                    return 'SLA Breached'
                elif (end_sla - current_time).total_seconds() <= 86400: # 1 Day
                    return 'Near SLA (Urgent)'
                return 'Within SLA'
                
        df['SLA_Status'] = df.apply(eval_sla, axis=1)
        
        # Coordinate Flag
        if 'RefTicket' in df.columns:
            # Mark as coordinate if RefTicket is not empty and not '0' or '0.0'
            df['IsCoordinate'] = df['RefTicket'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).apply(lambda x: x != '' and x != 'nan' and x != '0' and x != 'None')
        else:
            df['IsCoordinate'] = False
            
        # Open Flag
        df['IsOpen'] = ~df['Status'].str.contains('Complete|Closed|Resolve|Reject|Cancel|Close', case=False, na=False)
        
        # Only count OPEN coordinate tickets
        df['IsCoordinate'] = df['IsCoordinate'] & df['IsOpen']

        # Extract Date for trend
        if 'CreateDate' in df.columns:
            df['CreateDate_Day'] = df['CreateDate'].dt.date
            
        return df
    except Exception as e:
        st.error(f"Error parsing data: {e}")
        return pd.DataFrame()


df = load_data()

if df.empty:
    st.warning("No valid dataset found. Please upload a file via the sidebar.")
    st.stop()

# ==========================================
# SIDEBAR FILTERS
# ==========================================
st.sidebar.markdown("### 🔍 Filters")

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

f_status = filter_multiselect("Status", "Status", df)
f_ticket_type = filter_multiselect("Ticket Type", "TicketType", df)
f_category = filter_multiselect("Category (Level 1)", "CategoryLevel1", df)
f_defect1 = filter_multiselect("Defect Level 1", "Solution/Defect LV 1", df)
f_defect2 = filter_multiselect("Defect Level 2", "Solution/Defect LV 2", df)
f_assignee = filter_multiselect("Assignee (Response By)", "ResponseBy", df)

filtered_df = df.copy()
if len(date_range) == 2:
    filtered_df = filtered_df[(filtered_df['CreateDate_Day'] >= date_range[0]) & (filtered_df['CreateDate_Day'] <= date_range[1])]
if f_status: filtered_df = filtered_df[filtered_df['Status'].isin(f_status)]
if f_ticket_type: filtered_df = filtered_df[filtered_df['TicketType'].isin(f_ticket_type)]
if f_category: filtered_df = filtered_df[filtered_df['CategoryLevel1'].isin(f_category)]
if f_defect1: filtered_df = filtered_df[filtered_df['Solution/Defect LV 1'].isin(f_defect1)]
if f_defect2: filtered_df = filtered_df[filtered_df['Solution/Defect LV 2'].isin(f_defect2)]
if f_assignee: filtered_df = filtered_df[filtered_df['ResponseBy'].isin(f_assignee)]

# ==========================================
# HEADER & KPIs
# ==========================================
st.markdown("<h2>IT Service & Ticket Management</h2>", unsafe_allow_html=True)
original_filename = "Default System Data"
if os.path.exists(METADATA_FILE):
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
            original_filename = meta.get("filename", "Unknown")
    except: pass
elif 'Ticket_detail_report' in target_file if 'target_file' in locals() else False:
    original_filename = "Default System Data"

date_text = "N/A"
if not df.empty and 'CreateDate_Day' in df.columns and not df['CreateDate_Day'].isna().all():
    s_date = df['CreateDate_Day'].min().strftime('%d %b %Y')
    e_date = df['CreateDate_Day'].max().strftime('%d %b %Y')
    date_text = f"{s_date} - {e_date}"

st.markdown(f"<p style='color: #64748B;'>Interactive Executive Dashboard | 📁 File: <b>{original_filename}</b> | 📅 Date Range: <b>{date_text}</b></p>", unsafe_allow_html=True)

total_tickets = len(filtered_df)
open_tickets = len(filtered_df[filtered_df['IsOpen'] == True])
breached_tickets = len(filtered_df[filtered_df['SLA_Status'] == 'SLA Breached'])
near_sla_tickets = len(filtered_df[filtered_df['SLA_Status'] == 'Near SLA (Urgent)'])
coord_tickets = filtered_df['IsCoordinate'].sum() if 'IsCoordinate' in filtered_df else 0

k1, k2, k3, k4, k5 = st.columns(5)

def kpi_html(title, value, color="#0F172A", highlight=False):
    style_ext = f"border-bottom: 4px solid {color};" if highlight else ""
    return f"""
    <div class="dashboard-card" style="{style_ext}">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
    </div>
    """

k1.markdown(kpi_html("Total Tickets", f"{total_tickets:,}"), unsafe_allow_html=True)
k2.markdown(kpi_html("Open / In-Progress", f"{open_tickets:,}", C_OPEN, True), unsafe_allow_html=True)
k3.markdown(kpi_html("SLA Breached", f"{breached_tickets:,}", C_BREACH, True), unsafe_allow_html=True)
k4.markdown(kpi_html("Near SLA (1 Day)", f"{near_sla_tickets:,}", C_NEAR, True), unsafe_allow_html=True)
k5.markdown(kpi_html("Coordinate", f"{coord_tickets:,}", C_COORD, True), unsafe_allow_html=True)

# ==========================================
# 🚨 CRITICAL ACTION REQUIRED (NEW SECTION)
# ==========================================
st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
st.markdown("<h3>🚨 Critical Action Required <span style='font-size: 16px; color: #64748B;'>(ตารางเป้าหมายที่ต้องจัดการด่วน)</span></h3>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "🔴 SLA Risk (เกิน/ใกล้เกินกำหนด)", 
    "🔥 High Priority (ยังไม่แก้ไข)", 
    "👤 Unassigned (ยังไม่มีคนรับ)", 
    "🟣 Coordinate (ต้องประสานงาน)"
])

display_cols = ['TicketID', 'Status', 'SLA_Status', 'Priority', 'CategoryLevel1', 'ResponseBy', 'DescriptionOfProblem', 'SolutionForUser']
display_cols = [c for c in display_cols if c in filtered_df.columns]

def display_dataframe(df_subset):
    if df_subset.empty:
        st.success("🎉 ไม่มีรายการที่ต้องจัดการในหมวดหมู่นี้")
    else:
        st.dataframe(df_subset[display_cols], use_container_width=True, hide_index=True)

with tab1:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    sla_risk_df = filtered_df[filtered_df['SLA_Status'].isin(['SLA Breached', 'Near SLA (Urgent)'])]
    
    c_risk1, c_risk2 = st.columns([1, 2])
    with c_risk1:
        if not sla_risk_df.empty and 'ResponseBy' in sla_risk_df.columns:
            risk_chart = px.histogram(sla_risk_df, y='ResponseBy', color='SLA_Status', orientation='h',
                                      color_discrete_map={'SLA Breached': C_BREACH, 'Near SLA (Urgent)': C_NEAR},
                                      title="SLA Risk by Assignee")
            st.plotly_chart(risk_chart, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลกราฟ")
            
    with c_risk2:
        st.markdown("**📋 รายการ Ticket ที่หลุด SLA และใกล้หลุด SLA**")
        display_dataframe(sla_risk_df)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    if 'Priority' in filtered_df.columns:
        high_pri_df = filtered_df[(filtered_df['Priority'].str.contains('High|Critical|Urgent', case=False, na=False)) & (filtered_df['IsOpen'] == True)]
        st.markdown("**🔥 รายการ Ticket ระดับ High Priority ที่ยังคงเปิดอยู่**")
        display_dataframe(high_pri_df)
    else:
        st.info("ไม่พบคอลัมน์ Priority")
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    if 'ResponseBy' in filtered_df.columns:
        unassigned_df = filtered_df[(filtered_df['ResponseBy'].str.contains('Unknown|-|nan', case=False, na=False) | (filtered_df['ResponseBy'] == '')) & (filtered_df['IsOpen'] == True)]
        st.markdown("**👤 รายการ Ticket ที่เปิดไว้แต่ยังไม่มีผู้รับผิดชอบ**")
        display_dataframe(unassigned_df)
    else:
        st.info("ไม่พบคอลัมน์ ResponseBy")
    st.markdown("</div>", unsafe_allow_html=True)

with tab4:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    coord_df = filtered_df[filtered_df['IsCoordinate'] == True]
    
    c_coord1, c_coord2 = st.columns([1, 2])
    with c_coord1:
        if not coord_df.empty and 'CategoryLevel1' in coord_df.columns:
            coord_chart = px.pie(coord_df, names='CategoryLevel1', hole=0.5, 
                                 title="Coordinate Cases by Category",
                                 color_discrete_sequence=px.colors.sequential.Purples_r)
            coord_chart.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(coord_chart, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลกราฟ")
            
    with c_coord2:
        st.markdown("**🟣 รายการเอกสาร / Ticket ที่อยู่ระหว่างการประสานงาน**")
        
        # Ensure RefTicket is displayed
        temp_display_cols = display_cols.copy()
        if 'RefTicket' in coord_df.columns and 'RefTicket' not in temp_display_cols:
            temp_display_cols.insert(1, 'RefTicket')
        if not coord_df.empty:
            st.dataframe(coord_df[temp_display_cols], use_container_width=True, hide_index=True)
        else:
            st.success("🎉 ไม่มีรายการที่ต้องจัดการในหมวดหมู่นี้")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# GENERAL OVERVIEW CHARTS
# ==========================================
st.markdown("<h3>📊 General Overview</h3>", unsafe_allow_html=True)
c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown("<h4>🎯 SLA Health (All Tickets)</h4>", unsafe_allow_html=True)
    sla_data = filtered_df['SLA_Status'].value_counts().reset_index()
    sla_data.columns = ['Status', 'Count']
    color_map = {'Within SLA': C_RESOLVED, 'Near SLA (Urgent)': C_NEAR, 'SLA Breached': C_BREACH}
    fig_donut = px.pie(sla_data, names='Status', values='Count', hole=0.5, color='Status', color_discrete_map=color_map)
    fig_donut.update_layout(
        font=dict(size=14),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_donut, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown("<h4>⚠️ Top 5 Defect Categories</h4>", unsafe_allow_html=True)
    if 'Solution/Defect LV 1' in filtered_df.columns:
        def_counts = filtered_df[~filtered_df['Solution/Defect LV 1'].str.contains('Unknown', case=False)]['Solution/Defect LV 1'].value_counts().head(5).reset_index()
        def_counts.columns = ['Defect', 'Count']
        fig_bar = px.bar(def_counts, x='Count', y='Defect', orientation='h', text_auto=True, color='Defect', color_discrete_sequence=VIBRANT_PALETTE)
        fig_bar.update_layout(
            font=dict(size=14),
            yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=True, gridcolor='#E2E8F0'), yaxis_title="", showlegend=False
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

c3, c4 = st.columns([1, 1])

with c3:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown("<h4>👥 Top Assignee Workload</h4>", unsafe_allow_html=True)
    if 'ResponseBy' in filtered_df.columns:
        res_counts = filtered_df[~filtered_df['ResponseBy'].str.contains('Unknown', case=False)]['ResponseBy'].value_counts().head(5).reset_index()
        res_counts.columns = ['Assignee', 'Tickets']
        fig_res = px.bar(res_counts, x='Assignee', y='Tickets', text_auto=True, color='Assignee', color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_res.update_layout(
            font=dict(size=14),
            plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(showgrid=True, gridcolor='#E2E8F0'), xaxis_title="", showlegend=False
        )
        st.plotly_chart(fig_res, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c4:
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown("<h4>📈 Ticket Volume Trend</h4>", unsafe_allow_html=True)
    if 'CreateDate_Day' in filtered_df.columns:
        trend = filtered_df.groupby('CreateDate_Day').size().reset_index(name='Tickets')
        fig_trend = px.line(trend, x='CreateDate_Day', y='Tickets', markers=True)
        fig_trend.update_layout(
            font=dict(size=14),
            plot_bgcolor='rgba(0,0,0,0)', xaxis_title="", yaxis_title="Tickets", margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#E2E8F0')
        )
        fig_trend.update_traces(line_color=C_OPEN, line_width=4, marker=dict(size=10, color=C_OPEN))
        st.plotly_chart(fig_trend, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
st.markdown("<h4>🧩 Defect Breakdown (LV1 ➔ LV2)</h4>", unsafe_allow_html=True)
if 'Solution/Defect LV 1' in filtered_df.columns and 'Solution/Defect LV 2' in filtered_df.columns:
    defect_df = filtered_df[~filtered_df['Solution/Defect LV 1'].str.contains('Unknown', case=False)].copy()
    if not defect_df.empty:
        # Fill missing LV2 so sunburst doesn't break
        defect_df['Solution/Defect LV 2'] = defect_df['Solution/Defect LV 2'].fillna('Not Specified')
        fig_sunburst = px.sunburst(defect_df, path=['Solution/Defect LV 1', 'Solution/Defect LV 2'], 
                                   color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_sunburst.update_traces(textinfo="label+percent parent")
        st.plotly_chart(fig_sunburst, use_container_width=True)
    else:
        st.info("ไม่มีข้อมูล Defect")
st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# AI INSIGHTS
# ==========================================
st.markdown("<div class='dashboard-card' style='border-left: 5px solid #8B5CF6; background-color: #F8FAFC;'>", unsafe_allow_html=True)
st.markdown("<h3>💡 AI Business Insights</h3>", unsafe_allow_html=True)

insights = []
sla_breach_rate = (breached_tickets / total_tickets * 100) if total_tickets > 0 else 0

if sla_breach_rate > 10:
    insights.append(f"🔴 **SLA Alert:** งานที่ล่าช้าเกิน SLA มีสัดส่วนค่อนข้างสูง ({sla_breach_rate:.1f}%) แนะนำให้ติดตามงานที่ตกค้างทันทีที่ Tab 'SLA Risk'")
if 'Solution/Defect LV 1' in filtered_df.columns:
    top_def = filtered_df[~filtered_df['Solution/Defect LV 1'].str.contains('Unknown', case=False)]['Solution/Defect LV 1'].value_counts()
    if not top_def.empty:
        insights.append(f"🔍 **Top Issue:** ปัญหาที่พบมากที่สุดคือ **'{top_def.index[0]}'** ({top_def.iloc[0]} รายการ) ควรสร้าง Knowledge Base เผยแพร่ให้ผู้ใช้งาน")
if 'ResponseBy' in filtered_df.columns:
    top_res = filtered_df[~filtered_df['ResponseBy'].str.contains('Unknown', case=False)]['ResponseBy'].value_counts()
    if not top_res.empty:
        insights.append(f"👥 **Workload:** ทีมงาน/ผู้รับผิดชอบที่มีเคสในมือมากที่สุดคือ **{top_res.index[0]}**")
if coord_tickets > 0:
    insights.append(f"🟣 **Coordination:** มีงานที่อยู่ระหว่างประสานงาน (Coordinate) ถึง {coord_tickets} งาน ตรวจสอบได้ที่ Tab 'Coordinate'")

if not insights:
    insights.append("✅ ไม่พบปัญหาที่น่ากังวล ระบบอยู่ในสถานะปกติ")

for i, ins in enumerate(insights, 1):
    st.markdown(f"<p style='margin-bottom: 5px; font-size: 15px;'>{ins}</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# FULL DATA TABLE
# ==========================================
st.markdown("<h3>📋 All Ticket Data</h3>", unsafe_allow_html=True)
st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)

def color_breach(row):
    color = ''
    if row.get('SLA_Status') == 'SLA Breached':
        color = 'background-color: #FEE2E2; color: #991B1B;'
    elif row.get('SLA_Status') == 'Near SLA (Urgent)':
        color = 'background-color: #FEF3C7; color: #92400E;'
    return [color] * len(row)

if display_cols:
    styled_df = filtered_df[display_cols].style.apply(color_breach, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=400)
else:
    st.info("No data available.")
st.markdown("</div>", unsafe_allow_html=True)
