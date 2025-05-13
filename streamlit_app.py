import pandas as pd
from datetime import datetime
from streamlit_option_menu import option_menu
import urllib.parse
from supabase import create_client, Client
import ssl
import certifi
import os
import streamlit as st

# -----------------------------
# Page Setup
# -----------------------------
st.set_page_config(page_title="Chronify", layout="wide")
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# -----------------------------
# Supabase Auth Setup
# -----------------------------
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
SUPABASE_PASSWORD = urllib.parse.quote_plus(st.secrets["supabase"].get("password", "Nsbrava1430!"))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SUPABASE_AVAILABLE = True

# -----------------------------
# Dev Shortcut for Dummy Login
# -----------------------------
if os.getenv("DEV_MODE", "false") == "true":
    st.session_state["user"] = type("MockUser", (), {"email": "test@test.com"})()
    st.success("🧪 Dev mode enabled. Logged in as test@test.com")

# -----------------------------
# Auth UI
# -----------------------------
if "user" not in st.session_state:
    st.title("\U0001F512 Chronify Access")

    auth_mode = st.radio("Select Mode", ["Sign In", "Sign Up"], horizontal=True)
    email = st.text_input("Email", value="test@test.com").strip()
    password = st.text_input("Password", type="password", value="123")
    first_name = last_name = password_confirm = ""

    if auth_mode == "Sign Up":
        first_name = st.text_input("First Name").strip()
        last_name = st.text_input("Last Name").strip()
        password_confirm = st.text_input("Confirm Password", type="password")

    if auth_mode == "Sign In":
        if st.button("Sign In"):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response.user:
                    st.session_state["user"] = response.user
                    st.success(f"\u2705 Logged in as: {response.user.email}")

                    try:
                        profile = supabase.table("user_profiles").select("id").eq("email", email).execute()
                        if not profile.data:
                            supabase.table("user_profiles").insert({
                                "id": response.user.id,
                                "email": response.user.email,
                                "first_name": "Dev",
                                "last_name": "User"
                            }).execute()
                            st.info("✅ Profile created on login.")
                    except Exception as e:
                        st.warning(f"⚠️ Could not insert profile: {e}")

                    st.rerun()
                else:
                    st.error("\u274C Login failed.")
            except Exception as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    if email == "test@test.com" and password == "123":
                        st.session_state["user"] = type("MockUser", (), {"email": email})()
                        st.warning("\u26A0\uFE0F Supabase SSL error — logged in using offline fallback.")
                        st.rerun()
                    else:
                        st.error("\u274C SSL error with Supabase and no valid offline credentials.")
                else:
                    st.error(f"\u274C Login error: {e}")

    elif auth_mode == "Sign Up":
        if st.button("Sign Up"):
            missing_fields = []
            if not email: missing_fields.append("Email")
            if not password: missing_fields.append("Password")
            if not password_confirm: missing_fields.append("Confirm Password")
            if not first_name: missing_fields.append("First Name")
            if not last_name: missing_fields.append("Last Name")

            if missing_fields:
                st.error(f"\u274C Please fill in: {', '.join(missing_fields)}")
            elif password != password_confirm:
                st.error("\u274C Passwords do not match.")
            else:
                try:
                    response = supabase.auth.sign_up({"email": email, "password": password})
                    if response.user and response.user.id:
                        st.success("\u2705 Account created! Please check your email to confirm.")
                        st.info("ℹ️ You can log in after confirming your email. Your profile will be created on first login.")
                    else:
                        st.error("Sign up failed.")
                except ssl.SSLError:
                    st.error("\u274C Cannot sign up — SSL certificate verification failed.")
                except Exception as e:
                    st.error(f"\u274C Sign-up error: {e}")

# -----------------------------
# Main App Page
# -----------------------------
if "user" in st.session_state:
    user_email = st.session_state["user"].email
    st.sidebar.success(f"🔐 Logged in as: {user_email}")

    with st.sidebar:
        selected = option_menu(
            menu_title="CHRONIFY",
            options=["Home", "Forms", "Inventory View", "Inventory Management", "Stock History"],
            icons=["house", "file-earmark-plus", "list-ul", "gear", "clock-history"],
            menu_icon="boxes",
            default_index=0,
            styles={
                "container": {"padding": "5px", "background-color": "#0e1117"},
                "icon": {"color": "white", "font-size": "18px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "5px", "--hover-color": "#2e3b4e", "color": "white"},
                "nav-link-selected": {"background-color": "#0066ff"},
            }
        )

    # -----------------------------
    # Home Dashboard
    # -----------------------------
    if selected == "Home":
        st.title("Chronify")
        st.caption("Logan Industries")

        response = supabase.table("parts").select("*").execute()
        df = pd.DataFrame(response.data or [])

        for col in ["stock_qnt", "price", "qty_per_sheet"]:
            if col not in df.columns:
                df[col] = 0

        df["stock_value"] = df["stock_qnt"] * df["price"]
        total_items = len(df)
        total_value = df["stock_value"].sum()
        low_stock = len(df[df["stock_qnt"] < 3])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Products", total_items)
        col2.metric("Stock Value", f"${total_value:,.2f}")
        col3.metric("Low Stock Items", low_stock)

        # -----------------------------
        # Inventory Table Display
        # -----------------------------
        if not df.empty:
            df["Status"] = df["stock_qnt"].apply(lambda x: "Low Stock" if x < 3 else "In Stock")
            st.dataframe(df)

    # -----------------------------
    # Inventory View
    # -----------------------------
    elif selected == "Inventory View":
        st.subheader("📦 Full Inventory Overview")

        response = supabase.table("parts").select("*").execute()
        df = pd.DataFrame(response.data or [])

        expected_columns = ["part_number", "description", "category", "user", "stock_qnt"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = "" if col != "stock_qnt" else 0

        df_display = df[expected_columns]

        if df_display.empty:
            st.warning("No parts found in the inventory.")
        else:
            st.dataframe(df_display)

    # -----------------------------
    # Inventory Management
    # -----------------------------
    elif selected == "Inventory Management":
        st.subheader("📋 Editable Inventory Table")

        response = supabase.table("parts").select("part_number, description, category, stock_qnt").execute()
        df = pd.DataFrame(response.data or [])

        if df.empty:
            st.warning("No parts available to manage.")
        else:
            df["part_number"] = df["part_number"].astype(str)
            editable_df = df.set_index("part_number")
            edited_df = st.data_editor(editable_df, num_rows="dynamic", use_container_width=True, key="inventory_editor")

            if st.button("💾 Save Changes"):
                updates = []
                changed_by = user_email

                for idx in edited_df.index:
                    for col in ["description", "category", "stock_qnt"]:
                        if idx in df["part_number"].values:
                            old_value = df[df["part_number"] == idx][col].values[0] if col in df.columns else None
                        else:
                            old_value = None
                        new_value = edited_df.loc[idx, col] if col in edited_df.columns else None
                        if new_value != old_value:
                            updates.append((idx, col, new_value))

                if updates:
                    for part_number, col, new_value in updates:
                        try:
                            res = supabase.table("parts").update({col: int(new_value.item()) if hasattr(new_value, 'item') and col == "stock_qnt" else new_value}).eq("part_number", str(part_number)).execute()
                            if res.data:
                                st.info(f"✅ Updated {part_number} → {col} = {new_value}")
                            else:
                                st.warning(f"⚠️ No update returned for {part_number} → {col}")
                        except Exception as e:
                            st.error(f"Failed to update {part_number} → {col}: {e}")
                    st.success(f"✅ Saved {len(updates)} updates.")
                    st.info("🔄 Refresh the page manually or use the button below to reload.")
                    if st.button("🔁 Click to Refresh Now"):
                        st.rerun()
                else:
                    st.info("No changes detected.")

    # -----------------------------
    # Forms - Add New Part
    # -----------------------------
    elif selected == "Forms":
        st.subheader("➕ Add New Part")
        with st.form("add_part_form"):
            part_number = st.text_input("Part Number")
            description = st.text_input("Description")
            category = st.text_input("Category")
            material = st.text_input("Material")
            thickness = st.number_input("Thickness", value=0.0)
            qty_per_sheet = st.number_input("Qty Per Sheet", value=0.0)
            stock_qnt = st.number_input("Stock Quantity", min_value=0, step=1)
            sheet_price = st.number_input("Sheet Price", value=0.0)
            multiplier = st.number_input("Multiplier", value=1.0)
            price = round(sheet_price * multiplier, 2)
            status = st.selectbox("Status", ["Active", "Inactive"])
            user = user_email

            submitted = st.form_submit_button("Add Part")

            if submitted and part_number:
                response = supabase.table("parts").select("part_number").eq("part_number", part_number).execute()
                if response.data:
                    st.error("❌ Part number already exists.")
                else:
                    insert_data = {
                        "part_number": part_number,
                        "description": description,
                        "category": category,
                        "material": material,
                        "thickness": thickness,
                        "qty_per_sheet": qty_per_sheet,
                        "stock_qnt": stock_qnt,
                        "sheet_price": sheet_price,
                        "multiplier": multiplier,
                        "price": price,
                        "status": status,
                        "user": user
                    }
                    try:
                        supabase.table("parts").insert(insert_data).execute()
                        st.success("✅ Part added successfully.")
                    except Exception as e:
                        st.error(f"❌ Failed to add part: {e}")
