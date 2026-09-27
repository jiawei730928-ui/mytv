# -*- coding: utf-8 -*-
"""
熱門雷達 - WebHTV / FongMi T3 Python Spider
用途：只做「現在紅什麼」的榜單雷達，不負責播放。

2026-09-27 第二層榜單＋底部翻頁修正版
- 第一層：AI短劇 / AI漫劇 / 短劇 / 國漫 / 動漫 / 電影 / 電視劇
- 第二層：熱播 / 熱搜 / 人氣 / 最近更新 / 飆升榜
- 每個第二層最多 100 筆
- 每頁 30 筆：1~30 / 31~60 / 61~90 / 91~100
- 資料源不足 100 筆時顯示實際筆數，不硬湊
- 保留愛米3已成功的豆瓣海報處理：cover_url -> pic -> cover + Header\n- 修正短劇工程 AI短劇 / AI漫劇部分封面抓不到的問題
- AI短劇/AI漫劇：改成模糊標題交集，降低因括號/季數/簡繁造成的空榜
- 國漫/動漫：移除需要 SESSDATA 的劇集索引，改用匿名公開排行榜 + 公開統計欄位
- 熱搜若無真實片名命中，明確標示「熱搜參考」，避免空白也不假裝官方熱搜
"""

import sys, re, json, html, time, base64, hashlib, hmac
from urllib.parse import quote, urljoin

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

try:
    import requests
except Exception:
    requests = None

UA = "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
IMG_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

PAGE_SIZE = 30
MAX_ITEMS = 100


class Spider(Spider):
    def getName(self):
        return "🧭熱門雷達"

    def init(self, extend=""):
        self.h = {
            "User-Agent": UA,
            "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8"
        }
        self.cache = {}
        self.cache_ts = {}
        return self

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

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
        m = re.search(r'\b%s\s*=\s*(["\'])(.*?)\1' % re.escape(key), tag or '', re.I | re.S)
        return html.unescape(m.group(2).strip()) if m else ''

    def _cached(self, key, seconds, loader):
        now = time.time()
        if key in self.cache and now - self.cache_ts.get(key, 0) < seconds:
            return self.cache[key]
        try:
            v = loader()
            if v is not None:
                self.cache[key] = v
                self.cache_ts[key] = now
                return v
        except Exception:
            pass
        return self.cache.get(key, [])

    @staticmethod
    def _douban_pic(url):
        u = str(url or '').strip()
        if not u:
            return ''
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('http://'):
            u = 'https://' + u[7:]
        if 'doubanio.com' in u or 'douban.com' in u:
            if '@Referer=' not in u and '@User-Agent=' not in u:
                u += '@User-Agent=%s@Referer=https://www.douban.com/' % IMG_UA
        return u

    @staticmethod
    def _retag(rows, label):
        out = []
        for i, x in enumerate(rows or [], 1):
            y = dict(x)
            old = str(y.get('vod_remarks') or '')
            old = re.sub(r'^#\d+\s*·?\s*', '', old).strip()
            label_pat = r'^(?:最近更新參考|熱搜參考|人氣參考|飆升參考|最近更新|飆升榜|熱播|熱搜|人氣)(?:\s*·\s*|\s*$)'
            while old and re.match(label_pat, old):
                old = re.sub(label_pat, '', old, count=1).strip()
            y['vod_remarks'] = '#%d · %s%s' % (
                i, label, (' · ' + old if old else '')
            )
            out.append(y)
        return out

    @staticmethod
    def _unique(rows, limit=MAX_ITEMS):
        out, seen = [], set()
        for x in rows or []:
            name = re.sub(r'\s+', '', str(x.get('vod_name') or '')).lower()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(x)
            if len(out) >= limit:
                break
        return out

    def _intersect_titles(self, ranked_rows, pool_rows, label):
        names = set()
        for x in pool_rows or []:
            n = re.sub(r'\s+', '', str(x.get('vod_name') or '')).lower()
            if n:
                names.add(n)

        out = []
        for x in ranked_rows or []:
            n = re.sub(r'\s+', '', str(x.get('vod_name') or '')).lower()
            if n in names:
                out.append(dict(x))

        if len(out) < 3:
            out = list(pool_rows or [])
        return self._retag(self._unique(out), label)


    @staticmethod
    def _norm_title(s):
        s = str(s or '').lower()
        s = re.sub(r'[《》〈〉「」『』【】\[\]\(\)（）·•・:：\-—_，,。.!！?？/\\\s]+', '', s)
        s = re.sub(r'(短剧|短劇|漫剧|漫劇|全集|完整版|在线观看免费|在线观看)$', '', s)
        return s

    def _title_match(self, a, b):
        a = self._norm_title(a)
        b = self._norm_title(b)
        if not a or not b:
            return False
        if a == b:
            return True
        # 名稱稍有前後綴也算同片，但太短的字串不做包含判定，避免誤撞。
        if min(len(a), len(b)) >= 4 and (a in b or b in a):
            return True
        return False

    def _strict_intersect(self, ranked_rows, pool_rows, label):
        """跨榜單模糊比對；解決簡繁/括號/季數尾綴造成的假性零命中。"""
        pool = list(pool_rows or [])
        out = []
        for x in ranked_rows or []:
            name = x.get('vod_name') or ''
            if any(self._title_match(name, y.get('vod_name') or '') for y in pool):
                out.append(dict(x))
        return self._retag(self._unique(out), label)

    def _borrow_pics(self, rows, *sources):
        pic_map = {}
        for src in sources:
            for x in src or []:
                n = self._norm_title(x.get('vod_name'))
                pic = str(x.get('vod_pic') or '').strip()
                if n and pic and n not in pic_map:
                    pic_map[n] = pic
        out = []
        for x in rows or []:
            y = dict(x)
            if not str(y.get('vod_pic') or '').strip():
                n = self._norm_title(y.get('vod_name'))
                if n in pic_map:
                    y['vod_pic'] = pic_map[n]
            out.append(y)
        return out

    def _fill_distinct(self, primary, fallback, label, min_items=30):
        """
        真榜優先；若真榜筆數不足，才用同類候選補到最多第一頁30筆。
        補位不複製、不造假。
        """
        out = [dict(x) for x in (primary or [])]
        seen = {self._norm_title(x.get('vod_name')) for x in out}
        if len(out) < min_items:
            for x in fallback or []:
                n = self._norm_title(x.get('vod_name'))
                if not n or n in seen:
                    continue
                out.append(dict(x))
                seen.add(n)
                if len(out) >= min_items:
                    break
        out = self._borrow_pics(out, primary, fallback)
        return self._retag(self._unique(out), label)

    def _avoid_same(self, rows, reference_rows, label, compare_top=20):
        """
        若某榜前段和參考榜幾乎一樣，仍只使用「該榜本身已有候選」，
        只是把參考榜未出現的項目提前，避免畫面看起來完全沒切換。
        """
        rows = self._unique([dict(x) for x in (rows or [])], MAX_ITEMS)
        ref = {
            self._norm_title(x.get('vod_name'))
            for x in (reference_rows or [])[:compare_top]
            if self._norm_title(x.get('vod_name'))
        }
        if not rows or not ref:
            return self._retag(rows, label)

        first = rows[:compare_top]
        overlap = sum(
            1 for x in first if self._norm_title(x.get('vod_name')) in ref
        ) / float(max(1, min(len(first), len(ref))))

        if overlap < 0.75:
            return self._retag(rows, label)

        different = [
            x for x in rows
            if self._norm_title(x.get('vod_name')) not in ref
        ]
        same = [
            x for x in rows
            if self._norm_title(x.get('vod_name')) in ref
        ]
        return self._retag(self._unique(different + same), label)



    def _sort_metric(self, rows, key, label):
        rows = [dict(x) for x in (rows or [])]
        rows.sort(key=lambda x: float(x.get(key) or 0), reverse=True)
        return self._retag(self._unique(rows), label)

    def _bili_public_rank(self, season_type):
        """
        匿名公開排行榜，不依賴 SESSDATA。
        國創 season_type=4 用 /pgc/season/rank/web/list
        番劇 season_type=1 用 /pgc/web/rank/list
        """
        ck = 'bili_public_rank_%s' % season_type

        def load():
            endpoint = (
                '/pgc/web/rank/list'
                if int(season_type) == 1
                else '/pgc/season/rank/web/list'
            )
            u = 'https://api.bilibili.com%s?day=3&season_type=%s' % (endpoint, season_type)
            r = self._get(u, headers={
                'Referer': 'https://www.bilibili.com/v/popular/rank/',
                'Origin': 'https://www.bilibili.com'
            })
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            try:
                j = r.json()
            except Exception:
                return []
            if j.get('code') not in (0, None):
                return []

            data = j.get('result') or j.get('data') or {}
            rows = data.get('list') or []
            out = []

            def _num(v):
                try:
                    return int(v or 0)
                except Exception:
                    return 0

            def _epnum(v):
                m = re.findall(r'\d+(?:\.\d+)?', str(v or ''))
                try:
                    return float(m[-1]) if m else 0.0
                except Exception:
                    return 0.0

            for x in rows:
                title = str(x.get('title') or x.get('name') or '').strip()
                if not title:
                    continue
                stat = x.get('stat') or {}
                new_ep = x.get('new_ep') or {}
                ep_show = (
                    new_ep.get('index_show')
                    or new_ep.get('index')
                    or x.get('new_ep_index')
                    or ''
                )
                pub_ts = (
                    new_ep.get('pub_time')
                    or new_ep.get('pub_ts')
                    or new_ep.get('pubtime')
                    or 0
                )
                view = _num(stat.get('view') or x.get('views'))
                follow = _num(
                    stat.get('follow')
                    or stat.get('series_follow')
                    or stat.get('favorites')
                    or x.get('follow')
                )
                danmaku = _num(stat.get('danmaku') or stat.get('dm'))
                score = float(view) / float(max(follow, 1))

                pic = x.get('cover') or x.get('square_cover') or ''
                sid = str(x.get('season_id') or x.get('media_id') or len(out) + 1)

                remark = '#%d' % (len(out) + 1)
                if ep_show:
                    remark += ' · ' + str(ep_show)
                if view >= 10000:
                    remark += ' · %.1f萬播放' % (view / 10000.0)

                out.append({
                    'vod_id': 'radar|bili|%s|%s' % (quote(title, safe=''), sid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark,
                    '_view': view,
                    '_follow': follow,
                    '_danmaku': danmaku,
                    '_epnum': _epnum(ep_show),
                    '_pub_ts': _num(pub_ts),
                    '_rise': score,
                })
                if len(out) >= MAX_ITEMS:
                    break
            return out

        return self._cached(ck, 1200, load)

    def _bili_metric_rank(self, season_type, mode, label):
        rows = [dict(x) for x in self._bili_public_rank(season_type)]
        if not rows:
            return []

        hot_ref = [dict(x) for x in rows]

        if mode == 'hot':
            return self._retag(rows, label)

        elif mode == 'pop':
            # 追番/收藏優先；沒有追番欄位才退回播放數
            rows.sort(
                key=lambda x: (
                    x.get('_follow') or 0,
                    x.get('_view') or 0
                ),
                reverse=True
            )
            return self._avoid_same(rows, hot_ref, label)

        elif mode == 'update':
            # 有公開時間戳就按時間；沒有則用「連載集數」做更新參考。
            if any(x.get('_pub_ts') for x in rows):
                rows.sort(
                    key=lambda x: (
                        x.get('_pub_ts') or 0,
                        x.get('_epnum') or 0
                    ),
                    reverse=True
                )
                return self._avoid_same(rows, hot_ref, label)
            rows.sort(
                key=lambda x: (
                    x.get('_epnum') or 0,
                    -(x.get('_view') or 0)
                ),
                reverse=True
            )
            return self._avoid_same(rows, hot_ref, '最近更新參考')

        elif mode == 'rising':
            # 飆升參考：討論密度 × 觀看/追番比，避免等同官方熱播原排序
            for x in rows:
                view = float(x.get('_view') or 0)
                follow = float(x.get('_follow') or 0)
                danmaku = float(x.get('_danmaku') or 0)
                x['_rise2'] = ((danmaku + 1.0) * 1000.0 / (view + 1.0)) * (
                    (view + 1.0) / (follow + 100.0)
                )
            rows.sort(
                key=lambda x: (
                    x.get('_rise2') or 0,
                    x.get('_danmaku') or 0
                ),
                reverse=True
            )
            return self._avoid_same(rows, hot_ref, '飆升參考')

        elif mode == 'buzz':
            rows.sort(
                key=lambda x: (
                    x.get('_danmaku') or 0,
                    x.get('_view') or 0
                ),
                reverse=True
            )
            return self._avoid_same(rows, hot_ref, '熱搜參考')

        return self._retag(rows, label)

    def _bili_recent_rank(self, season_type):
        """B站近3日劇集排行，和總播放/追番是不同的近期訊號。"""
        ck = 'bili_recent_%s' % season_type

        def load():
            u = 'https://api.bilibili.com/pgc/season/rank/web/list?day=3&season_type=%s' % season_type
            r = self._get(u, headers={'Referer': 'https://www.bilibili.com/'})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            try:
                j = r.json()
            except Exception:
                return []

            data = j.get('result') or j.get('data') or {}
            rows = data.get('list') or data.get('items') or []
            out = []

            for x in rows:
                title = str(x.get('title') or x.get('name') or '').strip()
                if not title:
                    continue
                pic = x.get('cover') or x.get('square_cover') or ''
                ep = ((x.get('new_ep') or {}).get('index_show') or x.get('new_ep_index') or '')
                view = ((x.get('stat') or {}).get('view') or '')

                remark = '#%d' % (len(out) + 1)
                if ep:
                    remark += ' · ' + str(ep)
                if view:
                    try:
                        n = int(view)
                        if n >= 10000:
                            remark += ' · %.1f萬播放' % (n / 10000.0)
                    except Exception:
                        pass

                sid = str(x.get('season_id') or x.get('media_id') or len(out) + 1)
                out.append({
                    'vod_id': 'radar|bili|%s|%s' % (quote(title, safe=''), sid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(out) >= MAX_ITEMS:
                    break
            return out

        return self._cached(ck, 900, load)

    def _bili_hotwords(self):
        """B站公開即時熱搜詞。"""
        def load():
            r = self._get(
                'https://s.search.bilibili.com/main/hotword',
                headers={'Referer': 'https://www.bilibili.com/'}
            )
            if not r or getattr(r, 'status_code', 0) != 200:
                return []
            try:
                j = r.json()
            except Exception:
                return []
            out = []
            for x in (j.get('list') or []):
                w = str(x.get('keyword') or x.get('show_name') or '').strip()
                if w:
                    out.append(w)
            return out
        return self._cached('bili_hotwords', 600, load)

    def _bili_search_rank(self, season_type, label='熱搜'):
        pool = self._bili_public_rank(season_type)
        words = [self._norm_title(w) for w in self._bili_hotwords()]
        out = []
        for x in pool:
            name = self._norm_title(x.get('vod_name') or '')
            if any((w in name or name in w) for w in words if len(w) >= 2):
                out.append(dict(x))

        if out:
            return self._retag(self._unique(out), label)

        # 真熱搜沒有對上片名時，不空白；改用匿名公開排行中的彈幕討論度，
        # 並把項目標成「熱搜參考」，避免假裝是官方熱搜。
        return self._bili_metric_rank(season_type, 'buzz', '熱搜參考')

    # -------------------- 首頁：7 大類 + 第二層篩選 --------------------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": "ai_short",  "type_name": "🤖AI短劇"},
            {"type_id": "ai_manhua", "type_name": "🎨AI漫劇"},
            {"type_id": "short",     "type_name": "🎭短劇"},
            {"type_id": "guoman",    "type_name": "🐉國漫"},
            {"type_id": "anime",     "type_name": "🌸動漫"},
            {"type_id": "movie",     "type_name": "🎬電影"},
            {"type_id": "tv",        "type_name": "📺電視劇"},
        ]

        rank_values = [
            {"n": "熱播",     "v": "hot"},
            {"n": "熱搜",     "v": "search"},
            {"n": "人氣",     "v": "pop"},
            {"n": "最近更新", "v": "update"},
            {"n": "飆升榜",   "v": "rising"},
        ]

        filters = {}
        for c in classes:
            filters[c["type_id"]] = [{
                "key": "rank",
                "name": "榜單",
                "value": rank_values
            }]

        return {"class": classes, "filters": filters if filter else filters}

    def homeVideoContent(self):
        return {"list": self._duanju_baike('rebo.html')[:PAGE_SIZE]}

    # -------------------- 短劇百科 --------------------
    def _duanju_baike(self, page):
        def load():
            url = 'https://www.duanjubaike.net/paihang/' + page
            r = self._get(
                url,
                headers={"Referer": "https://www.duanjubaike.net/paihang/index.html"}
            )
            if not r or getattr(r, 'status_code', 0) != 200:
                return []

            text = r.text
            out, seen = [], set()

            pats = list(re.finditer(
                r'<a\b([^>]*href\s*=\s*(["\'])([^"\']*/duanju/info-[^"\']+\.html)\2[^>]*)>([\s\S]*?)</a>',
                text, re.I
            ))

            for m in pats:
                href = m.group(3)
                if href in seen:
                    continue

                block = m.group(4)
                clean = self._txt(block)
                if not clean:
                    continue

                im = re.search(r'<img\b([^>]*)>', block, re.I | re.S)
                pic, title = '', ''

                if im:
                    tag = im.group(1)
                    pic = self._attr(tag, 'src') or self._attr(tag, 'data-src') or self._attr(tag, 'data-original')
                    alt = self._attr(tag, 'alt')
                    mm = re.search(r'《(.+?)》', alt)
                    if mm:
                        title = mm.group(1).strip()
                    elif alt:
                        title = re.sub(r'^(?:短劇|短剧|漫劇|漫剧)', '', alt)
                        title = re.sub(r'(?:海報|海报|封面)$', '', title).strip()

                if not title:
                    mm = re.search(
                        r'全\s*\d+\s*集\s+(.+?)(?=\s+(?:評分|评分|\d+(?:\.\d+)?\s*萬?收藏|\d+(?:\.\d+)?\s*万收藏|\d+\s*收藏|預告|预告|\d+(?:\.\d+)?\s*萬?人預約|\d+(?:\.\d+)?\s*万人预约|真人劇|真人剧|第\d+季))',
                        clean, re.I
                    )
                    if mm:
                        title = mm.group(1).strip()

                if not title:
                    continue

                metric = ''
                mm = re.search(r'(\d+(?:\.\d+)?)\s*万\s*(最高热度|熱度|热度|熱搜|热搜|收藏|預約|预约|期待)', clean)
                if mm:
                    lab = mm.group(2).replace('热度', '熱度').replace('热搜', '熱搜').replace('预约', '預約')
                    metric = mm.group(1) + '萬' + lab

                ep = ''
                em = re.search(r'全\s*(\d+)\s*集', clean)
                if em and em.group(1) != '0':
                    ep = '全%s集' % em.group(1)

                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = urljoin(url, pic)

                rank = len(out) + 1
                remark = '#%d' % rank
                if metric:
                    remark += ' · ' + metric
                if ep:
                    remark += ' · ' + ep

                seen.add(href)
                def _num_metric(pattern):
                    mmx = re.search(pattern, clean, re.I)
                    if not mmx:
                        return 0.0
                    try:
                        n = float(mmx.group(1))
                    except Exception:
                        return 0.0
                    unit = mmx.group(2) if mmx.lastindex and mmx.lastindex >= 2 else ''
                    return n * (10000.0 if unit in ('万','萬') else 1.0)

                out.append({
                    'vod_id': 'radar|short|%s|%s' % (quote(title, safe=''), quote(href, safe='')),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark,
                    '_heat': _num_metric(r'(\d+(?:\.\d+)?)\s*([万萬]?)\s*(?:最高热度|最高熱度|热度|熱度)'),
                    '_fav': _num_metric(r'(\d+(?:\.\d+)?)\s*([万萬]?)\s*收藏'),
                    '_like': _num_metric(r'(\d+(?:\.\d+)?)\s*([万萬]?)\s*次?点赞')
                })

                if len(out) >= MAX_ITEMS:
                    break

            return out

        return self._cached('dbk_' + page, 1800, load)

    # -------------------- 短劇工程每日榜 --------------------
    def _short_rank(self, wanted='all'):
        def load():
            url = 'https://www.duanjugongcheng.com/cn/daily'
            r = self._get(url, headers={"Referer": "https://www.duanjugongcheng.com/cn/"})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []

            text = r.text
            out, seen = [], set()

            pats = list(re.finditer(
                r'<a\b([^>]*href\s*=\s*(["\'])(/cn/bangdan/ju/[^"\']+)\2[^>]*)>([\s\S]*?)</a>',
                text, re.I
            ))

            for idx, m in enumerate(pats):
                href = m.group(3)
                if href in seen:
                    continue

                block = m.group(4)
                title, pic = '', ''

                im = re.search(r'<img\b([^>]*)>', block, re.I | re.S)
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

                end = pats[idx + 1].start() if idx + 1 < len(pats) else min(len(text), m.end() + 1600)
                tail = text[m.end():min(end, m.end() + 1600)]
                around = block + tail

                # 短劇工程有些封面不在 <a> 內，而是在連結前面的相鄰區塊。
                # 愛米3實機若只抓 block，AI短劇 / AI漫劇會大量退回彩色文字方塊。
                if not pic:
                    pre = text[max(0, m.start() - 1400):m.start()]
                    ims = list(re.finditer(r'<img\b([^>]*)>', pre, re.I | re.S))
                    if ims:
                        tag = ims[-1].group(1)
                        pic = (
                            self._attr(tag, 'src')
                            or self._attr(tag, 'data-src')
                            or self._attr(tag, 'data-original')
                            or self._attr(tag, 'data-lazy-src')
                        )

                # 再補抓標題後方的圖片。
                if not pic:
                    im2 = re.search(r'<img\b([^>]*)>', around, re.I | re.S)
                    if im2:
                        tag = im2.group(1)
                        pic = (
                            self._attr(tag, 'src')
                            or self._attr(tag, 'data-src')
                            or self._attr(tag, 'data-original')
                            or self._attr(tag, 'data-lazy-src')
                        )

                kind = ''
                for k in ('AI短剧', 'AI短劇', '漫剧', '漫劇', '真人剧', '真人劇'):
                    if k in around:
                        kind = k.replace('剧', '劇')
                        break

                heat = ''
                hm = re.search(r'(\d+(?:\.\d+)?)\s*万', self._txt(around))
                if hm:
                    heat = hm.group(1) + '萬'

                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = urljoin(url, pic)

                seen.add(href)
                rank = len(out) + 1
                remark = '#%d' % rank
                if kind:
                    remark += ' · ' + kind
                if heat:
                    remark += ' · ' + heat

                out.append({
                    'vod_id': 'radar|short|%s|%s' % (quote(title, safe=''), quote(href, safe='')),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark,
                })

                if len(out) >= MAX_ITEMS:
                    break

            return out

        all_rows = self._cached('short_all', 900, load)
        if wanted == 'all':
            return all_rows

        kw = {
            'real': '真人劇',
            'manhua': '漫劇',
            'ai': 'AI短劇'
        }.get(wanted, '')

        return [x for x in all_rows if kw and kw in x.get('vod_remarks', '')]

    # -------------------- Bilibili 國漫榜 --------------------
    def _guoman_rank(self):
        def load():
            u = 'https://api.bilibili.com/pgc/season/rank/web/list?day=3&season_type=4'
            r = self._get(u, headers={"Referer": "https://www.bilibili.com/v/popular/rank/guochuang"})
            if not r or getattr(r, 'status_code', 0) != 200:
                return []

            try:
                j = r.json()
            except Exception:
                return []

            data = j.get('result') or j.get('data') or {}
            rows = data.get('list') or data.get('items') or []
            out = []

            for i, x in enumerate(rows, 1):
                title = str(x.get('title') or x.get('name') or '').strip()
                if not title:
                    continue
                pic = x.get('cover') or x.get('square_cover') or ''
                ep = ((x.get('new_ep') or {}).get('index_show') or x.get('new_ep_index') or '')
                view = ((x.get('stat') or {}).get('view') or '')
                remark = '#%d' % i
                if ep:
                    remark += ' · ' + str(ep)
                if view:
                    try:
                        n = int(view)
                        if n >= 10000:
                            remark += ' · %.1f萬播放' % (n / 10000.0)
                    except Exception:
                        pass
                sid = str(x.get('season_id') or x.get('media_id') or i)
                out.append({
                    'vod_id': 'radar|guoman|%s|%s' % (quote(title, safe=''), sid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
                if len(out) >= MAX_ITEMS:
                    break
            return out

        return self._cached('guoman', 1800, load)

    # -------------------- 豆瓣 電影 / 電視劇 / 動漫 --------------------
    @staticmethod
    def _douban_sign(path, ts):
        secret = b'bf7dddc7c9cfe6f7'
        full = 'https://frodo.douban.com/api/v2' + path
        from urllib.parse import urlparse, quote as q
        url_path = urlparse(full).path
        raw = '&'.join(['GET', q(url_path, safe=''), str(ts)])
        return base64.b64encode(
            hmac.new(secret, raw.encode(), hashlib.sha1).digest()
        ).decode()

    def _douban(self, collection):
        def load():
            path = '/subject_collection/%s/items' % collection
            hdr = {
                'User-Agent': 'api-client/1 com.douban.frodo/7.22.0(231) Android/23 product/Mate40 vendor/HUAWEI model/Mate40 platform/mobile',
                'Referer': 'https://m.douban.com/'
            }

            out, seen = [], set()

            # 0~39 / 40~79 / 80~99，最多 100 筆
            for start in (0, 40, 80):
                count = 40 if start < 80 else 20
                ts = time.strftime('%Y%m%d')
                params = {
                    'start': str(start),
                    'count': str(count),
                    'os_rom': 'android',
                    'apiKey': '0dad551ec0f84ed02907ff5c42e8ec70',
                    '_ts': ts,
                    '_sig': self._douban_sign(path, ts)
                }
                qs = '&'.join(
                    '%s=%s' % (quote(str(k), safe=''), quote(str(v), safe=''))
                    for k, v in params.items()
                )
                u = 'https://frodo.douban.com/api/v2' + path + '?' + qs
                r = self._get(u, headers=hdr)

                if not r or getattr(r, 'status_code', 0) != 200:
                    u2 = (
                        'https://m.douban.com/rexxar/api/v2/subject_collection/'
                        '%s/items?start=%s&count=%s&for_mobile=1'
                    ) % (collection, start, count)
                    r = self._get(u2, headers={'Referer': 'https://m.douban.com/'})
                    if not r or getattr(r, 'status_code', 0) != 200:
                        break

                try:
                    j = r.json()
                except Exception:
                    break

                rows = j.get('subject_collection_items') or j.get('items') or []
                if not rows:
                    break

                for x in rows:
                    title = str(x.get('title') or x.get('name') or '').strip()
                    if not title:
                        continue

                    key = re.sub(r'\s+', '', title).lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    # 愛米3已實機成功順序：cover_url -> pic -> cover
                    cover = str(x.get('cover_url') or '').strip()
                    if not cover:
                        pic = x.get('pic') or {}
                        if isinstance(pic, dict):
                            cover = (
                                pic.get('large') or pic.get('normal')
                                or pic.get('small') or pic.get('url') or ''
                            )
                        else:
                            cover = str(pic or '')

                    if not cover:
                        c2 = x.get('cover') or {}
                        if isinstance(c2, dict):
                            cover = (
                                c2.get('url') or c2.get('large')
                                or c2.get('normal') or ''
                            )
                        else:
                            cover = str(c2 or '')

                    cover = self._douban_pic(cover)

                    rating = x.get('rating') or {}
                    score = rating.get('value') if isinstance(rating, dict) else ''
                    sub = x.get('card_subtitle') or x.get('subtitle') or ''

                    rank = len(out) + 1
                    remark = '#%d' % rank
                    if score not in ('', None, 0, '0'):
                        remark += ' · %s分' % score
                    elif sub:
                        remark += ' · ' + str(sub)[:18]

                    did = str(x.get('id') or rank)
                    out.append({
                        'vod_id': 'radar|douban|%s|%s' % (quote(title, safe=''), did),
                        'vod_name': title,
                        'vod_pic': cover,
                        'vod_remarks': remark
                    })

                    if len(out) >= MAX_ITEMS:
                        return out

                if len(rows) < count:
                    break

            return out[:MAX_ITEMS]

        return self._cached('db_' + collection, 1800, load)

    # -------------------- 各榜單資料 --------------------
    def _rows_for(self, tid, rank):
        rank = rank or 'hot'

        short_search = self._duanju_baike('reso.html')
        short_hot = self._duanju_baike('rebo.html')
        short_pop = self._duanju_baike('shoucang.html')
        short_new = self._duanju_baike('xinju.html')
        manhua_hot = self._duanju_baike('manjurebo.html')
        manhua_new = self._duanju_baike('manjuxinju.html')

        daily_all = self._short_rank('all')
        ai_pool = self._short_rank('ai')
        manhua_daily = self._short_rank('manhua')

        if tid == 'ai_short':
            if rank == 'hot':
                return self._retag(ai_pool, '熱播')
            if rank == 'search':
                real = self._strict_intersect(short_search, ai_pool, '熱搜')
                filled = self._fill_distinct(real, ai_pool, '熱搜', min_items=30)
                filled = self._borrow_pics(filled, ai_pool, short_search, short_hot)
                return self._avoid_same(filled, self._retag(ai_pool, '熱播'), '熱搜')
            if rank == 'pop':
                real = self._strict_intersect(short_pop, ai_pool, '人氣')
                filled = self._fill_distinct(real, ai_pool, '人氣', min_items=30)
                filled = self._borrow_pics(filled, ai_pool, short_pop, short_hot)
                return self._avoid_same(filled, self._retag(ai_pool, '熱播'), '人氣')
            if rank == 'update':
                real = self._strict_intersect(short_new, ai_pool, '最近更新')
                return self._fill_distinct(real, ai_pool, '最近更新')
            # 飆升：以「熱播榜順序」去挑新劇，和「最近更新的新劇順序」自然分開
            rising = self._strict_intersect(short_hot, short_new, '飆升榜')
            rising = self._strict_intersect(rising, ai_pool, '飆升榜')
            filled = self._fill_distinct(rising, ai_pool[10:], '飆升榜')
            update_ref = self._fill_distinct(
                self._strict_intersect(short_new, ai_pool, '最近更新'),
                ai_pool,
                '最近更新'
            )
            return self._avoid_same(filled, update_ref, '飆升榜')

        if tid == 'ai_manhua':
            hot_pool = manhua_hot or manhua_daily
            if rank == 'hot':
                return self._retag(hot_pool, '熱播')
            if rank == 'search':
                real = self._strict_intersect(short_search, hot_pool, '熱搜')
                return self._fill_distinct(real, manhua_daily, '熱搜')
            if rank == 'pop':
                real = self._strict_intersect(short_pop, hot_pool, '人氣')
                metric = self._sort_metric(hot_pool, '_fav', '人氣參考')
                filled = self._fill_distinct(real, metric or manhua_daily, '人氣', min_items=30)
                filled = self._borrow_pics(filled, hot_pool, manhua_daily, short_pop)
                return self._avoid_same(filled, self._retag(hot_pool, '熱播'), '人氣')
            if rank == 'update':
                return self._fill_distinct(
                    self._retag(manhua_new, '最近更新'),
                    manhua_daily,
                    '最近更新'
                )
            # 熱播順序中挑出新劇；若仍與熱播太像，先拉開，再和最近更新比較一次
            real = self._strict_intersect(hot_pool, manhua_new, '飆升榜')
            filled = self._fill_distinct(real, hot_pool[10:], '飆升榜')
            filled = self._avoid_same(
                filled,
                self._retag(hot_pool, '熱播'),
                '飆升榜'
            )
            update_ref = self._fill_distinct(
                self._retag(manhua_new, '最近更新'),
                manhua_daily,
                '最近更新'
            )
            return self._avoid_same(filled, update_ref, '飆升榜')

        if tid == 'short':
            if rank == 'hot':
                return self._retag(short_hot, '熱播')
            if rank == 'search':
                return self._retag(short_search, '熱搜')
            if rank == 'pop':
                return self._retag(short_pop, '人氣')
            if rank == 'update':
                return self._retag(short_new or daily_all, '最近更新')
            # 和「最近更新」分開：用熱播順序挑新劇，而非沿用新劇榜順序
            real = self._strict_intersect(short_hot, short_new or daily_all, '飆升榜')
            filled = self._fill_distinct(real, short_hot[10:], '飆升榜')
            return self._avoid_same(
                filled,
                self._retag(short_new or daily_all, '最近更新'),
                '飆升榜'
            )

        if tid == 'guoman':
            if rank == 'hot':
                return self._bili_metric_rank(4, 'hot', '熱播')
            if rank == 'search':
                return self._bili_search_rank(4, '熱搜')
            if rank == 'pop':
                return self._bili_metric_rank(4, 'pop', '人氣')
            if rank == 'update':
                return self._bili_metric_rank(4, 'update', '最近更新')
            return self._bili_metric_rank(4, 'rising', '飆升榜')

        if tid == 'anime':
            if rank == 'hot':
                return self._bili_metric_rank(1, 'hot', '熱播')
            if rank == 'search':
                return self._bili_search_rank(1, '熱搜')
            if rank == 'pop':
                return self._bili_metric_rank(1, 'pop', '人氣')
            if rank == 'update':
                return self._bili_metric_rank(1, 'update', '最近更新')
            return self._bili_metric_rank(1, 'rising', '飆升榜')

        # 電影 / 電視劇維持已實機最穩定版本
        if tid == 'movie':
            coll = {
                'hot': 'movie_hot_gaia',
                'search': 'movie_showing',
                'pop': 'movie_hot_gaia',
                'update': 'movie_showing',
                'rising': 'movie_hot_gaia'
            }.get(rank, 'movie_hot_gaia')
        elif tid == 'tv':
            coll = {
                'hot': 'tv_hot',
                'search': 'tv_domestic',
                'pop': 'tv_hot',
                'update': 'tv_domestic',
                'rising': 'tv_hot'
            }.get(rank, 'tv_hot')
        else:
            return []

        lab = {
            'hot': '熱播', 'search': '熱搜', 'pop': '人氣',
            'update': '最近更新', 'rising': '飆升榜'
        }.get(rank, '熱播')
        return self._retag(self._douban(coll), lab)

    # -------------------- 分頁：每頁 30，最多 100 --------------------
    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        raw_tid = str(tid or '')
        ext = extend if isinstance(extend, dict) else {}
        rank = str(ext.get('rank') or 'hot')

        if raw_tid.startswith('radarnav|'):
            parts = raw_tid.split('|')
            if len(parts) >= 4:
                raw_tid = parts[1]
                rank = parts[2]
                try:
                    page = max(1, int(parts[3]))
                except Exception:
                    page = 1
            else:
                page = 1
        else:
            try:
                page = max(1, int(pg or 1))
            except Exception:
                page = 1

        rows = self._unique(self._rows_for(raw_tid, rank), MAX_ITEMS)
        total = min(len(rows), MAX_ITEMS)
        pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if page > pagecount:
            page = pagecount

        start = (page - 1) * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        page_rows = rows[start:end]

        nav = []
        if page > 1:
            nav.append({
                'vod_id': 'radarnav|%s|%s|1' % (raw_tid, rank),
                'vod_name': '⏮ 回頁首',
                'vod_pic': '',
                'vod_tag': 'folder',
                'vod_remarks': '第 1 / %d 頁' % pagecount,
                'land': 1
            })
            nav.append({
                'vod_id': 'radarnav|%s|%s|%d' % (raw_tid, rank, page - 1),
                'vod_name': '◀ 上一頁',
                'vod_pic': '',
                'vod_tag': 'folder',
                'vod_remarks': '第 %d / %d 頁' % (page - 1, pagecount),
                'land': 1
            })
        if page < pagecount:
            nav.append({
                'vod_id': 'radarnav|%s|%s|%d' % (raw_tid, rank, page + 1),
                'vod_name': '下一頁 ▶',
                'vod_pic': '',
                'vod_tag': 'folder',
                'vod_remarks': '第 %d / %d 頁' % (page + 1, pagecount),
                'land': 1
            })

        return {
            'list': page_rows + nav,
            'page': page,
            'pagecount': pagecount,
            'limit': PAGE_SIZE,
            'total': total
        }

    # 雷達不參與全域搜尋
    def searchContent(self, key, quick=False, pg='1'):
        return {'list': []}

    def searchContentPage(self, key, quick=False, pg='1'):
        return {'list': []}

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids or '')
        if raw.startswith('radarnav|'):
            return {'list': []}
        parts = raw.split('|')
        if len(parts) < 4:
            return {'list': []}

        from urllib.parse import unquote
        title = unquote(parts[2])
        src = parts[1]

        label = {
            'short': '短劇榜單',
            'guoman': '國漫榜單',
            'douban': '影視榜單'
        }.get(src, '熱門榜單')

        return {'list': [{
            'vod_id': raw,
            'vod_name': title,
            'vod_content': '%s收錄。這條「熱門雷達」只負責告訴你現在紅什麼；請用「%s」回正式片源搜尋播放。' % (label, title),
            'vod_play_from': '熱門雷達',
            'vod_play_url': '回正式片源搜尋$radar_none',
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        return {'parse': 1, 'jx': 0, 'url': ''}
