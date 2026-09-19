# -*- coding: utf-8 -*-
"""
紅果短劇（官網資料版）- WebHTV / FongMi T3 Python Spider
資料來源：https://hongguoduanju.com 公開 SSR 頁面
功能：首頁、分類、篩選、搜尋、詳情、集數
說明：官網可公開取得片單與每集 vid；實際影片播放另有受保護播放鏈，這版不繞過簽名/CENC。
"""
import sys, json, re
from urllib.parse import quote, urlencode

sys.path.append("..")
try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop("timeout", None)
            return rq.get(url, headers=headers, timeout=20, **kw)

class Spider(Spider):
    def getName(self):
        return "🍅紅果短劇"

    def init(self, extend=""):
        self.host = "https://hongguoduanju.com"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _router(self, path):
        try:
            r = self.fetch(self.host + path, headers=self.header, timeout=20)
            text = r.text or ""
            m = re.search(r'(?:window\.)?_ROUTER_DATA\s*=\s*', text)
            if not m:
                return {}
            start = m.end()
            depth = 0
            in_str = False
            esc = False
            end = -1
            for i in range(start, len(text)):
                c = text[i]
                if in_str:
                    if esc: esc = False
                    elif c == "\\": esc = True
                    elif c == '"': in_str = False
                    continue
                if c == '"': in_str = True
                elif c in "{[": depth += 1
                elif c in "}]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            return json.loads(text[start:end]) if end > start else {}
        except Exception:
            return {}

    def _item(self, x):
        x = x or {}
        vd = x.get("video_data") if isinstance(x.get("video_data"), dict) else x
        sid = str(vd.get("series_id") or x.get("keyword") or "")
        name = str(vd.get("series_title") or vd.get("series_name") or x.get("name") or "未命名")
        cnt = vd.get("episode_cnt") or 0
        return {
            "vod_id": sid,
            "vod_name": name,
            "vod_pic": str(vd.get("series_cover") or ""),
            "vod_remarks": ("全%s集" % cnt) if cnt else "",
        }

    def _filters(self):
        return [
            {"key":"topic","name":"主題","value":[
                {"n":"全部","v":""},{"n":"現言","v":"cate_1021"},{"n":"腦洞","v":"cate_262"},
                {"n":"奇幻","v":"cate_1020"},{"n":"玄幻","v":"cate_1019"},{"n":"古言","v":"cate_439"},
                {"n":"懸疑","v":"cate_165"},{"n":"喜劇","v":"cate_303"},{"n":"恐怖","v":"cate_1219"}]},
            {"key":"background","name":"背景","value":[
                {"n":"全部","v":""},{"n":"現代","v":"cate_757"},{"n":"都市","v":"cate_1"},
                {"n":"古代","v":"cate_758"},{"n":"鄉村","v":"cate_11"},{"n":"年代","v":"cate_79"},
                {"n":"職場","v":"cate_127"},{"n":"校園","v":"cate_4"}]},
            {"key":"setting","name":"設定","value":[
                {"n":"全部","v":""},{"n":"逆襲","v":"cate_1051"},{"n":"重生","v":"cate_36"},
                {"n":"穿越","v":"cate_37"},{"n":"系統","v":"cate_19"},{"n":"先婚後愛","v":"cate_265"},
                {"n":"豪門","v":"cate_936"},{"n":"甜寵","v":"cate_96"}]},
            {"key":"time","name":"時間","value":[
                {"n":"全部","v":""},{"n":"7天內上新","v":"1"},{"n":"14天內上新","v":"2"},
                {"n":"30天內上新","v":"3"},{"n":"90天內上新","v":"4"}]},
        ]

    def homeContent(self, filter):
        classes = [
            {"type_id":"all","type_name":"短劇"},
            {"type_id":"latest","type_name":"最新"},
            {"type_id":"hot","type_name":"最熱"},
            {"type_id":"male","type_name":"男頻"},
            {"type_id":"female","type_name":"女頻"},
        ]
        out = {"class": classes}
        if filter:
            out["filters"] = {c["type_id"]: self._filters() for c in classes}
        return out

    def homeVideoContent(self):
        d = self._router("/category?tab=1&sort_type=2")
        rows = ((d.get("loaderData") or {}).get("category_page") or {}).get("recommendList") or []
        return {"list":[self._item(x) for x in rows[:20]]}

    def categoryContent(self, tid, pg, filter, extend):
        q = {"tab":"1", "sort_type":"1"}
        if tid == "latest": q["sort_type"] = "2"
        elif tid == "male": q["gender"] = "1"
        elif tid == "female": q["gender"] = "2"
        for k,v in (extend or {}).items():
            if v not in ("", "all", "0", None):
                q[k] = str(v)
        try:
            p = int(pg or 1)
        except Exception:
            p = 1
        if p > 1: q["page"] = str(p)
        d = self._router("/category?" + urlencode(q))
        rows = ((d.get("loaderData") or {}).get("category_page") or {}).get("recommendList") or []
        return {"list":[self._item(x) for x in rows], "page":p, "pagecount":999, "limit":20, "total":9999}

    def detailContent(self, ids):
        sid = str(ids[0] if isinstance(ids, list) else ids)
        d = self._router("/detail?series_id=" + quote(sid))
        s = ((d.get("loaderData") or {}).get("detail_page") or {}).get("seriesDetail") or {}
        vids = s.get("vid_list") or []
        eps = "#".join("第%d集$hgplay:%s:%d:%s" % (i+1, sid, i+1, v) for i,v in enumerate(vids))
        actors = ",".join(str(x.get("nickname") or "") for x in (s.get("celebrities") or []) if x.get("nickname"))
        vod = {
            "vod_id": sid,
            "vod_name": str(s.get("series_name") or ""),
            "vod_pic": str(s.get("series_cover") or ""),
            "vod_actor": actors,
            "vod_content": str(s.get("series_intro") or ""),
            "vod_remarks": str(s.get("episode_right_text") or ""),
            "vod_play_from": "紅果",
            "vod_play_url": eps,
        }
        return {"list":[vod]}

    def searchContent(self, key, quick, pg="1"):
        d = self._router("/search/" + quote(str(key)))
        rows = ((d.get("loaderData") or {}).get("search_(keyword)/page") or {}).get("searchList") or []
        return {"list":[self._item(x) for x in rows]}

    def _find_key(self, obj, key):
        if isinstance(obj, dict):
            if key in obj:
                return obj.get(key)
            for v in obj.values():
                got = self._find_key(v, key)
                if got not in (None, "", [], {}):
                    return got
        elif isinstance(obj, list):
            for v in obj:
                got = self._find_key(v, key)
                if got not in (None, "", [], {}):
                    return got
        return None

    def playerContent(self, flag, id, vipFlags):
        try:
            raw = str(id or "")
            if not raw.startswith("hgplay:"):
                return {"parse":0, "playUrl":"", "url":"toast://紅果播放參數格式錯誤"}

            _, sid, idx, vid = raw.split(":", 3)
            idx = int(idx or 1)

            # 官網規則：第1集 /player/{series_id}；
            # 其餘集數 /player/{series_id}/{vid}
            if idx == 1:
                path = "/player/" + quote(sid)
            else:
                path = "/player/" + quote(sid) + "/" + quote(vid)

            d = self._router(path)

            # 公開播放頁 SSR 的 video_player_info.main_url
            info = self._find_key(d, "video_player_info")
            play = ""
            if isinstance(info, dict):
                play = str(info.get("main_url") or "")

            # 頁面結構改動時，仍嘗試尋找 main_url。
            if not play:
                got = self._find_key(d, "main_url")
                if isinstance(got, str):
                    play = got

            if not play:
                return {
                    "parse":0,
                    "playUrl":"",
                    "url":"toast://此集目前不是紅果官網公開可播放集數，或播放網址取得失敗"
                }

            # 不送第三方 Referer；直接交給 WebHTV 播放時效 CDN MP4。
            return {
                "parse":0,
                "playUrl":"",
                "url":play,
                "header":{
                    "User-Agent":self.header.get("User-Agent", "")
                }
            }
        except Exception:
            return {"parse":0, "playUrl":"", "url":"toast://紅果播放資料解析失敗"}
