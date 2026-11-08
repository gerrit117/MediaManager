"""Compare card geometry and modal motion against the synthetic managed-stack fixture.

Usage: python tests/browser/card_alignment.py TEST_ACCESS_JSON OUTPUT_DIRECTORY
Requires Playwright with Chromium and WebKit installed.
"""
import json,re,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
access=json.loads(Path(sys.argv[1]).read_text());assert access['project'].startswith('mmtest-')
base=access['base'];errors=[];writes=[];checks=[]
poster='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22300%22%3E%3Crect width=%22200%22 height=%22300%22 fill=%22%232d4565%22/%3E%3C/svg%3E'
rows=[dict(name='Short',year=2026,poster_path=poster,overview='Short description.',external_id=9000000,metadata_provider='tmdb',added=True,vote_average=8.6),dict(name='An extremely long series title with a year that wraps onto several lines',year=2025,poster_path=poster.replace('width=%22200%22','width=%22500%22').replace('%232d4565','%23534565'),overview='A much longer description. '*80,external_id=9000001,metadata_provider='tmdb',added=False,vote_average=7.2),dict(name='No poster or rating',year=None,poster_path=None,overview=None,external_id=9000002,metadata_provider='tmdb',added=False,vote_average=None)]
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=getattr(p,engine).launch()
  for role in ['admin','user']:
   ctx=browser.new_context(locale='de-DE',viewport={'width':390,'height':844},is_mobile=True,has_touch=True,color_scheme='dark')
   for _ in range(60):
    try:
     if ctx.request.get(base+'/api/v1/health').status==200:break
    except Exception:pass
    time.sleep(1)
   assert ctx.request.post(base+'/api/v1/auth/cookie/login',form={'username':role+'@example.com','password':access['password']}).status==204
   rows[0]['id']=ctx.request.get(base+'/api/v1/movies').json()[0]['id']
   ctx.route('**/api/v1/discover/**',lambda r:r.fulfill(status=200,json={'results':rows,'total_pages':1,'total_results':3,'page':1}))
   def metadata(r):
    row=next(x for x in rows if str(x['external_id'])==r.request.url.split('?')[0].split('/')[-1]);r.fulfill(status=200,json={**row,'seasons':[{'number':1,'episodes':[{'number':1,'title':'One'}]}]})
   ctx.route('**/api/v1/requests/preview/**',metadata)
   page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
   for width in [390,1440]:
    page.set_viewport_size({'width':width,'height':844 if width==390 else 1000});page.goto(base+'/web/dashboard/',wait_until='domcontentloaded');cards=page.locator('[data-media-card]');cards.nth(2).wait_for();page.get_by_role('button',name=re.compile('^Ausstehend')).first.wait_for();page.wait_for_function('document.querySelectorAll("[data-media-card]").length===6');page.evaluate('document.fonts.ready');page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    def boxes(n):
     c=cards.nth(n);return {'card':c.bounding_box(),'poster':c.locator('button[aria-label]').bounding_box(),'footer':c.locator(':scope > div').nth(2).bounding_box(),'action':c.locator(':scope > div').nth(2).locator('button,a').nth(1).bounding_box()}
    a,b=boxes(0),boxes(1)
    for part in ['poster','footer','action']:
     for key in ['y','height']:assert abs(a[part][key]-b[part][key])<1.1,(engine,role,width,part,key,a,b)
    assert abs(a['poster']['height']/a['poster']['width']-1.5)<0.01
    assert a['action']['height']==56
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    if width==390:page.screenshot(path=str(output/f'alignment-{engine}-{role}-cards.png'),full_page=True)
    details=[]
    for i in [0,1]:
     cards.nth(i).get_by_role('button',name='Details ansehen',exact=True).click();dialog=page.get_by_role('dialog');dialog.get_by_role('heading',name=rows[i]['name'],exact=True).wait_for();dialog.get_by_text('1 Staffel',exact=True).wait_for()
     assert dialog.get_by_role('heading',name=rows[i]['name'],exact=True).evaluate('(e)=>document.activeElement===e')
     close=dialog.get_by_role('button',name='Schließen',exact=True)
     details.append({'frame':dialog.bounding_box(),'close':close.bounding_box(),'shadow':close.evaluate('(e)=>getComputedStyle(e).boxShadow'),'actions':dialog.locator('[data-preview-actions]').bounding_box()})
     assert close.bounding_box()['width']==44 and close.bounding_box()['height']==44
     assert dialog.evaluate('(e)=>getComputedStyle(e).animationName')=='mm-dialog-show'
     assert float(dialog.evaluate('(e)=>getComputedStyle(e).animationDuration').removesuffix('s'))<=0.15
     assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth')
     if i==1:assert dialog.locator('[data-preview-description]').evaluate('(e)=>e.scrollHeight>e.clientHeight')
     if width==390:page.screenshot(path=str(output/f'alignment-{engine}-{role}-preview-{i}.png'))
     close.click();dialog.wait_for(state='hidden')
    for part in ['frame','close','actions']:
     for key in ['x','y','width','height']:assert abs(details[0][part][key]-details[1][part][key])<1.1,(part,key,details)
    assert details[0]['shadow']==details[1]['shadow']
    frames=page.evaluate('''() => {const found=[];function scan(rules){for(const r of rules){if(r.type===7&&r.name.startsWith('mm-dialog-'))found.push([...r.cssRules].map(k=>[...k.style]));else if(r.cssRules)scan(r.cssRules);}}for(const s of document.styleSheets){try{scan(s.cssRules)}catch{}}return found;}''')
    assert len(frames)>=2 and all(props==['opacity'] for frame in frames for props in frame),frames
   page.emulate_media(reduced_motion='reduce');cards.nth(1).get_by_role('button',name='Details ansehen',exact=True).click();dialog=page.get_by_role('dialog');assert dialog.evaluate('(e)=>getComputedStyle(e).animationDuration')=='0.001s';page.keyboard.press('Escape');dialog.wait_for(state='hidden')
   checks.append(engine+' '+role+': equal card geometry, stable preview/close/footer, opacity-only fast animation, reduced motion, mobile/desktop passed');ctx.close()
  browser.close()
 assert not errors,errors;assert not writes,writes
 (output/'card-alignment-result.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'real_downloads_started':0},indent=2));print(json.dumps(checks))
