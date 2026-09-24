import streamlit as st
import pandas as pd
import os
import pydeck as pdk
import base64

# Configuración de página
st.set_page_config(
    page_title="Optimum Home - Planificador de Rutas",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Base de datos de usuarios autorizados
if 'USERS_DB' not in st.session_state:
    st.session_state['USERS_DB'] = {
        "juan.lopez@optimumhome.org": {"name": "Juan Lopez", "role": "admin", "phone": "8329813911", "pass": "Optimum2026*"},
        "carlos.vivas@optimumhome.org": {"name": "Carlos Vivas", "role": "closer", "phone": "8327146598", "pass": "Optimum2026*"},
        "adrion.jones@optimumhome.org": {"name": "Adrion Jones", "role": "closer", "phone": "2107406000", "pass": "Optimum2026*"},
        "pedro.arriaga@optimumhome.org": {"name": "Pedro Arriaga", "role": "closer", "phone": "5125668320", "pass": "Optimum2026*"},
        "derek.dalton@optimumhome.org": {"name": "Derek Dalton", "role": "closer", "phone": "8304260878", "pass": "Optimum2026*"}
    }

# Inicializar estados de sesión
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_email' not in st.session_state:
    st.session_state['current_email'] = ""
if 'master_df' not in st.session_state:
    st.session_state['master_df'] = None

# Función robusta para procesar el CSV de Repcard y rescatar direcciones vacías
def procesar_csv_repcard(uploaded_file):
    df_raw = pd.read_csv(uploaded_file, low_memory=False)
    
    if 'Appointment Date/Time (Local Time)' in df_raw.columns and 'Latitude' in df_raw.columns:
        processed_df = pd.DataFrame()
        
        # Fecha y hora local
        dt_local = pd.to_datetime(df_raw['Appointment Date/Time (Local Time)'], errors='coerce')
        processed_df['Fecha_Visita'] = dt_local.dt.strftime('%Y-%m-%d').fillna('2026-09-24')
        processed_df['Hora_Visita'] = dt_local.dt.strftime('%H:%M').fillna('09:00')
        
        # Cerrador
        closer_first = df_raw['Closer First Name'].fillna('') if 'Closer First Name' in df_raw.columns else ''
        closer_last = df_raw['Closer Last Name'].fillna('') if 'Closer Last Name' in df_raw.columns else ''
        processed_df['Cerrador_Asignado'] = (closer_first + ' ' + closer_last).str.strip()
        processed_df['Cerrador_Asignado'] = processed_df['Cerrador_Asignado'].replace('', 'Juan Lopez')
        
        # Cliente
        fname = df_raw['First Name'].fillna('') if 'First Name' in df_raw.columns else ''
        lname = df_raw['Last Name'].fillna('') if 'Last Name' in df_raw.columns else ''
        processed_df['Nombre_Cliente'] = (fname + ' ' + lname).str.strip()
        processed_df['Nombre_Cliente'] = processed_df['Nombre_Cliente'].replace('', 'Cliente Repcard')
        
        # Rescate inteligente de dirección (si Appt Address está vacía, busca en Contact Address o Title)
        appt_addr = df_raw['Appointment Address'].fillna('') if 'Appointment Address' in df_raw.columns else pd.Series(['']*len(df_raw))
        contact_addr = df_raw['Contact Address'].fillna('') if 'Contact Address' in df_raw.columns else pd.Series(['']*len(df_raw))
        appt_title = df_raw['Appointment Title'].fillna('') if 'Appointment Title' in df_raw.columns else pd.Series(['']*len(df_raw))
        
        direcciones = []
        for a, c, t in zip(appt_addr, contact_addr, appt_title):
            if str(a).strip() and str(a).lower() != 'nan':
                direcciones.append(str(a).strip())
            elif str(c).strip() and str(c).lower() != 'nan':
                direcciones.append(str(c).strip())
            elif str(t).strip() and str(t).lower() != 'nan':
                direcciones.append(str(t).strip())
            else:
                direcciones.append('Houston, TX') # Respaldo operativo
        
        processed_df['Direccion_Completa'] = direcciones
        processed_df['Telefono_Principal'] = df_raw.get('Phone', 'N/A')
        
        # Coordenadas reales
        processed_df['lat'] = pd.to_numeric(df_raw['Latitude'], errors='coerce')
        processed_df['lon'] = pd.to_numeric(df_raw['Longitude'], errors='coerce')
        
        # Si por alguna razón la coordenada viene vacía, asignamos un respaldo temporal en Houston para que no rompa el mapa
        processed_df['lat'] = processed_df['lat'].fillna(29.7604)
        processed_df['lon'] = processed_df['lon'].fillna(-95.3698)
        
        return processed_df
    else:
        return df_raw

# Función para crear iconos SVG con el número perfectamente centrado
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

# ==========================================
# PANTALLA DE LOGIN SEGURO
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
        
        st.markdown("<h3 style='text-align: center; color: #1a2332;'>Acceso Seguro al Sistema de Rutas</h3>", unsafe_allow_html=True)
        st.info("💡 **Acceso:** Ingrese con correo corporativo y clave (`Optimum2026*`).")
        
        with st.form("login_form"):
            email_input = st.text_input("Correo Electrónico Corporativo").strip().lower()
            pass_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submit_login:
                users_db = st.session_state['USERS_DB']
                if email_input in users_db and users_db[email_input]['pass'] == pass_input:
                    st.session_state['logged_in'] = True
                    st.session_state['current_email'] = email_input
                    st.rerun()
                else:
                    st.error("❌ Correo o contraseña incorrectos.")
    st.stop()

# ==========================================
# APLICACIÓN PRINCIPAL
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
    
    st.markdown(f"**Usuario:** {user_info['name']}")
    st.markdown(f"**Rol:** {'Administrador' if is_admin else 'Cerrador de Campo'}")
    st.markdown(f"**Correo:** {st.session_state['current_email']}")
    st.markdown("---")
    
    uploaded_file = None
    if is_admin:
        st.subheader("⚙️ Panel de Administración")
        uploaded_file = st.file_uploader("Subir Reporte Nativo Repcard (CSV)", type=["csv"], key="repcard_uploader_v2")
        st.markdown("---")
    else:
        uploaded_file = None

    with st.expander("🔑 Cambiar Contraseña"):
        with st.form("change_pass_form"):
            new_pass = st.text_input("Nueva Contraseña", type="password")
            confirm_pass = st.text_input("Confirmar Contraseña", type="password")
            change_btn = st.form_submit_button("Actualizar Clave")
            if change_btn:
                if new_pass and new_pass == confirm_pass:
                    st.session_state['USERS_DB'][st.session_state['current_email']]['pass'] = new_pass
                    st.success("¡Contraseña actualizada!")
                else:
                    st.error("Las contraseñas no coinciden.")
                    
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['current_email'] = ""
        st.rerun()

if is_admin and uploaded_file is not None:
    st.session_state['master_df'] = procesar_csv_repcard(uploaded_file)
    st.success("¡Reporte de Repcard procesado y normalizado con éxito!")

# Cabecera principal
st.markdown("""
    <div style='padding: 20px; background: linear-gradient(90deg, #1a2332 0%, #2b3a4a 100%); border-radius: 10px; color: white; margin-bottom: 20px;'>
        <h2 style='margin:0; color: white;'>📍 Optimum Home - Planificador de Rutas</h2>
        <p style='margin:5px 0 0 0; color: #b59e67;'>Control operativo, geolocalización satelital y agenda cronológica Repcard</p>
    </div>
""", unsafe_allow_html=True)

df = st.session_state['master_df']

if df is None or len(df) == 0:
    st.warning("⚠️ **Sistema en Espera de Datos:** No hay rutas cargadas actualmente.")
    if is_admin:
        st.info("💡 Como Administrador, suba el archivo CSV exportado directamente desde **Repcard** en el panel lateral.")
    else:
        st.markdown("### El Administrador aún no ha cargado las rutas del día.")
else:
    if 'Cerrador_Asignado' not in df.columns:
        df['Cerrador_Asignado'] = user_info['name']
    if 'Fecha_Visita' not in df.columns:
        df['Fecha_Visita'] = '2026-09-24'
    if 'Hora_Visita' not in df.columns:
        df['Hora_Visita'] = '09:00'

    if is_admin:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Filtros de Administrador")
        fechas_disponibles = sorted(df['Fecha_Visita'].unique())
        filtro_fecha = st.sidebar.selectbox("Filtrar por Fecha:", ["Todas"] + list(fechas_disponibles))
        
        cerradores_disponibles = sorted(df['Cerrador_Asignado'].unique())
        filtro_cerrador = st.sidebar.selectbox("Filtrar por Cerrador:", ["Todos"] + list(cerradores_disponibles))
        
        df_filtrado = df.copy()
        if filtro_fecha != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Fecha_Visita'] == filtro_fecha]
        if filtro_cerrador != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Cerrador_Asignado'] == filtro_cerrador]
            
        df_filtrado = df_filtrado.sort_values(by=['Fecha_Visita', 'Hora_Visita'])
    else:
        df_closer = df[df['Cerrador_Asignado'].str.lower() == user_info['name'].lower()]
        
        if len(df_closer) > 0:
            fechas_closer = sorted(df_closer['Fecha_Visita'].unique())
            filtro_fecha_closer = st.selectbox("📅 Seleccione la Fecha de su Ruta:", fechas_closer)
            
            df_filtrado = df_closer[df_closer['Fecha_Visita'] == filtro_fecha_closer].sort_values(by='Hora_Visita')
        else:
            df_filtrado = pd.DataFrame()

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Paradas Programadas", len(df_filtrado))
    with col_m2:
        st.metric("Cerrador en Sesión", user_info['name'])
    with col_m3:
        st.metric("Secuencia", "Cronológica Repcard")

    st.markdown("---")

    if len(df_filtrado) == 0:
        st.info("No hay registros asignados para los filtros seleccionados.")
    else:
        # --- MAPA INTERACTIVO CON COORDENADAS DE REPCARD ---
        valid_coords = df_filtrado.dropna(subset=['lat', 'lon'])
        if len(valid_coords) > 0:
            st.subheader("🗺️ Mapa Satelital de Ruta Repcard")
            st.markdown("Ubicaciones exactas obtenidas de las coordenadas de Repcard, numeradas cronológicamente:")
            
            df_mapa = valid_coords.reset_index(drop=True).copy()
            df_mapa['Secuencia_Num'] = range(1, len(df_mapa) + 1)
            df_mapa['icon_data'] = df_mapa['Secuencia_Num'].apply(crear_icono_svg)

            layer_icon = pdk.Layer(
                "IconLayer",
                data=df_mapa,
                get_position="[lon, lat]",
                get_icon="icon_data",
                get_size=36,
                size_scale=1,
                pickable=True,
            )

            lat_centro = df_mapa['lat'].mean()
            lon_centro = df_mapa['lon'].mean()

            view_state = pdk.ViewState(
                latitude=lat_centro,
                longitude=lon_centro,
                zoom=11,
                pitch=0
            )

            deck = pdk.Deck(
                layers=[layer_icon],
                initial_view_state=view_state,
                map_style=pdk.map_styles.LIGHT,
                tooltip={
                    "html": "<b>Parada #{Secuencia_Num}</b><br/>Hora: {Hora_Visita}<br/>Cliente: {Nombre_Cliente}<br/>Dirección: {Direccion_Completa}",
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

        st.subheader("📋 Secuencia Cronológica de Paradas")
        cols_a_mostrar = [c for c in ['Fecha_Visita', 'Hora_Visita', 'Cerrador_Asignado', 'Nombre_Cliente', 'Direccion_Completa', 'Telefono_Principal'] if c in df_filtrado.columns]
        df_display = df_filtrado[cols_a_mostrar].copy()
        df_display.insert(0, 'Secuencia', range(1, len(df_display) + 1))
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.subheader("🔍 Detalle de Visita y Navegación Individual")
        opciones_visitas = [f"Parada #{i+1} [{row.get('Hora_Visita','')}] - {row.get('Nombre_Cliente', 'Cliente')}" for i, row in df_filtrado.reset_index(drop=True).iterrows()]
        seleccion_visitas = st.selectbox("Seleccione un cliente para gestionar la visita:", opciones_visitas)

        if seleccion_visitas:
            idx = opciones_visitas.index(seleccion_visitas)
            cliente_sel = df_filtrado.reset_index(drop=True).iloc[idx]
            
            col_det1, col_det2 = st.columns(2)
            with col_det1:
                st.markdown(f"**Secuencia de Ruta:** #{idx + 1}")
                st.markdown(f"**Hora Acordada:** ⏰ {cliente_sel.get('Hora_Visita', 'N/A')}")
                st.markdown(f"**Cliente:** {cliente_sel.get('Nombre_Cliente', 'N/A')}")
                st.markdown(f"**Dirección:** {cliente_sel.get('Direccion_Completa', 'N/A')}")
            with col_det2:
                st.markdown(f"**Cerrador Asignado:** {cliente_sel.get('Cerrador_Asignado', 'N/A')}")
                st.markdown(f"**Teléfono:** {cliente_sel.get('Telefono_Principal', 'N/A')}")
                st.markdown(f"**Estatus actual:** Pendiente")

            st.markdown("#### Abrir aplicación de ruta:")
            
            dir_url = str(cliente_sel.get('Direccion_Completa', '')).replace(' ', '+')
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                st.markdown(
                    f'<a href="https://www.google.com/maps/search/?api=1&query={dir_url}" target="_blank">'
                    '<button style="width:100%; padding:12px; background-color:#1a2332; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer; font-size:14px;">🗺️ Abrir Google Maps</button>'
                    '</a>', 
                    unsafe_allow_html=True
                )
            with col_btn2:
                st.markdown(
                    f'<a href="https://waze.com/ul?q={dir_url}" target="_blank">'
                    '<button style="width:100%; padding:12px; background-color:#1a2332; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer; font-size:14px;">🚗 Abrir Waze</button>'
                    '</a>', 
                    unsafe_allow_html=True
                )
