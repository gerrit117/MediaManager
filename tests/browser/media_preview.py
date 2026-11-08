"""Read-only media preview checks against the synthetic managed-stack fixture.

Usage: python tests/browser/media_preview.py TEST_ACCESS_JSON OUTPUT_DIRECTORY
Requires Playwright with Chromium and WebKit installed.
"""
import json,re,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
access=json.loads(Path(sys.argv[1]).read_text());assert access['project'].startswith('mmtest-')
base=access['base'];errors=[];writes=[];summary=[]
text='Full description, including the final sentence.\nThis is the untruncated ending.'
fixture=dict(name='Own preview movie',external_id=9000000,metadata_provider='tmdb',overview='Search summary',poster_path='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22300%22%3E%3Crect width=%22200%22 height=%22300%22 fill=%22%232d4565%22/%3E%3C/svg%3E',year=2026,added=False,vote_average=7.8,original_language='de')
metadata=dict(name=fixture['name'],year=2026,overview=text,seasons=[dict(number=1,name='Season 1',episodes=[dict(number=1,title='Episode 1')])])
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=getattr(p,engine).launch()
  for role in ['admin','user']:
   ctx=browser.new_context(locale='en-US',viewport={'width':390,'height':844},is_mobile=True,has_touch=True,color_scheme='dark')
   for _ in range(60):
    try:
     if ctx.request.get(base+'/api/v1/health').status==200:break
    except Exception:pass
    time.sleep(1)
   assert ctx.request.post(base+'/api/v1/auth/cookie/login',form={'username':role+'@example.com','password':access['password']}).status==204
   before={path:[x['id'] for x in ctx.request.get(base+path).json()] for path in ['/api/v1/movies','/api/v1/tv/shows']}
   quota=ctx.request.get(base+'/api/v1/requests/quota').json()['used']
   ctx.route('**/api/v1/discover/**',lambda r:r.fulfill(status=200,json={'results':[fixture],'total_results':1,'total_pages':1,'page':1}) if '/options' not in r.request.url else r.fulfill(status=200,json={'providers':[],'genres':[],'regions':[{'id':'DE','name':'Germany'}]}))
   ctx.route('**/api/v1/movies/search?*',lambda r:r.fulfill(status=200,json=[fixture]))
   failing=[False]
   ctx.route('**/api/v1/requests/preview/**',lambda r:r.fulfill(status=502 if failing[0] else 200,json={'detail':'Could not load title metadata. Please try again.'} if failing[0] else metadata))
   ctx.route('**/api/v1/movies?*',lambda r:r.fulfill(status=503,json={'detail':'Synthetic add error'}) if r.request.method=='POST' else r.continue_())
   page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
   for route in ['/web/dashboard/','/web/dashboard/movies/discover/','/web/dashboard/movies/add-movie/']:
    page.goto(base+route,wait_until='domcontentloaded')
    if 'add-movie' in route:page.locator('#search-box').fill('Own');page.get_by_role('button',name='Search',exact=True).click()
    page.get_by_role('button',name='Show details',exact=True).last.click();dialog=page.get_by_role('dialog');dialog.get_by_text(text,exact=True).wait_for()
    assert dialog.get_by_text('7.8/10',exact=False).count()==1
    assert dialog.get_by_text('Original language: DE',exact=True).count()==1
    assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    if role=='user':
     assert dialog.get_by_role('button',name='Add movie',exact=True).count()==0
     dialog.get_by_role('button',name='Request movie',exact=True).click();request=page.get_by_role('dialog').filter(has=page.get_by_role('button',name='Submit request',exact=True));request.get_by_text(text,exact=True).wait_for();request.get_by_role('button',name='Close',exact=True).first.click();request.wait_for(state='hidden')
    else:
     assert dialog.get_by_role('button',name='Request movie',exact=True).count()==0
     dialog.get_by_role('button',name='Add movie',exact=True).click();dialog.get_by_text('Synthetic add error',exact=True).wait_for()
    page.screenshot(path=str(output/f'preview-{engine}-{role}.png'))
    dialog.get_by_role('button',name='Close',exact=True).click();dialog.wait_for(state='hidden')
   # Both cover/title triggers open the same preview. A metadata failure keeps the search summary visible.
   failing[0]=True;page.get_by_role('button',name='Show details: Own preview movie',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('alert').wait_for();dialog.get_by_text('Search summary',exact=True).wait_for();dialog.get_by_role('button',name='Close',exact=True).click();dialog.wait_for(state='hidden');failing[0]=False
   page.get_by_role('button',name='Own preview movie',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_text(text,exact=True).wait_for();page.keyboard.press('Escape');dialog.wait_for(state='hidden')
   page.goto(base+'/web/dashboard/',wait_until='domcontentloaded');page.get_by_role('button',name='Show details',exact=True).first.click();dialog=page.get_by_role('dialog');dialog.get_by_text('Series details',exact=True).wait_for();dialog.get_by_text(text,exact=True).wait_for();assert dialog.get_by_role('button',name='Add series' if role=='admin' else 'Request series',exact=True).count()==1;dialog.get_by_role('button',name='Close',exact=True).click();dialog.wait_for(state='hidden')
   fixture.update(added=True,id=before['/api/v1/movies'][0]);page.goto(base+'/web/dashboard/movies/add-movie/',wait_until='domcontentloaded');page.locator('#search-box').fill('Own');page.get_by_role('button',name='Search',exact=True).click();page.get_by_role('button',name='Show details',exact=True).click();dialog=page.get_by_role('dialog');link=dialog.get_by_role('link',name='Open in library',exact=True);link.wait_for();assert before['/api/v1/movies'][0] in link.get_attribute('href');dialog.get_by_role('button',name='Close',exact=True).click();dialog.wait_for(state='hidden');fixture['added']=False;fixture.pop('id')
   page.evaluate("localStorage.setItem('mediamanager-language','de')");page.reload(wait_until='domcontentloaded');page.locator('#search-box').fill('Own');page.get_by_role('button',name='Suchen',exact=True).click();page.get_by_role('button',name='Details ansehen',exact=True).click();page.get_by_role('dialog').get_by_text('Beschreibung',exact=True).wait_for()
   assert before=={path:[x['id'] for x in ctx.request.get(base+path).json()] for path in before}
   assert ctx.request.get(base+'/api/v1/requests/quota').json()['used']==quota
   summary.append(engine+' '+role+': overview/discovery/search, complete metadata, roles, nested request, error fallback, mobile layout, DE/EN passed');ctx.close()
  browser.close()
 assert not errors,errors
 assert all('/api/v1/movies?' in url for url in writes),writes
 (output/'media-preview-result.json').write_text(json.dumps({'checks':summary,'page_errors':errors,'real_requests_and_library_adds':0},indent=2));print(json.dumps(summary))
