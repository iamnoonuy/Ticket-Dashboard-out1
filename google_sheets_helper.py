import json
import os
import gspread
import streamlit as st
import pandas as pd
from gspread_dataframe import set_with_dataframe, get_as_dataframe

# Built-in fallback mapping for Team GP (Thai Name, ResponseByID, English Name)
TEAM_GP_DEFAULT_MAP = [
    ("คุณกิติมา จันทร์เมือง", "KITIMA.CHU", "KITIMA CHUNMUANG"),
    ("คุณประชุมพร ชินกิจการ", "PRACHUMPORN.PRE", "PRACHUMPORN CHINKIJKARN"),
    ("คุณบุญตา สถาพร", "BOONTA.SAT", "BOONTA SATHAPORN"),
    ("คุณสัชฌกร โรมวิสัย", "SACHAKORN.ROA", "SACHAKORN ROAMVISAI"),
    ("คุณพรทิพย์ ลิ้มตระกูลเจริญ", "PORNTHIP.LIM", "PORNTHIP LIMTRAKULJAREAN"),
    ("คุณฉัตรา ดวงจันทร์", "CHARTRA.DUA", "CHARTRA DUANGJAN"),
    ("คุณฝนทิพย์ วิโรจน์ชีวัน", "FONTIP.WIR", "FONTIP WIROJCHEEWAN"),
    ("คุณธีรดา คุ้มครอง", "THREERADA.KOO", "THREERADA KOOMKRONG"),
    ("คุณณัฐธิดา อุดมดี", "NATTHIDA.UDO", "NATTHIDA UDOMDI"),
    ("คุณนุสรากุล ทองเม้า", "NUSARAKUN.YOT", "NUSARAKUN THONGMAO"),
    ("คุณนิวัฒน์ เอี่ยมวัชรมาศ", "NIWAT.IAM", "NIWAT IAMWATCHARAMAS"),
    ("คุณปิยะฉัตร แก้วทอง", "PIYACHAT.KAE", "PIYACHAT KAEWTONG"),
    ("คุณศิริวรรณ สรไชยากร", "SIRIWAN.SOR", "SIRIWAN SORNCHAIYAGORN"),
    ("คุณวิลาวัณย์ จันทร์สุกรี", "WILAWAN.CHU", "WILAWAN CHUNSUGREE"),
    ("คุณอลิสา นวนไทย", "ALISA.NUA", "ALISA NUANTHAI"),
    ("คุณปกฉัตร แซ่เซียว", "POKCHAT.SAE", "POKCHAT SAESIAO"),
    ("คุณนภสินธุ์ ขุนเทพ", "NOPPASIN.KHU", "NOPPASIN KHUNTHEP"),
    ("คุณพัชเรศ ศานติวิจัย", "PATCHARES.SAR", "PATCHARES SANTIWIJAI"),
    ("คุณณัฐา ธำรงลักษณ์", "NATTHA.THU", "NATTHA THUMRONGLUCK"),
    ("คุณสวรส นาคนาคา", "SAVAROS.WAI", "SAVAROS NAKNAKHA"),
    ("คุณเอื้องหลวง แซ่คิว", "AUENGLUANG.SAE", "AUENGLUANG SAEKIEW"),
    ("คุณภาคภูมิ อนุพงษ์ภิชาติ", "PARKPOOM.ANU", "PARKPOOM ANUPONGPICHART"),
    ("คุณญาณิศา วงศ์ศุภา", "YANISA.WON", "YANISA WONGSUPHA"),
    ("คุณธนพล ตั๊นตระกูล", "THANAPOL.TAN", "THANAPOL TANTRAKUL"),
    ("คุณฑิติยา นิยม", "THITIYA.NIY", "THITIYA NIYOM"),
    ("คุณเบญญาลักษณ์ ทองพูล", "BENYALUCK.THO", "BENYALUCK THONGPOOL"),
    ("คุณโสภณ ทิพยวัชรกุล", "SOPHON.THI", "SOPHON THIPPAYAWATCHARAKUL"),
    ("คุณรณพล ประถมบุตร", "RONNAPON.PRA", "RONNAPON PRATHOMBOOT"),
    ("คุณรังสิมันตุ์ ชูสนุก", "RANGSIMANT.SHO", "RANGSIMANT SHOOSANUK"),
    ("คุณศุภเดช บริสุทธนารักษ์", "SUPADEJ.BOR", "SUPADEJ BORISUTTHANARAK"),
    ("คุณชาคร สันธากร", "CHAKORN.SAN", "CHAKORN SANTHAKORN"),
    ("คุณกชกร จันทะไทย", "KOTCHAKORN.JAN", "KOTCHAKORN JANTHATHAI"),
    ("คุณซูลกิฟลี สามะ", "ZULKIFLEE.SAM", "ZULKIFLEE SAMA"),
    ("คุณพิชญ์สินี สุรินธรรม", "PITCHSINEE.SUR", "PITCHSINEE SURINTHAM"),
    ("คุณพิชชานันท์ นูรักษ์", "PITCHANAN.NOO", "PITCHANAN NOORAK"),
    ("คุณโศภิษฐา ทิพย์ศักดิ์", "SOPITTHA.TIP", "SOPITTHA TIPSAK"),
    ("คุณกฤษณะ ประสิทธิ์", "KRITSANA.PRA", "KRITSANA PRASIT"),
    ("คุณวงศธร กรรโณ", "WONGSATHORN.KAN", "WONGSATHORN KANNO"),
    ("คุณษมณณัฐ ประพันธ์โรจน์", "SAMONNAT.PRA", "SAMONNAT PRAPHANROJ"),
    ("คุณอรวรรณ อ่อนแสง", "ORAWAN.AON", "ORAWAN AONSAENG"),
    ("คุณธวัลรัตน์ จันขัน", "THAWANRAT.JAN", "THAWANRAT JANKHAN"),
    ("คุณจินดารัตน์ โรจนัด", "JINDARAT.ROJ", "JINDARAT ROJANAT"),
    ("คุณภัชรพันธ์ จิตไธสง", "PATCHARAPHAN.JIT", "PATCHARAPHAN JITTHAISONG"),
    ("คุณนาธนิน จิตจำนงค์", "NATHANIN.JIT", "NATHANIN JITJAMNONG"),
    ("คุณปัญญา เทือกมูล", "PANYA.THU", "PANYA THUAKMOON"),
    ("คุณอัมรัตน์ กุลศรีวนรัตน์", "AMMARAT.KUL", "AMMARAT KULSRIWONRAT"),
    ("คุณวิมลมณี ฉัตรแก้วสมบูรณ์", "WIMONMANEE.CHA", "WIMONMANEE CHATKAEWSOMBOON"),
    ("คุณตุลาพันธ์ ทองวงศ์", "TULAPHAN.THO", "TULAPHAN THONGWONG"),
    ("คุณเจตน์สฤษฏิ์ แก้วสอาด", "JETSARIT.KAE", "JETSARIT KAEWSAARD"),
]

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
            
    set_with_dataframe(ws, df)

@st.cache_data(ttl=300) # Cache for 5 minutes
def load_ticket_data_from_gsheets():
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet("ticket_data")
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
        
    df = get_as_dataframe(ws, evaluate_formulas=True)
    df = df.dropna(how='all')
    if df.empty:
        return df

    # Normalize column aliases across different report versions
    if 'BusinessGroup' not in df.columns and 'Business' in df.columns:
        df['BusinessGroup'] = df['Business']
    if 'SLAStatus' not in df.columns and 'ActualSLA' in df.columns:
        df['SLAStatus'] = df['ActualSLA']

    # Build lookup tables from default map + team_gp worksheet
    id_to_thai = {item[1].upper(): item[0].replace('คุณ', '').strip() for item in TEAM_GP_DEFAULT_MAP}
    en_to_thai = {item[2].upper(): item[0].replace('คุณ', '').strip() for item in TEAM_GP_DEFAULT_MAP}
    allowed_thai = {item[0].replace('คุณ', '').strip() for item in TEAM_GP_DEFAULT_MAP} | {item[0].strip() for item in TEAM_GP_DEFAULT_MAP}
    allowed_ids = {item[1].upper() for item in TEAM_GP_DEFAULT_MAP}
    allowed_en = {item[2].upper() for item in TEAM_GP_DEFAULT_MAP}

    try:
        team_ws = sh.worksheet("team_gp")
        team_df = get_as_dataframe(team_ws).dropna(how='all')
        if 'รายชื่อทีม' in team_df.columns:
            for _, row in team_df.iterrows():
                raw_th = str(row.get('รายชื่อทีม', '')).strip()
                clean_th = raw_th.replace('คุณ', '').strip()
                if clean_th and clean_th != 'nan':
                    allowed_thai.add(clean_th)
                    allowed_thai.add(raw_th)
                if 'ResponseByID' in team_df.columns and pd.notna(row.get('ResponseByID')):
                    rid = str(row['ResponseByID']).strip().upper()
                    if rid and rid != 'NAN':
                        allowed_ids.add(rid)
                        if clean_th:
                            id_to_thai[rid] = clean_th
                if 'Name_EN' in team_df.columns and pd.notna(row.get('Name_EN')):
                    nen = str(row['Name_EN']).strip().upper()
                    if nen and nen != 'NAN':
                        allowed_en.add(nen)
                        if clean_th:
                            en_to_thai[nen] = clean_th
    except Exception:
        pass

    # Filter & normalize ResponseBy using both ResponseBy and ResponseByID
    if 'ResponseBy' in df.columns:
        resp_by_raw = df['ResponseBy'].fillna('').astype(str).str.strip()
        resp_by_RawClean = resp_by_raw.replace({'nan': '', 'None': '', 'Unknown': '', '-': ''})
        resp_by_up = resp_by_RawClean.str.upper()

        if 'ResponseByID' in df.columns:
            resp_id_raw = df['ResponseByID'].fillna('').astype(str).str.strip()
            resp_id_clean = resp_id_raw.replace({'nan': '', 'None': '', '0': '', '0.0': ''})
            resp_id_up = resp_id_clean.str.upper()
        else:
            resp_id_up = pd.Series([''] * len(df), index=df.index)

        # Match against Team GP (by ID, English name, or Thai name)
        clean_th_series = resp_by_RawClean.str.replace('^คุณ', '', regex=True).str.strip()
        is_team_member = (
            resp_id_up.isin(allowed_ids) |
            resp_by_up.isin(allowed_en) |
            resp_by_RawClean.isin(allowed_thai) |
            clean_th_series.isin(allowed_thai)
        )

        # Unassigned tickets (both ResponseBy and ResponseByID are blank)
        is_unassigned = (resp_by_RawClean == '') & (resp_id_up == '')

        # Map ResponseBy to Thai name when matched so charts/filters display consistent Thai names
        mapped_names = []
        for idx in df.index:
            r_id = resp_id_up.loc[idx]
            r_en = resp_by_up.loc[idx]
            r_th = clean_th_series.loc[idx]
            if r_id in id_to_thai:
                mapped_names.append(id_to_thai[r_id])
            elif r_en in en_to_thai:
                mapped_names.append(en_to_thai[r_en])
            elif r_th in allowed_thai and r_th != '':
                mapped_names.append(r_th)
            elif resp_by_RawClean.loc[idx] != '':
                mapped_names.append(resp_by_RawClean.loc[idx])
            elif r_id != '':
                mapped_names.append(r_id)
            else:
                mapped_names.append('Unknown')
        df['ResponseBy'] = mapped_names

        df = df[is_team_member | is_unassigned].copy()

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
    
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
            
    set_with_dataframe(ws, df)
