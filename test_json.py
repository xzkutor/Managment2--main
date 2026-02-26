from parser import extract_products_from_json, scan_for_json_in_html
from bs4 import BeautifulSoup
import json

# test json extraction
obj = {'products':[{'name':'A','price':'10','url':'/a'},{'name':'B','price':'20','url':'/b'}]}
print('json extraction', extract_products_from_json(obj,'https://example.com'))

# test inline script
html = '<html><script>var data = {"products":[{"name":"X","price":"5","url":"/x"}]};</script></html>'
soup = BeautifulSoup(html,'html.parser')
print('inline script', scan_for_json_in_html(soup,'https://example.com'))
