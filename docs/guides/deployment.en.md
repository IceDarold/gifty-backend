# Deployment Guide (CI/CD)

Gifty uses a modern automated deployment pipeline that ensures **Zero-Downtime** and guarantees code quality through mandatory testing.

## Deployment Architecture

We use a **Blue-Green Deployment** strategy using host-based Nginx and Docker Compose for containerization.

### How it works:
1.  **Two Slots**: Two ports are reserved on the server: `8000` and `8001`.
2.  **Health Checks**: The new version of the application starts in the free "slot". Docker and our deployment script check the `/health` endpoint.
3.  **Seamless Switch**: Nginx switches traffic to the new port only after the application has confirmed its readiness.
4.  **Safe Rollback**: If the new version fails to start, the old one continues to run without service interruption.

---

## GitHub Actions Pipeline

The deployment process is described in the `.github/workflows/deploy-prod.yml` file. It consists of two main stages:

### 1. Testing Stage (`test`)
Runs on every push to `main`. 

- Sets up the environment (Python 3.11).
- Installs dependencies.
- Runs `pytest` according to settings in `tests_config.yaml`.
- **If tests fail, deployment will not proceed.**

### 2. Deployment Stage (`deploy`)
Runs via SSH on the target server:

- **SCP**: Copies the latest code to the `/app/gifty-backend` folder.
- **Build**: Builds a new Docker image.
- **Switch**: Executes the `scripts/deploy.sh` script to switch ports and update the Nginx config.

---

## Server Configuration

For the deployment to work, the following conditions must be met on the server:

### 1. Nginx Configuration
Nginx must use a dynamic `upstream` file. 
In the site config (`/etc/nginx/sites-enabled/gifty`):
```nginx
include /etc/nginx/conf.d/gifty_upstream.conf;

server {
    ...
    location / {
        proxy_pass http://gifty_backend;
    }
}
```

### 2. Permissions
The user GitHub connects with via SSH must have permissions to:

- Execute `docker-compose`.
- Overwrite files in `/etc/nginx/conf.d/`.
- Execute `sudo nginx -s reload` without a password (or via appropriate sudoers).

---

## GitHub Secrets Configuration

The following secrets must be set in the repository settings (Settings -> Secrets):

| Secret | Description |
| :--- | :--- |
| `PROD_SSH_HOST` | Server IP or domain |
| `PROD_SSH_PORT` | SSH port (if not 22) |
| `PROD_SSH_USER` | Username for connection |
| `PROD_SSH_KEY` | Private SSH key |
| `PROD_ENV_FILE` | Contents of the production `.env` file |

---

## Deployment Monitoring

The status of the current deployment can be tracked in the **Actions** tab on GitHub. 
## Documentation Deployment

The documentation deployment process is defined in `.github/workflows/docs.yml` and is tied to the `documentation` branch.

### Workflow Rules:
1.  **Primary Branch**: `documentation`. Only pushes to this branch trigger a site update at `dev.giftyai.ru`.
2.  **Work Branches**: `documentation/*`. Pushes to these branches trigger only a build check (`mkdocs build`) to ensure no errors exist.
3.  **Pull Request**: Creating a PR into the `documentation` branch also triggers a build check. Deployment happens only after the PR is merged.

