# -*- coding: utf-8 -*-
import json
import re
import time
import hashlib
import requests

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass


class Spider(Spider):
    def __init__(self):
        self.site = "https://mbd.baidu.com"
        self.detail_site = "https://sv.baidu.com"
        self.ua = "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        self.clarity_order = {"蓝光": 1, "超清": 2, "高清": 3, "标清": 4}

    def getName(self):
        return "百度短劇2"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        u = str(url).lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _post(self, url, data=None, headers=None):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            r = requests.post(url, headers=h, data=data or {}, timeout=15)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return json.loads(r.text)
        except Exception as e:
            print("百度短劇2 request:", e)
            return {}

    def homeContent(self, filter):
        main = ["全部", "新剧", "限时免费", "精选", "独播"]
        topics = [
            "神医", "连续剧", "都市", "现代言情", "异能", "逆袭", "甜宠",
            "总裁", "萌宝", "战神", "宫斗宅斗", "神豪", "虐恋", "闪婚",
            "玄幻", "穿越重生", "年代", "家庭伦理", "古代言情", "武侠武打",
            "赘婿", "单元剧", "青春校园", "历史架空", "王妃", "鉴宝",
            "科幻", "军旅战争", "种田"
        ]
        classes = [{"type_id": x, "type_name": x} for x in main + topics]
        return {"class": classes}

    def homeVideoContent(self):
        data = self.categoryContent("新剧", 1, False, {})
        return {"list": data.get("list", [])[:12]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1

        sub = tid if tid in ["新剧", "限时免费", "精选", "独播"] else "新剧"
        topic = "" if tid in ["全部", "全部题材", "新剧", "限时免费", "精选", "独播"] else tid

        # 百度原版的 version 不是固定 v2，而是 timestamp + v2 的 MD5
        timestamp = int(time.time())
        version = hashlib.md5((str(timestamp) + "v2").encode("utf-8")).hexdigest()

        payload = {
            "data": json.dumps({
                "data": {
                    "extRequest": {"flow_tabid": "13"},
                    "from": "feed",
                    "page": "channel_video_landing",
                    "pd": "feed",
                    "refreshIndex": page,
                    "cursor": "",
                    "theme": "",
                    "timestamp": timestamp,
                    "version": version,
                    "themes": [
                        {"kind": "综合", "names": [sub]},
                        {"kind": "题材", "names": [topic]}
                    ]
                }
            }, ensure_ascii=False)
        }

        res = self._post(
            self.site + "/feedapi/v1/videoserver/playlets/list?service=bdbox",
            payload
        )

        items = (((res or {}).get("data") or {}).get("items") or [])
        videos = []
        for it in items:
            vid = it.get("collId") or ""
            if not vid:
                continue
            videos.append({
                "vod_id": str(vid),
                "vod_name": it.get("title") or "未知标题",
                "vod_pic": it.get("img") or "",
                "vod_remarks": it.get("updateStatus") or "",
                "vod_content": it.get("description") or ""
            })

        return {
            "list": videos,
            "page": page,
            "pagecount": page + (1 if videos else 0),
            "limit": len(videos) or 20,
            "total": (page + 1) * (len(videos) or 20)
        }

    def detailContent(self, ids):
        cid = str(ids[0])
        url = self.detail_site + "/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1"
        res = self._post(url, {"playlet_id": cid, "vid": "undefined"})
        d = (res or {}).get("data") or {}
        vids = d.get("vid_list") or []

        if not vids:
            return {"list": []}

        eps = ["第%d集$%s" % (i + 1, vid) for i, vid in enumerate(vids)]
        return {"list": [{
            "vod_id": cid,
            "vod_name": d.get("playlet_title") or "未知剧名",
            "vod_pic": d.get("playlet_poster") or "",
            "vod_content": d.get("description") or "",
            "vod_remarks": "共%d集 热度值:%s" % (len(vids), d.get("hot_value") or 0),
            "vod_director": d.get("tag_text") or "",
            "vod_year": d.get("create_time") or "",
            "vod_play_from": "百度短劇2",
            "vod_play_url": "#".join(eps)
        }]}

    def searchContentPage(self, key, quick, pg=1):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1

        payload = {
            "data": json.dumps({
                "query": str(key),
                "page": page,
                "attribute": ["title"],
                "fe_page_type": "search",
                "extra": {
                    "tab_id": "216",
                    "flow_tabid": "13",
                    "shortplay_source": "feed",
                    "from": "feed",
                    "tab_type": "搜索",
                    "sub_template": "playlet_search_result"
                }
            }, ensure_ascii=False)
        }

        res = self._post(
            self.site + "/feedapi/v1/videoserver/playlets/search?service=bdbox",
            payload
        )
        items = (((res or {}).get("data") or {}).get("itemList") or [])
        videos = []
        for it in items:
            nid = str(it.get("nid") or "")
            vid = nid.split("_", 1)[1] if "_" in nid else nid
            if not vid:
                continue
            videos.append({
                "vod_id": vid,
                "vod_name": it.get("title") or "未知标题",
                "vod_pic": it.get("img") or "",
                "vod_remarks": str(it.get("collNum") or "0") + "集",
                "vod_content": it.get("description") or ""
            })

        return {
            "list": videos,
            "page": page,
            "pagecount": page + (1 if videos else 0),
            "limit": len(videos) or 20,
            "total": (page + 1) * (len(videos) or 20)
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def _find_media_urls(self, obj):
        found = []

        def walk(x):
            if isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            elif isinstance(x, str):
                s = x.replace("\\u002F", "/").replace("\\/", "/")
                if s.startswith("http") and (
                    ".m3u8" in s.lower() or ".mp4" in s.lower()
                ):
                    found.append(s)

        walk(obj)
        # preserve order / dedupe
        return list(dict.fromkeys(found))

    def playerContent(self, flag, id, vipFlags):
        play_headers = {
            "User-Agent": self.ua,
            "Referer": self.detail_site + "/",
            "Origin": self.detail_site,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        url = self.detail_site + "/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1"
        res = self._post(url, {"method": "post", "vid": str(id)}, play_headers)

        vr = (res or {}).get("video/relate") or {}
        data = vr.get("data") or {}
        video = (
            data.get("cur_video") or data.get("curVideo") or
            (res or {}).get("cur_video") or (res or {}).get("curVideo") or {}
        )

        clarity = (
            video.get("clarityUrl") or video.get("clarity_url") or
            video.get("clarityUrls") or video.get("clarity_urls") or []
        )

        choices = []
        if isinstance(clarity, list):
            for item in clarity:
                if not isinstance(item, dict):
                    continue
                u = (
                    item.get("url") or item.get("playUrl") or item.get("play_url") or
                    item.get("videoUrl") or item.get("video_url") or ""
                )
                if not u:
                    continue
                title = (
                    item.get("title") or item.get("name") or
                    item.get("clarity") or item.get("definition") or "播放"
                )
                choices.append((self.clarity_order.get(title, 999), title, u))

        if not choices and isinstance(video, dict):
            u = (
                video.get("url") or video.get("playUrl") or video.get("play_url") or
                video.get("videoUrl") or video.get("video_url") or
                video.get("mp4Url") or video.get("mp4_url") or ""
            )
            if u:
                choices.append((1, "播放", u))

        if not choices:
            for u in self._find_media_urls(res):
                choices.append((999, "播放", u))

        if not choices:
            return {
                "parse": 0,
                "url": "",
                "msg": "百度目前未取得可播放地址",
                "header": json.dumps(play_headers, ensure_ascii=False)
            }

        choices.sort(key=lambda x: x[0])

        if len(choices) == 1:
            return {
                "parse": 0,
                "url": choices[0][2],
                "header": json.dumps({
                    "User-Agent": self.ua,
                    "Referer": self.detail_site + "/"
                }, ensure_ascii=False)
            }

        flat = []
        for _, title, u in choices:
            flat.extend([title, u])

        return {
            "parse": 0,
            "url": flat,
            "header": json.dumps({
                "User-Agent": self.ua,
                "Referer": self.detail_site + "/"
            }, ensure_ascii=False)
        }

    def localProxy(self, param):
        return [200, "video/MP2T", {}, param]
