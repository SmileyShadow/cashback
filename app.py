import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

st.set_page_config(page_title="Cashback Cards App", page_icon="💳", layout="centered")

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
    # Only clear once and update all at once for all rows
    values = [["date", "card", "category", "amount", "paid"]]
    for p in purchases:
        values.append([p["date"], p["card"], p["category"], p["amount"], p["paid"]])
    # Don't clear, just batch update the range!
    purchases_ws.update(f"A1:E{len(values)}", values)
    # If the new data is shorter than the previous data, delete leftover rows
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

# ---------- HISTORY STYLE ------------
st.markdown("""
    <style>
    .purchase-row, .purchase-header {
        display: flex; align-items: center; gap: 0.5em;
        width: 100%; min-width: 390px; overflow-x: auto;
    }
    .purchase-row { 
        background: #fafcff; border-radius: 1.1em; box-shadow: 0 2px 7px #e4eefc70;
        padding: 0.7em 0.6em; margin-bottom: 0.55em;
    }
    .purchase-header {
        font-weight: 600; background: #f4f8ff; border-radius: 0.8em; 
        padding: 0.7em 1em; margin-bottom: 6px; color: #2851a3;
    }
    .purchase-row .col-date,
    .purchase-row .col-card,
    .purchase-row .col-cat,
    .purchase-row .col-amt,
    .purchase-row .col-paid,
    .purchase-row .col-edit {
        color: #222 !important;
        font-size: 1.08em;
        font-weight: 500;
    }
    .col-date { min-width: 88px; max-width: 24%; overflow-x:hidden;}
    .col-card { min-width: 55px; max-width: 18%; overflow-x:hidden;}
    .col-cat { min-width: 46px; max-width: 15%; overflow-x:hidden;}
    .col-amt { min-width: 66px; max-width: 15%; text-align:right; overflow-x:hidden;}
    .col-paid { min-width: 33px; max-width: 12%; text-align:center; overflow-x:hidden;}
    .col-edit { min-width: 45px; max-width: 13%; text-align:center; overflow-x:hidden;}
    .edit-btn {
        background: #eaf3fb;
        color: #222;
        border: none;
        border-radius: 0.7em;
        padding: 0.38em 0.9em;
        font-size: 1em;
        cursor: pointer;
        transition: background 0.2s;
    }
    .edit-btn:hover { background: #dbefff; }
    @media (max-width: 650px) {
      .purchase-row, .purchase-header { font-size: 1em; min-width: 330px; }
      .col-date { min-width: 70px;}
      .col-card { min-width: 42px;}
      .col-cat { min-width: 36px;}
      .col-amt { min-width: 53px;}
      .col-paid { min-width: 25px;}
      .col-edit { min-width: 38px;}
    }
    </style>
""", unsafe_allow_html=True)
# -------------------------------------

# ---- 1. Add Purchase (Main Tab) ----
if tab == "Add Purchase":
    st.header("🟢 Add Purchase")
    # -- Reset fields at the start of the rerun, if needed --
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
        all_cards = ["All"] + list(cards.keys())
        filter_card = st.selectbox("Filter by card", all_cards, key="history_card")
        paid_filter = st.radio("Show", ["All", "Paid only", "Unpaid only"], horizontal=True)
        filtered = [p for p in purchases if "card" in p and "category" in p and "amount" in p and "paid" in p]
        if filter_card != "All":
            filtered = [p for p in filtered if p["card"] == filter_card]
        if paid_filter == "Paid only":
            filtered = [p for p in filtered if p.get("paid") is True]
        elif paid_filter == "Unpaid only":
            filtered = [p for p in filtered if not p.get("paid")]

        df = pd.DataFrame(filtered)
        if not df.empty:
            def get_cashback(row):
                try:
                    return float(cards.get(row['card'], {}).get(row['category'], 0))
                except Exception:
                    return 0
            df['cashback %'] = df.apply(get_cashback, axis=1) * 100
            df['cashback'] = df['amount'].astype(float) * df.apply(get_cashback, axis=1)
            df['net'] = df['amount'].astype(float) - df['cashback']
            df['paid_str'] = df['paid'].apply(lambda x: "✅" if x else "❌")

            # --- FLEXBOX STYLE: Always one line, scrolls horizontally ---
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
            .flex-table-cell.amount { text-align: right; }
            .flex-table-cell.paid { text-align: center;}
            .flex-table-cell.edit { text-align: center;}
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
              <div class="flex-table-cell paid">Paid</div>
              <div class="flex-table-cell edit">Edit</div>
            </div>
            """, unsafe_allow_html=True)

            # --- TOTALS BAR (Optional) ---
            st.markdown(
                f"""
                <div style='display:flex; gap:1em; margin-bottom:1em; justify-content:center; flex-wrap:wrap;'>
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

            # --- PURCHASE ROWS (Each row = one line, always) ---
            for i, row in df.iterrows():
                st.markdown(
                    f"""
                    <div class="flex-table-row">
                      <div class="flex-table-cell">{row['date']}</div>
                      <div class="flex-table-cell">{row['card']}</div>
                      <div class="flex-table-cell">{row['category']}</div>
                      <div class="flex-table-cell amount">${row['amount']:.2f}</div>
                      <div class="flex-table-cell paid">{row['paid_str']}</div>
                      <div class="flex-table-cell edit">
                        <a href="javascript:window.alert('Edit not interactive in HTML, but you can enable an edit form below the row!')" 
                           style="color:#1f6fd4;text-decoration:none;font-size:1.2em;">✏️</a>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )



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

st.caption("Made for iPhone, by you! 🚀")
