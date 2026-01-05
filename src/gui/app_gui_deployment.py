import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import os
from datetime import datetime

# --- CONFIGURATION ---
API_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

st.set_page_config(page_title="Distributed Grid AI", page_icon="⚡", layout="wide")

# --- CUSTOM DARK THEME CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    section[data-testid="stSidebar"] { background-color: #262730; }
    div[data-testid="stMetric"] { background-color: #1f2937; border: 1px solid #374151; padding: 15px; border-radius: 8px; }
    div[data-testid="stMetricLabel"] { color: #9ca3af !important; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; }
    .status-badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.9em; display: inline-block; margin-top: 5px; }
    .status-up { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .status-down { background-color: #7f1d1d; color: #f87171; border: 1px solid #b91c1c; }
    .carbon-live-box { padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center; border: 1px solid #4b5563; }
    </style>
""", unsafe_allow_html=True)

# --- LIVE HEALTH & CARBON CHECK ---
@st.fragment(run_every=3)
def display_live_health_check():
    st.markdown("### 📡 Live System Monitor")
    
    # 1. READ SESSION STATE TO GET USER SELECTION
    # This allows the live ticker to react to the sidebar instantly
    user_selection = st.session_state.get("sim_selector", "Automatic")
    
    live_params = {}
    if "LOW" in user_selection:
        live_params["carbon_mode"] = "LOW"
    elif "HIGH" in user_selection:
        live_params["carbon_mode"] = "HIGH"
    # If Automatic, we send nothing (None)
    
    container = st.container(border=True)
    with container:
        # --- GET LIVE CARBON DATA ---
        try:
            # Pass the params here!
            carbon_resp = requests.get(f"{API_URL}/carbon-live", params=live_params, timeout=1)
            
            if carbon_resp.status_code == 200:
                c_data = carbon_resp.json()
                intensity = c_data.get("carbon_intensity", 0)
                status = c_data.get("status", "UNKNOWN")
                
                # Determine Color
                bg_color = "#064e3b" if status == "LOW" else "#7f1d1d"
                text_color = "#34d399" if status == "LOW" else "#f87171"
                
                st.markdown(f"""
                    <div class="carbon-live-box" style="background-color: {bg_color};">
                        <div style="font-size: 12px; color: #e5e7eb; margin-bottom: 4px;">LIVE GRID INTENSITY</div>
                        <div style="font-size: 24px; font-weight: bold; color: {text_color};">
                            {intensity} <span style="font-size: 14px;">gCO₂/kWh</span>
                        </div>
                        <div style="font-size: 12px; color: {text_color}; opacity: 0.8;">
                            STATUS: {status}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Sensor Offline")
        except:
            st.markdown('<div class="carbon-live-box" style="background:#374151; color:#9ca3af;">Sensor Unreachable</div>', unsafe_allow_html=True)

        # --- GET CLUSTER HEALTH ---
        try:
            status_url = f"{API_URL}/health"
            response = requests.get(status_url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                orch_up = True
                xgb_up = "Online" in data.get("xgb_service", "Offline")
                hw_up = "Online" in data.get("hw_service", "Offline")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                        <div style="text-align:center; background:#1f2937; padding:8px; border-radius:6px; border:1px solid #374151;">
                            <div style="color:#9ca3af; font-size:10px;">ORCH</div>
                            <div class="status-badge {'status-up' if orch_up else 'status-down'}" style="font-size:10px;">{'ON' if orch_up else 'OFF'}</div>
                        </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                        <div style="text-align:center; background:#1f2937; padding:8px; border-radius:6px; border:1px solid #374151;">
                            <div style="color:#9ca3af; font-size:10px;">XGB</div>
                            <div class="status-badge {'status-up' if xgb_up else 'status-down'}" style="font-size:10px;">{'UP' if xgb_up else 'DOWN'}</div>
                        </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                        <div style="text-align:center; background:#1f2937; padding:8px; border-radius:6px; border:1px solid #374151;">
                            <div style="color:#9ca3af; font-size:10px;">HW</div>
                            <div class="status-badge {'status-up' if hw_up else 'status-down'}" style="font-size:10px;">{'UP' if hw_up else 'DOWN'}</div>
                        </div>""", unsafe_allow_html=True)
        except Exception:
            st.error("🚨 SYSTEM OFFLINE")

# --- SIDEBAR ---
with st.sidebar:
    display_live_health_check()
    st.divider()
    
    st.header("🎮 Grid Control")
    country_map = {
            "Austria": "AT",
            "Belgium": "BE",
            "Bulgaria": "BG",
            "Croatia": "HR",
            "Czech Republic": "CZ",
            "Denmark": "DK",
            "Estonia": "EE",
            "Finland": "FI",
            "France": "FR",
            "Germany": "DE",
            "Greece": "GR",
            "Hungary": "HU",
            "Ireland": "IE",
            "Italy": "IT",
            "Latvia": "LV",
            "Lithuania": "LT",
            "Luxembourg": "LU",
            "Netherlands": "NL",
            "Norway": "NO",
            "Poland": "PL",
            "Portugal": "PT",
            "Romania": "RO",
            "Slovakia": "SK",
            "Slovenia": "SI",
            "Spain": "ES",
            "Sweden": "SE",
            "Switzerland": "CH",
            "United Kingdom": "UK",
        }
    country = st.selectbox("Country", list(country_map.keys()))
    
    st.markdown("### 🌍 Simulation Mode")
    
    # ADDED 'key="sim_selector"' here!
    sim_option = st.radio(
        "Grid Carbon Intensity",
        ["Automatic (Real-time)", "LOW (Eco-Friendly)", "HIGH (Dirty Grid)"],
        index=0,
        key="sim_selector"
    )
    
    # Logic for the Run Button (API Parameters)
    if "Automatic" in sim_option:
        api_param = None
    elif "LOW" in sim_option:
        api_param = "LOW"
    else:
        api_param = "HIGH"
    
    st.divider()
    run_btn = st.button("🚀 Run Forecast", type="primary", use_container_width=True)

# --- MAIN APP LOGIC ---
st.title("⚡ Distributed AI Energy Grid")

if run_btn:
    country_code = country_map[country]
    endpoint = f"{API_URL}/forecast/optimized/{country_code}"
    
    params = {}
    if api_param:
        params["carbon_mode"] = api_param
    
    try:
        with st.spinner("Routing request through microservices..."):
            resp = requests.get(endpoint, params=params, timeout=10)
            
        if resp.status_code == 200:
            payload = resp.json()
            metadata = payload.get("metadata", {})
            forecast_list = payload.get("forecast", [])
            model_used = metadata.get("selected_model", "Unknown")
            exec_carbon = metadata.get("execution_carbon_footprint_kg", 0.0)
            carbon_ctx = metadata.get("carbon_context", {})
            sim_carbon_val = carbon_ctx.get("carbon_intensity", "N/A")
            sim_status = carbon_ctx.get("status", "N/A")
            
            df = pd.DataFrame(forecast_list)
            
            if not df.empty:
                df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Selected Model", model_used)
                m2.metric("Grid Intensity", f"{sim_carbon_val} gCO₂/kWh", delta=sim_status, delta_color="inverse")
                m3.metric("Compute Footprint", f"{exec_carbon:.7f} kg")
                m4.metric("Horizon", f"{len(df)} Hours")

                st.subheader("📊 Generation Mix Forecast (MW)")
                fig = go.Figure()

                if 'Total_Generation' in df.columns:
                    fig.add_trace(go.Scatter(x=df['datetime_utc'], y=df['Total_Generation'], mode='lines', name='Total Generation', line=dict(color='white', width=3, dash='dash')))
                if 'Wind_Offshore' in df.columns:
                    fig.add_trace(go.Scatter(x=df['datetime_utc'], y=df['Wind_Offshore'], mode='lines', name='Wind Offshore', fill='tozeroy', line=dict(width=1, color='#3b82f6'), fillcolor='rgba(59, 130, 246, 0.4)'))
                if 'Wind_Onshore' in df.columns:
                    fig.add_trace(go.Scatter(x=df['datetime_utc'], y=df['Wind_Onshore'], mode='lines', name='Wind Onshore', fill='tozeroy', line=dict(width=1, color='#10b981'), fillcolor='rgba(16, 185, 129, 0.4)'))
                if 'Solar' in df.columns:
                    fig.add_trace(go.Scatter(x=df['datetime_utc'], y=df['Solar'], mode='lines', name='Solar', fill='tozeroy', line=dict(width=1, color='#f59e0b'), fillcolor='rgba(245, 158, 11, 0.4)'))
                if 'predicted_mw' in df.columns and 'Total_Generation' not in df.columns:
                     fig.add_trace(go.Scatter(x=df['datetime_utc'], y=df['predicted_mw'], mode='lines', name='Forecast', fill='tozeroy', line=dict(color='#3b82f6'), fillcolor='rgba(59, 130, 246, 0.2)'))

                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), height=500, margin=dict(l=20, r=20, t=20, b=20), hovermode="x unified", xaxis=dict(showgrid=False), yaxis=dict(title="Power Generation (MW)", showgrid=True, gridcolor='#374151'))
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("🔍 View Raw API Response"):
                    st.json(payload)
            else:
                st.warning("Orchestrator returned no data rows.")
        else:
            st.error(f"API Error: {resp.text}")
            
    except Exception as e:
        st.error(f"Connection Failed: {e}")