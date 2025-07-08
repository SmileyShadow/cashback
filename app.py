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
    purchases_ws.clear()
    if purchases:
        purchases_ws.append_row(["date", "card", "category", "amount", "paid"])
        for p in purchases:
            purchases_ws.append_row([p["date"], p["card"], p["category"], p["amount"], p["paid"]])

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

# ---- 1. Add Purchase (Main Tab) ----
if tab == "Add Purchase":
    st.header("🟢 Add Purchase")
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
                st.session_state.purchase_amount = 0.0
                st.session_state.purchase_paid = False
                st.rerun()
        if st.session_state.add_success:
            st.toast("Purchase added successfully!", icon="✅")
            st.session_state.add_success = False

# ---- 2. History Tab ----
elif tab == "History":
    st.header("📜 Purchase History")
    # Show a nice headline (column headers)
    st.markdown("""
        <div style="font-weight:600; background:#f4f8ff; border-radius:0.8em; padding:0.7em 1em; margin-bottom:8px; display:flex; gap:1.2em; color:#2851a3;">
            <div style='width:110px'>Date</div>
            <div style='width:70px'>Card</div>
            <div style='width:60px'>Category</div>
            <div style='width:60px'>Amount</div>
            <div style='width:40px'>Paid</div>
            <div style='width:50px'>Edit</div>
        </div>
    """, unsafe_allow_html=True)
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

            for i, row in df.iterrows():
                idx = purchases.index(filtered[i])
                editing = (st.session_state.edit_row == idx)
                with st.container():
                    if not editing:
                        c = st.columns([1.4,1,1,1,0.8,0.8])
                        c[0].write(row["date"])
                        c[1].write(row["card"])
                        c[2].write(row["category"])
                        c[3].write(f"${row['amount']:.2f}")
                        c[4].write(row["paid_str"])
                        if c[5].button("✏️", key=f"edit_{idx}"):
                            st.session_state.edit_row = idx
                            st.rerun()
                    else:
                        c = st.columns([1.4,1,1,1,0.8,0.8,1])
                        c[0].write(row["date"])
                        c[1].write(row["card"])
                        c[2].write(row["category"])
                        new_amt = c[3].number_input("Edit Amount", min_value=0.0, value=float(row["amount"]), key=f"edit_amt_{idx}")
                        new_paid = c[4].checkbox("Paid", value=row["paid"], key=f"edit_paid_{idx}")
                        if c[5].button("Save", key=f"save_{idx}"):
                            purchases[idx]["amount"] = new_amt
                            purchases[idx]["paid"] = new_paid
                            save_purchases(purchases)
                            st.success("Purchase updated!")
                            st.session_state.edit_row = None
                            st.rerun()
                        if c[6].button("Delete", key=f"delete_{idx}"):
                            purchases.pop(idx)
                            save_purchases(purchases)
                            st.success("Purchase deleted!")
                            st.session_state.edit_row = None
                            st.rerun()
                        if c[6].button("Cancel", key=f"cancel_{idx}"):
                            st.session_state.edit_row = None
                            st.rerun()

            if any(not p.get("paid") for p in filtered):
                if st.button("Mark all visible as paid", type="primary"):
                    for p in filtered:
                        p["paid"] = True
                    save_purchases(purchases)
                    st.success("All visible purchases marked as paid.")
                    st.rerun()

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
