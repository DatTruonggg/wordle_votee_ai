from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data"   # <project>/data, works wherever the repo is cloned
WORD_DATA = ("words_alpha.txt", "English_words.txt")    # merged; duplicates removed by the set

def load_words(word_len: int):
    words = set()
    for file in WORD_DATA:
        f_path = DIR / file

        with f_path.open("r", encoding="utf-8", errors="ignore") as w:
            for line in w:
                word = line.strip().lower() #remove \n and space
                if len(word) == word_len and word.isascii() and word.isalpha():
                    words.add(word)

    return words
