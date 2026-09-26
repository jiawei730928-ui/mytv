# -*- coding: utf-8 -*-
"""
熱門雷達 - WebHTV / FongMi T3 Python Spider
用途：只做「現在紅什麼」的榜單雷達，不負責播放。
資料來源：
- 短劇工程：紅果/抖音短劇日榜（真人劇、漫劇、AI短劇）
- Bilibili 公開 PGC 榜：國創
- 豆瓣 Frodo 公開榜：電影、劇集、國產劇、動畫、院線新片

點進作品只顯示資訊；使用者回到正式片源用原名搜尋播放。
"""
import sys, re, json, html, time, base64, hashlib, hmac
from urllib.parse import quote, urljoin

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

try:
    import requests
except Exception:
    requests = None

UA = "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

class Spider(Spider):
    def getName(self):
        return "🧭熱門雷達"

    def init(self, extend=""):
        self.h = {"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8"}
        self.cache = {}
        self.cache_ts = {}
        return self

    def destroy(self): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False

    # -------------------- 共用 --------------------
    def _get(self, url, headers=None, timeout=12):
        if not requests:
            return None
        h = dict(self.h)
        h.update(headers or {})
        try:
            return requests.get(url, headers=h, timeout=timeout, verify=False)
        except Exception:
            return None

    @staticmethod
    def _txt(s):
        s = html.unescape(str(s or ''))
        s = re.sub(r'<script\b[\s\S]*?</script>', ' ', s, flags=re.I)
        s = re.sub(r'<style\b[\s\S]*?</style>', ' ', s, flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _attr(tag, key):
        m = re.search(r'\b%s\s*=\s*(["\'])(.*?)\1' % re.escape(key), tag or '', re.I|re.S)
        return html.unescape(m.group(2).strip()) if m else ''

    def _cached(self, key, seconds, loader):
        now = time.time()
        if key in self.cache and now - self.cache_ts.get(key, 0) < seconds:
            return self.cache[key]
        try:
            v = loader()
            if v:
                self.cache[key] = v
                self.cache_ts[key] = now
                return v
        except Exception:
            pass
        return self.cache.get(key, [])

    def homeContent(self, filter=False):
        # 榜單雷達：只放有每天/近期更新資料的項目。
        classes = [
            {"type_id":"short_hot", "type_name":"🔥短劇熱播"},
            {"type_id":"short_new", "type_name":"🆕短劇新劇"},
            {"type_id":"short_search", "type_name":"🔎短劇熱搜"},
            {"type_id":"short_fav", "type_name":"❤️短劇收藏"},
            {"type_id":"short_rise", "type_name":"🚀今日飆升"},
            {"type_id":"short_today_new", "type_name":"✨今日新進榜"},
            {"type_id":"short_reserve", "type_name":"⏰短劇預約"},
            {"type_id":"short_manhua", "type_name":"📚漫劇熱播"},
            {"type_id":"short_manhua_new", "type_name":"📖漫劇新劇"},
            {"type_id":"short_ai", "type_name":"🤖AI短劇"},
            {"type_id":"guoman", "type_name":"🐉國漫熱榜"},
            {"type_id":"movie_hot", "type_name":"🎞️電影熱榜"},
            {"type_id":"movie_showing", "type_name":"🆕院線新片"},
            {"type_id":"tv_hot", "type_name":"📺劇集熱榜"},
            {"type_id":"tv_domestic", "type_name":"🇨🇳陸劇熱榜"},
            {"type_id":"animation", "type_name":"🌸動漫熱榜"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        # 首頁直接給「短劇總榜」前 30，打開源就能看到今天最熱。
        rows = self._duanju_baike('rebo.html')[:30]
        return {"list": rows}

    # -------------------- 短劇百科：熱播 / 新劇 / 熱搜 / 收藏 / 預約 / 漫劇 --------------------
    def _duanju_baike(self, page):
        def load():
            url = 'https://www.duanjubaike.net/paihang/' + page
            r = self._get(url, headers={"Referer":"https://www.duanjubaike.net/paihang/index.html"})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            text = r.text
            out, seen = [], set()
            # 排行榜卡片會連到 /duanju/info-xxxx.html；整張卡片文字已包含熱度/集數/片名。
            pats = list(re.finditer(r'<a\b([^>]*href\s*=\s*(["\'])([^"\']*/duanju/info-[^"\']+\.html)\2[^>]*)>([\s\S]*?)</a>', text, re.I))
            for m in pats:
                href = m.group(3)
                if href in seen:
                    continue
                block = m.group(4)
                clean = self._txt(block)
                if not clean:
                    continue
                im = re.search(r'<img\b([^>]*)>', block, re.I|re.S)
                pic = title = ''
                if im:
                    tag = im.group(1)
                    pic = self._attr(tag,'src') or self._attr(tag,'data-src') or self._attr(tag,'data-original')
                    alt = self._attr(tag,'alt')
                    mm = re.search(r'《(.+?)》', alt)
                    if mm: title = mm.group(1).strip()
                    elif alt:
                        title = re.sub(r'^(?:短劇|短剧|漫劇|漫剧)', '', alt)
                        title = re.sub(r'(?:海報|海报|封面)$', '', title).strip()
                # 卡片文字格式：短剧 6607万热度 全71集 片名 评分/收藏...
                if not title:
                    mm = re.search(
                        r'全\s*\d+\s*集\s+(.+?)(?=\s+(?:評分|评分|\d+(?:\.\d+)?\s*萬?收藏|\d+(?:\.\d+)?\s*万收藏|\d+\s*收藏|預告|预告|\d+(?:\.\d+)?\s*萬?人預約|\d+(?:\.\d+)?\s*万人预约|真人劇|真人剧|第\d+季))',
                        clean, re.I)
                    if mm: title = mm.group(1).strip()
                if not title:
                    continue
                metric = ''
                mm = re.search(r'(\d+(?:\.\d+)?)\s*万\s*(最高热度|熱度|热度|熱搜|热搜|收藏|預約|预约|期待)', clean)
                if mm:
                    lab = mm.group(2).replace('热度','熱度').replace('热搜','熱搜').replace('预约','預約')
                    metric = mm.group(1) + '萬' + lab
                ep = ''
                em = re.search(r'全\s*(\d+)\s*集', clean)
                if em and em.group(1) != '0': ep = '全%s集' % em.group(1)
                if pic.startswith('//'): pic='https:'+pic
                elif pic.startswith('/'): pic=urljoin(url,pic)
                rank = len(out)+1
                remark = '#%d' % rank
                if metric: remark += ' · ' + metric
                if ep: remark += ' · ' + ep
                seen.add(href)
                out.append({
                    'vod_id':'radar|short|%s|%s' % (quote(title,safe=''), quote(href,safe='')),
                    'vod_name':title, 'vod_pic':pic, 'vod_remarks':remark
                })
                if len(out) >= 100: break
            return out
        return self._cached('dbk_'+page, 1800, load)

    # -------------------- 短劇工程：每日 TOP100 --------------------
    def _short_rank(self, wanted='all'):
        def load():
            url = 'https://www.duanjugongcheng.com/cn/daily'
            r = self._get(url, headers={"Referer":"https://www.duanjugongcheng.com/cn/"})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            text = r.text
            out, seen = [], set()

            # 每一筆榜單作品都會連到 /cn/bangdan/ju/<slug>，從作品連結附近抽封面/題材/熱度。
            pats = list(re.finditer(r'<a\b([^>]*href\s*=\s*(["\'])(/cn/bangdan/ju/[^"\']+)\2[^>]*)>([\s\S]*?)</a>', text, re.I))
            for idx, m in enumerate(pats):
                href = m.group(3)
                if href in seen:
                    continue
                block = m.group(4)
                # 作品名：優先 img alt="xxx封面"，再用 a 文字。
                title = ''
                im = re.search(r'<img\b([^>]*)>', block, re.I|re.S)
                pic = ''
                if im:
                    tag = im.group(1)
                    alt = self._attr(tag, 'alt')
                    title = re.sub(r'封面$', '', alt).strip()
                    pic = self._attr(tag, 'src') or self._attr(tag, 'data-src') or self._attr(tag, 'data-original')
                if not title:
                    title = self._txt(block)
                title = re.sub(r'^(?:\d+\s*)+', '', title).strip()
                if not title or len(title) < 2:
                    continue

                # 取此 anchor 後方到下一作品前的少量 HTML，找「真人劇 / 漫劇 / AI短劇」與 xx萬。
                end = pats[idx+1].start() if idx+1 < len(pats) else min(len(text), m.end()+1200)
                tail = text[m.end():min(end, m.end()+1200)]
                around = block + tail
                kind = ''
                for k in ('AI短剧','AI短劇','漫剧','漫劇','真人剧','真人劇'):
                    if k in around:
                        kind = k.replace('剧','劇')
                        break
                heat = ''
                hm = re.search(r'(\d+(?:\.\d+)?)\s*万', self._txt(around))
                if hm:
                    heat = hm.group(1) + '萬'

                # 封面可能在 anchor 外層前方；往前看一小段補抓。
                if not pic:
                    pre = text[max(0, m.start()-650):m.start()]
                    ims = list(re.finditer(r'<img\b([^>]*)>', pre, re.I|re.S))
                    if ims:
                        tag = ims[-1].group(1)
                        pic = self._attr(tag, 'src') or self._attr(tag, 'data-src') or self._attr(tag, 'data-original')
                        if not title:
                            title = re.sub(r'封面$', '', self._attr(tag, 'alt')).strip()
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = urljoin(url, pic)

                seen.add(href)
                rank = len(out) + 1
                remark = '#%d' % rank
                if kind: remark += ' · ' + kind
                if heat: remark += ' · ' + heat
                out.append({
                    'vod_id':'radar|short|%s|%s' % (quote(title, safe=''), quote(href, safe='')),
                    'vod_name':title,
                    'vod_pic':pic,
                    'vod_remarks':remark,
                })
                if len(out) >= 100:
                    break
            return out

        all_rows = self._cached('short_all', 900, load)
        if wanted == 'all':
            return all_rows
        # 若載入時已包含類型，從 remarks 篩；避免每分類重新抓。
        kw = {'real':'真人劇','manhua':'漫劇','ai':'AI短劇'}.get(wanted, '')
        return [x for x in all_rows if kw and kw in x.get('vod_remarks','')]

    def _short_special(self, mode):
        # 短劇工程首頁直接標出「沖榜最快 / 今日新進榜」。
        # 只取作品 href，再用完整熱播榜補回封面與片名，避免自己猜名稱。
        def load():
            u='https://www.duanjugongcheng.com/cn/daily'
            r=self._get(u, headers={"Referer":"https://www.duanjugongcheng.com/cn/"})
            if not r or getattr(r,'status_code',0)!=200: return []
            t=r.text
            if mode=='rise': a,b='冲榜最快','今日新进榜'
            else: a,b='今日新进榜','今日跌出榜'
            ia=t.find(a); ib=t.find(b, ia+1) if ia>=0 else -1
            if ia<0 or ib<0: return []
            seg=t[ia:ib]
            hrefs=[]
            for m in re.finditer(r'href\s*=\s*(["\'])(/cn/bangdan/ju/[^"\']+)\1', seg, re.I):
                if m.group(2) not in hrefs: hrefs.append(m.group(2))
            # 建立當日榜 href -> 卡片。
            rows=self._short_rank('all')
            mp={}
            for x in rows:
                try:
                    from urllib.parse import unquote
                    raw=unquote(str(x.get('vod_id','')).split('|',3)[3])
                    mp[raw]=x
                except Exception: pass
            out=[]
            for h in hrefs:
                if h in mp:
                    y=dict(mp[h]); y['vod_remarks']=('#%d · '%(len(out)+1)) + ('今日飆升' if mode=='rise' else '今日新進') + ' · ' + re.sub(r'^#\d+\s*·?\s*','',y.get('vod_remarks',''))
                    out.append(y)
            return out
        return self._cached('short_special_'+mode, 900, load)

    # -------------------- Bilibili：國創排行榜 --------------------
    def _guoman_rank(self):
        def load():
            u = 'https://api.bilibili.com/pgc/season/rank/web/list?day=3&season_type=4'
            r = self._get(u, headers={"Referer":"https://www.bilibili.com/v/popular/rank/guochuang"})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            try: j = r.json()
            except Exception: return []
            data = j.get('result') or j.get('data') or {}
            rows = data.get('list') or data.get('items') or []
            out = []
            for i, x in enumerate(rows, 1):
                title = str(x.get('title') or x.get('name') or '').strip()
                if not title: continue
                pic = x.get('cover') or x.get('square_cover') or ''
                ep = ((x.get('new_ep') or {}).get('index_show') or x.get('new_ep_index') or '')
                view = ((x.get('stat') or {}).get('view') or '')
                remark = '#%d' % i
                if ep: remark += ' · ' + str(ep)
                if view:
                    try:
                        n = int(view)
                        if n >= 10000: remark += ' · %.1f萬播放' % (n/10000.0)
                    except Exception: pass
                sid = str(x.get('season_id') or x.get('media_id') or i)
                out.append({'vod_id':'radar|guoman|%s|%s'%(quote(title,safe=''),sid), 'vod_name':title, 'vod_pic':pic, 'vod_remarks':remark})
            return out
        return self._cached('guoman', 1800, load)

    # -------------------- 豆瓣：電影 / 劇集 / 動畫 --------------------
    @staticmethod
    def _douban_sign(path, ts):
        # 豆瓣 Frodo 現成公開客戶端簽名方式。
        secret = b'bf7dddc7c9cfe6f7'
        full = 'https://frodo.douban.com/api/v2' + path
        from urllib.parse import urlparse, quote as q
        url_path = urlparse(full).path
        raw = '&'.join(['GET', q(url_path, safe=''), str(ts)])
        return base64.b64encode(hmac.new(secret, raw.encode(), hashlib.sha1).digest()).decode()

    def _douban(self, collection):
        def load():
            path = '/subject_collection/%s/items' % collection
            ts = time.strftime('%Y%m%d')
            params = {
                'start':'0','count':'40','os_rom':'android',
                'apiKey':'0dad551ec0f84ed02907ff5c42e8ec70',
                '_ts':ts, '_sig':self._douban_sign(path, ts)
            }
            qs = '&'.join('%s=%s'%(quote(str(k),safe=''), quote(str(v),safe='')) for k,v in params.items())
            u = 'https://frodo.douban.com/api/v2' + path + '?' + qs
            hdr = {
                'User-Agent':'api-client/1 com.douban.frodo/7.22.0(231) Android/23 product/Mate40 vendor/HUAWEI model/Mate40 platform/mobile',
                'Referer':'https://m.douban.com/'
            }
            r = self._get(u, headers=hdr)
            if not r or getattr(r, 'status_code', 0) != 200:
                # 簡單備援：m.douban rexxar（部分網路環境可直接用）
                u2 = 'https://m.douban.com/rexxar/api/v2/subject_collection/%s/items?start=0&count=40&for_mobile=1' % collection
                r = self._get(u2, headers={'Referer':'https://m.douban.com/'})
                if not r or getattr(r, 'status_code', 0) != 200:
                    return []
            try: j = r.json()
            except Exception: return []
            rows = j.get('subject_collection_items') or j.get('items') or []
            out=[]
            for i,x in enumerate(rows,1):
                title=str(x.get('title') or x.get('name') or '').strip()
                if not title: continue
                pic=x.get('pic') or {}
                if isinstance(pic,dict):
                    cover=pic.get('large') or pic.get('normal') or pic.get('small') or ''
                else: cover=str(pic or '')
                rating=x.get('rating') or {}
                score=rating.get('value') if isinstance(rating,dict) else ''
                sub=x.get('card_subtitle') or x.get('subtitle') or ''
                remark='#%d'%i
                if score not in ('',None,0,'0'): remark+=' · %s分'%score
                elif sub: remark+=' · '+str(sub)[:18]
                did=str(x.get('id') or i)
                out.append({'vod_id':'radar|douban|%s|%s'%(quote(title,safe=''),did), 'vod_name':title, 'vod_pic':cover, 'vod_remarks':remark})
            return out
        return self._cached('db_'+collection, 1800, load)

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try: page=max(1,int(pg or 1))
        except Exception: page=1
        # 這些榜單本身就是前 40/100 名；第一頁已足夠當雷達。
        if page > 1:
            return {'list':[], 'page':page, 'pagecount':1, 'limit':0, 'total':0}
        tid=str(tid)
        if tid=='short_hot': rows=self._duanju_baike('rebo.html')
        elif tid=='short_new': rows=self._duanju_baike('xinju.html')
        elif tid=='short_search': rows=self._duanju_baike('reso.html')
        elif tid=='short_fav': rows=self._duanju_baike('shoucang.html')
        elif tid=='short_reserve': rows=self._duanju_baike('yuyue.html')
        elif tid=='short_manhua': rows=self._duanju_baike('manjurebo.html')
        elif tid=='short_manhua_new': rows=self._duanju_baike('manjuxinju.html')
        elif tid=='short_rise': rows=self._short_special('rise')
        elif tid=='short_today_new': rows=self._short_special('new')
        elif tid=='short_ai': rows=self._short_rank('ai')
        elif tid=='guoman': rows=self._guoman_rank()
        elif tid=='movie_hot': rows=self._douban('movie_hot_gaia')
        elif tid=='movie_showing': rows=self._douban('movie_showing')
        elif tid=='tv_hot': rows=self._douban('tv_hot')
        elif tid=='tv_domestic': rows=self._douban('tv_domestic')
        elif tid=='animation': rows=self._douban('tv_animation')
        else: rows=[]
        return {'list':rows, 'page':1, 'pagecount':1, 'limit':len(rows), 'total':len(rows)}

    # 雷達不做站內搜尋；避免它被全域搜尋當成播放源。
    def searchContent(self, key, quick=False, pg='1'):
        return {'list':[]}

    def searchContentPage(self, key, quick=False, pg='1'):
        return {'list':[]}

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids,(list,tuple)) else ids or '')
        parts = raw.split('|')
        if len(parts) < 4:
            return {'list':[]}
        from urllib.parse import unquote
        title = unquote(parts[2])
        src = parts[1]
        label = {'short':'短劇榜單','guoman':'國漫榜單','douban':'影視榜單'}.get(src,'熱門榜單')
        return {'list':[{
            'vod_id':raw,
            'vod_name':title,
            'vod_content':'%s收錄。這條「熱門雷達」只負責告訴你現在紅什麼；請用「%s」回正式片源搜尋播放。' % (label, title),
            'vod_play_from':'熱門雷達',
            'vod_play_url':'回正式片源搜尋$radar_none',
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        # 故意不提供假播放網址。
        return {'parse':1, 'jx':0, 'url':''}

    def localProxy(self, param): return None
