# NeuroGraph-DB deployment

The active FastAPI application, verified ML bundles, PostgreSQL 16, and Neo4j 5
run together on one EC2 server. Caddy supplies public HTTPS. The Next.js frontend
runs on Vercel Hobby and forwards `/api/v1` and `/health` to `BACKEND_URL`.

## Account and cost restriction

Deployment is authorized only while AWS reports account `854784157430` as an
`ACTIVE` `FREE` account plan with at least $10 remaining credit. The provisioning
and SSM scripts check this through AWS's API. They never upgrade the account or
purchase support, domains, Marketplace products, or subscriptions.

EC2, disk, public IPv4, and S3 usage consume Free-plan credit. This is temporary
credit-funded hosting, not an unlimited always-free allocation. AWS's Free plan
ends when its credit or time allowance ends. Keep the account on the Free plan;
the scripts are a deployment check, not a spending limit for a Paid account.

## Infrastructure and runtime

- `stack.json`: CloudFormation for a single `m7i-flex.large` (8 GB), encrypted
  50 GB disk, public web ports 80/443, private S3 artifacts, and SSM management.
  There is no public SSH, PostgreSQL, or Neo4j port, NAT gateway, or load balancer.
- `compose.yaml`, `Caddyfile`: databases, CPU backend, model cache, and HTTPS.
- `start.sh`: database restore, migrations, cloud account password rotation,
  synthetic campaign projection, model checksum/reproduction checks, pinned
  RoBERTa cache warmup, and health-checked service startup.
- `../../scripts/provision_aws.py`: guarded CloudFormation creation.
- `../../scripts/package_aws.py`: private source/bundle/database packaging.
- `../../scripts/aws_remote.py`: guarded SSM deployment command execution.
- `../../scripts/deploy_frontend.py`: production configuration, build, and deploy.
- `../../scripts/smoke_deployment.py`: public authentication, model results,
  optional CSV scoring, and Neo4j graph verification.

The initial deployment packages the current working tree, including the active
CSV scoring changes. It does not require a Git push or Render synchronization.
Verified bundles and database exports are transferred privately, outside Git
and outside the Docker image. `.deployment/` stores local deployment state and
credentials with restricted permissions and is ignored by Git.

Health checks use `/health/live`. The existing generic `/health/ready` contract
also checks the separate generic inference runtime; it is not the readiness
signal for the verified benchmark and inductive serving paths.

## Rebuild the frontend after a backend change

From the repository root, with the Vercel CLI authenticated:

```sh
python3 scripts/deploy_frontend.py https://neurograph-16-171-237-56.sslip.io
```

Only the public proxy URL is placed in Vercel's environment. Database passwords,
JWT secrets, and Vercel-generated OIDC tokens are never copied into frontend
configuration. Production login does not show the local development passwords.

## Operations

The EC2 address is allocated dynamically. An EC2 stop/start may change it; update
the Caddy hostname and rebuild the frontend if that happens. A restart of Docker
or the application retains the database and model-cache volumes.

For terminal maintenance, authenticate AWS CLI to the intended account and use
SSM. Server deployment logs are in `/opt/neurograph/deployment.log`; the exit code
is in `/opt/neurograph/deployment.exit`. Do not print `.env` or credential files
into logs. Before replacing the server, export PostgreSQL and preserve required
Neo4j data: its root disk and local Docker volumes are deleted on termination.
