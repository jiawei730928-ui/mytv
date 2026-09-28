# -*- coding: utf-8 -*-
"""
七貓 - WebHTV / FongMi T3 Python Spider
2026-09-28 研究候選版

兩個分類：
- 七貓短劇：沿用已公開驗證的 qmplaylet API / 簽名邏輯
- 七貓漫劇：依七貓漫劇 1.0.3 APK 實際接口與攔截器邏輯重建

七貓漫劇已由 APK 確認：
- api-store.qmmanju.com / api-read.qmmanju.com
- /api/v1/playlet/index
- /api/v1/playlet/detail
- /api/v1/playlet/search
- /api/v1/playlet/sort-list
- /player/api/v1/playlet/info
- /player/api/v1/playlet/next
- application-id=com.td.freader, app-version=10003
- qm-params = JSON -> Base64 -> 七貓字元替換
- sign = MD5(待簽字串 + d3dGiJc651gSQ8w1)
"""
import sys, re, json, base64, hashlib, time, random
from urllib.parse import quote, unquote, urlencode

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider: pass

try:
    import requests
except Exception:
    requests = None


KEY = 'd3dGiJc651gSQ8w1'
CHAR_MAP = {
    '+':'P','/':'X','0':'M','1':'U','2':'l','3':'E','4':'r','5':'Y','6':'W','7':'b','8':'d','9':'J',
    'A':'9','B':'s','C':'a','D':'I','E':'0','F':'o','G':'y','H':'_','I':'H','J':'G','K':'i','L':'t','M':'g','N':'N','O':'A','P':'8','Q':'F','R':'k','S':'3','T':'h','U':'f','V':'R','W':'q','X':'C','Y':'4','Z':'p',
    'a':'m','b':'B','c':'O','d':'u','e':'c','f':'6','g':'K','h':'x','i':'5','j':'T','k':'-','l':'2','m':'z','n':'S','o':'Z','p':'1','q':'V','r':'v','s':'j','t':'Q','u':'7','v':'D','w':'w','x':'n','y':'L','z':'e'
}

SHORT_STORE = 'https://api-store.qmplaylet.com'
SHORT_READ = 'https://api-read.qmplaylet.com'
MANJU_STORE = 'https://api-store.qmmanju.com'
MANJU_READ = 'https://api-read.qmmanju.com'


class Spider(Spider):
    def __init__(self):
        self.cache = {}
        self.cache_ts = {}

    def getName(self):
        return '🐱七貓'

    def init(self, extend=''):
        return self

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv|mkv|ts|mpd)(?:[?#]|$)', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    @staticmethod
    def _md5(s):
        return hashlib.md5(str(s).encode('utf-8')).hexdigest().lower()

    @staticmethod
    def _clean_title(s):
        return re.sub(r'<[^>]+>', '', str(s or '')).strip()

    def _request(self, url, method='GET', headers=None, data=None, timeout=10):
        if not requests:
            return {}
        try:
            if method.upper() == 'POST':
                # 七貓漫劇 custom RequestBody 是 application/x-www-form-urlencoded
                r = requests.post(url, headers=headers or {}, data=data or {}, timeout=timeout, verify=False)
            else:
                r = requests.get(url, headers=headers or {}, timeout=timeout, verify=False)
            if getattr(r, 'status_code', 0) != 200:
                return {}
            return r.json()
        except Exception:
            return {}

    # ---------------- 七貓共同簽名 ----------------
    def _qm_encode(self, data):
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        b64 = base64.b64encode(raw.encode('utf-8')).decode('ascii')
        return ''.join(CHAR_MAP.get(c, c) for c in b64)

    def _headers(self, kind='short', extra_qm=None):
        now = int(time.time() * 1000)
        if kind == 'manju':
            app_version = '10003'
            app_id = 'com.td.freader'
        else:
            app_version = '10001'
            app_id = 'com.duoduo.read'

        # APK gf.E(Map) 實際包含這些欄位；採匿名裝置固定值避免每次刷新身份。
        qm_data = {
            'static_score': '0.8',
            'uuid': '00000000-7fc7-08dc-0000-000000000000',
            'device-id': '20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70',
            'mac': '',
            'sourceuid': 'aa7de295aad621a6',
            'model': '22021211RC',
            'wlb-imei': '',
            'client-id': 'aa7de295aad621a6',
            'brand': 'Redmi',
            'oaid': '',
            'oaid-no-cache': '',
            'sys-ver': '12',
            'trusted-id': '',
            'phone-level': 'H',
            'imei': '',
            'wlb-uid': 'aa7de295aad621a6',
            'session-id': str(now),
        }
        if extra_qm:
            qm_data.update({str(k): str(v) for k, v in extra_qm.items()})
        qm = self._qm_encode(qm_data)

        # HeaderInterceptor 以 Map key 排序後 key=value 直接串接，再走 Security.sign。
        base = {
            'AUTHORIZATION': '',
            'app-version': app_version,
            'application-id': app_id,
            'channel': 'unknown',
            'is-white': '',
            'net-env': '5',
            'platform': 'android',
            'qm-params': qm,
            'reg': '',
        }
        sign_raw = ''.join('%s=%s' % (k, base[k]) for k in sorted(base.keys()))
        sign = self._md5(sign_raw + KEY)
        h = dict(base)
        h['sign'] = sign
        h['User-Agent'] = 'webviewversion/0'
        h['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        return h

    def _signed_form(self, params):
        """七貓漫劇 Lcj2：TreeMap key=value 串接後 Security.sign，再附 sign 欄位。"""
        p = {str(k): '' if v is None else str(v) for k, v in (params or {}).items()}
        raw = ''.join('%s=%s' % (k, p[k]) for k in sorted(p.keys()))
        p['sign'] = self._md5(raw + KEY)
        return p

    # ---------------- 七貓短劇（已知現成邏輯） ----------------
    def _short_index(self, tag='0', page=1):
        tag = str(tag or '0')
        if page <= 1:
            raw = 'operation=1playlet_privacy=1tag_id=%s%s' % (tag, KEY)
            sign = self._md5(raw)
            u = '%s/api/v1/playlet/index?tag_id=%s&playlet_privacy=1&operation=1&sign=%s' % (
                SHORT_STORE, quote(tag), sign)
        else:
            raw = 'next_id=%soperation=1playlet_privacy=1tag_id=%s%s' % (page, tag, KEY)
            sign = self._md5(raw)
            u = '%s/api/v1/playlet/index?tag_id=%s&next_id=%s&playlet_privacy=1&operation=1&sign=%s' % (
                SHORT_STORE, quote(tag), page, sign)
        return self._request(u, headers=self._headers('short'))

    def _short_search(self, word, page=1):
        track = 'ec1280db127955061754851657967'
        raw = 'extend=page=%sread_preference=0track_id=%swd=%s%s' % (page, track, word, KEY)
        sign = self._md5(raw)
        u = '%s/api/v1/playlet/search?extend=&page=%s&wd=%s&read_preference=0&track_id=%s&sign=%s' % (
            SHORT_STORE, page, quote(word), track, sign)
        return self._request(u, headers=self._headers('short'))

    def _short_info(self, pid):
        raw = 'playlet_id=%s%s' % (pid, KEY)
        sign = self._md5(raw)
        u = '%s/player/api/v1/playlet/info?playlet_id=%s&sign=%s' % (SHORT_READ, quote(str(pid)), sign)
        return self._request(u, headers=self._headers('short'))

    # ---------------- 七貓漫劇（APK 1.0.3 邏輯） ----------------
    def _manju_index(self, page=1, tag='0'):
        # Lhu.h() 實際 body 欄位：tag_id,next_id,slot_id,playlet_privacy,preference,latest_play_over,operation
        body = {
            'tag_id': str(tag or '0'),
            'next_id': '' if page <= 1 else str(page),
            'slot_id': '',
            'playlet_privacy': '1',
            'preference': '',
            'latest_play_over': '',
            'operation': '1',
        }
        body = self._signed_form(body)
        # store 專屬 interceptor 的 qmToken() 明確回傳 refresh-type=0
        h = self._headers('manju', {'refresh-type': '0'})
        return self._request(MANJU_STORE + '/api/v1/playlet/index', method='POST', headers=h, data=body)

    def _manju_sort(self):
        # APK mock 證實此接口直接提供 hot_list / new_list / search_list。
        # 介面方法在 Flutter AOT，不確定 GET/POST；兩種依序嘗試。
        h = self._headers('manju', {'refresh-type': '0'})
        u = MANJU_STORE + '/api/v1/playlet/sort-list'
        j = self._request(u, headers=h)
        if (j.get('data') or {}):
            return j
        return self._request(u, method='POST', headers=h, data=self._signed_form({}))

    def _manju_search(self, word, page=1):
        h = self._headers('manju', {'refresh-type': '0'})
        track = 'ec1280db127955061754851657967'

        # 七貓短劇同族搜索格式；漫劇 APK mock 回傳欄位 id/title/total_num 完全同型。
        params = {
            'extend': '',
            'page': str(page),
            'wd': str(word),
            'read_preference': '0',
            'track_id': track,
        }
        raw = ''.join('%s=%s' % (k, params[k]) for k in sorted(params.keys()))
        qsign = self._md5(raw + KEY)
        q = dict(params); q['sign'] = qsign
        u = MANJU_STORE + '/api/v1/playlet/search?' + urlencode(q)
        j = self._request(u, headers=h)
        if ((j.get('data') or {}).get('list')):
            return j

        # APK 新版也大量使用 signed form RequestBody；GET 無資料時改 POST。
        return self._request(
            MANJU_STORE + '/api/v1/playlet/search', method='POST', headers=h,
            data=self._signed_form(params)
        )

    def _manju_detail_meta(self, pid):
        h = self._headers('manju')
        u = MANJU_STORE + '/api/v1/playlet/detail?playlet_id=' + quote(str(pid))
        return self._request(u, headers=h)

    def _manju_info(self, pid):
        # Retrofit Lnw4.m() 已確認只有 query: playlet_id, is_material；簽名在 HeaderInterceptor。
        h = self._headers('manju')
        u = '%s/player/api/v1/playlet/info?playlet_id=%s&is_material=0' % (MANJU_READ, quote(str(pid)))
        j = self._request(u, headers=h)
        if j.get('data'):
            return j

        # 相容性兜底：若服務端仍接受舊式 query sign 再試一次，不影響正常新版。
        raw = 'is_material=0playlet_id=%s%s' % (pid, KEY)
        u2 = u + '&sign=' + self._md5(raw)
        return self._request(u2, headers=h)

    # ---------------- 解析器 ----------------
    @staticmethod
    def _pick_data_list(j):
        d = (j or {}).get('data') or {}
        if isinstance(d, list):
            return d
        for k in ('list', 'playlet_list', 'items', 'hot_list', 'new_list', 'search_list'):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, list) and v:
                return v
        return []

    def _cards(self, rows, prefix):
        out = []
        for x in rows or []:
            if not isinstance(x, dict):
                continue
            pid = x.get('playlet_id') or x.get('id') or x.get('book_id')
            name = self._clean_title(x.get('title') or x.get('name'))
            if not pid or not name:
                continue
            pic = x.get('image_link') or x.get('cover_url') or x.get('cover') or ''
            ep = x.get('total_episode_num') or x.get('total_num') or x.get('episode_count') or ''
            hot = x.get('hot_value') or ''
            remark = str(ep or '')
            if remark and str(remark).isdigit():
                remark += '集'
            if hot:
                remark = (remark + ' · ' + str(hot)).strip(' ·')
            out.append({
                'vod_id': '%s@%s' % (prefix, quote(str(pid))),
                'vod_name': name,
                'vod_pic': str(pic or ''),
                'vod_remarks': remark,
            })
        return out

    @staticmethod
    def _find_episode_rows(data):
        """兼容 play_list/list/video_list/episodes 及巢狀播放器資料。"""
        best = []
        seen_obj = set()

        def walk(v, depth=0):
            nonlocal best
            if depth > 8:
                return
            if isinstance(v, dict):
                oid = id(v)
                if oid in seen_obj:
                    return
                seen_obj.add(oid)
                # 任一物件本身像單集
                url = v.get('video_url') or v.get('url') or v.get('play_url') or v.get('main_play_url')
                if url and isinstance(url, str) and url.startswith('http'):
                    best.append(v)
                for k, x in v.items():
                    if k in ('play_list', 'video_list', 'episodes', 'episode_list', 'list', 'items', 'videos') and isinstance(x, list):
                        for z in x:
                            walk(z, depth + 1)
                    elif isinstance(x, (dict, list)):
                        walk(x, depth + 1)
            elif isinstance(v, list):
                for z in v:
                    walk(z, depth + 1)

        walk(data)
        return best

    def _detail_from_info(self, prefix, pid, j, meta=None):
        d = (j or {}).get('data') or {}
        md = (meta or {}).get('data') or {}
        if isinstance(md, list):
            md = md[0] if md else {}
        if not isinstance(md, dict):
            md = {}
        if not isinstance(d, dict):
            d = {}

        info = dict(md)
        # info 接口若本身帶片名/封面，優先使用
        for k, v in d.items():
            if k not in info or not info.get(k):
                info[k] = v

        title = self._clean_title(info.get('title') or info.get('playlet_title') or info.get('name') or '七貓')
        pic = info.get('image_link') or info.get('cover_url') or info.get('cover') or ''
        intro = info.get('intro') or info.get('description') or info.get('content') or ''
        tags = info.get('tags') or ''
        total = info.get('total_episode_num') or info.get('total_num') or ''

        eps = self._find_episode_rows(d)
        play = []
        seen = set()
        for idx, x in enumerate(eps, 1):
            url = x.get('video_url') or x.get('url') or x.get('play_url') or x.get('main_play_url') or ''
            if not isinstance(url, str) or not url.startswith('http') or url in seen:
                continue
            seen.add(url)
            sort = x.get('sort') or x.get('video_sort') or x.get('episode') or x.get('index') or idx
            play.append('%s$%s' % (sort, url))

        if not play:
            return {'list': []}
        remarks = []
        if tags:
            remarks.append(str(tags))
        if total:
            t = str(total)
            remarks.append(t if '集' in t else t + '集')

        return {'list': [{
            'vod_id': '%s@%s' % (prefix, quote(str(pid))),
            'vod_name': title,
            'vod_pic': str(pic or ''),
            'vod_remarks': ' · '.join(remarks),
            'vod_content': str(intro or ''),
            'vod_play_from': '七貓短劇' if prefix == '短劇' else '七貓漫劇',
            'vod_play_url': '#'.join(play),
        }]}

    # ---------------- T3 ----------------
    def homeContent(self, filter=False):
        classes = [
            {'type_id': '七貓短劇', 'type_name': '🐱七貓短劇'},
            {'type_id': '七貓漫劇', 'type_name': '🎨七貓漫劇'},
        ]
        filters = {
            '七貓短劇': [{
                'key': 'tag', 'name': '分類',
                'value': [
                    {'n':'全部','v':'0'}, {'n':'男頻','v':'1'}, {'n':'新劇','v':'3'},
                    {'n':'現代言情','v':'21'}, {'n':'穿越','v':'373'}, {'n':'戰神','v':'527'},
                    {'n':'古裝','v':'1272'}
                ]
            }],
            '七貓漫劇': [{
                'key':'rank', 'name':'榜單',
                'value':[{'n':'推薦','v':'index'}, {'n':'熱播','v':'hot'}, {'n':'新劇','v':'new'}, {'n':'熱搜','v':'search'}]
            }]
        }
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        j = self._short_index('0', 1)
        return {'list': self._cards(self._pick_data_list(j), '短劇')[:30]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        ext = extend if isinstance(extend, dict) else {}

        if str(tid) == '七貓短劇':
            tag = str(ext.get('tag') or '0')
            j = self._short_index(tag, page)
            rows = self._cards(self._pick_data_list(j), '短劇')
            d = j.get('data') or {}
            has_next = bool(d.get('next_id') or d.get('next_page') or d.get('has_next')) if isinstance(d, dict) else False
            return {
                'list': rows, 'page': page,
                'pagecount': page + (1 if has_next or len(rows) >= 20 else 0),
                'limit': len(rows) or 20,
                'total': (page - 1) * (len(rows) or 20) + len(rows)
            }

        if str(tid) == '七貓漫劇':
            rank = str(ext.get('rank') or 'index')
            rows = []
            if rank in ('hot', 'new', 'search'):
                j = self._manju_sort()
                d = j.get('data') or {}
                key = {'hot':'hot_list', 'new':'new_list', 'search':'search_list'}[rank]
                rows = self._cards(d.get(key) or [], '漫劇') if isinstance(d, dict) else []
            if not rows:
                j = self._manju_index(page)
                rows = self._cards(self._pick_data_list(j), '漫劇')
            # sort-list 是榜單本身，不做假分頁；index 才允許下一頁。
            if rank in ('hot','new','search') and rows:
                return {'list': rows, 'page': 1, 'pagecount': 1, 'limit': len(rows), 'total': len(rows)}
            return {
                'list': rows, 'page': page,
                'pagecount': page + (1 if len(rows) >= 20 else 0),
                'limit': len(rows) or 20,
                'total': (page - 1) * (len(rows) or 20) + len(rows)
            }

        return {'list': [], 'page': page, 'pagecount': 1}

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        word = str(key or '').strip()
        if not word:
            return {'list': []}

        out = []
        # 七貓短劇
        sj = self._short_search(word, page)
        out.extend(self._cards(self._pick_data_list(sj), '短劇'))

        # 七貓漫劇
        mj = self._manju_search(word, page)
        out.extend(self._cards(self._pick_data_list(mj), '漫劇'))

        # 用 prefix+id 去重，不把同名但不同平台的作品誤合併。
        seen, uniq = set(), []
        for x in out:
            k = x.get('vod_id')
            if not k or k in seen:
                continue
            seen.add(k); uniq.append(x)
        return {'list': uniq, 'page': page, 'pagecount': page + (1 if len(uniq) >= 20 else 0)}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids or '')
        if '@' not in raw:
            return {'list': []}
        prefix, enc = raw.split('@', 1)
        pid = unquote(enc)

        if prefix == '短劇':
            j = self._short_info(pid)
            return self._detail_from_info('短劇', pid, j)

        if prefix == '漫劇':
            meta = self._manju_detail_meta(pid)
            j = self._manju_info(pid)
            return self._detail_from_info('漫劇', pid, j, meta)

        return {'list': []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        return {
            'parse': 0 if url.startswith('http') else 1,
            'jx': 0,
            'playUrl': '',
            'url': url,
            'header': {'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36'}
        }
