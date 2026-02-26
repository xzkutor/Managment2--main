from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
from difflib import SequenceMatcher
import json
from urllib.parse import urlparse
from parser import (
    scrape_prohockey,
    scrape_hockeyshans,
    HEADERS,
    create_session,
    fetch_main_site_products,
    fetch_other_site_products,
    product_exists_on_main,
    get_prohockey_categories,
)

app = Flask(__name__)
CORS(app)

class ProductScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def scrape_products(self, url):
        """
        Попытка парсить продукты с сайта
        Возвращает список словарей с ключами: article, name, model, url
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'lxml')
            
            products = []
            domain = urlparse(url).netloc
            
            # Пытаемся найти товары по общим селекторам
            # Ищем элементы с названиями товаров, артикулами и моделями
            
            for item in soup.find_all(['div', 'article', 'td'], class_=['product', 'item', 'good', 'товар']):
                product = self.extract_product_info(item, domain)
                if product:
                    products.append(product)
            
            # Если не найдено, пытаемся альтернативные селекторы
            if not products:
                for item in soup.find_all('div'):
                    if any(attr in str(item.get('class', [])).lower() for attr in ['product', 'item', 'catalog']):
                        product = self.extract_product_info(item, domain)
                        if product:
                            products.append(product)
            
            return products
        
        except Exception as e:
            return {'error': f'Ошибка при парсинге: {str(e)}'}
    
    def extract_product_info(self, element, domain):
        """Извлекает информацию о товаре из элемента"""
        try:
            # Ищем название
            name_elem = element.find(['h2', 'h3', 'h4', 'a', 'span'], class_=['name', 'title', 'product-name'])
            name = name_elem.get_text(strip=True) if name_elem else None
            
            # Ищем артикул
            article_elem = element.find(['span', 'div', 'p'], class_=['article', 'sku', 'code', 'артикул'])
            article = article_elem.get_text(strip=True) if article_elem else None
            
            # Ищем модель
            model_elem = element.find(['span', 'div', 'p'], class_=['model', 'модель'])
            model = model_elem.get_text(strip=True) if model_elem else None
            
            # Если не нашли через классы, ищем в тексте
            if not article or not name:
                all_text = element.get_text(separator=' ', strip=True)
                if len(all_text) < 500:  # Чтобы не брать огромные блоки
                    if not name or len(name) < 5:
                        name = all_text[:100]
                    if not article:
                        article = name[:20] if name else 'N/A'
            
            if name and len(name) > 3:
                return {
                    'article': article or 'N/A',
                    'name': name[:200],
                    'model': model or 'N/A',
                    'source_domain': domain
                }
        except:
            pass
        
        return None

class ProductComparator:
    def __init__(self):
        self.similarity_threshold = 0.6
    
    def compare_products(self, all_products):
        """
        Сравнивает товары и группирует похожие
        Возвращает: {similar_products: [...], unique_products: [...]}
        """
        matched_groups = []
        used_indices = set()
        
        for i in range(len(all_products)):
            if i in used_indices:
                continue
            
            group = [all_products[i]]
            used_indices.add(i)
            
            for j in range(i + 1, len(all_products)):
                if j in used_indices:
                    continue
                
                if self.is_similar(all_products[i], all_products[j]):
                    group.append(all_products[j])
                    used_indices.add(j)
            
            if len(group) > 1:
                matched_groups.append(group)
            else:
                # Добавляем даже неуникальные товары в результат
                matched_groups.append(group)
        
        # Разделяем на похожие и уникальные
        similar = [group for group in matched_groups if len(group) > 1]
        unique = [group[0] for group in matched_groups if len(group) == 1]
        
        return {
            'similar_products': similar,
            'unique_products': unique,
            'total_products': len(all_products)
        }
    
    def is_similar(self, product1, product2):
        """Проверяет схожесть двух товаров"""
        # Сравниваем названия
        name_similarity = self.get_similarity(
            product1['name'].lower(),
            product2['name'].lower()
        )
        
        # Сравниваем артикули
        article_similarity = self.get_similarity(
            product1['article'].lower(),
            product2['article'].lower()
        )
        
        # Если артикули совпадают или очень похожи, это скорее всего одно и то же
        if article_similarity > 0.8:
            return True
        
        # Если названия достаточно похожи
        if name_similarity > self.similarity_threshold:
            return True
        
        return False
    
    def get_similarity(self, str1, str2):
        """Получает коэффициент схожести двух строк"""
        return SequenceMatcher(None, str1, str2).ratio()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def scrape():
    # keep the old scrape behaviour for backwards compatibility
    # (it still powers the previous comparison UI if needed)
    return "not implemented", 501


@app.route('/api/categories', methods=['GET'])
def categories_list():
    """Return the list of available reference-site categories.

    The frontend uses this to populate its category dropdown dynamically.
    """
    session = create_session()
    cats = get_prohockey_categories(session)
    return jsonify({'categories': cats})


@app.route('/api/check', methods=['POST'])
def check_missing():
    print("=" * 50)
    print("📨 Received check request")
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()
    urls = data.get('urls', [])
    category = data.get('category') or None  # convert empty string to None
    if not urls:
        return jsonify({'error': 'Не указаны URL'}), 400

    session = create_session()
    main_products = fetch_main_site_products(session, [category] if category else None)
    print(f"Main site items: {len(main_products)} (category={category})")

    missing = []
    scanned = 0
    for url in urls:
        if not url.startswith('http'):
            url = 'https://' + url
        print(f"checking other site: {url} (category={category})")
        others = fetch_other_site_products(session, url, category=category)
        scanned += len(others)
        for p in others:
            if not product_exists_on_main(p['name']):
                p['status'] = 'нема такого товару'
                missing.append(p)

    return jsonify({
        'missing': missing,
        'total': len(missing),
        'total_urls': len(urls),
        'scanned': scanned,
    })

@app.route('/api/parse-example', methods=['POST'])
def parse_example():
    """Парсит пример товаров для демонстрации"""
    data = request.json
    html_content = data.get('html', '')
    
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    for row in soup.find_all('tr')[1:]:  # Пропускаем header
        cols = row.find_all('td')
        if len(cols) >= 3:
            products.append({
                'article': cols[0].get_text(strip=True),
                'name': cols[1].get_text(strip=True),
                'model': cols[2].get_text(strip=True),
                'source_domain': 'example'
            })
    
    return jsonify({'products': products})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
