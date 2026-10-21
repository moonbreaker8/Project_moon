"""웨더뉴스 오사카·교토 예보 → weathernews.json

웨더뉴스는 공개 API가 없어서, GitHub Actions 가 1시간마다 이 스크립트로
웹페이지의 시간별·주간 예보를 읽어 JSON 으로 저장합니다 (사이트가 이 파일을 불러감).
표준 라이브러리만 사용.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
PAGES = {
    "osaka": "https://weathernews.jp/onebox/tenki/osaka/27100/",
    "kyoto": "https://weathernews.jp/onebox/tenki/kyoto/26100/",
}
OUT = Path(__file__).resolve().parent.parent / "weathernews.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (osaka-trip personal page)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def to_date(day, today):
    """'19' 같은 일(day)만 있으므로 오늘 기준으로 가장 가까운 날짜로 맞춤."""
    best = None
    for dm in (-1, 0, 1):
        y, m = today.year, today.month + dm
        if m == 0:
            y, m = y - 1, 12
        elif m == 13:
            y, m = y + 1, 1
        try:
            d = today.replace(year=y, month=m, day=day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.strftime("%Y-%m-%d")


def num(s):
    s = (s or "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse(html, today):
    hourly, daily = [], []
    a = html.find('id="flick_list_1hour"')
    b = html.find('id="flick_list_today"', a)
    if a >= 0:
        block = html[a:b if b > a else None]
        # 날짜 묶음(group) 단위로 자르기
        for g in re.split(r'<div class="group">', block)[1:]:
            dm = re.search(r'<div class="date">\s*<p>(\d+)日', g)
            if not dm:
                continue
            date = to_date(int(dm.group(1)), today)
            for li in re.findall(r'<ul[^>]*class="list[^"]*">(.*?)</ul>', g, re.S):
                t = re.search(r'<li class="time">\s*<p>(\d+)</p>', li)
                wx = re.search(r'wxicon/(\d+)\.png', li)
                rain = re.search(r'<li class="rain"><p>([\d.]+)', li)
                temp = re.search(r'<li class="temp">\s*<p>(-?[\d.]+)', li)
                if not t:
                    continue
                hourly.append({
                    "time": f"{date}T{int(t.group(1)):02d}",
                    "wx": int(wx.group(1)) if wx else None,
                    "r": num(rain.group(1)) if rain else None,
                    "t": num(temp.group(1)) if temp else None,
                })
    for w in re.findall(r'<ul id="wx__week\d+" class="wxweek_content[^"]*">(.*?)</ul>', html, re.S):
        day = re.search(r'<p class="day">(\d+)</p>', w)
        if not day:
            continue
        wx = re.search(r'wxicon/(\d+)\.png', w)
        hi = re.search(r'<li class="high">\s*<p>(-?[\d.]+)', w)
        lo = re.search(r'<li class="low">\s*<p>(-?[\d.]+)', w)
        pop = re.search(r'<li class="rain">\s*<p>(\d+)', w)
        daily.append({
            "date": to_date(int(day.group(1)), today),
            "wx": int(wx.group(1)) if wx else None,
            "max": num(hi.group(1)) if hi else None,
            "min": num(lo.group(1)) if lo else None,
            "pop": num(pop.group(1)) if pop else None,
        })
    return {"hourly": hourly, "daily": daily}


def main():
    now = datetime.now(JST)
    out = {"updated": now.strftime("%Y-%m-%dT%H:%M"), "cities": {}}
    for city, url in PAGES.items():
        src = sys.argv[1] if len(sys.argv) > 1 and city == "osaka" else None  # 테스트용: 저장된 html
        html = Path(src).read_text(encoding="utf-8") if src else fetch(url)
        out["cities"][city] = parse(html, now.date())
        print(city, len(out["cities"][city]["hourly"]), "hours,", len(out["cities"][city]["daily"]), "days")
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
