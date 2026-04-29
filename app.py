import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from fpdf import FPDF
import tempfile
import os
import requests

# -- Set page config must be the FIRST Streamlit command --
st.set_page_config(
    page_title="Cashback Cards App",
    page_icon="https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png",
    layout="centered"
)

# -- Add custom Apple Touch Icon and browser tab icon --
st.markdown("""
    <link rel="apple-touch-icon" sizes="180x180" href="https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#2498F7">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

def generate_pdf_receipt(df, logo_url=None):
    import shutil

    class PDF(FPDF):
        def header(self):
            if logo_url:
                try:
                    response = requests.get(logo_url)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                        tmp_logo.write(response.content)
                        tmp_logo.flush()
                        self.image(tmp_logo.name, 10, 8, 20)
                except Exception:
                    pass
            self.set_font('DejaVu', 'B', 16)
            self.cell(0, 10, 'Purchase Receipt', ln=True, align='C')
            self.ln(6)
        def footer(self):
            self.set_y(-12)
            self.set_font('DejaVu', 'I', 8)
            self.set_text_color(130,130,130)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')

    # --- Download font reliably to static folder ---
    os.makedirs("static", exist_ok=True)
    FONT_PATH = "static/DejaVuSans.ttf"
    FONT_URL = "https://github.com/dejavu-fonts/dejavu-fonts/raw/version_2_37/ttf/DejaVuSans.ttf"

    if not os.path.exists(FONT_PATH) or os.path.getsize(FONT_PATH) < 100_000:
        r = requests.get(FONT_URL, timeout=10)
        if r.ok and r.headers.get("Content-Type","").startswith("font/"):
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
        else:
            # Fallback to a backup font location
            backup_url = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf"
            r2 = requests.get(backup_url, timeout=10)
            with open(FONT_PATH, "wb") as f:
                f.write(r2.content)
    
    pdf = PDF()
    pdf.add_font('DejaVu', '', FONT_PATH, uni=True)
    pdf.add_font('DejaVu', 'B', FONT_PATH, uni=True)
    pdf.add_font('DejaVu', 'I', FONT_PATH, uni=True)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("DejaVu", size=11)

    # Colors
    header_bg = (40, 116, 207)
    header_fg = (255,255,255)
    row_alt_bg = (240,244,251)
    row_normal_bg = (255,255,255)

    # Table header
    col_names = ["Date", "Card", "Category", "Amount", "Cashback", "Net"]
    col_widths = [32, 26, 30, 28, 26, 28]
    pdf.set_fill_color(*header_bg)
    pdf.set_text_color(*header_fg)
    pdf.set_font("DejaVu", "B", 11)
    for i, col in enumerate(col_names):
        pdf.cell(col_widths[i], 9, str(col), border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(60,60,60)

    # Table rows
    for j, (_, row) in enumerate(df.iterrows()):
        fill = row_alt_bg if j%2==0 else row_normal_bg
        pdf.set_fill_color(*fill)
        
        date_val = str(row.get('date_only', row.get('date', '')))
        card_val = str(row.get('card', ''))
        cat_val = str(row.get('category', ''))
        amt_val = f"${float(row.get('amount', 0)):.2f}"
        cb_val = f"${float(row.get('cashback', 0)):.2f}"
        net_val = f"${float(row.get('net', 0)):.2f}"

        pdf.cell(col_widths[0], 8, date_val, border=1, align='C', fill=True)
        pdf.cell(col_widths[1], 8, card_val, border=1, align='C', fill=True)
        pdf.cell(col_widths[2], 8, cat_val, border=1, align='C', fill=True)
        pdf.cell(col_widths[3], 8, amt_val, border=1, align='C', fill=True)
        pdf.cell(col_widths[4], 8, cb_val, border=1, align='C', fill=True)
        pdf.cell(col_widths[5], 8, net_val, border=1, align='C', fill=True)
        pdf.ln()

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(88, 10, "Totals", border=1, align='R')
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(col_widths[3], 10, f"${df['amount'].astype(float).sum():.2f}", border=1, align='C')
    pdf.cell(col_widths[4], 10, f"${df.get('cashback', pd.Series([0])).astype(float).sum():.2f}", border=1, align='C')
    pdf.cell(col_widths[5], 10, f"${df.get('net', pd.Series([0])).astype(float).sum():.2f}", border=1, align='C')
    pdf.ln(12)

    pdf.set_font("DejaVu", 'I', 9)
    pdf.set_text_color(100,100,100)
    pdf.cell(0, 8, "Thank you for your payment!  —  Cashback Cards App", align='C')

    temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(temp_path)
    return temp_path

@st.cache_data(show_spinner=False)
def get_cached_pdf_bytes(json_string):
    """Helper function to load PDFs from the archive efficiently."""
    temp_df = pd.DataFrame(json.loads(json_string))
    logo_url = "https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png"
    path = generate_pdf_receipt(temp_df, logo_url=logo_url)
    with open(path, "rb") as f:
        return f.read()

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource(ttl=300)
def get_gsheets():
    credentials = Credentials.from_service_account_info(
        json.loads(st.secrets["GCP_SERVICE_ACCOUNT"]), scopes=SCOPE)
    gc = gspread.authorize(credentials)
    sh = gc.open("cashback_app")
    cards_ws = sh.worksheet("cards")
    purchases_ws = sh.worksheet("purchases")
    receipts_ws = sh.worksheet("receipts") # Added new worksheet for archive
    return cards_ws, purchases_ws, receipts_ws

cards_ws, purchases_ws, receipts_ws = get_gsheets()

def load_cards():
    records = cards_ws.get_all_records()
    cards = {}
    for row in records:
        name = row["card_name"]
        category = row["category"]
        percent = float(row["cashback_percent"])
        if name not in cards:
            cards[name] = {}
        cards[name][category] = percent
    return cards

def save_cards(cards):
    values = [["card_name", "category", "cashback_percent"]]
    for card, categories in cards.items():
        for category, percent in categories.items():
            values.append([card, category, percent])
            
    cards_ws.clear()
    if len(values) > 1:
        # Optimized single API call
        cards_ws.update(f"A1:C{len(values)}", values)

def load_purchases():
    records = purchases_ws.get_all_records()
    for p in records:
        if "paid" not in p:
            p["paid"] = False
        if isinstance(p["paid"], str):
            if p["paid"].lower() == "true":
                p["paid"] = True
            else:
                p["paid"] = False
        if "amount" not in p or p["amount"] == "" or p["amount"] is None:
            p["amount"] = 0.0
        try:
            p["amount"] = float(p["amount"])
        except:
            p["amount"] = 0.0
    return records

def save_purchases(purchases):
    values = [["date", "card", "category", "amount", "paid"]]
    for p in purchases:
        values.append([p["date"], p["card"], p["category"], p["amount"], p["paid"]])
    purchases_ws.update(f"A1:E{len(values)}", values)
    sheet_len = len(purchases_ws.get_all_values())
    if sheet_len > len(values):
        purchases_ws.batch_clear([f"A{len(values)+1}:E{sheet_len}"])

# --- Functions for Receipts Archive ---
def load_receipts():
    return receipts_ws.get_all_records()

def save_receipt(date_paid, total_amount, purchase_data):
    items_json = purchase_data.to_json(orient="records")
    
    # Check if headers exist in row 1
    try:
        first_row = receipts_ws.row_values(1)
    except:
        first_row = []
        
    # If the headers are missing or wrong, add them!
    if not first_row or first_row[0] != "date_paid":
        receipts_ws.clear()
        receipts_ws.append_row(["date_paid", "total_amount", "items_json"])
        
    # Save the receipt
    receipts_ws.append_row([str(date_paid), float(total_amount), items_json])

# --- Session State Management ---
if "new_card_categories" not in st.session_state:
    st.session_state.new_card_categories = {}
if "edit_purchase_index" not in st.session_state:
    st.session_state.edit_purchase_index = None
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Add Purchase"
if "purchase_amount" not in st.session_state:
    st.session_state.purchase_amount = 0.0
if "purchase_paid" not in st.session_state:
    st.session_state.purchase_paid = False
if "add_success" not in st.session_state:
    st.session_state.add_success = False
if "should_reset_amount" not in st.session_state:
    st.session_state.should_reset_amount = False
if "edit_row" not in st.session_state:
    st.session_state.edit_row = None
if "just_paid" not in st.session_state:
    st.session_state.just_paid = None

def tabs_nav():
    tabs = {
        "Add Purchase": "🟢 Add Purchase",
        "History": "📜 History",
        "Receipts": "📁 Receipts", 
        "Cards": "💳 Cards",
    }
    st.markdown("""
        <style>
        .stButton button {font-size:1.25rem;padding:0.75em 0;border-radius:2em;}
        </style>
        """, unsafe_allow_html=True)
    cols = st.columns(len(tabs))
    selected = st.session_state.get("current_tab", "Add Purchase")
    for i, (tab, label) in enumerate(tabs.items()):
        if cols[i].button(label, use_container_width=True):
            st.session_state.current_tab = tab
    st.markdown("---")
    return st.session_state.get("current_tab", "Add Purchase")

tab = tabs_nav()
cards = load_cards()
purchases = load_purchases()

# ---- 1. Add Purchase Tab ----
if tab == "Add Purchase":
    st.header("🟢 Add Purchase")
    if st.session_state.get("should_reset_amount", False):
        st.session_state.purchase_amount = 0.0
        st.session_state.purchase_paid = False
        st.session_state.should_reset_amount = False

    if not cards:
        st.info("Please add a card first in the 'Cards' tab.")
    else:
        card_names = list(cards.keys())
        purchase_card = st.selectbox("Card", card_names)
        categories = list(cards[purchase_card].keys())
        if categories:
            purchase_category = st.selectbox("Category", categories)
        else:
            st.warning("This card has no categories. Please add some in Cards tab.")
            purchase_category = ""
        purchase_amount = st.number_input(
            "Amount", min_value=0.0, step=0.01, format="%.2f",
            key="purchase_amount"
        )
        purchase_paid = st.checkbox("Paid?", value=st.session_state.purchase_paid, key="purchase_paid")
        add_pressed = st.button("Add Purchase", use_container_width=True)
        if add_pressed:
            if st.session_state.purchase_amount == 0.0:
                st.warning("Amount must be greater than zero.")
            else:
                new_purchase = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "card": purchase_card,
                    "category": purchase_category,
                    "amount": float(st.session_state.purchase_amount),
                    "paid": st.session_state.purchase_paid,
                }
                purchases.append(new_purchase)
                save_purchases(purchases)
                st.session_state.add_success = True
                st.session_state.should_reset_amount = True
                st.rerun()
        if st.session_state.add_success:
            st.toast("Purchase added successfully!", icon="✅")
            st.session_state.add_success = False

# ---- 2. History Tab ----
elif tab == "History":
    st.header("📜 Purchase History")

    if not purchases:
        st.info("No purchases yet.")
    else:
        # Prepare DataFrame
        df = pd.DataFrame([
            p for p in purchases if "card" in p and "category" in p and "amount" in p and "paid" in p
        ])
        if not df.empty:
            def get_cashback(row):
                try:
                    return float(cards.get(row['card'], {}).get(row['category'], 0))
                except Exception:
                    return 0
            df['cashback_percent'] = df.apply(get_cashback, axis=1)
            df['cashback'] = df['amount'].astype(float) * df['cashback_percent']
            df['net'] = df['amount'].astype(float) - df['cashback']
            df['paid_str'] = df['paid'].apply(lambda x: "✅" if x else "❌")
            df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
            df['date_only'] = df['date_dt'].dt.strftime('%Y-%m-%d')
            
            # --- SORTING: Newest to Oldest ---
            df = df.sort_values(by='date_dt', ascending=False)

            # --- FILTERS ---
            all_cards = ["All"] + list(cards.keys())
            filter_card = st.selectbox("Filter by card", all_cards, key="history_card")
            paid_filter = st.radio("Show", ["All", "Paid only", "Unpaid only"], horizontal=True)
            months = df['date_dt'].dt.to_period('M').dropna().unique()
            months = sorted([str(m) for m in months], reverse=True)
            filter_month = st.selectbox("Filter by month", ["All"] + months, key="history_month")

            # --- FILTER DATA ---
            filtered = df.copy()
            if filter_card != "All":
                filtered = filtered[filtered['card'] == filter_card]
            if paid_filter == "Paid only":
                filtered = filtered[filtered['paid'] == True]
            elif paid_filter == "Unpaid only":
                filtered = filtered[filtered['paid'] == False]
            if filter_month != "All":
                filtered = filtered[filtered['date_dt'].dt.to_period('M').astype(str) == filter_month]

            # --- COLORS ---
            color_total = "#2874cF"
            color_cashback = "#2ecc71"
            color_net = "#fbc531"
            color_unpaid = "#ea5454"
            color_net_dark = "#34495e"

            # --- TOTALS BAR ---
            st.markdown(
                f"""
                <div style='display:flex; gap:0.7em; margin-bottom:0.77em; justify-content:center; flex-wrap:wrap;'>
                  <div style='background:{color_total};color:white;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 9px {color_total}44;min-width:102px;text-align:center;'>
                    <span style='font-size:1em;'>💳 Total</span><br>
                    <span style='font-size:1.11em;font-weight:bold;'>${filtered['amount'].sum():.2f}</span>
                  </div>
                  <div style='background:{color_cashback};color:white;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 9px {color_cashback}44;min-width:102px;text-align:center;'>
                    <span style='font-size:1em;'>🟢 Cashback</span><br>
                    <span style='font-size:1.11em;font-weight:bold;'>${filtered['cashback'].sum():.2f}</span>
                  </div>
                  <div style='background:{color_net};color:#222;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 9px {color_net}44;min-width:102px;text-align:center;'>
                    <span style='font-size:1em;'>🧾 Net</span><br>
                    <span style='font-size:1.11em;font-weight:bold;'>${filtered['net'].sum():.2f}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            # --- UNPAID TOTALS BAR ---
            unpaid = filtered[filtered['paid'] == False]
            if not unpaid.empty:
                st.markdown(
                    f"""
                    <div style='display:flex; gap:0.7em; margin-bottom:0.77em; justify-content:center; flex-wrap:wrap;'>
                      <div style='background:{color_unpaid};color:white;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 8px {color_unpaid}55;min-width:102px;text-align:center;'>
                        <span style='font-size:1em;'>🔴 Unpaid</span><br>
                        <span style='font-size:1.11em;font-weight:bold;'>${unpaid['amount'].sum():.2f}</span>
                      </div>
                      <div style='background:{color_cashback};color:white;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 8px {color_cashback}55;min-width:102px;text-align:center;'>
                        <span style='font-size:1em;'>🟢 Cashback</span><br>
                        <span style='font-size:1.11em;font-weight:bold;'>${unpaid['cashback'].sum():.2f}</span>
                      </div>
                      <div style='background:{color_net_dark};color:white;padding:0.87em 1em;border-radius:1.2em;box-shadow:0 2px 8px {color_net_dark}55;min-width:102px;text-align:center;'>
                        <span style='font-size:1em;'>🧾 Net</span><br>
                        <span style='font-size:1.11em;font-weight:bold;'>${unpaid['net'].sum():.2f}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

            # --- PAY ALL FILTERED BUTTON ---
            to_pay = filtered[filtered['paid'] == False]
            if not to_pay.empty:
                if st.button(f"Pay All Filtered ({len(to_pay)} purchases)", type="primary"):
                    for idx in to_pay.index:
                        purchases[idx]["paid"] = True
                    save_purchases(purchases)
                    
                    # 1. Trigger the immediate download pop-up
                    st.session_state.just_paid = to_pay.copy()
                    
                    # 2. Save the backup receipt to the archive tab
                    payment_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                    total_paid = float(to_pay['amount'].sum())
                    save_receipt(payment_date, total_paid, to_pay)
                    
                    st.success(f"Marked {len(to_pay)} purchases as paid and saved backup to Receipts archive!")
                    st.rerun()

            # --- IMMEDIATE DOWNLOAD POP-UP (RESTORED) ---
            if st.session_state.get("just_paid") is not None:
                just_paid = st.session_state["just_paid"]
                if not just_paid.empty:
                    st.subheader("🧾 Receipt for Paid Purchases")
                    logo_url = "https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png"
                    pdf_path = generate_pdf_receipt(just_paid, logo_url=logo_url)
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button("⬇️ Download Receipt as PDF", pdf_file.read(), file_name="paid_receipt.pdf", mime="application/pdf")
                    if st.button("❌ Hide Receipt"):
                        st.session_state.just_paid = None
                        st.rerun()

            # --- FLEX ROW TABLE STYLES ---
            st.markdown("""
            <style>
            .flex-table-row, .flex-table-header {
                display: flex;
                align-items: center;
                background: #eef1f8;
                color: #2851a3;
                font-weight: 700;
                border-radius: 1.1em;
                box-shadow: 0 2px 8px #e4eefc50;
                padding: 0.65em 0.75em;
                margin-bottom: 7px;
                min-width: 650px;
                overflow-x: auto;
                font-size: 1.09em;
                gap: 0.3em;
            }
            .flex-table-row {
                background: #fff !important;
                color: #222 !important;
                font-weight: 500;
                box-shadow: 0 2px 8px #e4eefc80;
            }
            .flex-col {
                min-width: 80px;
                text-align: left;
                padding-right: 8px;
            }
            .flex-col.amount, .flex-col.cashback, .flex-col.net {
                text-align: right;
                min-width: 85px;
            }
            .flex-col.paid, .flex-col.edit {
                text-align: center;
                min-width: 48px;
            }
            .flex-col.edit { padding-left: 6px; }
            .edit-btn {
                background: #eaf3fb;
                color: #1d5ca5;
                border: none;
                border-radius: 0.7em;
                padding: 0.23em 0.9em;
                font-size: 1.09em;
                cursor: pointer;
                font-weight: 600;
                box-shadow: 0 1px 3px #e1e7f6cc;
                transition: background 0.18s;
            }
            .edit-btn:hover { background: #dbefff; }
            @media (max-width: 700px) {
                .flex-table-row, .flex-table-header { min-width: 550px; font-size:1.01em;}
                .flex-col { min-width: 62px;}
                .flex-col.amount, .flex-col.cashback, .flex-col.net { min-width: 73px;}
                .flex-col.paid, .flex-col.edit { min-width: 40px;}
            }
            @media (max-width: 450px) {
                .flex-table-row, .flex-table-header { min-width: 400px; font-size: .98em;}
                .flex-col { min-width: 48px; }
                .flex-col.amount, .flex-col.cashback, .flex-col.net { min-width: 60px;}
                .flex-col.paid, .flex-col.edit { min-width: 36px;}
            }
            </style>
            """, unsafe_allow_html=True)

            # --- HEADER ---
            st.markdown("""
            <div class="flex-table-header">
              <div class="flex-col">Date</div>
              <div class="flex-col">Card</div>
              <div class="flex-col">Category</div>
              <div class="flex-col amount">Amount</div>
              <div class="flex-col cashback">Cashback</div>
              <div class="flex-col net">Net</div>
              <div class="flex-col paid">Paid</div>
              <div class="flex-col edit">Edit</div>
            </div>
            """, unsafe_allow_html=True)

            # --- PURCHASE ROWS ---
            if not filtered.empty:
                for i, row in filtered.iterrows():
                    idx = row.name
                    st.markdown(
                        f"""
                        <div class="flex-table-row">
                          <div class="flex-col">{row['date_only']}</div>
                          <div class="flex-col">{row['card']}</div>
                          <div class="flex-col">{row['category']}</div>
                          <div class="flex-col amount">${row['amount']:.2f}</div>
                          <div class="flex-col cashback">${row['cashback']:.2f}</div>
                          <div class="flex-col net">${row['net']:.2f}</div>
                          <div class="flex-col paid">{row['paid_str']}</div>
                          <div class="flex-col edit">
                            {('<b>Editing…</b>' if st.session_state.get('edit_row') == idx else '')}
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    # Edit button logic
                    if st.session_state.get("edit_row") != idx:
                        if st.button("✏️", key=f"edit_{idx}"):
                            st.session_state.edit_row = idx

                    # --- EDIT FORM ---
                    if st.session_state.get("edit_row") == idx:
                        edit_row = df.loc[idx]
                        st.markdown(
                            "<div style='background:#f9fcff;border-radius:0.99em;padding:1.08em 0.8em 0.5em 0.8em;margin-bottom:1em;margin-top:-0.6em;box-shadow:0 2px 6px #e3eefa;'>",
                            unsafe_allow_html=True
                        )
                        st.write("**Edit Purchase:**")
                        colE1, colE2, colE3 = st.columns([3, 1, 1])
                        with colE1:
                            new_amount = st.number_input("Amount", value=float(edit_row["amount"]), min_value=0.0, step=0.01, key=f"edit_amount_{idx}")
                            new_paid = st.checkbox("Paid", value=edit_row["paid"], key=f"edit_paid_{idx}")
                        with colE2:
                            if st.button("Save", key=f"save_edit_{idx}"):
                                purchases[idx]["amount"] = new_amount
                                purchases[idx]["paid"] = new_paid
                                save_purchases(purchases)
                                st.success("Purchase updated!")
                                st.session_state.edit_row = None
                                st.rerun()
                        with colE3:
                            if st.button("Delete", key=f"delete_edit_{idx}"):
                                purchases.pop(idx)
                                save_purchases(purchases)
                                st.success("Purchase deleted!")
                                st.session_state.edit_row = None
                                st.rerun()
                            if st.button("Cancel", key=f"cancel_edit_{idx}"):
                                st.session_state.edit_row = None
                                st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No purchases match your filters.")
        else:
            st.info("No purchases found.")

# ---- 3. Saved Receipts Archive Tab ----
elif tab == "Receipts":
    st.header("📁 Saved Receipts Archive")
    
    saved_receipts = load_receipts()
    
    if not saved_receipts:
        st.info("You haven't generated any receipts yet. Pay some purchases in the History tab first!")
    else:
        # Reverse to show the newest receipts at the top
        saved_receipts.reverse()

        for index, receipt in enumerate(saved_receipts):
            with st.expander(f"🧾 Receipt from {receipt['date_paid']} — Total: ${float(receipt['total_amount']):.2f}"):
                # Convert saved JSON back to DataFrame
                receipt_df = pd.DataFrame(json.loads(receipt['items_json']))
                
                # Setup preview columns safely
                cols_to_show = [c for c in ['date_only', 'card', 'category', 'amount', 'net'] if c in receipt_df.columns]
                st.dataframe(receipt_df[cols_to_show], use_container_width=True)
                
                pdf_bytes = get_cached_pdf_bytes(receipt['items_json'])
                
                st.download_button(
                    label="⬇️ Download PDF Receipt",
                    data=pdf_bytes,
                    file_name=f"Receipt_{str(receipt['date_paid'])[:10]}.pdf",
                    mime="application/pdf",
                    key=f"dl_archive_{index}"
                )

# ---- 4. Cards Tab ----
elif tab == "Cards":
    st.header("💳 Cards")
    with st.expander("➕ Create Card"):
        card_name = st.text_input("Card Name", key="card_name")
        col1, col2, col3 = st.columns([3,2,1])
        with col1:
            cat_name = st.text_input("Category", key="cat_name")
        with col2:
            cat_percent = st.number_input("% Cashback", 0.0, 100.0, 1.0, step=0.1, key="cat_percent")
        with col3:
            if st.button("Add Category", key="addcatbtn"):
                if cat_name and cat_percent > 0:
                    st.session_state.new_card_categories[cat_name] = cat_percent / 100.0
                    st.success(f"Added category '{cat_name}' ({cat_percent}%)")
        if st.session_state.new_card_categories:
            st.markdown("**Categories Added:**")
            for cat, pct in list(st.session_state.new_card_categories.items()):
                colA, colB = st.columns([4,1])
                colA.write(f"- {cat}: {pct*100:.1f}% ")
                if colB.button("🗑️ Remove", key=f"delcat_{cat}"):
                    st.session_state.new_card_categories.pop(cat)
                    st.rerun()
        if st.button("Create Card", use_container_width=True):
            if card_name and st.session_state.new_card_categories:
                cards[card_name] = st.session_state.new_card_categories.copy()
                save_cards(cards)
                st.session_state.new_card_categories = {}
                st.success(f"Card '{card_name}' created.")
                st.rerun()
            else:
                st.error("Enter card name and at least one category.")

    if cards:
        for card, cats in list(cards.items()):
            with st.expander(f"✏️ Edit Card: {card}"):
                del_card = st.button(f"🗑️ Delete Card", key=f"delcard_{card}")
                if del_card:
                    cards.pop(card)
                    save_cards(cards)
                    st.success(f"Deleted card '{card}'")
                    st.rerun()
                for cat, pct in list(cats.items()):
                    col1, col2, col3 = st.columns([3,2,1])
                    with col1:
                        new_cat_name = st.text_input("Category", value=cat, key=f"editcatname_{card}_{cat}")
                    with col2:
                        new_pct = st.number_input("% Cashback", 0.0, 100.0, pct*100, key=f"editcatpct_{card}_{cat}")
                    with col3:
                        if st.button("🗑️ Remove", key=f"removecat_{card}_{cat}"):
                            cards[card].pop(cat)
                            save_cards(cards)
                            st.rerun()
                    if new_cat_name != cat and new_cat_name != "":
                        cards[card][new_cat_name] = cards[card].pop(cat)
                        save_cards(cards)
                        st.rerun()
                    if new_pct != pct*100:
                        cards[card][new_cat_name] = new_pct/100.0
                        save_cards(cards)
                        st.rerun()
                colx1, colx2, colx3 = st.columns([3,2,1])
                with colx1:
                    extra_cat = st.text_input("New Category", key=f"extra_cat_{card}")
                with colx2:
                    extra_pct = st.number_input("% Cashback", 0.0, 100.0, 1.0, step=0.1, key=f"extra_pct_{card}")
                with colx3:
                    if st.button("Add to Card", key=f"add_extra_{card}"):
                        if extra_cat and extra_pct > 0:
                            cards[card][extra_cat] = extra_pct / 100.0
                            save_cards(cards)
                            st.success(f"Added category '{extra_cat}' to {card}")
                            st.rerun()
    else:
        st.info("No cards added yet.")

st.caption("by Mohammed Salman! 🚀")
