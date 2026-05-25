from src.config import LOCAL_DB_PATH
from src.db import init_db


def main():
    init_db()
    print(f"Base locale SQLite initialisee : {LOCAL_DB_PATH}")


if __name__ == "__main__":
    main()
