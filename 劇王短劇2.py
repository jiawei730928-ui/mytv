# -*- coding: utf-8 -*-
import re, json, requests
from urllib.parse import quote
from bs4 import BeautifulSoup
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

class Spider(Spider):
    def __init__(self):
        self.site="https://djw1.com"
        self.headers={"User-Agent":"Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 Chrome/120 Safari/537.36","Referer":self.site+"/"}
    def getName(self): return "劇王短劇2"
    def init(self,extend=""): pass
    def isVideoFormat(self,url): return ".m3u8" in str(url).lower() or ".mp4" in str(url).lower()
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def _get(self,url):
        if not str(url).startswith("http"): url=self.site+(url if str(url).startswith("/") else "/"+str(url))
        r=requests.get(url,headers=self.headers,timeout=12); r.raise_for_status(); r.encoding="utf-8"; return r.text
    def _items(self,html):
        doc=BeautifulSoup(html,"html.parser"); out=[]; seen=set()
        for li in doc.select("section.container.items li"):
            a=li.select_one("a.image-line") or li.find("a"); img=li.find("img")
            if not a or not img: continue
            href=a.get("href",""); name=img.get("alt","") or img.get("title",""); pic=img.get("src","") or img.get("data-src","")
            if pic.startswith("//"): pic="https:"+pic
            elif pic.startswith("/"): pic=self.site+pic
            rm=li.select_one(".remarks.light") or li.select_one(".remarks"); remark=rm.get_text(" ",strip=True) if rm else ""
            if href and name and href not in seen:
                seen.add(href); out.append({"vod_id":href,"vod_name":name,"vod_pic":pic,"vod_remarks":remark})
        return out
    def homeContent(self,filter):
        classes=[]
        try:
            doc=BeautifulSoup(self._get("/all/"),"html.parser"); seen=set()
            for a in doc.select("section.container.items a"):
                href=a.get("href",""); name=re.sub(r"\s*[（(]\d+[）)]\s*$","",a.get_text(" ",strip=True)).strip()
                if href and name and href not in seen:
                    if href.startswith("/"): href=self.site+href
                    seen.add(href); classes.append({"type_id":href,"type_name":name})
                    if len(classes)>=30: break
        except Exception as e: print("homeContent:",e)
        return {"class":classes}
    def homeVideoContent(self): return {"list":[]}
    def categoryContent(self,tid,pg,filter,extend):
        try: page=max(1,int(pg or 1))
        except: page=1
        try:
            base=str(tid)
            if not base.startswith("http"): base=self.site+(base if base.startswith("/") else "/"+base)
            if not base.endswith("/"): base+="/"

            # 第一頁完全沿用原版（已知可正常取得影片）
            if page == 1:
                url = base
            else:
                # 劇王的分類網址不一定接受硬拼 page/N/。
                # 從第一頁開始，實際讀取網頁上的「下一頁」href，逐頁走到指定頁。
                url = base
                for _ in range(1, page):
                    html_now = self._get(url)
                    doc_now = BeautifulSoup(html_now, "html.parser")
                    next_url = ""

                    # rel=next 優先
                    a_next = doc_now.find("a", attrs={"rel":"next"})
                    if a_next and a_next.get("href"):
                        next_url = a_next.get("href")

                    # 再找文字/符號型下一頁
                    if not next_url:
                        for a in doc_now.find_all("a", href=True):
                            txt = a.get_text(" ", strip=True)
                            cls = " ".join(a.get("class", []))
                            if txt in ("下一页","下一頁","下页","下頁","›","»",">") or "next" in cls.lower():
                                next_url = a.get("href")
                                break

                    # 再找頁碼 = 目前頁+1
                    if not next_url:
                        target = str(_ + 1)
                        for a in doc_now.find_all("a", href=True):
                            if a.get_text(strip=True) == target:
                                next_url = a.get("href")
                                break

                    if not next_url:
                        url = ""
                        break
                    if next_url.startswith("//"): next_url = "https:" + next_url
                    elif next_url.startswith("/"): next_url = self.site + next_url
                    elif not next_url.startswith("http"): next_url = base + next_url
                    url = next_url

            videos=self._items(self._get(url)) if url else []
        except Exception as e: print("categoryContent:",e); videos=[]
        return {"list":videos,"page":page,"pagecount":page+(1 if videos else 0),"limit":len(videos) or 20,"total":(page+1)*(len(videos) or 20)}
    def detailContent(self,ids):
        did=str(ids[0])
        try:
            doc=BeautifulSoup(self._get(did),"html.parser")
            h=doc.find(["h1","h2"]); title=h.get_text(" ",strip=True) if h else ""
            og=doc.find("meta",property="og:image"); pic=og.get("content","") if og else ""
            c=doc.select_one(".info-detail"); content=c.get_text(" ",strip=True) if c else ""
            r=doc.select_one(".info-mark"); remark=r.get_text(" ",strip=True) if r else ""
            y=doc.select_one(".info-addtime"); year=y.get_text(" ",strip=True) if y else ""
            eps=[]; box=doc.select_one("div.ep-list-items")
            if box:
                for i,a in enumerate(box.find_all("a"),1):
                    href=a.get("href",""); name=a.get_text(" ",strip=True) or "第%d集"%i
                    if href:
                        if href.startswith("/"): href=self.site+href
                        eps.append("%s$%s"%(name,href))
            return {"list":[{"vod_id":did,"vod_name":title,"vod_pic":pic,"vod_remarks":remark,"vod_year":year,"vod_content":content,"vod_play_from":"劇王","vod_play_url":"#".join(eps)}]}
        except Exception as e: print("detailContent:",e); return {"list":[]}
    def searchContentPage(self,key,quick,pg=1):
        try: page=max(1,int(pg or 1))
        except: page=1
        try: videos=self._items(self._get("%s/search/%s/page/%d/"%(self.site,quote(str(key)),page)))
        except Exception as e: print("search:",e); videos=[]
        return {"list":videos,"page":page,"pagecount":page+(1 if videos else 0),"limit":len(videos) or 20,"total":(page+1)*(len(videos) or 20)}
    def searchContent(self,key,quick,pg="1"): return self.searchContentPage(key,quick,pg)
    def playerContent(self,flag,id,vipFlags):
        try:
            html=self._get(str(id)); m=re.search(r'"wwm3u8"\s*:\s*"([^"]+)"',html)
            play=m.group(1).replace("\\/","/").replace("\\","") if m else ""
            if play: return {"parse":0,"url":play,"header":json.dumps(self.headers,ensure_ascii=False)}
        except Exception as e: print("playerContent:",e)
        return {"parse":0,"url":"","header":json.dumps(self.headers,ensure_ascii=False)}
    def localProxy(self,param): return [200,"video/MP2T",{},param]
