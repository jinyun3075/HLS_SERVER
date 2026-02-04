import logging
import os
from datetime import datetime

if not os.path.exists("logs"):
    os.makedirs("logs")

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"logs/app_{today}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger