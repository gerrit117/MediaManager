# Accounts and requests

MediaManager has two roles: **Admin** and **User**. Administrators manage the library, downloaders, approvals, invitations and account limits. Users request movies, seasons or individual episodes directly from search, discovery or movie collections. Ordinary users cannot create library entries or access the downloader administration endpoints.

Newly requested titles are kept as hidden catalogue metadata until files are successfully imported. Existing library records and administrator-added titles retain their normal behavior. The Requests pages show only the signed-in user's requests; administrators see all requests. Pending, approved, in-progress and finished filters use current download and file availability information. The overview shows the request center and the same TMDB weekly trends used by Discover. The old recommendation service has been replaced; compatibility endpoints delegate to TMDB discovery.

## Quotas

An administrator sets a shared monthly limit and optional automatic approval per user. A movie costs one unit. A season costs one unit whether requested as a season or initially as an episode. Further episodes and later requests for that same season do not consume another unit for that user, including after a month changes. Different seasons cost separate units. The same movie is not charged again for a later request at another quality.

Accounting is enforced server-side under the account's database lock. Deleting a request does not refund its charge. Existing retained requests are assigned their movie/season scope during migration; older accounting entries whose requests were already deleted remain counted without guessing their identity. Monthly usage resets at midnight on the first day of the month in Europe/Berlin; the overview displays the reset date and remaining quota.

Download workers continue to apply the configured release rules for all protocols. Active downloads are shared by requests for the same media; requesting a title from another account must not submit an already running download again. Library scanning and administrative imports remain available.

## Email and registration

Configure **Settings → Email & accounts**: SMTP host, port, sender address, optional login, and STARTTLS or implicit TLS. IMAP is not required. SMTP settings are private, persistent and applied without restarting the container. Use **Test connection** to check the connection/login and **Send test email** to test delivery. Test success confirms SMTP acceptance; an inbox/spam filter can still affect arrival.

The same connection sends confirmation, recovery and administrator notification emails. Administrator recipient addresses do not grant administrator privileges. SMTP passwords and account tokens are not returned in settings or written to application logs. Set the public WebUI URL in the same email settings to an address recipients can open. It is used for account links and applies without restarting. SMTP delivery must be configured before creating new invited or administrator-provisioned accounts.

An administrator creates a single-use invitation in **User management → Invitations**, optionally bound to one email address. Codes contain five uppercase letters/digits and are displayed once; only keyed digests are stored. Invitations expire after 1–30 days and can be revoked. Registration without a valid code is rejected. New accounts start as ordinary users with a monthly limit of 10 and manual approval. They must confirm their email before signing in. Administrator-created accounts also require email confirmation and can be assigned their role and quota directly.

Verification links expire after 24 hours. Password recovery uses the authentication library's expiring, password-bound tokens; resetting the password invalidates an already used reset link. Public registration and email actions are rate limited. Existing accounts and hashes are preserved. New or changed passwords require at least eight characters with uppercase and lowercase letters, a digit and a special character.

During first-run onboarding the initial administrator is trusted without sending email. If an installation starts from an existing manual configuration with no accounts and no onboarding credentials, generated bootstrap credentials are written privately to `bootstrap-admin.json` in the persistent configuration directory.

Existing linked OIDC accounts remain usable. OIDC callbacks cannot bypass invitation-only registration to create a new account. New accounts use the invitation or administrator-provisioning workflow.
