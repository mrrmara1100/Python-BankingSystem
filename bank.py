"""
Simple CLI Banking System
-------------------------
Features: sign up, login (authorization), deposit, withdraw, transfer,
currency exchange (USD <-> KHR), transaction history, and delete account.
Balances are shown automatically on the main menu.
User data is stored in users.json (same folder as this file).
Each user has two balances: USD (dollars) and KHR (Cambodian riels).

When you sign up, the bank gives you an ID. You log in with that ID and your password.

Built-in account (ID / password):
    1000 / admin

Requires the Rich library for colors and tables:
    pip install rich
"""

import json
import os
import sys
import uuid
import hashlib
import getpass
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
MAX_LOGIN_ATTEMPTS = 3
MIN_PASSWORD_LENGTH = 4
FIRST_USER_ID = 1000
ADMIN_ID = "1000"   # the built-in admin account cannot be deleted

# Smallest amount you can deposit in each currency
MIN_DEPOSIT = {
    "USD": 1,
    "KHR": 4000,
}

# Exchange rate: how many riels one dollar is worth
EXCHANGE_RATE = 4000

# Theme colors (Rich styles work like CSS for the terminal)
CYAN = "#00FFFF"
ELECTRIC_GREEN = "#39FF14"
RED = "#FF4D4D"

# Make sure special characters (like the banner blocks) print correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

console = Console(highlight=False)

BANNER = """\
█   █ █████ █      ████  ███  █   █ █████    █████  ███      ████ █     ███    ████   ███  █   █ █   █
█   █ █     █     █     █   █ ██ ██ █          █   █   █    █     █      █     █   █ █   █ ██  █ █  █
█ █ █ ████  █     █     █   █ █ █ █ ████       █   █   █    █     █      █     ████  █████ █ █ █ ███
██ ██ █     █     █     █   █ █   █ █          █   █   █    █     █      █     █   █ █   █ █  ██ █  █
█   █ █████ █████  ████  ███  █   █ █████      █    ███      ████ █████ ███    ████  █   █ █   █ █   █"""


# ---------------------------------------------------------------------------
# Colorful output helpers
# ---------------------------------------------------------------------------

def blend_color(start_hex, end_hex, ratio):
    """Mix two hex colors. ratio 0 = start color, ratio 1 = end color."""
    r1, g1, b1 = int(start_hex[1:3], 16), int(start_hex[3:5], 16), int(start_hex[5:7], 16)
    r2, g2, b2 = int(end_hex[1:3], 16), int(end_hex[3:5], 16), int(end_hex[5:7], 16)
    r = round(r1 + (r2 - r1) * ratio)
    g = round(g1 + (g2 - g1) * ratio)
    b = round(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def show_banner():
    """Print the one-line welcome banner with a cyan-to-electric-green gradient."""
    lines = BANNER.splitlines()
    width = max(len(line) for line in lines)

    # If the window is too narrow for the big letters, use plain text instead
    if console.width < width + 8:
        lines = ["WELCOME TO CLI BANK"]
        width = len(lines[0])

    art = Text()
    for line_number, line in enumerate(lines):
        if line_number > 0:
            art.append("\n")
        for position, character in enumerate(line):
            color = blend_color(CYAN, ELECTRIC_GREEN, position / (width - 1))
            art.append(character, style=f"bold {color}")

    console.print(Panel(
        Align.center(art),
        border_style=CYAN,
        subtitle=Text("Dollars (USD)  •  Riels (KHR)", style=ELECTRIC_GREEN),
        padding=(1, 2),
    ))


def title(text):
    console.print(f"\n===== {text} =====", style=f"bold {CYAN}", markup=False)


def success(message):
    console.print(f"✔ {message}", style=f"bold {ELECTRIC_GREEN}", markup=False)


def error(message):
    console.print(f"✘ {message}", style=f"bold {RED}", markup=False)


def info(message):
    console.print(message, markup=False)


def ask(prompt):
    """Ask the user for input with a cyan prompt."""
    return console.input(Text(prompt, style=CYAN))


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def load_users():
    """Read all users from the JSON file and return them as a dictionary."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        error("users.json was not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        error("users.json is not valid JSON.")
        sys.exit(1)


def save_users(users):
    """Write all users back to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, indent=4)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def hash_password(password):
    """Turn a password into a SHA-256 hash so the real password is never stored."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ask_password(prompt="Enter password: "):
    """Ask for a password without showing it on screen (when running in a terminal)."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return input(prompt)


def is_active(users, user_id):
    """True if the account exists and has not been deleted."""
    user = users.get(user_id)
    return user is not None and not user.get("deleted", False)


def next_user_id(users):
    """Return the next free ID: one more than the highest ID in use."""
    if not users:
        return str(FIRST_USER_ID)
    highest = max(int(user_id) for user_id in users)
    return str(highest + 1)


def format_money(amount, currency):
    """Show money nicely, e.g. $1,200.50 or 2,000,000 KHR."""
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{int(amount):,} KHR"


def format_signed_money(amount, currency):
    """Like format_money, but with + or - in front, e.g. +$50.00 or -10,000 KHR."""
    sign = "+" if amount >= 0 else "-"
    return sign + format_money(abs(amount), currency)


def ask_currency():
    """Let the user pick USD or KHR. Returns the currency code, or None to go back."""
    while True:
        info("  1. USD (Dollars)")
        info("  2. KHR (Riels)")
        info("  0. Back to main menu")
        choice = ask("Choose currency: ").strip()
        if choice == "1":
            return "USD"
        if choice == "2":
            return "KHR"
        if choice == "0":
            return None
        error("Invalid choice. Please choose 1, 2 or 0.")


def ask_amount(currency, minimum=None):
    """Ask for an amount until it is valid. Returns the amount, or None to go back.

    Riels must be whole numbers, dollars can have up to 2 decimals.
    If minimum is given, the amount must be at least that much.
    """
    if minimum is None:
        prompt = f"Enter amount in {currency} (0 to go back): "
    else:
        prompt = f"Enter amount in {currency} (min {format_money(minimum, currency)}, 0 to go back): "

    while True:
        text = ask(prompt).strip().replace(",", "")
        if text == "0":
            return None

        try:
            amount = float(text)
        except ValueError:
            error("Please enter a valid number.")
            continue

        if amount <= 0:
            error("Amount must be greater than zero.")
            continue

        if currency == "KHR" and amount != int(amount):
            error("Riels must be a whole number (no decimals).")
            continue

        if currency == "USD" and round(amount, 2) != amount:
            error("Dollars can have at most 2 decimal places.")
            continue

        if minimum is not None and amount < minimum:
            error(f"The minimum is {format_money(minimum, currency)}.")
            continue

        if currency == "KHR":
            return int(amount)
        return round(amount, 2)


def wait_for_back():
    """Wait until the user types 0 to go back to the main menu."""
    while True:
        choice = ask("Enter 0 to go back to the main menu: ").strip()
        if choice == "0":
            return
        error("Please enter 0 to go back.")


def update_balance(user, currency, change):
    """Add (or subtract, if change is negative) money from a user's balance."""
    new_balance = user["balance"][currency] + change
    if currency == "USD":
        new_balance = round(new_balance, 2)
    else:
        new_balance = int(new_balance)
    user["balance"][currency] = new_balance


def show_account(users, user_id):
    """Show the user's name, ID, email and both balances in a box."""
    user = users[user_id]

    # Text(...) shows user data exactly as stored, even if it contains [brackets]
    details = Text()
    details.append("Email : ", style=CYAN)
    details.append(user["email"] + "\n")
    details.append("USD   : ", style=CYAN)
    details.append(format_money(user["balance"]["USD"], "USD") + "\n", style=f"bold {ELECTRIC_GREEN}")
    details.append("KHR   : ", style=CYAN)
    details.append(format_money(user["balance"]["KHR"], "KHR"), style=f"bold {ELECTRIC_GREEN}")

    console.print()
    console.print(Panel(
        details,
        title=Text(f"{user['name']}  (ID {user_id})", style=f"bold {CYAN}"),
        border_style=CYAN,
        expand=False,
        padding=(0, 2),
    ))


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------

def make_transaction_id():
    """Create a unique ID such as TXN-3F9A1C7B."""
    return "TXN-" + uuid.uuid4().hex[:8].upper()


def current_timestamp():
    """Full date and time with the time zone, e.g. 2026-11-18 14:30:05 +0700."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def add_transaction(user, txn_type, currency, amount, details,
                    transaction_id=None, timestamp=None):
    """Save one transaction in the user's history.

    amount is positive for money in and negative for money out.
    The balance after the transaction is taken from the user's current balance,
    so call this right after update_balance().
    """
    if transaction_id is None:
        transaction_id = make_transaction_id()
    if timestamp is None:
        timestamp = current_timestamp()

    if "transactions" not in user:
        user["transactions"] = []

    user["transactions"].append({
        "transaction_id": transaction_id,
        "timestamp": timestamp,
        "type": txn_type,
        "currency": currency,
        "amount": amount,
        "balance_after": user["balance"][currency],
        "details": details,
    })


def show_history(users, user_id):
    """Show the user's transactions in a table (newest first), then wait for 0."""
    user = users[user_id]
    transactions = user.get("transactions", [])

    title("TRANSACTION HISTORY")
    if not transactions:
        info("No transactions yet.")
        wait_for_back()
        return

    table = Table(
        title=f"{user['name']}  (ID {user_id})",
        title_style=f"bold {CYAN}",
        caption=f"{len(transactions)} transaction(s) · newest first",
        border_style=CYAN,
        header_style=f"bold {ELECTRIC_GREEN}",
        row_styles=["", "dim"],
    )
    table.add_column("#", justify="right")
    table.add_column("Transaction ID", no_wrap=True)
    table.add_column("Timestamp", no_wrap=True)
    table.add_column("Type")
    table.add_column("Amount", justify="right", no_wrap=True)
    table.add_column("Balance After", justify="right", no_wrap=True)
    table.add_column("Details")

    number = len(transactions)
    for txn in reversed(transactions):
        currency = txn["currency"]
        if txn["amount"] >= 0:
            amount_color = ELECTRIC_GREEN
        else:
            amount_color = RED

        # Text(...) shows the value exactly as stored, even if it contains [brackets]
        table.add_row(
            str(number),
            Text(txn["transaction_id"]),
            Text(txn["timestamp"]),
            Text(txn["type"]),
            Text(format_signed_money(txn["amount"], currency), style=amount_color),
            Text(format_money(txn["balance_after"], currency)),
            Text(txn["details"]),
        )
        number -= 1

    console.print(table)
    wait_for_back()


# ---------------------------------------------------------------------------
# Sign up and login (authorization)
# ---------------------------------------------------------------------------

def sign_up(users):
    """Create a new account, save it, and show the new user's ID and name."""
    title("SIGN UP")
    name = ask("Enter your name: ").strip()
    if name == "":
        error("Name cannot be empty.")
        return

    email = ask("Enter your email: ").strip()
    if "@" not in email or "." not in email:
        error("Please enter a valid email address.")
        return

    password = ask_password("Create a password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        error(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return

    confirm = ask_password("Confirm password: ")
    if confirm != password:
        error("Passwords do not match.")
        return

    user_id = next_user_id(users)
    users[user_id] = {
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "balance": {
            "USD": 0.0,
            "KHR": 0
        },
        "transactions": []
    }
    save_users(users)

    console.print()
    success("Account created successfully!")
    info(f"Your ID : {user_id}")
    info(f"Name    : {name}")
    info("Remember your ID. You need it with your password to log in.")


def login(users):
    """Ask for ID and password. Returns the user ID if correct, otherwise None."""
    title("LOGIN")
    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        user_id = ask("Enter your user ID: ").strip()
        password = ask_password()

        if is_active(users, user_id) and users[user_id]["password_hash"] == hash_password(password):
            console.print()
            success(f"Welcome, {users[user_id]['name']}!")
            return user_id

        attempts_left = MAX_LOGIN_ATTEMPTS - attempt
        error(f"Wrong ID or password. Attempts left: {attempts_left}")
        console.print()

    error("Too many failed attempts. Access denied.")
    return None


# ---------------------------------------------------------------------------
# Banking features
# ---------------------------------------------------------------------------

def deposit(users, user_id):
    """Deposit screen. Stays open for more deposits until the user picks 0."""
    user = users[user_id]
    while True:
        title("DEPOSIT")
        currency = ask_currency()
        if currency is None:
            return
        amount = ask_amount(currency, MIN_DEPOSIT[currency])
        if amount is None:
            return

        update_balance(user, currency, amount)
        add_transaction(user, "Deposit", currency, amount, "Cash deposit")
        save_users(users)
        success(f"Deposited {format_money(amount, currency)}.")
        info(f"New {currency} balance: {format_money(user['balance'][currency], currency)}")


def withdraw(users, user_id):
    """Withdraw screen. Stays open for more withdrawals until the user picks 0."""
    user = users[user_id]
    while True:
        title("WITHDRAW")
        currency = ask_currency()
        if currency is None:
            return
        amount = ask_amount(currency)
        if amount is None:
            return

        if amount > user["balance"][currency]:
            error("Insufficient funds.")
            info(f"Your {currency} balance: {format_money(user['balance'][currency], currency)}")
            continue

        update_balance(user, currency, -amount)
        add_transaction(user, "Withdrawal", currency, -amount, "Cash withdrawal")
        save_users(users)
        success(f"Withdrew {format_money(amount, currency)}.")
        info(f"New {currency} balance: {format_money(user['balance'][currency], currency)}")


def exchange(users, user_id):
    """Currency exchange screen. Stays open for more exchanges until the user picks 0."""
    user = users[user_id]
    while True:
        title("CURRENCY EXCHANGE")
        info(f"Rate: 1 USD = {format_money(EXCHANGE_RATE, 'KHR')}")
        info("  1. USD → KHR (dollars to riels)")
        info("  2. KHR → USD (riels to dollars)")
        info("  0. Back to main menu")
        choice = ask("Choose an option: ").strip()

        if choice == "0":
            return
        if choice == "1":
            from_currency, to_currency = "USD", "KHR"
        elif choice == "2":
            from_currency, to_currency = "KHR", "USD"
        else:
            error("Invalid choice. Please choose 1, 2 or 0.")
            continue

        amount = ask_amount(from_currency)
        if amount is None:
            return

        if amount > user["balance"][from_currency]:
            error("Insufficient funds.")
            info(f"Your {from_currency} balance: "
                 f"{format_money(user['balance'][from_currency], from_currency)}")
            continue

        if from_currency == "USD":
            # Dollars to riels: every dollar becomes EXCHANGE_RATE riels
            amount_paid = amount
            amount_received = round(amount * EXCHANGE_RATE)
        else:
            # Riels to dollars: give whole cents only, and only take the riels
            # that were actually converted (any small leftover stays in the account)
            cents = amount * 100 // EXCHANGE_RATE
            if cents == 0:
                error(f"Too small to exchange. You need at least "
                      f"{format_money(EXCHANGE_RATE / 100, 'KHR')} for $0.01.")
                continue
            amount_received = cents / 100
            amount_paid = round(cents * EXCHANGE_RATE / 100)

        console.print()
        info(f"Exchange {format_money(amount_paid, from_currency)} "
             f"for {format_money(amount_received, to_currency)}?")
        confirm = ask("Confirm (y/n): ").strip().lower()
        if confirm != "y":
            error("Exchange cancelled.")
            continue

        update_balance(user, from_currency, -amount_paid)
        update_balance(user, to_currency, amount_received)

        # Both sides of the exchange share one transaction ID and time
        transaction_id = make_transaction_id()
        timestamp = current_timestamp()
        details = f"{from_currency} → {to_currency} @ 1 USD = {EXCHANGE_RATE:,} KHR"
        add_transaction(user, "Exchange Out", from_currency, -amount_paid, details,
                        transaction_id, timestamp)
        add_transaction(user, "Exchange In", to_currency, amount_received, details,
                        transaction_id, timestamp)
        save_users(users)

        success(f"Exchanged {format_money(amount_paid, from_currency)} → "
                f"{format_money(amount_received, to_currency)}. "
                f"Transaction ID: {transaction_id}")
        if amount_paid != amount:
            info(f"{format_money(amount - amount_paid, 'KHR')} was too small "
                 f"to convert and stays in your account.")
        info(f"New balances: {format_money(user['balance']['USD'], 'USD')}  |  "
             f"{format_money(user['balance']['KHR'], 'KHR')}")


def transfer(users, user_id):
    title("TRANSFER")
    receiver_id = ask("Enter receiver's user ID (0 to go back): ").strip()

    if receiver_id == "0":
        return
    if receiver_id == user_id:
        error("You cannot transfer money to yourself.")
        return
    if not is_active(users, receiver_id):
        error("Receiver not found.")
        return

    currency = ask_currency()
    if currency is None:
        return
    amount = ask_amount(currency)
    if amount is None:
        return

    sender = users[user_id]
    receiver = users[receiver_id]

    if amount > sender["balance"][currency]:
        error("Insufficient funds.")
        info(f"Your {currency} balance: {format_money(sender['balance'][currency], currency)}")
        return

    console.print()
    info(f"Send {format_money(amount, currency)} to {receiver['name']} (ID {receiver_id})?")
    confirm = ask("Confirm (y/n): ").strip().lower()
    if confirm != "y":
        error("Transfer cancelled.")
        return

    update_balance(sender, currency, -amount)
    update_balance(receiver, currency, amount)

    # Both accounts get the same transaction ID and time, so the transfer can be traced
    transaction_id = make_transaction_id()
    timestamp = current_timestamp()
    add_transaction(sender, "Transfer Out", currency, -amount,
                    f"To {receiver['name']} (ID {receiver_id})",
                    transaction_id, timestamp)
    add_transaction(receiver, "Transfer In", currency, amount,
                    f"From {sender['name']} (ID {user_id})",
                    transaction_id, timestamp)
    save_users(users)

    success(f"Transfer successful! Transaction ID: {transaction_id}")
    info(f"New {currency} balance: {format_money(sender['balance'][currency], currency)}")


def delete_account(users, user_id):
    """Delete the logged-in user's account. Returns True if it was deleted."""
    user = users[user_id]
    title("DELETE ACCOUNT")

    if user_id == ADMIN_ID:
        error("The admin account cannot be deleted.")
        return False

    # Money must be taken out first, so nothing is lost
    if user["balance"]["USD"] != 0 or user["balance"]["KHR"] != 0:
        error("Your account still has money in it: "
              f"{format_money(user['balance']['USD'], 'USD')} and "
              f"{format_money(user['balance']['KHR'], 'KHR')}.")
        info("Withdraw or transfer all of it first, then try again.")
        return False

    console.print("This permanently deletes your account and your transaction history. "
                  "It cannot be undone.", style=f"bold {RED}", markup=False)

    password = ask_password("Enter your password to continue: ")
    if hash_password(password) != user["password_hash"]:
        error("Wrong password. Your account was NOT deleted.")
        return False

    confirm = ask("Type DELETE to confirm (anything else cancels): ").strip()
    if confirm != "DELETE":
        error("Cancelled. Your account was NOT deleted.")
        return False

    # Remove all personal data but keep the ID reserved, so a new user never
    # gets the same ID (other people's history may still mention it)
    users[user_id] = {
        "deleted": True,
        "deleted_at": current_timestamp(),
    }
    save_users(users)

    success(f"Account {user_id} has been deleted. Goodbye, {user['name']}!")
    return True


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

def show_start_menu():
    title("START MENU")
    info("1. Login")
    info("2. Sign up")
    info("3. Exit")


def show_menu():
    title("MAIN MENU")
    info("1. Deposit")
    info("2. Withdraw")
    info("3. Transfer")
    info("4. Currency exchange")
    info("5. Transaction history")
    info("6. Logout")
    info("7. Delete account")


def main():
    show_banner()
    users = load_users()

    while True:
        show_start_menu()
        choice = ask("Choose an option (1-3): ").strip()

        if choice == "1":
            user_id = login(users)
            if user_id is not None:
                banking_menu(users, user_id)
        elif choice == "2":
            sign_up(users)
        elif choice == "3":
            success("Thank you for banking with us. Goodbye!")
            break
        else:
            error("Invalid option. Please choose 1-3.")


def banking_menu(users, user_id):
    """The menu a user sees after logging in. Returns when they log out."""
    while True:
        show_account(users, user_id)
        show_menu()
        choice = ask("Choose an option (1-7): ").strip()

        if choice == "1":
            deposit(users, user_id)
        elif choice == "2":
            withdraw(users, user_id)
        elif choice == "3":
            transfer(users, user_id)
        elif choice == "4":
            exchange(users, user_id)
        elif choice == "5":
            show_history(users, user_id)
        elif choice == "6":
            success(f"Goodbye, {users[user_id]['name']}!")
            break
        elif choice == "7":
            if delete_account(users, user_id):
                break
        else:
            error("Invalid option. Please choose 1-7.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print("\nSession ended.")
