"""
Удобный скрипт засева/сброса БД.

    python seed.py            # создать БД и засеять из Excel (если ещё не засеяна)
    python seed.py --reset    # удалить app.db и пересоздать с нуля
"""
import sys

from database import init_db, DB_PATH

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    init_db(reset=reset)
    print("База готова" + (" (пересоздана с нуля)" if reset else "") + f": {DB_PATH}")
