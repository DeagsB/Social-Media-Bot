from connectors.facebook_connector import FacebookConnector
print('creating')
c = FacebookConnector(dry_run=True)
print('posting')
print(c.post('hello'))
print('done')
