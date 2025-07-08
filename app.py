import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

st.set_page_config(page_title="Cashback Cards App", page_icon="💳", layout="centered")

# --- Google Sheets Authentication ---
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

if 'gcp_service_account' not in st.session_state:
    # Load from Streamlit secrets
    st.session_state.gcp_service_account = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
credentials = Credentials.from_service_account_info(
    st.session_state.gcp_service_account, scopes=SCOPE)
gc = gspread.authorize(credentials)

# --- Your Google Sheet name here ---
SHEET_NAME = "cashback_app"
sh = gc.open(SHEET_NAME)
cards_ws = sh.worksheet("cards")
purchases_ws = sh.worksheet("purchases")

# --- Helper functions for Google Sheets ---
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
    return records

def save_purchases(purchases):
    purchases_ws.clear()
    if purchases:
        purchases_ws.append_row(list(purchases[0].keys()))
        for p in purchases:
            purchases_ws.append_row(list(p.values()))

# --- App state (temporary for new categories before card creation) ---
if "new_card_categories" not in st.session_state:
    st.session_state.new_card_categories = {}

# --- UI Helper: Tabs at the bottom ---
def tabs_nav():
    tabs = {
        "Add Purchase": "🟢",
        "History": "📜",
        "Cards": "💳",
    }
    cols = st.columns(len(tabs))
    selected = st.session_state.get("current_tab", "Add Purchase")
    for i, (tab, icon) in enumerate(tabs.items()):
        if cols[i].button(f"{icon}\n{tab}", use_container_width=True):
            st.session_state.current_tab = tab
    st.markdown("<br>", unsafe_allow_html=True)  # spacing
    return st.session_state.get("current_tab", "Add Purchase")

# --- Load main data from Google Sheets at start ---
cards = load_cards()
purchases = load_purchases()

# --- Main navigation ---
tab = tabs_nav()

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
        purchase_amount = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
        purchase_paid = st.checkbox("Paid?", value=False)
        if st.button("Add Purchase", use_container_width=True):
            new_purchase = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "card": purchase_card,
                "category": purchase_category,
                "amount": float(purchase_amount),
                "paid": purchase_paid,
            }
            purchases.append(new_purchase)
            save_purchases(purchases)
            st.success("Purchase added!")
            st.experimental_rerun()

# ---- 2. History Tab ----
elif tab == "History":
    st.header("📜 Purchase History")
    if not purchases:
        st.info("No purchases yet.")
    else:
        # Filter by card
        all_cards = ["All"] + list(cards.keys())
        filter_card = st.selectbox("Filter by card", all_cards, key="history_card")
        if filter_card == "All":
            filtered = purchases
        else:
            filtered = [p for p in purchases if p["card"] == filter_card]

        df = pd.DataFrame(filtered)
        if not df.empty:
            # Calculate cashback and net
            def get_cashback(row):
                return cards.get(row['card'], {}).get(row['category'], 0)
            df['cashback %'] = df.apply(get_cashback, axis=1) * 100
            df['cashback'] = df['amount'] * df.apply(get_cashback, axis=1)
            df['net'] = df['amount'] - df['cashback']
            df['paid_str'] = df['paid'].apply(lambda x: "✅" if x else "❌")
            st.dataframe(
                df[["date","card","category","amount","paid_str","cashback %","cashback","net"]],
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "cashback": st.column_config.NumberColumn("Cashback", format="$%.2f"),
                    "net": st.column_config.NumberColumn("Net", format="$%.2f"),
                    "cashback %": st.column_config.NumberColumn("Cashback %", format="%.1f%%"),
                },
                hide_index=True,
                use_container_width=True,
            )

            # Inline edit/delete/paid toggle
            for i, row in df.iterrows():
                with st.expander(f"{row['date']} | {row['card']} | {row['category']} | ${row['amount']:.2f}"):
                    # Find the index in original purchases list
                    idx = purchases.index(filtered[i])
                    new_amount = st.number_input("Edit Amount", min_value=0.01, value=float(row['amount']), key=f"edit_amt_{i}")
                    new_paid = st.checkbox("Paid?", value=row['paid'], key=f"edit_paid_{i}")
                    if st.button("Save Edit", key=f"saveedit_{i}"):
                        purchases[idx]['amount'] = new_amount
                        purchases[idx]['paid'] = new_paid
                        save_purchases(purchases)
                        st.success("Updated!")
                        st.experimental_rerun()
                    if st.button("Delete Purchase", key=f"delpur_{i}"):
                        purchases.pop(idx)
                        save_purchases(purchases)
                        st.success("Deleted!")
                        st.experimental_rerun()
            # Mark all as paid
            if any(not p["paid"] for p in filtered):
                if st.button("Mark all as paid", type="primary"):
                    for p in filtered:
                        p["paid"] = True
                    save_purchases(purchases)
                    st.success("All marked as paid.")
                    st.experimental_rerun()

            # Totals
            st.info(f"Total: ${df['amount'].sum():.2f} | Cashback: ${df['cashback'].sum():.2f} | Net: ${df['net'].sum():.2f}")

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
        # Show current categories
        if st.session_state.new_card_categories:
            st.markdown("**Categories Added:**")
            for cat, pct in list(st.session_state.new_card_categories.items()):
                colA, colB = st.columns([4,1])
                colA.write(f"- {cat}: {pct*100:.1f}% ")
                if colB.button("🗑️ Remove", key=f"delcat_{cat}"):
                    st.session_state.new_card_categories.pop(cat)
                    st.experimental_rerun()
        if st.button("Create Card", use_container_width=True):
            if card_name and st.session_state.new_card_categories:
                cards[card_name] = st.session_state.new_card_categories.copy()
                save_cards(cards)
                st.session_state.new_card_categories = {}
                st.success(f"Card '{card_name}' created.")
                st.experimental_rerun()
            else:
                st.error("Enter card name and at least one category.")

    # List & edit existing cards
    if cards:
        for card, cats in list(cards.items()):
            with st.expander(f"✏️ Edit Card: {card}"):
                del_card = st.button(f"🗑️ Delete Card", key=f"delcard_{card}")
                if del_card:
                    cards.pop(card)
                    save_cards(cards)
                    st.success(f"Deleted card '{card}'")
                    st.experimental_rerun()
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
                            st.experimental_rerun()
                    # Update category name or percent
                    if new_cat_name != cat and new_cat_name != "":
                        cards[card][new_cat_name] = cards[card].pop(cat)
                        save_cards(cards)
                        st.experimental_rerun()
                    if new_pct != pct*100:
                        cards[card][new_cat_name] = new_pct/100.0
                        save_cards(cards)
                        st.experimental_rerun()

    else:
        st.info("No cards added yet.")

st.caption("Made for iPhone, by you! 🚀")
