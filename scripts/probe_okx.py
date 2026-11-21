import json
from urllib.parse import urlencode
from urllib.request import Request,urlopen
for endpoint in ['contracts/open-interest-history','taker-volume-contract']:
    url='https://www.okx.com/api/v5/rubik/stat/'+endpoint+'?'+urlencode(dict(instId='BTC-USDT-SWAP',period='1H',limit=3))
    try:
        with urlopen(Request(url,headers={'User-Agent':'python-research/1','Accept':'application/json'}),timeout=15) as r:
            body=json.loads(r.read())
        print(endpoint,'HTTP_OK',body.get('code'),str(body.get('msg'))[:80],str(body.get('data'))[:700])
    except Exception as e:print(endpoint,'ERROR',type(e).__name__,str(e)[:300])
