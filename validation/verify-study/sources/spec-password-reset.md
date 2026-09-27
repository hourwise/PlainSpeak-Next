# Password reset requirements

The service MUST send the reset link only to the email address already
registered on the account. The link MUST expire 30 minutes after it is issued
and MUST NOT be usable more than once.

The service SHOULD rate-limit reset requests to at most 5 per hour for each
account. It MUST NOT reveal whether an email address is registered.

After a successful reset, the service MUST end every other active session for
the account within 60 seconds.
