# conftest.py — корень тестов
# pytest автоматически подхватывает этот файл

import sys
import os

# Гарантируем, что корень проекта в sys.path
sys.path.insert(0, os.path.dirname(__file__))
