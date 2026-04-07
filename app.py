from __future__ import annotations

import streamlit as st

from storage_service import authenticate, load_users, user_dict_from_user
from storage_service import ensure_dirs as storage_ensure_dirs

import ui_pages as ui

ACCENT_RED = "#FF0000"
SECONDARY_SILVER = "#C0C0C0"
BG_BLACK = "#000000"


def apply_invictus_theme() -> None:
    st.markdown(
        f"""
        <style>
          .stApp {{
            background: {BG_BLACK};
            color: #FFFFFF;
          }}
          .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
          }}
          section[data-testid="stSidebar"] {{
            background: #050505;
            border-right: 1px solid rgba(192,192,192,0.25);
          }}
          section[data-testid="stSidebar"] * {{
            color: #FFFFFF;
          }}
          section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
            border-left: 4px solid {ACCENT_RED};
            padding-left: 10px;
            margin-left: -4px;
            background: rgba(255,0,0,0.06);
          }}
          div[data-baseweb="input"] > div {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 8px;
          }}
          div[data-baseweb="textarea"] > div {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 8px;
          }}
          div[data-baseweb="select"] > div {{
            border-radius: 8px;
          }}
          .stButton>button {{
            background: {ACCENT_RED};
            color: #FFFFFF;
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 0.6rem 1rem;
            font-weight: 700;
          }}
          .stButton>button:hover {{
            background: #d80000;
            border-color: rgba(255,255,255,0.3);
          }}
          div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(192,192,192,0.25);
            border-radius: 14px;
            padding: 1rem;
          }}
          .stDataFrame {{
            border: 1px solid rgba(192,192,192,0.25);
            border-radius: 12px;
            overflow: hidden;
          }}
          h1, h2, h3 {{
            letter-spacing: 0.2px;
          }}
          .invictus-badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border: 1px solid rgba(192,192,192,0.35);
            border-radius: 999px;
            color: {SECONDARY_SILVER};
            font-size: 0.85rem;
          }}
          .invictus-sub {{
            color: rgba(192,192,192,0.9);
          }}
          .invictus-grid-hr {{
            border: 0;
            border-top: 1px solid rgba(192,192,192,0.2);
            margin: 1.25rem 0;
          }}

          /* --- SmartSurat Scanner: make st.camera_input feel "full screen" --- */
          div[data-testid="stCameraInput"] {{
            width: 100% !important;
            max-width: 1000px !important;
            margin: 0 auto !important;
          }}
          div[data-testid="stCameraInput"] > div {{
            width: 100% !important;
          }}
          div[data-testid="stCameraInput"] video {{
            width: 100% !important;
            max-height: 72vh !important;
            height: auto !important;
            border: 3px solid {ACCENT_RED};
            border-radius: 15px;
            object-fit: cover;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "authed_user" not in st.session_state:
        st.session_state.authed_user = None


def main() -> None:
    st.set_page_config(page_title="SmartSurat · Invictus", page_icon="📄", layout="wide")
    apply_invictus_theme()
    storage_ensure_dirs()
    _init_state()

    users = load_users()
    authed = st.session_state.authed_user

    if not authed:
        ui.centered_login(users, authenticate, user_dict_from_user)
        return

    user = ui.user_from_session(authed)
    page = ui.sidebar(user)

    if page == "Muat Naik":
        ui.page_muat_naik(user)
    elif page == "Daftar & Agih":
        ui.page_admin(user)
    elif page == "Pengesahan":
        ui.page_rep(user)
    elif page == "Dashboard":
        ui.page_dashboard(user)
    elif page == "Profil":
        ui.page_profile(user)
    elif page == "Manual Pengguna":
        ui.page_manual()
    elif page == "Aduan / Cadangan":
        ui.page_placeholder("Aduan / Cadangan", "Placeholder — saluran maklum balas dalaman (tiada panggilan API luaran).")
    else:
        st.markdown("## SmartSurat")
        st.warning("Halaman tidak dikenali.")


if __name__ == "__main__":
    main()
