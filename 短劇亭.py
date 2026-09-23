# -*- coding: utf-8 -*-
import re, json, requests
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://duanjuting.com"
        self.headers = {
            "User-Agent":"Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer": self.siteUrl + "/"
        }
        self.cates = {"短劇":"1","AI漫劇":"24","劇情":"18","電影":"3","電視劇":"2","動漫":"5"}

    def getName(self): return "短劇亭"
    def init(self, extend=""): pass
    def destroy(self): pass
    def isVideoFormat(self, url): return ".m3u8" in str(url).lower() or ".mp4" in str(url).lower()
    def manualVideoCheck(self): return False

    def _get(self, path):
        url = path if str(path).startswith("http") else self.siteUrl + path
        r = requests.get(url, headers=self.headers, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text

    def _clean(self, s):
        s = re.sub(r"<[^>]+>", "", s or "")
        return re.sub(r"\s+", " ", s).strip()

    def _abs(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.siteUrl + u
        return u

    def _cards(self, html):
        out=[]; seen=set()
        for m in re.finditer(r'href=["\'](/ju/index(\d+)\.html)["\'][^>]*>(.*?)</a>', html, re.S|re.I):
            vid = m.group(2)
            body = m.group(3)
            if vid in seen: continue
            name = self._clean(body)
            if not name or len(name)>80: continue
            a=max(0,m.start()-900); b=min(len(html),m.end()+350)
            block=html[a:b]
            pics=re.findall(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)',block,re.I)
            pic=self._abs(pics[-1]) if pics else ""
            remarks=""
            rm=re.findall(r'(全\d+集|更新至第?\d+集|已完结|全集|HD中字|HD)',block)
            if rm: remarks=rm[-1]
            seen.add(vid)
            out.append({"vod_id":vid,"vod_name":name,"vod_pic":pic,"vod_remarks":remarks})
        return out

    def homeContent(self, filter):
        return {"class":[{"type_name":k,"type_id":v} for k,v in self.cates.items()]}

    def homeVideoContent(self):
        try:
            return {"list":self._cards(self._get("/"))[:40]}
        except Exception as e:
            print("homeVideoContent:",e)
            return {"list":[]}

    def categoryContent(self, tid, pg, filter, extend):
        try: page=max(1,int(pg or 1))
        except: page=1
        path="/t/index%s.html"%tid if page==1 else "/t/index%s-%s.html"%(tid,page)
        try:
            html=self._get(path)
            videos=self._cards(html)
            mm=re.search(r'(\d+)\s*/\s*(\d+)',html)
            pages=int(mm.group(2)) if mm else page+(1 if videos else 0)
            return {"list":videos,"page":page,"pagecount":pages,
                    "limit":len(videos) or 30,"total":pages*(len(videos) or 30)}
        except Exception as e:
            print("categoryContent:",e)
            return {"list":[],"page":page,"pagecount":page}

    def searchContent(self, key, quick, pg=1):
        from urllib.parse import quote
        try: page=max(1,int(pg or 1))
        except: page=1
        candidates=[
            "/search.php?searchword="+quote(str(key)),
            "/search?wd="+quote(str(key)),
            "/s/-------------.html?wd="+quote(str(key))
        ]
        for p in candidates:
            try:
                vs=self._cards(self._get(p))
                if vs: return {"list":vs,"page":page,"pagecount":page}
            except: pass
        return {"list":[],"page":page,"pagecount":page}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key,quick,pg)

    def detailContent(self, ids):
        vid=re.sub(r"\D","",str(ids[0]))
        try:
            html=self._get("/ju/index%s.html"%vid)
            title=""
            m=re.search(r"<h1[^>]*>(.*?)</h1>",html,re.S|re.I)
            if m: title=self._clean(m.group(1))

            pic=""
            pics=re.findall(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)',html,re.I)
            if pics: pic=self._abs(pics[0])

            def meta(label):
                mm=re.search(label+r'\s*</?[^>]*>?(?:\s|&nbsp;)*([^<\r\n]+)',html,re.S|re.I)
                return self._clean(mm.group(1)) if mm else ""

            year=meta("年份")
            area=meta("地区")
            actor=meta("主演")
            director=meta("导演")

            # 每條播放線獨立保存自己的集數
            lines={}
            pat=r'href=["\'](/kan/'+re.escape(vid)+r'-(\d+)-(\d+)\.html)["\'][^>]*>(.*?)</a>'
            for mm in re.finditer(pat,html,re.S|re.I):
                path,line,ep,body=mm.group(1),mm.group(2),mm.group(3),mm.group(4)
                name=self._clean(body) or ("第%02d集"%(int(ep)+1))
                lines.setdefault(line,[]).append((int(ep),name,path))

            play_from=[]; play_url=[]
            for line in sorted(lines,key=lambda x:int(x)):
                arr=sorted(lines[line],key=lambda x:x[0])
                play_from.append("雲點播"+str(int(line)+1))
                play_url.append("#".join("%s$myt:%s"%(name,path) for _,name,path in arr))

            vod={
                "vod_id":vid,"vod_name":title,"vod_pic":pic,
                "vod_year":year,"vod_area":area,
                "vod_actor":actor,"vod_director":director,
                "vod_play_from":"$$$".join(play_from),
                "vod_play_url":"$$$".join(play_url)
            }
            return {"list":[vod]}
        except Exception as e:
            print("detailContent:",e)
            return {"list":[]}

    def playerContent(self, flag, id, vipFlags):
        sid=str(id)
        if sid.startswith("http") and (".m3u8" in sid or ".mp4" in sid):
            return {"parse":0,"url":sid,"header":json.dumps(self.headers)}

        path=sid[4:] if sid.startswith("myt:") else sid
        try:
            html=self._get(path)

            # 已由實際播放頁確認：var now = 真實 master m3u8
            m=re.search(r'var\s+now\s*=\s*["\'](https?://[^"\']+)["\']',html,re.I)
            if not m:
                m=re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']',html,re.I)

            if m:
                url=m.group(1).replace("\\/","/")
                return {"parse":0,"url":url,"header":json.dumps(self.headers)}
        except Exception as e:
            print("playerContent:",e)

        return {"parse":0,"url":self.siteUrl,"header":json.dumps(self.headers)}

    def localProxy(self,param):
        return [200,"video/MP2T",{},param]
