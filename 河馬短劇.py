# -*- coding: utf-8 -*-
import json, re, requests
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://www.kuaikaw.cn"
        self.cateManual = {
            "甜寵":"462","古裝仙俠":"1102","現代言情":"1145","青春":"1170",
            "豪門恩怨":"585","逆襲":"417-464","重生":"439-465",
            "系統":"1159","總裁":"1147","職場商戰":"943"
        }
        self.headers = {
            "User-Agent":"Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer":self.siteUrl
        }

    def getName(self): return "河馬短劇"
    def init(self, extend=""): pass
    def isVideoFormat(self, url): return any(x in str(url).lower() for x in [".mp4",".m3u8"])
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def _get(self, path):
        url = path if str(path).startswith("http") else self.siteUrl + path
        r = requests.get(url, headers=self.headers, timeout=12)
        r.raise_for_status()
        return r.text

    def _next(self, path):
        html = self._get(path)
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
        return json.loads(m.group(1)) if m else {}

    def _props(self, path):
        return self._next(path).get("props",{}).get("pageProps",{})

    def _book(self, b):
        bid = str(b.get("bookId") or b.get("id") or "")
        name = b.get("bookName") or b.get("title") or ""
        pic = b.get("coverWap") or b.get("cover") or b.get("wapUrl") or ""
        total = b.get("totalChapterNum") or ""
        status = b.get("statusDesc") or ""
        return {"vod_id":"/drama/"+bid,"vod_name":name,"vod_pic":pic,
                "vod_remarks":(str(status)+" "+(str(total)+"集" if total else "")).strip()}

    def homeContent(self, filter):
        return {"class":[{"type_name":k,"type_id":v} for k,v in self.cateManual.items()]}

    def homeVideoContent(self):
        videos=[]
        try:
            p=self._props("/")
            rows=[]
            rows += p.get("bannerList") or []
            for c in p.get("seoColumnVos") or []:
                rows += c.get("bookInfos") or []
            seen=set()
            for b in rows:
                v=self._book(b)
                if v["vod_name"] and v["vod_id"] not in seen:
                    seen.add(v["vod_id"]); videos.append(v)
        except Exception as e:
            print("homeVideoContent:",e)
        return {"list":videos}

    def categoryContent(self, tid, pg, filter, extend):
        try: page=max(1,int(pg or 1))
        except: page=1
        videos=[]; pages=page
        try:
            p=self._props("/browse/%s/%s"%(tid,page))
            pages=int(p.get("pages") or page)
            videos=[self._book(x) for x in (p.get("bookList") or [])]
            videos=[x for x in videos if x["vod_name"]]
        except Exception as e:
            print("categoryContent:",e)
        return {"list":videos,"page":page,"pagecount":pages,
                "limit":len(videos) or 20,"total":pages*(len(videos) or 20)}

    def searchContent(self, key, quick, pg=1):
        try: page=max(1,int(pg or 1))
        except: page=1
        videos=[]; pages=page
        try:
            from urllib.parse import quote
            p=self._props("/search?searchValue=%s&page=%s"%(quote(str(key)),page))
            pages=int(p.get("pages") or page)
            videos=[self._book(x) for x in (p.get("bookList") or [])]
            videos=[x for x in videos if x["vod_name"]]
        except Exception as e:
            print("searchContent:",e)
        return {"list":videos,"page":page,"pagecount":pages}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key,quick,pg)

    def detailContent(self, ids):
        vod_id=str(ids[0])
        if not vod_id.startswith("/drama/"): vod_id="/drama/"+vod_id.split("/")[-1]
        try:
            p=self._props(vod_id)
            b=p.get("bookInfoVo") or {}
            chapters=p.get("chapterList") or []
            title=b.get("title") or b.get("bookName") or ""
            cats=",".join([x.get("name","") for x in (b.get("categoryList") or [])])
            actors=", ".join([x.get("name","") for x in (b.get("performerList") or [])])
            eps=[]
            for i,ch in enumerate(chapters,1):
                cid=str(ch.get("chapterId") or "")
                name=ch.get("chapterName") or ("第%d集"%i)
                if cid: eps.append("%s$hm:%s:%s"%(name,vod_id.replace("/drama/",""),cid))
            vod={"vod_id":vod_id,"vod_name":title,"vod_pic":b.get("coverWap",""),
                 "type_name":cats,"vod_remarks":str(b.get("totalChapterNum",""))+"集",
                 "vod_actor":actors,"vod_content":b.get("introduction",""),
                 "vod_play_from":"河馬劇場","vod_play_url":"#".join(eps)}
            return {"list":[vod]}
        except Exception as e:
            print("detailContent:",e)
            return {"list":[]}

    def _find_mp4(self, obj, chapter_id=""):
        if isinstance(obj,dict):
            # 優先目前章節的 video 欄位
            if str(obj.get("chapterId","")) == str(chapter_id):
                cv=obj.get("chapterVideoVo") or {}
                for k in ("mp4","mp4720p","vodMp4Url"):
                    u=cv.get(k) if isinstance(cv,dict) else ""
                    if u and ".mp4" in str(u): return u
            for k in ("chapterInfo",):
                if k in obj:
                    u=self._find_mp4(obj[k],chapter_id)
                    if u: return u
            for v in obj.values():
                u=self._find_mp4(v,chapter_id)
                if u: return u
        elif isinstance(obj,list):
            for v in obj:
                u=self._find_mp4(v,chapter_id)
                if u: return u
        return ""

    def playerContent(self, flag, id, vipFlags):
        sid=str(id)
        if sid.startswith("http"):
            return {"parse":0,"url":sid,"header":json.dumps(self.headers)}
        if not sid.startswith("hm:"):
            return {"parse":0,"url":sid,"header":json.dumps(self.headers)}
        try:
            _,drama_id,chapter_id=sid.split(":",2)
            path="/episode/%s/%s"%(drama_id,chapter_id)
            data=self._next(path)
            mp4=self._find_mp4(data,chapter_id)
            if not mp4:
                html=self._get(path)
                urls=re.findall(r'https?://[^"\'\\\s]+?\.mp4(?:\?[^"\'\\\s]*)?',html)
                exact=[u for u in urls if chapter_id in u]
                mp4=(exact or urls or [""])[0]
            if mp4:
                return {"parse":0,"url":mp4,"header":json.dumps(self.headers)}
        except Exception as e:
            print("playerContent:",e)
        return {"parse":0,"url":self.siteUrl,"header":json.dumps(self.headers)}

    def localProxy(self,param):
        return [200,"video/MP2T",{},param]
