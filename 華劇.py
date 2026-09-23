# -*- coding: utf-8 -*-
import re, json, requests, random, string
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://tw.huaju.app"
        self.headers = {
            "User-Agent":"Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer": self.siteUrl + "/home?tab=series&_proto=http"
        }

    def getName(self): return "華劇"
    def init(self, extend=""): pass
    def destroy(self): pass
    def isVideoFormat(self, url): return ".m3u8" in str(url).lower() or ".mp4" in str(url).lower()
    def manualVideoCheck(self): return False

    def _csrf(self):
        # 實機已驗證：/@csrf?key=8字元 → URL decode → repeating-key XOR
        from urllib.parse import unquote
        # 使用已實機成功過的 key；若站端要求隨機，再退回隨機英數
        keys=["adGHc3fO"]
        keys += ["".join(random.choice(string.ascii_letters+string.digits) for _ in range(8)) for _ in range(2)]
        last=None
        for key in keys:
            try:
                r=requests.get(self.siteUrl+"/@csrf",params={"key":key},headers=self.headers,timeout=12)
                r.raise_for_status()
                raw=unquote(r.text)
                token="".join(chr(ord(ch)^ord(key[i%len(key)])) for i,ch in enumerate(raw))
                if token:
                    return token
            except Exception as e:
                last=e
        if last: raise last
        return ""

    def _api(self, path, params=None):
        params=dict(params or {})
        params["FORM_HASH"]=self._csrf()
        r=requests.get(self.siteUrl+"/@apix/v1/"+path.lstrip("/"),
                       params=params,headers=self.headers,timeout=18)
        r.raise_for_status()
        data=r.json()
        # 相容可能存在的 data/result 包裝
        if isinstance(data,dict):
            for k in ("data","result"):
                if k in data and isinstance(data[k],(dict,list)):
                    return data[k]
        return data

    def homeContent(self, filter):
        return {"class":[
            {"type_name":"國產劇","type_id":"国产剧"},
            {"type_name":"短劇","type_id":"短剧"},
            {"type_name":"動漫","type_id":"动漫"},
            {"type_name":"電影","type_id":"电影"},
            {"type_name":"綜藝","type_id":"综艺"}
        ]}

    def _item(self, x):
        return {
            "vod_id":str(x.get("eid") or ""),
            "vod_name":x.get("vod_name") or x.get("name") or x.get("title") or "",
            "vod_pic":x.get("vod_pic") or x.get("pic") or x.get("cover") or "",
            "vod_remarks":str(x.get("vod_remarks") or x.get("vod_year") or x.get("year") or "")
        }

    def homeVideoContent(self):
        # 首頁不是播放必要環節；先用空列表避免硬猜華劇首頁 API
        return {"list":[]}

    def categoryContent(self, tid, pg, filter, extend):
        # 華劇已實證搜尋 API；分類 API 尚未固定，測試版不偽造分類結果
        try: page=max(1,int(pg or 1))
        except: page=1
        return {"list":[],"page":page,"pagecount":page}

    def searchContent(self, key, quick, pg=1):
        try: page=max(1,int(pg or 1))
        except: page=1
        try:
            d=self._api("flim/search",{"q":str(key),"page":page,"size":20,"facet":1})
            rows=d.get("list") or [] if isinstance(d,dict) else []
            vs=[self._item(x) for x in rows]
            vs=[x for x in vs if x["vod_id"] and x["vod_name"]]
            return {"list":vs,"page":int(d.get("page") or page),
                    "pagecount":int(d.get("pages") or page),
                    "limit":int(d.get("size") or 20),
                    "total":int(d.get("total") or len(vs))}
        except Exception as e:
            print("searchContent:",e)
            return {"list":[],"page":page,"pagecount":page}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key,quick,pg)

    def detailContent(self, ids):
        eid=str(ids[0])
        try:
            d=self._api("flim/detail",{"eid":eid,"limit":12})
            item=d.get("item") or {}
            raws=d.get("raw_videos") or []
            play_from=[]; play_url=[]
            for src in raws:
                if src.get("source_offline"): continue
                names=str(src.get("vod_play_from") or "").split("$$$")
                urls=str(src.get("vod_play_url") or "").split("$$$")
                for i,line in enumerate(urls):
                    if not line: continue
                    sname=(src.get("source_name") or (names[i] if i<len(names) else "") or "華劇")
                    eps=[]
                    for ep in line.split("#"):
                        if "$" not in ep: continue
                        label,url=ep.split("$",1)
                        if url.startswith("http"):
                            eps.append(label+"$"+url)
                    if eps:
                        play_from.append(str(sname))
                        play_url.append("#".join(eps))
            vod={
                "vod_id":eid,
                "vod_name":item.get("vod_name") or item.get("name") or item.get("title") or "",
                "vod_pic":item.get("vod_pic") or item.get("pic") or item.get("cover") or "",
                "vod_year":str(item.get("vod_year") or item.get("year") or ""),
                "type_name":item.get("unified_cat_name") or item.get("type_name") or "",
                "vod_actor":item.get("vod_actor") or "",
                "vod_director":item.get("vod_director") or "",
                "vod_content":item.get("vod_content") or item.get("content") or item.get("vod_blurb") or "",
                "vod_play_from":"$$$".join(play_from),
                "vod_play_url":"$$$".join(play_url)
            }
            return {"list":[vod]}
        except Exception as e:
            print("detailContent:",e)
            return {"list":[]}

    def playerContent(self, flag, id, vipFlags):
        # detail 的 vod_play_url 已是真實公開 http(s) m3u8
        return {"parse":0,"url":str(id),"header":json.dumps(self.headers)}

    def localProxy(self,param):
        return [200,"video/MP2T",{},param]
