import streamlit as st
import pandas as pd
import os
import pydeck as pdk
import base64
import re
import math

# Page Configuration
st.set_page_config(
    page_title="Optimum Home - Door-to-Door Route Planner",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authorized Users Database (Includes Adrion Jones, Martez Geddis, Carlos, Juan, Pedro, Derek)
if 'USERS_DB' not in st.session_state:
    st.session_state['USERS_DB'] = {
        "juan.lopez@optimumhome.org": {"name": "Juan Lopez", "role": "admin", "phone": "8329813911", "pass": "Optimum2026*"},
        "carlos.vivas@optimumhome.org": {"name": "Carlos Vivas", "role": "closer", "phone": "8327146598", "pass": "Optimum2026*"},
        "adrion.jones@optimumhome.org": {"name": "Adrion Jones", "role": "closer", "phone": "2107406000", "pass": "Optimum2026*"},
        "pedro.arriaga@optimumhome.org": {"name": "Pedro Arriaga", "role": "closer", "phone": "5125668320", "pass": "Optimum2026*"},
        "derek.dalton@optimumhome.org": {"name": "Derek Dalton", "role": "closer", "phone": "8304260878", "pass": "Optimum2026*"},
        "martez.geddis@optimumhome.org": {"name": "Martez Geddis", "role": "closer", "phone": "2103473160", "pass": "Optimum2026*"}
    }

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_email' not in st.session_state:
    st.session_state['current_email'] = ""
if 'master_df' not in st.session_state:
    st.session_state['master_df'] = None

# Robust Processor for Excel (.xlsx) and CSV files
def procesar_archivo_datos(uploaded_file):
    filename = uploaded_file.name if hasattr(uploaded_file, 'name') else str(uploaded_file)
    
    if filename.endswith('.xlsx'):
        df_raw = pd.read_excel(uploaded_file)
    else:
        df_raw = pd.read_csv(uploaded_file, low_memory=False)
        
    processed_df = pd.DataFrame()
    
    if 'Contact Address' in df_raw.columns or 'Contact First Name' in df_raw.columns:
        processed_df['Visit Date'] = df_raw.get('Date Contact was Created (YYY-MM-DD)', '2026-10-01').fillna('2026-10-01')
        processed_df['Visit Time'] = '09:00'
        processed_df['Assigned Closer'] = 'Field Team'
        
        fname = df_raw['Contact First Name'].fillna('') if 'Contact First Name' in df_raw.columns else ''
        lname = df_raw['Contact Last Name'].fillna('') if 'Contact Last Name' in df_raw.columns else ''
        processed_df['Client Name'] = (fname + ' ' + lname).str.strip().replace('', 'Lead Client')
        
        processed_df['Full Address'] = df_raw.get('Contact Address', '').astype(str) + ', ' + df_raw.get('City', '').astype(str) + ', ' + df_raw.get('State', '').astype(str) + ' ' + df_raw.get('Zip', '').astype(str)
        processed_df['Phone Number'] = df_raw.get('Contact Phone', 'N/A')
        processed_df['Contact Status'] = df_raw.get('Contact Status', 'Pending')
        processed_df['Notes'] = df_raw.get('Notes', 'N/A')
        
        processed_df['lat'] = pd.to_numeric(df_raw.get('Contact Latitude'), errors='coerce').fillna(29.998)
        processed_df['lon'] = pd.to_numeric(df_raw.get('Contact Longitude'), errors='coerce').fillna(-95.263)
        return processed_df
        
    elif 'Appointment Date/Time (Local Time)' in df_raw.columns:
        dt_local = pd.to_datetime(df_raw['Appointment Date/Time (Local Time)'], errors='coerce')
        processed_df['Visit Date'] = dt_local.dt.strftime('%Y-%m-%d').fillna('2026-10-01')
        processed_df['Visit Time'] = dt_local.dt.strftime('%H:%M').fillna('09:00')
        
        closer_first = df_raw['Closer First Name'].fillna('') if 'Closer First Name' in df_raw.columns else ''
        closer_last = df_raw['Closer Last Name'].fillna('') if 'Closer Last Name' in df_raw.columns else ''
        processed_df['Assigned Closer'] = (closer_first + ' ' + closer_last).str.strip().replace('', 'Juan Lopez')
        
        fname = df_raw['First Name'].fillna('') if 'First Name' in df_raw.columns else ''
        lname = df_raw['Last Name'].fillna('') if 'Last Name' in df_raw.columns else ''
        processed_df['Client Name'] = (fname + ' ' + lname).str.strip().replace('', 'Repcard Client')
        
        direcciones = []
        for _, row in df_raw.iterrows():
            full_name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip().lower()
            appt = str(row.get('Appointment Address', '')).strip()
            if appt and appt.lower() != 'nan' and appt.lower() != full_name:
                direcciones.append(appt)
                continue
            contact = str(row.get('Contact Address', '')).strip()
            if contact and contact.lower() != 'nan' and contact.lower() != full_name:
                direcciones.append(contact)
                continue
            notes = str(row.get('Appointment Notes', ''))
            match = re.search(r'Address:\s*([^\n]+)', notes, re.IGNORECASE)
            if match:
                direcciones.append(match.group(1).strip())
                continue
            direcciones.append('Houston, TX')
            
        processed_df['Full Address'] = direcciones
        processed_df['Phone Number'] = df_raw.get('Phone', 'N/A')
        processed_df['Contact Status'] = 'Appointment Scheduled'
        processed_df['Notes'] = df_raw.get('Appointment Notes', 'N/A')
        
        processed_df['lat'] = pd.to_numeric(df_raw.get('Latitude'), errors='coerce').fillna(29.7604)
        processed_df['lon'] = pd.to_numeric(df_raw.get('Longitude'), errors='coerce').fillna(-95.3698)
        return processed_df
        
    return df_raw

# Preload default Excel file if available
if st.session_state['master_df'] is None:
    default_excel = "HUMBLE LEADS FOR MR. VIVAS.xlsx"
    if os.path.exists(default_excel):
        try:
            st.session_state['master_df'] = procesar_archivo_datos(default_excel)
        except Exception:
            pass

def crear_icono_svg(numero):
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
        <circle cx="24" cy="24" r="20" fill="#b59e67" stroke="#1a2332" stroke-width="4"/>
        <text x="24" y="31" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#1a2332" text-anchor="middle">{numero}</text>
    </svg>"""
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return {
        "url": f"data:image/svg+xml;base64,{encoded}",
        "width": 48,
        "height": 48,
        "anchorY": 24,
        "anchorX": 24
    }

def calcular_distancia_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

# ==========================================
# SECURE LOGIN SCREEN (ENGLISH)
# ==========================================
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 20px;">
                <svg width="50" height="50" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="50" cy="50" r="48" fill="#1a2332" stroke="#b59e67" stroke-width="4"/>
                    <path d="M50 25L30 45V75H70V45L50 25Z" fill="#b59e67"/>
                    <circle cx="50" cy="55" r="12" fill="#1a2332"/>
                </svg>
                <div>
                    <div style="font-family: sans-serif; font-weight: 700; font-size: 22px; color: #1a2332; line-height: 1;">OPTIMUM</div>
                    <div style="font-family: sans-serif; font-weight: 600; font-size: 14px; color: #b59e67; letter-spacing: 3px; margin-top: 2px;">HOME</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h3 style='text-align: center; color: #1a2332;'>Secure System Access</h3>", unsafe_allow_html=True)
        st.info("💡 **Access:** Log in with your corporate email and password (`Optimum2026*`).")
        
        with st.form("login_form"):
            email_input = st.text_input("Corporate Email").strip().lower()
            pass_input = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Log In", use_container_width=True)
            
            if submit_login:
                users_db = st.session_state['USERS_DB']
                if email_input in users_db and users_db[email_input]['pass'] == pass_input:
                    st.session_state['logged_in'] = True
                    st.session_state['current_email'] = email_input
                    st.rerun()
                else:
                    st.error("❌ Incorrect email or password.")
    st.stop()

# ==========================================
# MAIN APPLICATION (100% ENGLISH)
# ==========================================
user_info = st.session_state['USERS_DB'][st.session_state['current_email']]
is_admin = (user_info['role'] == 'admin')

with st.sidebar:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px; padding: 5px 0 15px 0;">
            <svg width="40" height="40" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="48" fill="#1a2332" stroke="#b59e67" stroke-width="4"/>
                <path d="M50 25L30 45V75H70V45L50 25Z" fill="#b59e67"/>
                <circle cx="50" cy="55" r="12" fill="#1a2332"/>
            </svg>
            <div>
                <div style="font-family: sans-serif; font-weight: 700; font-size: 16px; color: #1a2332; line-height: 1;">OPTIMUM</div>
                <div style="font-family: sans-serif; font-weight: 600; font-size: 11px; color: #b59e67; letter-spacing: 2px; margin-top: 2px;">HOME</div>
            </div>
        </div>
        <hr style="margin: 0 0 15px 0; border: none; border-top: 1px solid #e5e7eb;">
    """, unsafe_allow_html=True)
    
    st.markdown(f"**User:** {user_info['name']}")
    st.markdown(f"**Role:** {'Administrator' if is_admin else 'Field Closer / Canvasser'}")
    st.markdown(f"**Email:** {st.session_state['current_email']}")
    st.markdown("---")
    
    uploaded_file = None
    if is_admin:
        st.subheader("⚙️ Administration Panel")
        uploaded_file = st.file_uploader("Upload Zone Leads List (Excel / CSV)", type=["xlsx", "csv"], key="zone_uploader")
        st.markdown("---")
    else:
        uploaded_file = None

    with st.expander("🔑 Change Password"):
        with st.form("change_pass_form"):
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")
            change_btn = st.form_submit_button("Update Password")
            if change_btn:
                if new_pass and new_pass == confirm_pass:
                    st.session_state['USERS_DB'][st.session_state['current_email']]['pass'] = new_pass
                    st.success("Password successfully updated!")
                else:
                    st.error("Passwords do not match.")
                    
    st.markdown("---")
    if st.button("Log Out", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['current_email'] = ""
        st.rerun()

if is_admin and uploaded_file is not None:
    filename = uploaded_file.name
    with open(filename, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.session_state['master_df'] = procesar_archivo_datos(filename)
    st.success("Zone leads list successfully updated and globally synced!")
    st.rerun()

# Main Header
st.markdown("""
    <div style='padding: 20px; background: linear-gradient(90deg, #1a2332 0%, #2b3a4a 100%); border-radius: 10px; color: white; margin-bottom: 20px;'>
        <h2 style='margin:0; color: white;'>📍 Optimum Home - Door-to-Door Route Planner</h2>
        <p style='margin:5px 0 0 0; color: #b59e67;'>Live GPS Proximity Routing, Contact Status Filtering & Satellite Geolocation</p>
    </div>
""", unsafe_allow_html=True)

df = st.session_state['master_df']

if df is None or len(df) == 0:
    st.warning("⚠️ **System Awaiting Data:** No zone leads currently loaded.")
    if is_admin:
        st.info("💡 As Administrator, upload the zone Excel list in the sidebar.")
    else:
        st.markdown("### The Administrator has not loaded today's zone list yet.")
else:
    if 'Assigned Closer' not in df.columns:
        df['Assigned Closer'] = 'Field Team'
    if 'Contact Status' not in df.columns:
        df['Contact Status'] = 'Pending'

    if is_admin:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Admin Filters")
        statuses = ["All"] + sorted(df['Contact Status'].dropna().unique().tolist())
        filter_status = st.sidebar.selectbox("Filter Contact Status:", statuses)
        
        df_filtered = df.copy()
        if filter_status != "All":
            df_filtered = df_filtered[df_filtered['Contact Status'] == filter_status]
    else:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Field GPS & Filters")
        
        statuses = ["All"] + sorted(df['Contact Status'].dropna().unique().tolist())
        filter_status = st.sidebar.selectbox("Filter Contact Status:", statuses)
        
        use_gps = st.sidebar.checkbox("🧭 Sort by Nearest Proximity (GPS)", value=True, help="Automatically sorts stops starting from your current street location.")
        
        user_lat = st.sidebar.number_input("My Current Latitude", value=29.998, format="%.5f")
        user_lon = st.sidebar.number_input("My Current Longitude", value=-95.263, format="%.5f")
        
        df_filtered = df.copy()
        if filter_status != "All":
            df_filtered = df_filtered[df_filtered['Contact Status'] == filter_status]
            
        if use_gps and len(df_filtered) > 0:
            df_filtered['Distance_km'] = df_filtered.apply(lambda r: calcular_distancia_km(user_lat, user_lon, r['lat'], r['lon']), axis=1)
            df_filtered = df_filtered.sort_values(by='Distance_km')

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total Zone Leads", len(df_filtered))
    with col_m2:
        st.metric("Active Field User", user_info['name'])
    with col_m3:
        st.metric("Routing Mode", "Door-to-Door Proximity")

    st.markdown("---")

    if len(df_filtered) == 0:
        st.info("No records found for the selected filters.")
    else:
        # --- INTERACTIVE MAP ---
        valid_coords = df_filtered.dropna(subset=['lat', 'lon'])
        if len(valid_coords) > 0:
            st.subheader("🗺️ Zone Satellite Map & Proximity Pins")
            st.markdown("Pins are ordered dynamically by distance from your current position or list sequence:")
            
            df_map = valid_coords.reset_index(drop=True).copy()
            df_map['Sequence_Num'] = range(1, len(df_map) + 1)
            df_map['icon_data'] = df_map['Sequence_Num'].apply(crear_icono_svg)

            layer_icon = pdk.Layer(
                "IconLayer",
                data=df_map,
                get_position="[lon, lat]",
                get_icon="icon_data",
                get_size=36,
                size_scale=1,
                pickable=True,
            )

            lat_centro = df_map['lat'].mean()
            lon_centro = df_map['lon'].mean()

            view_state = pdk.ViewState(
                latitude=lat_centro,
                longitude=lon_centro,
                zoom=13,
                pitch=0
            )

            deck = pdk.Deck(
                layers=[layer_icon],
                initial_view_state=view_state,
                map_style=pdk.map_styles.LIGHT,
                tooltip={
                    "html": "<b>Stop #{Sequence_Num}</b><br/>Client: {Client Name}<br/>Status: {Contact Status}<br/>Address: {Full Address}",
                    "style": {
                        "backgroundColor": "#1a2332",
                        "color": "white",
                        "font-family": "sans-serif",
                        "padding": "8px"
                    }
                }
            )
            st.pydeck_chart(deck)
            st.markdown("---")

        st.subheader("📋 Zone Leads Chronological Sequence")
        cols_to_show = [c for c in ['Contact Status', 'Client Name', 'Full Address', 'Phone Number', 'Notes'] if c in df_filtered.columns]
        df_display = df_filtered[cols_to_show].copy()
        df_display.insert(0, 'Sequence', range(1, len(df_display) + 1))
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.subheader("🔍 Lead Detail & Field Navigation")
        lead_options = [f"Stop #{i+1} [{row.get('Contact Status','Pending')}] - {row.get('Client Name', 'Client')} ({row.get('Full Address','')})" for i, row in df_filtered.reset_index(drop=True).iterrows()]
        selected_lead = st.selectbox("Select a property to visit:", lead_options)

        if selected_lead:
            idx = lead_options.index(selected_lead)
            lead_sel = df_filtered.reset_index(drop=True).iloc[idx]
            
            col_det1, col_det2 = st.columns(2)
            with col_det1:
                st.markdown(f"**Route Stop:** #{idx + 1}")
                st.markdown(f"**Contact Status:** 📌 {lead_sel.get('Contact Status', 'N/A')}")
                st.markdown(f"**Client Name:** {lead_sel.get('Client Name', 'N/A')}")
                st.markdown(f"**Property Address:** {lead_sel.get('Full Address', 'N/A')}")
            with col_det2:
                st.markdown(f"**Phone Number:** {lead_sel.get('Phone Number', 'N/A')}")
                st.markdown(f"**Lead Notes:** {lead_sel.get('Notes', 'N/A')}")
                st.markdown(f"**Visit Status:** Active / Pending")

            st.markdown("#### Open Navigation App:")
            
            dir_url = str(lead_sel.get('Full Address', '')).replace(' ', '+')
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                st.markdown(
                    f'<a href="https://www.google.com/maps/search/?api=1&query={dir_url}" target="_blank">'
                    '<button style="width:100%; padding:12px; background-color:#1a2332; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer; font-size:14px;">🗺️ Google Maps</button>'
                    '</a>', 
                    unsafe_allow_html=True
                )
            with col_btn2:
                st.markdown(
                    f'<a href="https://waze.com/ul?q={dir_url}" target="_blank">'
                    '<button style="width:100%; padding:12px; background-color:#1a2332; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer; font-size:14px;">🚗 Waze</button>'
                    '</a>', 
                    unsafe_allow_html=True
                )
            with col_btn3:
                st.markdown(
                    f'<a href="https://maps.apple.com/?q={dir_url}" target="_blank">'
                    '<button style="width:100%; padding:12px; background-color:#b59e67; color:#1a2332; border:none; border-radius:10px; font-weight:bold; cursor:pointer; font-size:14px;">🍏 Apple Maps</button>'
                    '</a>', 
                    unsafe_allow_html=True
                )
