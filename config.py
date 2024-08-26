import pathlib

RELEVANT_COLUMNS = ["Datum", "Omschrijving", "Bedrag", "Naam tegenpartij",
                    "Adres tegenpartij", "gestructureerde mededeling", "Vrije mededeling", "Saldo"]
ADDED_COLUMNS = ["Category", "Split with Medha"]
CATEGORY_OPTIONS = ["Other", "Groceries", "Credit card", "Lunch", "Rent", "Salary",
                    "Utilities", "Eating out", "Dates", "Clothes", "Coffee/snacks", "Transport", "Health", "Entertainment", "Reinbursement", "Reinbursable", "Paypal"]

DATA_DIR = "raw_data"
DATA_FILES = list(pathlib.Path(DATA_DIR).glob('**/*'))
