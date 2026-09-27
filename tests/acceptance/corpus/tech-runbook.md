# Rotating the signing key

Do this during a maintenance window. Do not rotate the key while a release is in progress.

1. Generate the new key with `keytool -genkeypair -alias release-2027`.
2. Upload the public half to the verification service before you switch.
3. Update `SIGNING_KEY_ALIAS` in the pipeline settings.
4. Run a test release to the staging channel and confirm that the signature verifies.
5. Revoke the old key no earlier than 7 days after the switch.

If verification fails at step 4, restore the previous alias and stop. Do not revoke anything until the cause is understood.
