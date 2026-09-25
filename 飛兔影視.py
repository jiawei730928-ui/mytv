# -*- coding: utf-8 -*-
"""
飛兔影視 - WebHTV / FongMi T3 Python Spider
依現成 TVBox/drpy 規則移植：首頁/分類、搜尋、詳情、集數、播放。
只保留一般影視、動漫與超爽短劇分類，不帶成人分類。
"""
import sys, re, json, base64
from urllib.parse import quote, urljoin, unquote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            return rq.get(url, headers=headers, timeout=15, **kw)

class Spider(Spider):
    def getName(self):
        return "🐇飛兔影視"

    def init(self, extend=""):
        self.hosts = ["https://feitu.tv", "https://www.feitu.tv"]
        self.host = self.hosts[0]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.classes = [
            {"type_id":"1", "type_name":"電影"},
            {"type_id":"2", "type_name":"電視劇"},
            {"type_id":"3", "type_name":"綜藝"},
            {"type_id":"4", "type_name":"動漫"},
            {"type_id":"110", "type_name":"超爽短劇"},
        ]

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv|mkv)(?:\?|$)', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _get(self, path, referer=None):
        last = None
        # 若傳進完整 URL，就直接取；否則兩個主機輪詢。
        targets = [path] if str(path).startswith(('http://','https://')) else [h + (path if str(path).startswith('/') else '/' + str(path)) for h in self.hosts]
        for url in targets:
            try:
                hdr = dict(self.headers)
                hdr['Referer'] = referer or (url.split('/detail/')[0].split('/watch/')[0] + '/')
                r = self.fetch(url, headers=hdr, timeout=15)
                if getattr(r, 'status_code', 200) == 200 and getattr(r, 'text', ''):
                    # 跟著實際成功主機走，避免 www/non-www 跳轉造成後續錯路徑。
                    try:
                        m = re.match(r'^(https?://[^/]+)', getattr(r, 'url', '') or url)
                        if m:
                            self.host = m.group(1)
                            self.headers['Referer'] = self.host + '/'
                    except Exception:
                        pass
                    return r.text
                last = r
            except Exception:
                continue
        return getattr(last, 'text', '') if last is not None else ''

    @staticmethod
    def _clean(s):
        if s is None:
            return ''
        s = re.sub(r'<script[\s\S]*?</script>', '', str(s), flags=re.I)
        s = re.sub(r'<style[\s\S]*?</style>', '', s, flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = (s.replace('&nbsp;', ' ').replace('&amp;', '&')
               .replace('&quot;', '"').replace('&#39;', "'")
               .replace('&lt;', '<').replace('&gt;', '>'))
        return re.sub(r'\s+', ' ', s).strip()

    def _fix(self, u):
        u = str(u or '').strip().replace('\\/', '/')
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        return urljoin(self.host + '/', u)

    @staticmethod
    def _attr(tag, name):
        m = re.search(r'\b%s\s*=\s*(["\'])(.*?)\1' % re.escape(name), tag or '', re.I|re.S)
        return m.group(2).strip() if m else ''

    def _cards(self, html):
        """相容 hl-vod-list 與 hl-one-list；只收 detail 詳情連結。"""
        if not html:
            return []
        out, seen = [], set()
        for m in re.finditer(r'<li\b[^>]*>([\s\S]*?)</li>', html, re.I):
            block = m.group(1)
            am = re.search(r'<a\b([^>]*?href\s*=\s*(["\'])([^"\']*/detail/[^"\']+)\2[^>]*)>', block, re.I|re.S)
            if not am:
                continue
            tag, href = am.group(1), am.group(3)
            if href in seen:
                continue
            title = self._attr(tag, 'title')
            if not title:
                im = re.search(r'<img\b([^>]*)>', block, re.I|re.S)
                title = self._attr(im.group(1), 'alt') if im else ''
            if not title:
                tm = re.search(r'class\s*=\s*["\'][^"\']*(?:hl-title|title)[^"\']*["\'][^>]*>([\s\S]*?)</', block, re.I)
                title = self._clean(tm.group(1)) if tm else ''
            pic = ''
            im = re.search(r'<(?:img|a|span)\b([^>]*(?:data-original|data-src|src)\s*=\s*["\'][^"\']+["\'][^>]*)>', block, re.I|re.S)
            if im:
                for k in ('data-original','data-src','src'):
                    pic = self._attr(im.group(1), k)
                    if pic:
                        break
            remark = ''
            rm = re.search(r'class\s*=\s*["\'][^"\']*(?:hl-pic-text|remarks|hl-text-conch\s+score)[^"\']*["\'][^>]*>([\s\S]*?)</', block, re.I)
            if rm:
                remark = self._clean(rm.group(1))
            if title:
                seen.add(href)
                out.append({
                    'vod_id': href,
                    'vod_name': self._clean(title),
                    'vod_pic': self._fix(pic),
                    'vod_remarks': remark,
                })
        return out

    def homeContent(self, filter=False):
        return {'class': self.classes}

    def homeVideoContent(self):
        html = self._get('/')
        return {'list': self._cards(html)[:30]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        # 現成 drpy 與 Kitty 都使用這條路徑。
        html = self._get('/filter/%s/page/%s' % (tid, page))
        rows = self._cards(html)
        return {
            'list': rows,
            'page': page,
            'pagecount': page + 1 if rows else page,
            'limit': len(rows) or 24,
            'total': page * (len(rows) or 24),
        }

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        word = quote(str(key or '').strip(), safe='')
        html = self._get('/search/%s-%s/' % (word, page))
        rows = self._cards(html)
        return {'list': rows, 'page': page, 'pagecount': page + 1 if rows else page}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        if not vid:
            return {'list': []}
        html = self._get(vid)
        if not html:
            return {'list': []}

        # 站內現行樣式：hl-dc-pic 內的 hl-item-thumb hl-lazy。
        name = ''
        pic = ''
        mm = re.search(r'<(?:a|span|div)\b([^>]*class\s*=\s*["\'][^"\']*hl-item-thumb[^"\']*hl-lazy[^"\']*["\'][^>]*)>', html, re.I|re.S)
        if mm:
            name = self._attr(mm.group(1), 'title')
            pic = self._attr(mm.group(1), 'data-original') or self._attr(mm.group(1), 'data-src')
        if not name:
            hm = re.search(r'<h1\b[^>]*>([\s\S]*?)</h1>', html, re.I)
            name = self._clean(hm.group(1)) if hm else ''
        if not name:
            tm = re.search(r'<title>([\s\S]*?)</title>', html, re.I)
            name = self._clean(tm.group(1)).split(' - ')[0] if tm else ''
        if not pic:
            pm = re.search(r'<meta\b[^>]*(?:property|name)=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
            pic = pm.group(1) if pm else ''

        desc = ''
        # Kitty 現成規則是 hl-full-box 最後一列「簡介：...」。
        for li in re.findall(r'<li\b[^>]*class\s*=\s*["\'][^"\']*hl-full-box[^"\']*["\'][^>]*>([\s\S]*?)</li>', html, re.I):
            txt = self._clean(li)
            if txt.startswith(('簡介', '简介')):
                desc = re.sub(r'^(?:簡介|简介)\s*[：:]\s*', '', txt)
        if not desc:
            dm = re.search(r'<meta\b[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)', html, re.I)
            desc = self._clean(dm.group(1)) if dm else ''

        # 不靠巢狀 DIV：直接從 watch URL 拆出線路號，這比 CSS 結構變動更穩。
        groups, order = {}, []
        for a in re.finditer(r'<a\b([^>]*href\s*=\s*(["\'])([^"\']*/watch/[^"\']+)\2[^>]*)>([\s\S]*?)</a>', html, re.I):
            href = a.group(3)
            text = self._clean(a.group(4)) or '播放'
            lm = re.search(r'/watch/\d+-(\d+)-(\d+)(?:/|$)', href)
            line = lm.group(1) if lm else '1'
            if line not in groups:
                groups[line] = []
                order.append(line)
            if href not in [x[1] for x in groups[line]]:
                groups[line].append((text, href))

        play_from, play_url = [], []
        for line in order:
            eps = groups.get(line) or []
            if eps:
                play_from.append('線路%s' % line)
                play_url.append('#'.join('%s$%s' % (n, u) for n, u in eps))

        if not play_url:
            return {'list': []}

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': self._fix(pic),
            'vod_content': desc,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    @staticmethod
    def _decode_player_url(data):
        u = str((data or {}).get('url') or '').replace('\\/', '/')
        enc = str((data or {}).get('encrypt') or '0')
        try:
            if enc == '1':
                u = unquote(u)
            elif enc == '2':
                u = base64.b64decode(u + '=' * (-len(u) % 4)).decode('utf-8', 'ignore')
                u = unquote(u)
        except Exception:
            pass
        return u.replace('\\/', '/')

    def _extract_play(self, html, base_url, depth=0):
        if not html or depth > 2:
            return ''

        # Kitty 現成 feitu 規則最後就是抓頁面中的 m3u8。
        dm = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', html, re.I)
        if dm:
            return self._fix(dm.group(1).replace('\\/', '/'))
        dm = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4)(?:\?[^\s"\']*)?)', html, re.I)
        if dm:
            return dm.group(1).replace('\\/', '/')

        pm = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?', html, re.I)
        if pm:
            try:
                obj = json.loads(pm.group(1))
                u = self._decode_player_url(obj)
                if self.isVideoFormat(u):
                    return self._fix(u)
                if u.startswith('http') and depth < 2:
                    nested = self._get(u, referer=base_url)
                    got = self._extract_play(nested, u, depth + 1)
                    if got:
                        return got
            except Exception:
                pass

        im = re.search(r'<iframe\b[^>]*src\s*=\s*(["\'])([^"\']+)\1', html, re.I)
        if im and depth < 2:
            iu = urljoin(base_url, im.group(2).replace('\\/', '/'))
            nested = self._get(iu, referer=base_url)
            got = self._extract_play(nested, iu, depth + 1)
            if got:
                return got
        return ''

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or '')
        if self.isVideoFormat(raw):
            return {'parse': 0, 'jx': 0, 'url': raw, 'header': self.headers}
        page = self._fix(raw)
        html = self._get(page)
        play = self._extract_play(html, page)
        if play:
            return {
                'parse': 0,
                'jx': 0,
                'playUrl': '',
                'url': play,
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': page},
            }
        # 最後才交給殼解析；不綁第三方解析站。
        return {'parse': 1, 'jx': 1, 'playUrl': '', 'url': page, 'header': self.headers}

    def localProxy(self, param):
        return None
