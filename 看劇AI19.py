# -*- coding: utf-8 -*-
"""
看劇AI19 - WebHTV 精簡移植版
依 2026-09 現行 HMAC API 版本保留：分類、搜尋、詳情、多線路播放。
"""
import sys, time, hmac, hashlib, secrets, urllib.parse, math
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass
import requests

HOSTS = [
    "https://kanju19.com",
    "https://main.kanju13.com",
    "https://kanju20.com",
    "https://kanju.ai",
]
KEY = "557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0"
UA = "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
YJ_M3U8 = "https://zy.baipiaozhe.com/v1/playback/yjm3u8/%s.m3u8"
CLIENT = {
    "x-ai-movie-client-name": "dianyingtiantang-frontend",
    "x-ai-movie-client-version": "1.0.0",
    "x-ai-movie-build-version": "dianyingtiantang-v2026.08.11.1-8cbb0b0d407e-672e67d62528",
    "x-ai-movie-protocol-version": "2026-07-05.library-v2.playback-v1",
}
CATEGORIES = {
    "movie":"電影", "series":"電視劇", "short_drama":"短劇",
    "anime":"動漫", "variety":"綜藝", "documentary":"紀錄片",
}
GENRES = {
    "movie":["動作","冒險","劇情","喜劇","奇幻","古裝","家庭","科幻"],
    "series":["動作","冒險","劇情","刑偵","古裝","歷史","台劇","懸疑"],
    "short_drama":["劇情","動作","反轉爽劇","古裝仙俠","喜劇","女頻戀愛","家庭","年代"],
    "anime":["熱血","冒險","奇幻","日本動漫","國產動漫","爆笑","武俠","兒童"],
    "variety":["大陸綜藝","真人秀","情感","愛情","社交觀察"],
    "documentary":["歷史","紀錄片"],
}

class Spider(Spider):
    def getName(self): return "🤖看劇AI19"
    def isVideoFormat(self, url):
        return any(x in str(url or '').lower() for x in ('.m3u8','.mp4','.mkv','.flv'))
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def init(self, extend=""):
        self._hi = 0
        for i, h in enumerate(HOSTS):
            try:
                r = requests.get(h + "/v1/runtime/bootstrap", headers={"User-Agent": UA}, timeout=(4, 8))
                if r.status_code == 200:
                    self._hi = i
                    break
            except Exception:
                continue
        return ""

    def _host(self):
        return HOSTS[getattr(self, '_hi', 0)]

    def _sign(self, method, path):
        ts = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        msg = "%s\n%s\n%s\n%s" % (method, path, ts, nonce)
        sig = hmac.new(KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return ts, nonce, sig

    def _req(self, method, path, body=None):
        for _ in range(len(HOSTS)):
            host = self._host()
            try:
                ts, nonce, sig = self._sign(method, path)
                hdr = {
                    "User-Agent": UA, "Accept":"application/json", "Referer":host + "/",
                    "x-ai-movie-timestamp":ts, "x-ai-movie-nonce":nonce,
                    "x-ai-movie-signature":sig,
                }
                hdr.update(CLIENT)
                if body is None:
                    r = requests.get(host + path, headers=hdr, timeout=10)
                else:
                    hdr['Content-Type'] = 'application/json'
                    r = requests.post(host + path, json=body, headers=hdr, timeout=10)
                if r.status_code in (200, 201):
                    return r.json()
            except Exception:
                pass
            self._hi = (self._hi + 1) % len(HOSTS)
        return {}

    @staticmethod
    def _vod(c):
        c = c or {}
        return {
            "vod_id": c.get("id", ""),
            "vod_name": c.get("title", ""),
            "vod_pic": c.get("poster_url", ""),
            "vod_remarks": c.get("remarks") or str(c.get("year") or ""),
            "vod_year": str(c.get("year") or ""),
            "vod_area": c.get("area") or "",
            "vod_class": "/".join((c.get("genres") or [])[:3]),
        }

    @staticmethod
    def _ext(extend):
        if isinstance(extend, dict): return extend
        out = {}
        for p in str(extend or '').split('&'):
            if '=' in p:
                k,v = p.split('=',1)
                out[urllib.parse.unquote(k)] = urllib.parse.unquote(v)
        return out

    def homeContent(self, filter=False):
        cls = [{"type_id":k,"type_name":v} for k,v in CATEGORIES.items()]
        filters = {}
        for k in CATEGORIES:
            filters[k] = [{
                "key":"genre", "name":"類型",
                "value":[{"n":"全部","v":""}] + [{"n":g,"v":g} for g in GENRES[k]]
            }]
        return {"class":cls,"filters":filters,"list":[]}

    def homeVideoContent(self):
        j = self._req('GET','/v1/feed/home')
        out, seen = [], set()
        for sec in j.get('sections') or []:
            for c in sec.get('cards') or []:
                v=self._vod(c)
                if v['vod_id'] and v['vod_id'] not in seen:
                    seen.add(v['vod_id']); out.append(v)
        for c in j.get('cards') or []:
            v=self._vod(c)
            if v['vod_id'] and v['vod_id'] not in seen:
                seen.add(v['vod_id']); out.append(v)
        return {'list':out}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try: page=max(1,int(pg or 1))
        except Exception: page=1
        kind = str(tid)
        if kind not in CATEGORIES: kind='movie'
        ext=self._ext(extend)
        path='/v1/browse/catalog?kind=%s&page=%d&limit=40' % (kind,page)
        if ext.get('genre'):
            path += '&genre=' + urllib.parse.quote(str(ext['genre']))
        j=self._req('GET',path)
        cards=j.get('cards') or []
        total=int((j.get('pagination') or {}).get('total') or len(cards))
        return {'list':[self._vod(c) for c in cards], 'page':page,
                'pagecount':max(1,int(math.ceil(total/40.0))), 'limit':40, 'total':total}

    def searchContent(self, key, quick=False, pg='1'):
        try: page=max(1,int(pg or 1))
        except Exception: page=1
        word=str(key or '').strip()
        if not word: return {'list':[]}
        path='/v1/browse/catalog?q=%s&page=%d&limit=20' % (urllib.parse.quote(word),page)
        j=self._req('GET',path)
        return {'list':[self._vod(c) for c in (j.get('cards') or [])], 'page':page}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key,quick,pg)

    def detailContent(self, ids):
        vid=str(ids[0] if isinstance(ids,(list,tuple)) else ids or '').split('/')[0]
        if not vid: return {'list':[]}
        d=self._req('GET','/v1/catalog/%s' % urllib.parse.quote(vid))
        if not d or d.get('error'): return {'list':[]}
        eps=d.get('episodes') or []
        eplist=[]
        for i,e in enumerate(eps,1):
            tok=e.get('token')
            if tok:
                eplist.append('%s$%s' % (e.get('title') or e.get('display_name') or ('第%d集'%i), tok))
        base='#'.join(eplist)
        play_from='看劇AI'
        play_url=base
        if eps and base:
            tok0=eps[0].get('token')
            if tok0:
                rj=self._req('GET','/v1/playback/resolve/%s' % urllib.parse.quote(str(tok0)))
                names=[]
                for lo in rj.get('line_options') or []:
                    n=lo.get('provider_name') or lo.get('label') or ''
                    if n and n not in names: names.append(n)
                    if len(names)>=10: break
                if names:
                    play_from='$$$'.join(names)
                    play_url='$$$'.join([base]*len(names))
        return {'list':[{
            'vod_id':vid, 'vod_name':d.get('title',''), 'vod_pic':d.get('poster_url',''),
            'vod_year':str(d.get('year') or ''), 'vod_area':d.get('area') or '',
            'vod_class':'/'.join((d.get('genres') or [])[:3]),
            'vod_director':'/'.join((d.get('directors') or [])[:2]),
            'vod_actor':'/'.join((d.get('actors') or [])[:3]),
            'vod_content':d.get('description') or '',
            'vod_remarks':d.get('remarks') or (('全%s集'%d.get('episode_count')) if d.get('episode_count') else ''),
            'vod_play_from':play_from, 'vod_play_url':play_url,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        tok=str(id or '').strip()
        if not tok: return {'parse':1,'url':''}
        rj=self._req('GET','/v1/playback/resolve/%s' % urllib.parse.quote(tok))
        lines=rj.get('line_options') or []
        ordered=[]
        if flag:
            ordered += [x for x in lines if (x.get('provider_name') or x.get('label') or '') == str(flag)]
        ordered += [x for x in lines if x not in ordered]
        for lo in ordered:
            u=str(lo.get('url') or '').strip()
            if u.startswith('resolve://'):
                rr=self._req('POST','/v1/playback/resolve-line', {'ticket':u[10:]})
                u=str((rr.get('line') or {}).get('url') or '').strip()
            if u.startswith('http'):
                direct=self.isVideoFormat(u)
                return {'parse':0 if direct else 1,'jx':0,'playUrl':'','url':u,
                        'header':{'User-Agent':UA,'Referer':self._host()+'/'}}
        # 現成來源的免費 m3u8 fallback。
        murl=YJ_M3U8 % tok
        try:
            rr=requests.get(murl,headers={'User-Agent':UA},timeout=6)
            if rr.status_code==200 and '#EXTM3U' in rr.text:
                return {'parse':0,'jx':0,'url':murl,'header':{'User-Agent':UA}}
        except Exception:
            pass
        return {'parse':1,'jx':1,'url':'','header':{'User-Agent':UA}}

    def localProxy(self, param): return None
