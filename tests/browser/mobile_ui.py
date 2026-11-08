"""Mobile regression checks against the synthetic managed-stack fixture.

Usage: python tests/browser/mobile_ui.py TEST_ACCESS_JSON OUTPUT_DIRECTORY
Requires Playwright with Chromium and WebKit installed. Never use production data.
"""
import json,re,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
access=json.loads(Path(sys.argv[1]).read_text());assert access['project'].startswith('mmtest-')
base=access['base'];errors=[];writes=[];summary=[]
releases=[dict(id=str(i),title=('Own.Extremely.Long.Release.Name.'*3)+('German.1080p.BluRay.DTS-HD' if i%2==0 else 'English.2160p.WEB.AAC'),size=(i+1)*1024**3,usenet=i%3!=0,seeders=25,score=100-i,indexer='Synthetic indexer',flags=[],season='1',age=1000) for i in range(24)]
def overflow(page):assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),page.url
def discovery(route):return route.fulfill(status=200,json={'results':[],'total_pages':1,'page':1,'total_results':0})
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=getattr(p,engine).launch()
  admin=browser.new_context(locale='en-US',viewport={'width':390,'height':844},is_mobile=True,has_touch=True,color_scheme='dark')
  for attempt in range(60):
   try:
    if admin.request.get(base+'/api/v1/health').status==200:break
   except Exception:pass
   time.sleep(1)
  assert admin.request.post(base+'/api/v1/auth/cookie/login',form={'username':'admin@example.com','password':access['password']}).status==204
  movie=admin.request.get(base+'/api/v1/movies').json()[0]
  show=next(s for s in admin.request.get(base+'/api/v1/tv/shows').json() if s.get('seasons'))
  admin.route('**/api/v1/discover/**',discovery)
  admin.route('**/api/v1/movies/*/torrents*',lambda r:r.fulfill(status=200,json=releases))
  admin.route('**/api/v1/tv/torrents?*',lambda r:r.fulfill(status=200,json=releases))
  page=admin.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
  page.goto(base+'/web/dashboard/',wait_until='domcontentloaded');page.get_by_role('heading',name='Overview',exact=True).wait_for()
  stats=page.locator('section[aria-label="Request center"] > div').first
  assert stats.evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length')==2
  assert stats.bounding_box()['height']<220
  overflow(page);page.screenshot(path=str(output/f'mobile-{engine}-overview.png'),full_page=True)
  page.get_by_role('button',name='Toggle Sidebar',exact=True).click()
  sheet=page.locator('[data-mobile="true"]');sheet.wait_for(state='visible')
  link=sheet.get_by_role('link',name='Add a movie',exact=True)
  assert link.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')>=16
  assert link.bounding_box()['height']>=44
  link.click();sheet.wait_for(state='hidden');page.get_by_role('heading',name='Search movies',exact=True).wait_for()
  assert page.locator('main img').count()==0
  assert page.locator('main').last.bounding_box()['x']>=0
  assert page.get_by_role('button',name='Search',exact=True).is_disabled()
  page.get_by_text('Advanced Settings',exact=True).click();page.get_by_text('TMDB (Recommended)',exact=True).wait_for(state='visible')
  admin.route('**/api/v1/movies/search?*',lambda r:r.fulfill(status=200,json=[dict(name='Own search result',external_id=9000000,metadata_provider='tmdb',overview='Synthetic result',added=False,poster_path=None,year=2026)]))
  page.locator('#search-box').fill('Own');page.get_by_role('button',name='Search',exact=True).click();page.get_by_text('Own search result',exact=False).first.wait_for()
  overflow(page);page.screenshot(path=str(output/f'mobile-{engine}-search.png'),full_page=True)
  page.goto(base+'/web/dashboard/tv/add-show/',wait_until='domcontentloaded');page.get_by_role('heading',name='Search series',exact=True).wait_for();assert page.locator('main img').count()==0;overflow(page)
  page.goto(base+'/web/dashboard/movies/'+movie['id']+'/',wait_until='domcontentloaded');page.get_by_role('button',name='Download Movie',exact=True).wait_for()
  assert page.get_by_role('button',name='Request Movie',exact=True).count()==0
  # Action cards should size to their content instead of growing to poster height.
  for title in ['Administrator Controls','Download Options']:
   box=page.get_by_text(title,exact=True).locator('..').locator('..').bounding_box();assert box['height']<330,(title,box)
  page.get_by_role('button',name='Download Movie',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('button',name='Search indexers',exact=True).click()
  dialog.locator('.release-results tbody tr').first.wait_for();assert dialog.locator('.release-results tbody tr').count()==10
  assert dialog.locator('.release-results tbody tr').first.evaluate('(e)=>getComputedStyle(e).display')=='grid'
  assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth'),dialog.evaluate('(e)=>[e.scrollWidth,e.clientWidth]')
  assert dialog.locator('.release-results').evaluate('(e)=>e.scrollHeight<=e.clientHeight+1')
  page.screenshot(path=str(output/f'mobile-{engine}-releases.png'))
  dialog.get_by_role('button',name='Next',exact=True).click();assert dialog.get_by_text('2 / 3',exact=True).count()==1
  dialog.locator('summary').click();dialog.get_by_role('button',name='1080p',exact=True).click();assert dialog.get_by_text('1 / 2',exact=True).count()==1
  assert all('1080p' in text for text in dialog.locator('.release-results tbody tr td:first-child').all_text_contents())
  dialog.get_by_role('button',name='Reset filters',exact=True).click();dialog.get_by_role('combobox',name='Sort',exact=True).select_option('size')
  assert dialog.locator('.release-results tbody tr').first.get_by_text('Torrent',exact=True).count()==1
  dialog.get_by_role('button',name='Download',exact=True).first.click();suffix=page.get_by_role('dialog',name='Set File Path Suffix');suffix.wait_for();suffix.get_by_role('button',name='Cancel',exact=True).click();suffix.wait_for(state='hidden')
  dialog.get_by_role('button',name='Close',exact=True).click()
  # Desktop keeps sortable table, while the same DOM shows cards on mobile.
  page.set_viewport_size({'width':1440,'height':1000});page.get_by_role('button',name='Download Movie',exact=True).click();dialog=page.get_by_role('dialog');assert dialog.locator('.release-results tbody tr').first.evaluate('(e)=>getComputedStyle(e).display')=='table-row'
  dialog.get_by_role('button',name='Close',exact=True).click()
  page.goto(base+'/web/dashboard/tv/'+show['id']+'/',wait_until='domcontentloaded');assert page.get_by_role('button',name='Request Season',exact=True).count()==0
  page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='Download Season',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('button',name='Search indexers',exact=True).click();dialog.locator('.release-results tbody tr').first.wait_for();assert dialog.locator('.release-results tbody tr').count()==10;assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth');dialog.get_by_role('button',name='Close',exact=True).click()
  # User still has request-only actions and no direct download route.
  user=browser.new_context(locale='en-US',viewport={'width':390,'height':844})
  assert user.request.post(base+'/api/v1/auth/cookie/login',form={'username':'user@example.com','password':access['password']}).status==204
  user.route('**/api/v1/discover/**',discovery);up=user.new_page();up.on('pageerror',lambda e:errors.append(str(e)))
  up.goto(base+'/web/dashboard/movies/'+movie['id']+'/',wait_until='domcontentloaded');up.get_by_role('button',name='Request Movie',exact=True).wait_for();assert up.get_by_role('button',name='Download Movie',exact=True).count()==0;overflow(up)
  page.evaluate("localStorage.setItem('mediamanager-language','de')");page.goto(base+'/web/dashboard/movies/add-movie/',wait_until='domcontentloaded');page.get_by_role('heading',name='Filme suchen',exact=True).wait_for()
  summary.append(engine+' mobile navigation, search, overview, roles, releases, filtering, pagination, suffix dialog and desktop table passed');browser.close()
 assert not errors,errors
 assert not writes,writes
 (output/'mobile-ui-result.json').write_text(json.dumps({'checks':summary,'page_errors':errors,'downloads_started':0},indent=2));print(json.dumps(summary))
