"""Добавляет результат из issue в data/results.json (запускается GitHub Actions).

Игра создаёт issue с заголовком «run: …» и JSON в теле.
Принимаются только issue от владельца репозитория (их создаёт токен игры) —
если кто-то посторонний откроет такой issue, он будет просто закрыт.
Итог пишется в файл $STATUS_FILE: первая строка — ok/skip, вторая — текст комментария.
"""
import datetime
import json
import os
import re
import sys

RESULTS = os.path.join(os.path.dirname(__file__), "..", "data", "results.json")
NAME_MAX = 16


def finish(status, message):
    path = os.environ.get("STATUS_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(status + "\n" + message + "\n")
    print(status, "-", message)
    sys.exit(0)


def clean_name(raw):
    name = " ".join(str(raw or "").split())[:NAME_MAX]
    name = "".join(ch for ch in name if ch.isalnum() or ch in " _-.!")
    return name.strip()


def to_int(v, lo=0, hi=1_000_000):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 0


def parse_body(body):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body or "", re.S)
    text = m.group(1) if m else (body or "").strip()
    return json.loads(text)


def main():
    author = os.environ.get("ISSUE_AUTHOR", "")
    owner = os.environ.get("OWNER", "")
    if not owner or author.lower() != owner.lower():
        finish("skip", f"Результаты принимаются только от игры (автор issue: {author}).")
    try:
        data = parse_body(os.environ.get("ISSUE_BODY", ""))
    except (ValueError, TypeError):
        finish("skip", "Не смог прочитать результат (нужен JSON).")

    name = clean_name(data.get("name"))
    if not name:
        finish("skip", "Пустое имя.")
    try:
        seconds = float(data.get("seconds"))
    except (TypeError, ValueError):
        finish("skip", "Нет времени прохождения.")
    if not (10 <= seconds <= 100 * 3600):
        finish("skip", "Странное время прохождения.")

    try:
        with open(RESULTS, encoding="utf-8") as f:
            db = json.load(f)
    except (OSError, ValueError):
        db = {"runs": []}
    runs = db.setdefault("runs", [])
    run = {
        "id": max((r.get("id", 0) for r in runs), default=0) + 1,
        "name": name,
        "seconds": round(seconds, 2),
        "kills": to_int(data.get("kills")),
        "coins": to_int(data.get("coins")),
        "deaths": to_int(data.get("deaths")),
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "issue": to_int(os.environ.get("ISSUE_NUMBER")),
    }
    runs.append(run)
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # место по лучшему времени игрока
    best = {}
    for r in runs:
        k = " ".join(r["name"].split()).casefold()
        best[k] = min(best.get(k, r["seconds"]), r["seconds"])
    mine = best[" ".join(name.split()).casefold()]
    place = 1 + sum(1 for v in best.values() if v < mine)
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    t = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    finish("ok", f"Записано: {name} — {t}. Место в таблице: {place} из {len(best)}.")


if __name__ == "__main__":
    main()
