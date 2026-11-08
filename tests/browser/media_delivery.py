"""Browser coverage against a disposable managed stack; no real downloads."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
access=json.loads(Path(sys.argv[1]).read_text());assert access['project'].startswith('mmtest-')
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True);base=access['base'];errors=[];checks=[]
with sync_playwright() as p:
 for name in ['chromium','webkit']:
  browser=getattr(p,name).launch();ctx=browser.new_context(viewport={'width':390,'height':844},locale='en-US')
  assert ctx.request.post(base+'/api/v1/auth/cookie/login',form={'username':'admin@example.com','password':access['password']}).status==204
  assert ctx.request.patch(base+'/api/v1/users/me',data={'preferred_language':'en'}).status==200
  page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
  page.goto(base+'/web/dashboard/settings/',wait_until='networkidle')
  page.get_by_role('tab',name='Notifications',exact=True).click();page.get_by_role('heading',name='Notifications',exact=True).wait_for()
  page.get_by_text('New requests',exact=True).wait_for();page.get_by_role('button',name='Save notification settings',exact=True).click();page.get_by_role('status').filter(has_text='Notification settings saved.').wait_for()
  if not page.evaluate('window.isSecureContext'):assert not page.get_by_role('button',name='Enable push on this device',exact=True).is_enabled() # No fake permission grant.
  page.screenshot(path=str(output/f'notifications-{name}-390.png'),full_page=True)
  page.get_by_role('tab',name='Emby',exact=True).click();page.get_by_role('heading',name='Emby',exact=True).wait_for();assert page.get_by_label('Emby API key',exact=True).get_attribute('type')=='password'
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
  page.screenshot(path=str(output/f'emby-{name}-390.png'),full_page=True)
  movies=ctx.request.get(base+'/api/v1/movies').json();movie=movies[0]
  page.goto(base+'/web/dashboard/movies/'+movie['id']+'/',wait_until='networkidle')
  button=page.get_by_role('button',name='Protect from automatic upgrades',exact=True);button.wait_for();button.click();page.get_by_role('button',name='Protected from upgrades',exact=True).wait_for()
  result=ctx.request.get(base+'/api/v1/media-controls/protection/movie/'+movie['id']).json();assert result['own_lock']
  page.get_by_role('button',name='Protected from upgrades',exact=True).click()
  # PWA metadata is served as ordinary static assets; worker deliberately has no fetch/cache handler.
  manifest=ctx.request.get(base+'/web/manifest.webmanifest').json();assert manifest['display']=='standalone';assert ctx.request.get(base+'/web/push-worker.js').status==200
  user=browser.new_context(viewport={'width':390,'height':844},locale='en-US');assert user.request.post(base+'/api/v1/auth/cookie/login',form={'username':'user@example.com','password':access['password']}).status==204
  assert user.request.patch(base+'/api/v1/users/me',data={'preferred_language':'en'}).status==200
  assert user.request.get(base+'/api/v1/media-controls/emby/matches').status==403
  assert user.request.put(base+'/api/v1/media-controls/protection/movie/'+movie['id'],data={'locked':True}).status==403
  pref=user.request.get(base+'/api/v1/account-notifications/preferences').json();assert 'request_created' not in pref['categories'];assert 'vapid_public_key' in pref
  up=user.new_page();up.on('pageerror',lambda error:errors.append(str(error)));up.goto(base+'/web/dashboard/settings/',wait_until='networkidle');up.get_by_role('tab',name='Notifications',exact=True).click();up.get_by_role('heading',name='Notifications',exact=True).wait_for();assert up.get_by_role('tab',name='Emby',exact=True).count()==0
  assert user.request.put(base+'/api/v1/account-notifications/preferences',data={'categories':{'request_created':{'email':True,'push':True}}}).status==400
  up.screenshot(path=str(output/f'user-notifications-{name}-390.png'),full_page=True)
  assert up.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
  checks.append(name+': mobile notifications, masked Emby settings, protection, permission isolation and PWA assets passed');browser.close()
assert not errors,errors
(output/'result.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'real_downloads':0},indent=2));print(json.dumps(checks))
