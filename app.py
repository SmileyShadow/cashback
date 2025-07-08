import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Cashback Cards Tracker", page_icon="💳", layout="centered")

st.title("💳 Cashback Cards Tracker")

# --- Data Storage ---
if "cards" not in st.session_state:
    st.session_state.cards = {}  # card_name: {category: percentage}
if "purchases" not in st.session_state:
    st.session_state.purchases = []  # List of dicts

# --- Card Management ---
st.header("Your Cards")
with st.expander("Add New Card"):
    card_name = st.text_input("Card Name")
    new_card_category = st.text_input("Add Category Name")
    new_card_percent = st.number_input("Cashback % for this category", 0.0, 100.0, 1.0, step=0.1)
    add_category_btn = st.button("Add Category to Card")
    if "new_card_categories" not in st.session_state:
        st.session_state.new_card_categories = {}
    if add_category_btn and new_card_category and new_card_percent > 0:
        st.session_state.new_card_categories[new_card_category] = new_card_percent / 100.0
        st.success(f"Added category '{new_card_category}' with {new_card_percent}% cashback.")
    if st.button("Create Card"):
        if card_name and st.session_state.new_card_categories:
            st.session_state.cards[card_name] = st.session_state.new_card_categories.copy()
            st.success(f"Card '{card_name}' created.")
            st.session_state.new_card_categories = {}
        else:
            st.error("Enter card name and at least one category.")

# List & edit existing cards
if st.session_state.cards:
    for card, cats in list(st.session_state.cards.items()):
        with st.expander(f"Edit Card: {card}"):
            delete = st.button(f"Delete {card}", key=f"del_{card}")
            if delete:
                st.session_state.cards.pop(card)
                st.success(f"Deleted card '{card}'")
                st.stop()
            for cat, pct in list(cats.items()):
                new_pct = st.number_input(f"Edit {cat} cashback (%)", 0.0, 100.0, pct*100, key=f"edit_{card}_{cat}")
                if new_pct != pct*100:
                    st.session_state.cards[card][cat] = new_pct/100.0
            if st.button(f"Remove all categories from {card}", key=f"clear_{card}"):
                st.session_state.cards[card] = {}
            add_cat_name = st.text_input(f"Add new category for {card}", key=f"addcat_{card}")
            add_cat_pct = st.number_input(f"Cashback %", 0.0, 100.0, 1.0, key=f"addcatpct_{card}")
            if st.button(f"Add Category to {card}", key=f"addcatbtn_{card}"):
                if add_cat_name and add_cat_pct > 0:
                    st.session_state.cards[card][add_cat_name] = add_cat_pct / 100.0

else:
    st.info("No cards added yet.")

# --- Purchase Management ---
st.header("Add Purchase")
if not st.session_state.cards:
    st.warning("Add at least one card before adding purchases.")
else:
    purchase_card = st.selectbox("Select Card", list(st.session_state.cards.keys()))
    if st.session_state.cards[purchase_card]:
        purchase_category = st.selectbox("Select Category", list(st.session_state.cards[purchase_card].keys()))
    else:
        purchase_category = st.text_input("Enter Category")
    purchase_amount = st.number_input("Amount", min_value=0.01, step=0.01)
    purchase_paid = st.checkbox("Paid?", value=False)
    if st.button("Add Purchase"):
        st.session_state.purchases.append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "card": purchase_card,
            "category": purchase_category,
            "amount": purchase_amount,
            "paid": purchase_paid,
        })
        st.success("Purchase added!")

# --- Edit/Delete Purchases ---
st.header("Purchase History")
if st.session_state.purchases:
    df = pd.DataFrame(st.session_state.purchases)
    df['cashback %'] = df.apply(lambda row: 
        st.session_state.cards.get(row['card'], {}).get(row['category'], 0) * 100, axis=1)
    df['cashback'] = df.apply(lambda row: 
        row['amount'] * st.session_state.cards.get(row['card'], {}).get(row['category'], 0), axis=1)
    df['net'] = df['amount'] - df['cashback']
    st.dataframe(df.style.format({"amount": "${:.2f}", "cashback": "${:.2f}", "net": "${:.2f}", "cashback %": "{:.1f}%"}))

    # Edit or Delete
    for i, purchase in enumerate(st.session_state.purchases):
        with st.expander(f"{purchase['date']} | {purchase['card']} | {purchase['category']} | ${purchase['amount']:.2f}"):
            new_amount = st.number_input("Edit Amount", min_value=0.01, value=float(purchase['amount']), key=f"edit_amt_{i}")
            new_paid = st.checkbox("Paid?", value=purchase['paid'], key=f"edit_paid_{i}")
            if st.button("Save Edit", key=f"saveedit_{i}"):
                st.session_state.purchases[i]['amount'] = new_amount
                st.session_state.purchases[i]['paid'] = new_paid
                st.experimental_rerun()
            if st.button("Delete Purchase", key=f"delpur_{i}"):
                st.session_state.purchases.pop(i)
                st.experimental_rerun()

    # Totals
    total = df['amount'].sum()
    total_cashback = df['cashback'].sum()
    net = df['net'].sum()
    unpaid = df[df['paid']==False]['amount'].sum()
    st.info(f"Total Spent: ${total:.2f} | Total Cashback: ${total_cashback:.2f} | Net: ${net:.2f} | Unpaid: ${unpaid:.2f}")
else:
    st.info("No purchases yet.")

# --- End of App ---
st.caption("Made with ❤️ for personal use. By YourName.")

