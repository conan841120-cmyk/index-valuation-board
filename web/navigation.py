"""Three editorial-style entrances, shared by the complete published site."""
CSS = '''.site-nav{display:flex;flex-wrap:wrap;gap:10px;margin:0 auto 18px;max-width:1440px;padding:0;font:14px/1.5 "PingFang SC",system-ui,sans-serif}
.site-nav a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:9px 18px;border:1px solid #ded6c8;background:#f7f3ec;color:#14100c;text-decoration:none;text-underline-offset:3px}
.site-nav a:hover{border-color:#14100c;background:#eee7dc}.site-nav a[aria-current="page"]{background:#14100c;border-color:#14100c;color:#f7f3ec}.site-nav a:focus-visible{outline:2px solid #8a1f12;outline-offset:3px}
@media(max-width:720px){.site-nav{gap:7px}.site-nav a{flex:1 1 100%;padding:9px 12px}}'''


def navigation(current):
    base = '' if current == 'valuation' else '../'
    entries = [('valuation', base or './', '指数估值与恒生宏观'),
               ('us', base + 'us-market/', '美股信息日报与预警'),
               ('sp500', base + 'sp500-deviation/', '标普均线偏离')]
    return '<nav class="site-nav" aria-label="站点导航">' + ''.join(
        '<a href="%s"%s>%s</a>' % (url, ' aria-current="page"' if key == current else '', title)
        for key, url, title in entries) + '</nav>'
