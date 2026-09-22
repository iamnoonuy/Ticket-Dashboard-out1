import json
import gspread
import streamlit as st
import pandas as pd
from gspread_dataframe import set_with_dataframe, get_as_dataframe

@st.cache_resource
def get_gspread_client():
    creds_json = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    gc = gspread.service_account_from_dict(creds_json)
    return gc

@st.cache_resource
def get_spreadsheet():
    gc = get_gspread_client()
    url = st.secrets["GSHEETS_URL"]
    sh = gc.open_by_url(url)
    return sh

def load_users_from_gsheets():
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet("users")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="users", rows="100", cols="10")
        
    records = ws.get_all_records()
    users_dict = {}
    for r in records:
        if 'username' in r:
            users_dict[str(r['username'])] = {
                "password": str(r.get('password', '')),
                "role": str(r.get('role', 'user')),
                "allowed_pages": json.loads(r.get('allowed_pages', '[]'))
            }
    return users_dict

def save_users_to_gsheets(users_dict):
    sh = get_spreadsheet()
    ws = sh.worksheet("users")
    
    # Convert dict back to list of dicts
    data = []
    for uname, udata in users_dict.items():
        data.append({
            "username": uname,
            "password": udata["password"],
            "role": udata["role"],
            "allowed_pages": json.dumps(udata["allowed_pages"])
        })
        
    df = pd.DataFrame(data)
    ws.clear()
    if not df.empty:
        set_with_dataframe(ws, df)

def upload_ticket_data_to_gsheets(df):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet("ticket_data")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="ticket_data", rows="1000", cols="50")
        
    ws.clear()
    
    # Convert datetime columns to string to avoid JSON serialization errors in gspread
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
            
    # set_with_dataframe uploads large dfs much faster
    set_with_dataframe(ws, df)

import os

@st.cache_data(ttl=300) # Cache for 5 minutes
def load_ticket_data_from_gsheets():
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet("ticket_data")
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
        
    df = get_as_dataframe(ws, evaluate_formulas=True)
    # Drop rows where all columns are NaN (gspread_dataframe reads the entire sheet size)
    df = df.dropna(how='all')
    
    # Filter by Team GP from Google Sheets
    if 'ResponseBy' in df.columns:
        try:
            team_ws = sh.worksheet("team_gp")
            team_df = get_as_dataframe(team_ws)
            team_df = team_df.dropna(how='all')
            if 'รายชื่อทีม' in team_df.columns:
                team_names_clean = team_df['รายชื่อทีม'].dropna().astype(str).str.replace('^คุณ', '', regex=True).str.strip().tolist()
                team_names_raw = team_df['รายชื่อทีม'].dropna().astype(str).str.strip().tolist()
                allowed_names = set(team_names_clean + team_names_raw)
                
                # We also need to keep unassigned/unknown tickets so the dashboard can still track them
                unassigned_flags = df['ResponseBy'].str.contains('Unknown|-|nan', case=False, na=False) | (df['ResponseBy'] == '')
                
                df = df[df['ResponseBy'].isin(allowed_names) | unassigned_flags]
        except Exception as e:
            pass
            
    return df

def load_ticket_notes():
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet("ticket_notes")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="ticket_notes", rows="1000", cols="4")
        ws.append_row(["TicketID", "Note Status", "UpdatedBy", "UpdatedTime"])
        
    df = get_as_dataframe(ws).dropna(how='all')
    return df

def save_ticket_notes(df):
    sh = get_spreadsheet()
    ws = sh.worksheet("ticket_notes")
    ws.clear()
    
    # Avoid JSON serialization error
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
            
    set_with_dataframe(ws, df)
