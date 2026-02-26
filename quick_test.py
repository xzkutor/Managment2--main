from parser import create_session, fetch_other_site_products

session = create_session()
print('explicit hockeyshans')
res = fetch_other_site_products(session, 'hockeyshans.com.ua/category/2', category=None)
print('count', len(res))
print(res[:5])
print('root hockeyshans')
res2 = fetch_other_site_products(session, 'hockeyshans.com.ua', category=None)
print('count2', len(res2))
print(res2[:5])
