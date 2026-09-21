# -*- coding: utf-8 -*-
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass


class Spider(Spider):
    def __init__(self):
        self.site = "https://djw1.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer": "https://djw1.com/"
        }

    def getName(self):
        return "劇王短劇2"

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        u = str(url).lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def _get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            print("劇王短劇2:", e)
            return ""

    def _clean(self, s):
        return re.sub(r"\s+", " ", s or "").strip()

    def _id_from_href(self, href):
        # /detail/123.html、/vod/123.html、/play/123.html 都盡量相容
        m = re.search(r"/(?:detail|vod|show|play)/(\d+)(?:/[^/]*)?\.html", href or "")
        return m.group(1) if m else ""

    def _cards(self, html):
        soup = BeautifulSoup(html, "html.parser")
        out, seen = [], set()

        # 不綁死舊版 class；從所有可能的詳情/播放連結反推作品
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            vid = self._id_from_href(href)
            if not vid or vid in seen:
                continue

            # 單集 /play/id/2.html 不當成作品卡
            if re.search(r"/play/\d+/\d+\.html", href):
                continue

            img = a.find("img")
            title = (
                a.get("title")
                or (img.get("alt") if img else "")
                or self._clean(a.get_text(" ", strip=True))
            )
            if not title or title.isdigit() or len(title) < 2:
                continue

            pic = ""
            if img:
                pic = (
                    img.get("data-src")
                    or img.get("data-original")
                    or img.get("src")
                    or ""
                )
                pic = urljoin(self.site, pic)

            parent = a
            for _ in range(3):
                if parent.parent:
                    parent = parent.parent
            text = self._clean(parent.get_text(" ", strip=True))
            remark = ""
            m = re.search(r"(全\s*\d+\s*集|\d+\s*集(?:全|完结)?|更新至\s*\d+\s*集)", text)
            if m:
                remark = re.sub(r"\s+", "", m.group(1))

            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return out

    def homeContent(self, filter):
        # 劇王頁面實際常見標籤；先確保 WebHTV 有可切換分類
        names = [
            "最新", "女频", "男频", "古装", "都市", "逆袭",
            "重生", "穿越", "萌宝", "年代", "悬疑", "甜宠"
        ]
        return {"class": [{"type_id": x, "type_name": x} for x in names]}

    def homeVideoContent(self):
        # 舊 /all/ 若改版，首頁也作備援
        for url in (self.site + "/all/", self.site + "/"):
            html = self._get(url)
            videos = self._cards(html)
            if videos:
                return {"list": videos[:20]}
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1

        # 劇王搜尋目前仍是公開路由；拿標籤做分類查詢，比綁死舊 /all/ DOM 穩
        if tid == "最新":
            urls = [
                f"{self.site}/all/page/{page}/",
                f"{self.site}/all/{page}/",
                self.site + "/all/" if page == 1 else ""
            ]
        else:
            q = quote(str(tid))
            urls = [
                f"{self.site}/search/{q}/page/{page}/",
                f"{self.site}/search/{q}/{page}/"
            ]

        videos = []
        for url in urls:
            if not url:
                continue
            html = self._get(url)
            videos = self._cards(html)
            if videos:
                break

        return {
            "list": videos,
            "page": page,
            "pagecount": page + (1 if videos else 0),
            "limit": len(videos) or 20,
            "total": (page + 1) * (len(videos) or 20)
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        q = quote(str(key))
        urls = [
            f"{self.site}/search/{q}/page/{page}/",
            f"{self.site}/search/{q}/{page}/"
        ]
        videos = []
        for url in urls:
            videos = self._cards(self._get(url))
            if videos:
                break
        return {
            "list": videos,
            "page": page,
            "pagecount": page + (1 if videos else 0),
            "limit": len(videos) or 20,
            "total": (page + 1) * (len(videos) or 20)
        }

    def _work_page(self, vid):
        # 目前公開索引可確認 /play/{作品id}.html 是第1集且帶完整選集
        candidates = [
            f"{self.site}/play/{vid}.html",
            f"{self.site}/detail/{vid}.html",
            f"{self.site}/vod/{vid}.html"
        ]
        for u in candidates:
            html = self._get(u)
            if html and ("第01集" in html or "第1集" in html or "状态" in html or "狀態" in html):
                return u, html
        return candidates[0], self._get(candidates[0])

    def detailContent(self, ids):
        vid = str(ids[0])
        base_url, html = self._work_page(vid)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = self._clean(h1.get_text(" ", strip=True))
            title = re.sub(r"\s*第0*1集.*$", "", title)
        if not title:
            title = soup.title.get_text(strip=True) if soup.title else "劇王短劇"

        pic = ""
        for img in soup.find_all("img"):
            alt = img.get("alt", "")
            if title and title in alt:
                pic = img.get("data-src") or img.get("data-original") or img.get("src") or ""
                break
        pic = urljoin(self.site, pic) if pic else ""

        text = self._clean(soup.get_text(" ", strip=True))
        content = ""
        m = re.search(r"简介[:：]\s*(.+?)(?:分享地址|1-25|01|最新更新)", text)
        if m:
            content = self._clean(m.group(1))

        # 直接從公開單集路由收完整集數：/play/id.html = 第1集；/play/id/N.html = 第N集
        eps = {}
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = re.search(rf"/play/{re.escape(vid)}/(\d+)\.html", href)
            if m:
                n = int(m.group(1))
                eps[n] = urljoin(self.site, href)

        # 第一集沒有 /1/ 也很常見
        eps[1] = f"{self.site}/play/{vid}.html"

        # 若 HTML 只把數字做 JS，不給 href，從「全xx集」補足公開路由
        total = 0
        mt = re.search(r"全\s*(\d+)\s*集", text)
        if mt:
            total = int(mt.group(1))
        if total and total <= 500:
            for n in range(1, total + 1):
                eps.setdefault(n, f"{self.site}/play/{vid}/{n}.html" if n > 1 else f"{self.site}/play/{vid}.html")

        play = "#".join([f"第{n}集${eps[n]}" for n in sorted(eps)])
        remark = f"全{total}集" if total else ""

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": content,
            "vod_play_from": "劇王短劇2",
            "vod_play_url": play
        }]}

    def playerContent(self, flag, id, vipFlags):
        # id 直接是公開單集頁 URL
        page = str(id)
        if not page.startswith("http"):
            page = urljoin(self.site, page)
        html = self._get(page)
        if not html:
            return {"parse": 0, "url": "", "msg": "單集頁讀取失敗"}

        # 舊版核心 wwm3u8 + 常見變體
        patterns = [
            r'"wwm3u8"\s*:\s*"([^"]+)"',
            r"'wwm3u8'\s*:\s*'([^']+)'",
            r'"url"\s*:\s*"(https?[^"]+?\.m3u8[^"]*)"',
            r'(https?://[^"\'\s\\]+?\.m3u8(?:\?[^"\'\s\\]*)?)',
            r'(https?://[^"\'\s\\]+?\.mp4(?:\?[^"\'\s\\]*)?)'
        ]
        play = ""
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                play = m.group(1)
                break

        play = (
            play.replace("\\u002F", "/")
                .replace("\\/", "/")
                .replace("\\", "")
                .replace("&amp;", "&")
        )

        if not play:
            return {"parse": 0, "url": "", "msg": "未取得公開播放網址"}

        return {
            "parse": 0,
            "url": play,
            "header": json.dumps(self.headers, ensure_ascii=False)
        }

    def localProxy(self, param):
        return [200, "video/MP2T", {}, param]
