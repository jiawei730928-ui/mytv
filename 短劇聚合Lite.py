# -*- coding: utf-8 -*-
"""
短劇聚合 Lite - WebHTV / FongMi T3
從 2026-09 現成「短劇聚合2」收斂成較乾淨的 4 平台：
七貓 / 星芽 / 圍觀 / 河馬。
目的：一條源補多個短劇庫，同時把河馬全域搜尋換成新版 SEO API。
"""
import sys, re, json, base64, hashlib, time, random
from urllib.parse import quote, unquote
import requests
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

class Spider(Spider):
    def __init__(self):
        self.keys='d3dGiJc651gSQ8w1'
        self.char_map={
            '+':'P','/':'X','0':'M','1':'U','2':'l','3':'E','4':'r','5':'Y','6':'W','7':'b','8':'d','9':'J',
            'A':'9','B':'s','C':'a','D':'I','E':'0','F':'o','G':'y','H':'_','I':'H','J':'G','K':'i','L':'t','M':'g','N':'N','O':'A','P':'8','Q':'F','R':'k','S':'3','T':'h','U':'f','V':'R','W':'q','X':'C','Y':'4','Z':'p',
            'a':'m','b':'B','c':'O','d':'u','e':'c','f':'6','g':'K','h':'x','i':'5','j':'T','k':'-','l':'2','m':'z','n':'S','o':'Z','p':'1','q':'V','r':'v','s':'j','t':'Q','u':'7','v':'D','w':'w','x':'n','y':'L','z':'e'
        }
        self.hdef={'User-Agent':'okhttp/3.12.11','content-type':'application/json; charset=utf-8'}
        self.platform={
            '七猫':{'host':'https://api-store.qmplaylet.com','url1':'/api/v1/playlet/index','url2':'https://api-read.qmplaylet.com/player/api/v1/playlet/info','search':'/api/v1/playlet/search'},
            '星芽':{'host':'https://app.whjzjx.cn','url1':'/cloud/v2/theater/home_page?theater_class_id','url2':'/v2/theater_parent/detail','search':'/v3/search','login':'https://u.shytkjgs.com/user/v1/account/login'},
            '围观':{'host':'https://api.drama.9ddm.com','search':'/drama/home/search','detail':'/drama/home/shortVideoDetail'},
            '河马':{'host':'https://www.kuaikaw.cn','search':'/seo/video/6007'},
        }
        self.qm_cache=None; self.qm_time=0
        self.xy_headers=dict(self.hdef)

    def init(self, extend=''): return self
    def getName(self): return '🎭短劇聚合Lite'
    def isVideoFormat(self,url): return bool(re.search(r'\.(?:mp4|m3u8)(?:\?|$)',str(url or ''),re.I))
    def manualVideoCheck(self): return False
    def destroy(self): pass

    @staticmethod
    def _md5(s): return hashlib.md5(str(s).encode()).hexdigest().lower()
    @staticmethod
    def _b64e(s): return base64.b64encode(str(s).encode()).decode()
    @staticmethod
    def _b64d(s):
        try: return base64.b64decode(str(s)+'='*(-len(str(s))%4)).decode('utf-8','ignore')
        except Exception: return str(s)

    def _request(self,url,method='GET',headers=None,data=None,timeout=10):
        try:
            h=dict(self.hdef); h.update(headers or {})
            if method.upper()=='POST': r=requests.post(url,headers=h,json=data,timeout=timeout,verify=False)
            else: r=requests.get(url,headers=h,timeout=timeout,verify=False)
            return r.json()
        except Exception: return {}

    def _qm_headers(self):
        now=int(time.time()*1000)
        if self.qm_cache and now-self.qm_time<300000: return self.qm_cache
        data={
            'static_score':'0.8','uuid':'00000000-7fc7-08dc-0000-000000000000',
            'device-id':'20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70',
            'sourceuid':'aa7de295aad621a6','refresh-type':'0','model':'22021211RC',
            'client-id':'aa7de295aad621a6','brand':'Redmi','sys-ver':'12','phone-level':'H',
            'wlb-uid':'aa7de295aad621a6','session-id':str(now)
        }
        enc=base64.b64encode(json.dumps(data,separators=(',',':')).encode()).decode()
        qm=''.join(self.char_map.get(c,c) for c in enc)
        raw='AUTHORIZATION=app-version=10001application-id=com.duoduo.readchannel=unknownis-white=net-env=5platform=androidqm-params=%sreg=%s'%(qm,self.keys)
        sign=self._md5(raw)
        self.qm_cache={
            'net-env':'5','reg':'','channel':'unknown','is-white':'','platform':'android',
            'application-id':'com.duoduo.read','authorization':'','app-version':'10001',
            'user-agent':'webviewversion/0','qm-params':qm,'sign':sign
        }
        self.qm_time=now
        return self.qm_cache

    def _xy_auth(self):
        if self.xy_headers.get('authorization'): return self.xy_headers
        try:
            r=requests.post(self.platform['星芽']['login'],headers={
                'User-Agent':'okhttp/4.10.0','platform':'1','Content-Type':'application/json'
            },json={'device':'24250683a3bdb3f118dff25ba4b1cba1a'},timeout=10,verify=False)
            token=(r.json().get('data') or {}).get('token')
            if token: self.xy_headers={**self.hdef,'authorization':token}
        except Exception: pass
        return self.xy_headers

    @staticmethod
    def _ext(extend):
        if isinstance(extend,dict): return extend
        try:
            d=json.loads(str(extend or ''))
            return d if isinstance(d,dict) else {}
        except Exception: return {}

    def homeContent(self,filter=False):
        classes=[
            {'type_id':'七猫','type_name':'七貓短劇'},
            {'type_id':'星芽','type_name':'星芽短劇'},
            {'type_id':'围观','type_name':'圍觀短劇'},
            {'type_id':'河马','type_name':'河馬短劇'},
        ]
        filters={
            '七猫':[{'key':'area','name':'分類','value':[{'n':'全部','v':'0'},{'n':'男頻','v':'1'},{'n':'新劇','v':'3'},{'n':'現代言情','v':'21'},{'n':'穿越','v':'373'},{'n':'戰神','v':'527'},{'n':'古裝','v':'1272'}]}],
            '星芽':[{'key':'area','name':'劇場','value':[{'n':'劇場','v':'1'},{'n':'熱播','v':'2'},{'n':'新劇','v':'3'},{'n':'星選','v':'7'}]},
                    {'key':'class2','name':'類型','value':[{'n':'全部','v':'0'},{'n':'都市','v':'4'},{'n':'逆襲','v':'7'},{'n':'古裝','v':'5'},{'n':'現代言情','v':'15'},{'n':'重生','v':'6'},{'n':'玄幻','v':'35'},{'n':'穿越','v':'17'},{'n':'腦洞','v':'32'},{'n':'甜寵','v':'33'}]}],
            '围观':[{'key':'area','name':'分類','value':[{'n':'全部','v':''},{'n':'都市','v':'都市'},{'n':'逆襲','v':'逆袭'},{'n':'家庭','v':'家庭'},{'n':'古裝','v':'古装'},{'n':'甜寵','v':'甜宠'},{'n':'懸疑','v':'悬疑'},{'n':'穿越','v':'穿越'}]}],
            '河马':[{'key':'area','name':'分類','value':[{'n':'甜寵','v':'462'},{'n':'古裝仙俠','v':'1102'},{'n':'現代言情','v':'1145'},{'n':'逆襲','v':'417-464'},{'n':'重生','v':'439-465'},{'n':'系統','v':'1159'},{'n':'總裁','v':'1147'}]}],
        }
        return {'class':classes,'filters':filters}

    def homeVideoContent(self): return self.categoryContent('七猫','1',False,{})

    def _wg_url(self,path):
        ci=self._md5(str(int(time.time()*1000))[-10:])
        return (self.platform['围观']['host']+path+
            '?version_code=1500&version_name=1.5.0&device_name=Pixel%208%20Pro&device_type=phone'
            '&is_first_day=true&is_first_24h=true&app_launch_way=icon&default_homepage=homepage_interaction'
            '&device_owning_firm=Google&font_scale=default&os_type=1&clientInfo='+ci)

    def categoryContent(self,tid,pg,filter=False,extend=None):
        try: page=max(1,int(pg or 1))
        except Exception: page=1
        ext=self._ext(extend); area=ext.get('area')
        out=[]
        try:
            if tid=='七猫':
                if page>1: return {'list':[],'page':page,'pagecount':1}
                area='0' if area is None else str(area)
                sign=self._md5('operation=1playlet_privacy=1tag_id=%s%s'%(area,self.keys))
                p=self.platform['七猫']; u='%s%s?tag_id=%s&playlet_privacy=1&operation=1&sign=%s'%(p['host'],p['url1'],area,sign)
                j=self._request(u,headers=self._qm_headers(),timeout=6)
                for x in ((j.get('data') or {}).get('list') or []):
                    out.append({'vod_id':'七猫@'+quote(str(x.get('playlet_id',''))),'vod_name':x.get('title',''),'vod_pic':x.get('image_link',''),'vod_remarks':'%s集'%x.get('total_episode_num','')})
                return {'list':out,'page':page,'pagecount':1,'limit':len(out),'total':len(out)}

            if tid=='星芽':
                area=str(area if area is not None else '1'); c2=str(ext.get('class2') or '0')
                p=self.platform['星芽']; u='%s%s=%s&type=1&class2_ids=%s&page_num=%s&page_size=24'%(p['host'],p['url1'],area,c2,page)
                j=self._request(u,headers=self._xy_auth(),timeout=10); data=j.get('data') or {}
                for z in data.get('list') or []:
                    x=z.get('theater') or z
                    if x.get('id'):
                        out.append({'vod_id':'星芽@%s%s?theater_parent_id=%s'%(p['host'],p['url2'],x['id']),'vod_name':x.get('title',''),'vod_pic':x.get('cover_url',''),'vod_remarks':'%s集'%x.get('total','')})
                total=int(data.get('total') or len(out)); pc=max(1,(total+23)//24)
                return {'list':out,'page':page,'pagecount':pc,'limit':24,'total':total}

            if tid=='围观':
                body={'audience':'全部','order':'最新','page':page,'pageSize':30,'searchWord':'','subject':area or ''}
                j=self._request(self._wg_url(self.platform['围观']['search']),method='POST',headers={'User-Agent':'okhttp/5.1.0','Content-Type':'application/json; charset=utf-8'},data=body,timeout=10)
                for x in j.get('data') or []:
                    out.append({'vod_id':'围观@'+str(x.get('oneId','')),'vod_name':x.get('title',''),'vod_pic':x.get('horzPoster') or x.get('vertPoster') or '','vod_remarks':'%s集'%x.get('episodeCount','')})
                return {'list':out,'page':page,'pagecount':page+(1 if len(out)>=30 else 0),'limit':30,'total':(page-1)*30+len(out)}

            if tid=='河马':
                area=str(area or '462'); host=self.platform['河马']['host']; u='%s/browse/%s/%s'%(host,area,page)
                h={'User-Agent':'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/126 Safari/537.36','Referer':u}
                html=requests.get(u,headers=h,timeout=10,verify=False).text
                m=re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S)
                pp=(json.loads(m.group(1)).get('props') or {}).get('pageProps') if m else {}
                pp=pp or {}
                for x in pp.get('bookList') or []:
                    if x.get('bookId'):
                        out.append({'vod_id':'河马@/drama/'+str(x['bookId']),'vod_name':x.get('bookName',''),'vod_pic':x.get('coverWap',''),'vod_remarks':('%s %s集'%(x.get('statusDesc',''),x.get('totalChapterNum',''))).strip()})
                pages=int(pp.get('pages') or page)
                return {'list':out,'page':page,'pagecount':pages,'limit':len(out) or 20,'total':pages*(len(out) or 20)}
        except Exception: pass
        return {'list':out,'page':page,'pagecount':1,'limit':len(out),'total':len(out)}

    def searchContent(self,key,quick=False,pg='1'):
        try: page=max(1,int(pg or 1))
        except Exception: page=1
        word=str(key or '').strip(); out=[]; seen=set()
        if not word: return {'list':[]}
        def push(v):
            i=str(v.get('vod_id') or '')
            if i and v.get('vod_name') and i not in seen: seen.add(i); out.append(v)

        # 七猫
        try:
            p=self.platform['七猫']; sign=self._md5('operation=2playlet_privacy=1search_word=%s%s'%(word,self.keys))
            u='%s%s?search_word=%s&playlet_privacy=1&operation=2&sign=%s'%(p['host'],p['search'],quote(word),sign)
            j=self._request(u,headers=self._qm_headers(),timeout=6)
            for x in ((j.get('data') or {}).get('list') or []):
                push({'vod_id':'七猫@'+quote(str(x.get('playlet_id',''))),'vod_name':x.get('title',''),'vod_pic':x.get('image_link',''),'vod_remarks':'七貓｜%s集'%x.get('total_episode_num','')})
        except Exception: pass
        # 星芽
        try:
            p=self.platform['星芽']; j=self._request(p['host']+p['search'],method='POST',headers=self._xy_auth(),data={'text':word},timeout=10)
            d=j.get('data') or {}; rows=((d.get('theater') or {}).get('search_data') or d.get('search_data') or d.get('list') or [])
            for x in rows:
                if x.get('id'): push({'vod_id':'星芽@%s%s?theater_parent_id=%s'%(p['host'],p['url2'],x['id']),'vod_name':x.get('title',''),'vod_pic':x.get('cover_url',''),'vod_remarks':'星芽｜%s集'%x.get('total','')})
        except Exception: pass
        # 围观
        try:
            body={'audience':'','order':'','page':page,'pageSize':30,'searchWord':word,'subject':''}
            j=self._request(self._wg_url(self.platform['围观']['search']),method='POST',headers={'User-Agent':'okhttp/5.1.0','Content-Type':'application/json; charset=utf-8'},data=body,timeout=10)
            for x in j.get('data') or []:
                push({'vod_id':'围观@'+str(x.get('oneId','')),'vod_name':x.get('title',''),'vod_pic':x.get('horzPoster') or x.get('vertPoster') or '','vod_remarks':'圍觀｜%s集'%x.get('episodeCount','')})
        except Exception: pass
        # 河马新版搜索 API
        try:
            p=self.platform['河马']; tmp=''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz',k=16))
            h={'User-Agent':'Mozilla/5.0','Referer':p['host']+'/search?searchValue='+quote(word),'Origin':p['host'],'Content-Type':'application/json','Accept':'application/json, text/plain, */*','pname':'www.kuaikaw.cn','tmpid':tmp}
            j=self._request(p['host']+p['search'],method='POST',headers=h,data={'sourceType':1,'keyword':word,'index':page,'page':page},timeout=10)
            for x in ((j.get('data') or {}).get('bookList') or []):
                if x.get('bookId'): push({'vod_id':'河马@/drama/'+str(x['bookId']),'vod_name':x.get('bookName',''),'vod_pic':x.get('coverWap',''),'vod_remarks':('%s %s集'%(x.get('statusDesc',''),x.get('totalChapterNum',''))).strip()})
        except Exception: pass
        return {'list':out,'page':page,'pagecount':1,'limit':len(out),'total':len(out)}

    def searchContentPage(self,key,quick=False,pg='1'): return self.searchContent(key,quick,pg)

    def detailContent(self,ids):
        raw=str(ids[0] if isinstance(ids,(list,tuple)) else ids or '')
        if '@' not in raw: return {'list':[]}
        plat,did=raw.split('@',1); vod={'vod_id':raw,'vod_name':'','vod_pic':'','vod_content':'','vod_remarks':'','vod_play_from':'','vod_play_url':''}
        try:
            if plat=='七猫':
                rid=unquote(did); p=self.platform['七猫']; sign=self._md5('playlet_id=%s%s'%(rid,self.keys))
                j=self._request('%s?playlet_id=%s&sign=%s'%(p['url2'],rid,sign),headers=self._qm_headers()); d=j.get('data') or {}
                eps=['%s$%s'%(x.get('sort',''),x.get('video_url','')) for x in d.get('play_list') or [] if x.get('video_url')]
                vod.update({'vod_name':d.get('title',''),'vod_pic':d.get('image_link',''),'vod_content':d.get('intro',''),'vod_remarks':'%s集'%d.get('total_episode_num',''),'vod_play_from':'七貓短劇','vod_play_url':'#'.join(eps)})
            elif plat=='星芽':
                j=self._request(did,headers=self._xy_auth(),timeout=10); d=j.get('data') or {}
                eps=['%s$%s'%(x.get('num',''),x.get('son_video_url','')) for x in d.get('theaters') or [] if x.get('son_video_url')]
                vod.update({'vod_name':d.get('title',''),'vod_pic':d.get('cover_url',''),'vod_remarks':str(d.get('desc_tags','')),'vod_play_from':'星芽短劇','vod_play_url':'#'.join(eps)})
            elif plat=='围观':
                p=self.platform['围观']; u=self._wg_url(p['detail'])+'&oneId=%s&page=1&pageSize=1000&userId=0&queryAll=true'%quote(did)
                j=self._request(u,headers={'User-Agent':'okhttp/5.1.0','Content-Type':'application/json; charset=utf-8'},timeout=10); rows=j.get('data') or []
                eps=[]
                for x in rows:
                    cl=x.get('videoClarityList') or []
                    eps.append('%s$%s'%(x.get('playOrder') or x.get('title') or len(eps)+1,self._b64e(json.dumps(cl,ensure_ascii=False))))
                vod.update({'vod_name':j.get('title') or (rows[0].get('title') if rows else ''),'vod_pic':j.get('vertPoster') or (rows[0].get('vertPoster') if rows else ''),'vod_content':j.get('description',''),'vod_remarks':'共%s集'%len(rows),'vod_play_from':'圍觀短劇','vod_play_url':'#'.join(eps)})
            elif plat=='河马':
                p=self.platform['河马']; path=did if did.startswith('/drama/') else '/drama/'+did; full=p['host']+path
                h={'User-Agent':'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/126 Safari/537.36','Referer':full}
                html=requests.get(full,headers=h,timeout=10,verify=False).text
                m=re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S); pp=(json.loads(m.group(1)).get('props') or {}).get('pageProps') if m else {}; pp=pp or {}
                b=pp.get('bookInfoVo') or {}; eps=[]
                for i,x in enumerate(pp.get('chapterList') or [],1):
                    cid=str(x.get('chapterId') or ''); n=x.get('chapterName') or '第%s集'%i; vv=x.get('chapterVideoVo') or {}; u=vv.get('mp4') or vv.get('mp4720p') or vv.get('vodMp4Url')
                    if u and self.isVideoFormat(u): eps.append('%s$%s'%(n,u))
                    elif cid: eps.append('%s$%s+%s'%(n,path.replace('/drama/',''),cid))
                vod.update({'vod_name':b.get('title') or b.get('bookName') or '','vod_pic':b.get('coverWap',''),'vod_content':b.get('introduction',''),'vod_remarks':('%s %s集'%(b.get('statusDesc',''),b.get('totalChapterNum',''))).strip(),'vod_play_from':'河馬短劇','vod_play_url':'#'.join(eps)})
        except Exception: return {'list':[]}
        return {'list':[vod] if vod.get('vod_name') and vod.get('vod_play_url') else []}

    def playerContent(self,flag,id,vipFlags=None):
        raw=str(id or '')
        if self.isVideoFormat(raw): return {'parse':0,'jx':0,'url':raw}
        if '圍觀' in str(flag) or '围观' in str(flag):
            try:
                arr=json.loads(self._b64d(raw)); best=''
                # 優先 1080/超清，否則第一條 URL。
                for x in arr:
                    n=str(x.get('name') or x.get('quality') or '').lower(); u=x.get('url') or ''
                    if u and not best: best=u
                    if u and ('1080' in n or '超清' in n or 'super' in n): best=u; break
                return {'parse':0,'jx':0,'url':best or raw,'header':{'User-Agent':'okhttp/5.1.0'}}
            except Exception: return {'parse':0,'url':raw}
        if '河馬' in str(flag) or '河马' in str(flag):
            if '+' in raw:
                drama,cid=raw.split('+',1); u='%s/episode/%s/%s'%(self.platform['河马']['host'],drama,cid); h={'User-Agent':'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/126 Safari/537.36','Referer':u}
                try:
                    html=requests.get(u,headers=h,timeout=10,verify=False).text
                    m=re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S); pp=(json.loads(m.group(1)).get('props') or {}).get('pageProps') if m else {}; cv=((pp or {}).get('chapterInfo') or {}).get('chapterVideoVo') or {}; play=cv.get('mp4') or cv.get('mp4720p') or cv.get('vodMp4Url')
                    if not play:
                        mm=re.search(r'https?://[^"\'\\\s]+?\.mp4(?:\?[^"\'\\\s]*)?',html); play=mm.group(0) if mm else ''
                    if play: return {'parse':0,'jx':0,'url':play,'header':h}
                except Exception: pass
        return {'parse':0,'jx':0,'url':raw}

    def localProxy(self,param): return None
