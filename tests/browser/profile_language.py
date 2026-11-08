"""Profile-language checks against the synthetic managed-stack fixture.

Usage: python tests/browser/profile_language.py TEST_ACCESS_JSON OUTPUT_DIRECTORY
Requires Playwright with Chromium and WebKit installed.
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
access=json.loads(Path(sys.argv[1]).read_text());assert access['project'].startswith('mmtest-')
base=access['base'];errors=[];writes=[];checks=[]
with sync_playwright() as p:
 for engine in ['chromium','webkit']:
  browser=getattr(p,engine).launch()
  def context(role,locale='en-US',legacy=None):
   c=browser.new_context(locale=locale,viewport={'width':390,'height':844})
   assert c.request.post(base+'/api/v1/auth/cookie/login',form={'username':role+'@example.com','password':access['password']}).status==204
   if legacy:c.add_init_script('localStorage.setItem("mediamanager-language",'+json.dumps(legacy)+')')
   return c
  a=context('admin');u=context('user');old_a=a.request.get(base+'/api/v1/users/me').json();old_u=u.request.get(base+'/api/v1/users/me').json()
  def patch(c,language):assert c.request.patch(base+'/api/v1/users/me',data={'preferred_language':language}).status==200
  patch(a,None);patch(u,None)
  legacy=context('user',legacy='de');page=legacy.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append((r.method,r.url)) if r.method not in ['GET','HEAD','OPTIONS'] else None)
  page.goto(base+'/web/dashboard/settings/',wait_until='domcontentloaded');page.get_by_role('heading',name='Einstellungen',exact=True).wait_for();select=page.get_by_role('combobox',name='Sprache',exact=True);assert select.input_value()=='de';assert u.request.get(base+'/api/v1/users/me').json()['preferred_language'] is None
  page.get_by_role('button',name='Sprache im Profil speichern',exact=True).click();page.get_by_role('status').filter(has_text='Sprache gespeichert.').wait_for();assert u.request.get(base+'/api/v1/users/me').json()['preferred_language']=='de'
  page.screenshot(path=str(output/f'profile-language-{engine}-saved.png'),full_page=True)
  # A fresh browser with English defaults must use the saved German profile.
  second=context('user','en-US');sp=second.new_page();sp.on('pageerror',lambda e:errors.append(str(e)));sp.goto(base+'/web/dashboard/settings/',wait_until='domcontentloaded');sp.get_by_role('heading',name='Einstellungen',exact=True).wait_for();assert sp.get_by_role('combobox',name='Sprache',exact=True).input_value()=='de'
  sp.get_by_role('combobox',name='Sprache',exact=True).select_option('en');sp.get_by_role('status').filter(has_text='Language saved.').wait_for();assert u.request.get(base+'/api/v1/users/me').json()['preferred_language']=='en';sp.get_by_role('heading',name='Settings',exact=True).wait_for()
  sp.evaluate('localStorage.clear()');sp.reload(wait_until='domcontentloaded');sp.get_by_role('heading',name='Settings',exact=True).wait_for();assert sp.get_by_role('combobox',name='Language',exact=True).input_value()=='en'
  # Another account can use another language in the same browser.
  patch(a,'de');assert second.request.post(base+'/api/v1/auth/cookie/login',form={'username':'admin@example.com','password':access['password']}).status==204
  sp.goto(base+'/web/dashboard/settings/',wait_until='domcontentloaded');sp.get_by_role('heading',name='Einstellungen',exact=True).wait_for();assert a.request.get(base+'/api/v1/users/me').json()['preferred_language']=='de';assert u.request.get(base+'/api/v1/users/me').json()['preferred_language']=='en'
  third=context('user','de-DE');tp=third.new_page();tp.on('pageerror',lambda e:errors.append(str(e)));tp.goto(base+'/web/dashboard/settings/',wait_until='domcontentloaded');tp.get_by_role('heading',name='Settings',exact=True).wait_for()
  def fail(r):r.fulfill(status=503,json={'detail':'Synthetic save failure'}) if r.request.method=='PATCH' else r.continue_()
  third.route('**/api/v1/users/me',fail);tp.get_by_role('combobox',name='Language',exact=True).select_option('de');tp.get_by_role('alert').filter(has_text='Language could not be saved. Please try again.').wait_for();assert tp.get_by_role('combobox',name='Language',exact=True).input_value()=='en';assert u.request.get(base+'/api/v1/users/me').json()['preferred_language']=='en'
  # Core account fields, verification and request permissions are untouched.
  assert a.request.get(base+'/api/v1/users/me').json()=={**old_a,'preferred_language':'de'}
  assert u.request.get(base+'/api/v1/users/me').json()=={**old_u,'preferred_language':'en'}
  patch(a,old_a.get('preferred_language'));patch(u,old_u.get('preferred_language'))
  checks.append(engine+': legacy browser fallback, explicit profile save, fresh-device restore, browser-storage clearing, account isolation/switch and save-error recovery passed');browser.close()
 assert not errors,errors;assert all(method=='PATCH' and url.endswith('/api/v1/users/me') for method,url in writes),writes
 (output/'profile-language-result.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'real_downloads_started':0},indent=2));print(json.dumps(checks))
