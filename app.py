import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# -- Add custom Apple Touch Icon and browser tab icon --
st.markdown("""
    <link rel="apple-touch-icon" sizes="180x180" href="https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#2498F7">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

# -- Set page config: title, browser tab icon (favicon), and layout --
st.set_page_config(
    page_title="Cashback Cards App",
    page_icon="https://raw.githubusercontent.com/SmileyShadow/cashback/main/static/icon.png.png",
    layout="centered"
)

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
    return cards_ws, purchases_ws

cards_ws, purchases_ws = get_gsheets()

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
    rows = []
    for card, categories in cards.items():
        for category, percent in categories.items():
            rows.append({"card_name": card, "category": category, "cashback_percent": percent})
    cards_ws.clear()
    if rows:
        cards_ws.append_row(["card_name", "category", "cashback_percent"])
        for row in rows:
            cards_ws.append_row([row["card_name"], row["category"], row["cashback_percent"]])

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

def tabs_nav():
    tabs = {
        "Add Purchase": "🟢 Add Purchase",
        "History": "📜 History",
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

            # --- TOTALS BAR (Top!) ---
            st.markdown(
                f"""
                <div style='display:flex; gap:1em; margin-bottom:1.2em; justify-content:center; flex-wrap:wrap;'>
                  <div style='background:#2498F7;color:white;padding:1em 1.5em;border-radius:1.5em;box-shadow:0 2px 12px #2498f755;'>
                    <span style='font-size:1.3em;'>💳 Total</span><br>
                    <span style='font-size:1.4em;font-weight:bold;'>${df['amount'].sum():.2f}</span>
                  </div>
                  <div style='background:#3DBB5B;color:white;padding:1em 1.5em;border-radius:1.5em;box-shadow:0 2px 12px #3DBB5B55;'>
                    <span style='font-size:1.3em;'>💰 Cashback</span><br>
                    <span style='font-size:1.4em;font-weight:bold;'>${df['cashback'].sum():.2f}</span>
                  </div>
                  <div style='background:#FFB200;color:white;padding:1em 1.5em;border-radius:1.5em;box-shadow:0 2px 12px #FFB20055;'>
                    <span style='font-size:1.3em;'>🧾 Net</span><br>
                    <span style='font-size:1.4em;font-weight:bold;'>${df['net'].sum():.2f}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            # --- FILTERS (below totals) ---
            all_cards = ["All"] + list(cards.keys())
            filter_card = st.selectbox("Filter by card", all_cards, key="history_card")
            paid_filter = st.radio("Show", ["All", "Paid only", "Unpaid only"], horizontal=True)
            # -- Month filter --
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

            # --- FLEXBOX STYLE ---
            st.markdown("""
            <style>
            .flex-table-row {
                display: flex;
                background: #fff;
                color: #222;
                border-radius: 1.2em;
                box-shadow: 0 2px 12px #d8dbf0;
                margin-bottom: 0.9em;
                font-size: 1.08em;
                font-weight: 500;
                align-items: center;
                padding: 0.3em 1em;
                overflow-x: auto;
                min-width: 450px;
                max-width: 100vw;
            }
            .flex-table-cell {
                flex: 1 0 80px;
                padding: 0.3em 0.4em;
                text-align: left;
                white-space: nowrap;
            }
            .flex-table-cell.amount, .flex-table-cell.cashback, .flex-table-cell.net { text-align: right; }
            .flex-table-cell.paid { text-align: center;}
            .flex-table-cell.edit { text-align: center;}
            .edit-btn {
                background: #eaf3fb;
                color: #1d5ca5;
                border: none;
                border-radius: 0.7em;
                padding: 0.32em 1.1em;
                font-size: 1.08em;
                cursor: pointer;
                font-weight: 700;
                box-shadow: 0 1px 3px #e1e7f6cc;
                transition: background 0.18s;
            }
            .edit-btn:hover { background: #dbefff; }
            @media (max-width: 650px) {
                .flex-table-row { font-size: 1em; min-width: 350px;}
            }
            </style>
            """, unsafe_allow_html=True)

            # --- HEADER ---
            st.markdown("""
            <div class="flex-table-row" style="background:#eef1f8;font-weight:700;color:#2851a3;">
              <div class="flex-table-cell">Date</div>
              <div class="flex-table-cell">Card</div>
              <div class="flex-table-cell">Category</div>
              <div class="flex-table-cell amount">Amount</div>
              <div class="flex-table-cell cashback">Cashback</div>
              <div class="flex-table-cell net">Net</div>
              <div class="flex-table-cell paid">Paid</div>
              <div class="flex-table-cell edit">Edit</div>
            </div>
            """, unsafe_allow_html=True)

            # --- PURCHASE ROWS ---
            if not filtered.empty:
                for i, row in filtered.iterrows():
                    idx = row.name
                    st.markdown(
                        f"""
                        <div class="flex-table-row">
                          <div class="flex-table-cell">{row['date_only']}</div>
                          <div class="flex-table-cell">{row['card']}</div>
                          <div class="flex-table-cell">{row['category']}</div>
                          <div class="flex-table-cell amount">${row['amount']:.2f}</div>
                          <div class="flex-table-cell cashback">${row['cashback']:.2f}</div>
                          <div class="flex-table-cell net">${row['net']:.2f}</div>
                          <div class="flex-table-cell paid">{row['paid_str']}</div>
                          <div class="flex-table-cell edit">
                            {('<b>Editing…</b>' if st.session_state.get('edit_row') == idx else '')}
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    # Show Streamlit edit button if not currently editing this row
                    if st.session_state.get("edit_row") != idx:
                        if st.button("✏️", key=f"edit_{idx}"):
                            st.session_state.edit_row = idx

                    # --- EDIT FORM: directly under the row being edited ---
                    if st.session_state.get("edit_row") == idx:
                        edit_row = df.loc[idx]
                        st.markdown(
                            "<div style='background:#f9fcff;border-radius:1em;padding:1.2em 1em 0.7em 1em;margin-bottom:1.1em;margin-top:-0.7em;box-shadow:0 2px 8px #e3eefa;'>",
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



# ---- 3. Cards Tab ----
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
