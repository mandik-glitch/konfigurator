"""Pomůcky k průzkumu: pouze veřejné GET, bez účtů a formulářů."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import json
import re
import requests

ROOT = Path(__file__).resolve().parent

class Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node): yield from c.walk()
    def text(self):
        if self.tag in ('script','style','noscript'): return ''
        return ' '.join(c.text() if isinstance(c,Node) else c for c in self.children)
    def classes(self): return self.attrs.get('class','').split()

class Tree(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=Node('root');self.current=self.root
    def handle_starttag(self, tag, attrs):
        n=Node(tag,attrs,self.current);self.current.children.append(n)
        if tag not in self.VOID: self.current=n
    def handle_endtag(self, tag):
        n=self.current
        while n.parent:
            if n.tag==tag:self.current=n.parent;return
            n=n.parent
    def handle_data(self, text):self.current.children.append(text)

def get(url):
    r=requests.get(url,timeout=35);r.raise_for_status()
    tree=Tree();tree.feed(r.text)
    return r,tree.root

def cards(url):
    r,tree=get(url); out=[]
    for n in tree.walk():
        if 'p' not in n.classes():continue
        txt=' '.join(n.text().split())
        skus=re.findall(r'\b493\d{7}\b',txt)
        if not skus:continue
        links=[x for x in n.walk() if x.tag=='a' and 'name' in x.classes()]
        if not links:continue
        a=links[0]
        out.append({'sku':skus[-1],'name':' '.join(a.text().split()),'url':urljoin(r.url,a.attrs.get('href','')),'evidence':txt})
    return out

def details(url):
    r,tree=get(url)
    heading=next((' '.join(n.text().split()) for n in tree.walk() if n.tag=='h1'),'')
    props={}
    for n in tree.walk():
        prop=n.attrs.get('itemprop')
        if prop in ('sku','gtin13','weight','price','priceCurrency','availability','name'):
            val=n.attrs.get('content') or n.attrs.get('href') or ' '.join(n.text().split())
            if len(val)<200:props.setdefault(prop,[]).append(val)
    snippets=[]
    for n in tree.walk():
        if n.tag=='tr':
            txt=' '.join(n.text().split())
            if len(txt)<350 and re.search('Hmot|EAN|ozm|osnos|[Dd]élka|[Šš]ířka|ýška|Kapac|katalo|SKU',txt):snippets.append(txt)
        if 'price-additional' in n.classes() or 'availability-value' in n.classes():
            snippets.append(' '.join(n.text().split()))
    return {'url':r.url,'name':heading,'properties':props,'specifications':snippets}

if __name__=='__main__':
    import sys
    url=sys.argv[1]
    print(json.dumps(cards(url) if len(sys.argv)>2 else details(url),ensure_ascii=False,indent=2))
