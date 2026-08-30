# Release checklist

Before deploying:

- Confirm the change log is complete
- Check that migrations have been reviewed
- Verify the rollback plan is current
- Ensure monitoring dashboards are updated
- Confirm the on-call rota is staffed

During deployment:

- Watch the error rate for ten minutes
- Check latency in every region
- Confirm the health endpoint responds
- Verify background jobs are running
- Watch the queue depth

After deployment:

- Update the release notes
- Close the change ticket
- Notify the support team
- Record any follow-up work
- Archive the deployment log
