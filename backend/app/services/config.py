import os

# This finds the absolute path to the project root,
# regardless of where the server is actually run from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.path.join(BASE_DIR, "pharmacy_inventory.db")