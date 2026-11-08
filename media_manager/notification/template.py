"""Shared, email-client-friendly MediaManager layout; all dynamic text is escaped."""
from html import escape

def render(title,body,link=None,language='de',details=None):
    esc=lambda value:escape(str(value),quote=True)
    rows=''.join(f'<tr><td style="padding:8px 0;color:#a3a3a3;width:35%">{esc(k)}</td><td style="padding:8px 0;color:#fafafa">{esc(v)}</td></tr>' for k,v in (details or {}).items())
    button='Öffnen' if language=='de' else 'Open'
    action=f'<a href="{esc(link)}" style="display:inline-block;background:#fafafa;color:#171717;padding:13px 22px;border-radius:10px;text-decoration:none;font-weight:bold">{button}</a>' if link else ''
    footer='Du kannst deine Benachrichtigungen in deinem MediaManager-Konto verwalten.' if language=='de' else 'Manage your notifications in your MediaManager account.'
    return f'''<!doctype html><html lang="{esc(language)}"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#090909;color:#fafafa;font-family:Arial,Helvetica,sans-serif"><!-- mm-email-layout --><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:32px 16px"><table role="presentation" width="100%" style="max-width:580px"><tr><td style="padding:8px 0 24px"><img src="cid:mediamanager-logo" width="44" height="44" alt="" style="vertical-align:middle;margin-right:12px"><span style="font-size:23px;font-weight:bold;color:#fafafa">MediaManager</span></td></tr><tr><td style="background:#171717;border:1px solid #333;border-radius:18px;padding:28px"><h1 style="font-size:24px;margin:0 0 20px">{esc(title)}</h1><p style="line-height:1.7;color:#d4d4d4;white-space:pre-line">{body}</p><table width="100%" style="font-size:14px">{rows}</table><div style="margin-top:24px">{action}</div></td></tr><tr><td style="padding:20px 4px;color:#a3a3a3;font-size:12px;line-height:1.6">{footer}</td></tr></table></td></tr></table></body></html>'''
