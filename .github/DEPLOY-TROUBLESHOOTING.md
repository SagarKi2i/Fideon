# Deploy troubleshooting

Use this when the **deploy** job fails in GitHub Actions (e.g. `deploy-dev`, `deploy-staging`, or `deploy-env`).

---

## SSH connection timed out

**Error:** `Connection to *** port 22 timed out` / `ERROR: Cannot reach VM on port 22`

The runner cannot open an SSH connection to your Azure VM. Fix in this order:

### 1. VM is running

- In **Azure Portal** → your VM → **Overview**: status should be **Running**.
- If it’s stopped, start it and re-run the workflow.

### 2. Network Security Group (NSG) allows port 22

- GitHub Actions run on Microsoft-hosted runners; their IPs change.
- **Option A (recommended):** Allow SSH from **Any** (`0.0.0.0/0`) for port **22 TCP** on the VM’s NSG. Restrict later with a firewall or private networking if needed.
- **Option B:** Use [GitHub’s IP allow list](https://api.github.com/meta) and update your NSG with the `actions` IP ranges (more maintenance).
- In Azure: VM → **Networking** → **Network settings** → **Inbound port rules** → ensure a rule allows **Port 22**, **TCP**, **Source: Any**, **Action: Allow**. If you have multiple rules for port 22, ensure none of them **Deny** and that a higher-priority rule doesn’t block traffic.
- **Application security groups:** If the VM’s NIC is in an **Application security group**, check that group’s rules too; a deny rule there can block SSH even if the NSG allows it.
- **VM public IP:** Ensure the VM has a **public IP** and that it is **static** (or update **AZURE_VM_HOST** in GitHub whenever the IP changes). In Azure: VM → **Overview** → **Public IP address**; use that exact value for **AZURE_VM_HOST**.

### 3. Correct secrets for the right environment

- Deploy uses the **GitHub Environment** (e.g. `development`, `staging`, `production`). Each has its own secrets.
- **Repo** → **Settings** → **Environments** → choose the environment (e.g. `development`) → **Environment secrets**.
- Ensure these are set and correct:
  - **AZURE_VM_HOST** – VM’s public IP or FQDN (e.g. `myvm.eastus.cloudapp.azure.com` or `52.x.x.x`).
  - **AZURE_VM_USERNAME** – SSH user (e.g. `azureuser`).
  - **CHATBOT_SERVER_KEY** – Private key content for that VM (starts with `-----BEGIN ... KEY-----`).
- If you use one VM for dev and another for staging/prod, each environment must have its own `AZURE_VM_HOST` (and key) pointing to the right VM.

### 4. SSH daemon (sshd) is running on the VM

- From a machine that can reach the VM (e.g. Azure Cloud Shell, or your PC if NSG allows you):
  - `ssh -i your_key.pem azureuser@<AZURE_VM_HOST> "echo OK"`
- If that fails, on the VM run:
  - `sudo systemctl status sshd` (or `sshd` on some images).
  - Start if needed: `sudo systemctl start sshd` and enable: `sudo systemctl enable sshd`.

### 5. Key and user match the VM

- The secret **CHATBOT_SERVER_KEY** must be the private key whose public key is in the VM’s `~/.ssh/authorized_keys` for **AZURE_VM_USERNAME**.
- No passphrase on the key, or the deploy will hang waiting for input.

After changing any of the above, re-run the failed **Deploy** job (or push again).

---

## Missing required secrets

**Error:** `Missing required secrets for VM deploy in environment 'development': AZURE_VM_HOST ...`

- Add the missing secrets to that environment: **Settings** → **Environments** → `<environment>` → **Environment secrets**.
- Required for VM deploy: `AZURE_VM_HOST`, `AZURE_VM_USERNAME`, `CHATBOT_SERVER_KEY`.

---

## Health check failed after deploy

**Error:** `ERROR: <container_name> failed health check at ...`

- The container started but did not respond on the expected port/path in time.
- Check the **Container logs** printed in the same job; fix the app or env (e.g. missing env vars, wrong port).
- The workflow will roll back to the previous container if rollback is configured.

---

## Quick checklist (development)

| Check | Where |
|-------|--------|
| VM status = Running | Azure Portal → VM → Overview |
| Port 22 allowed (SSH) | VM/Subnet → Networking → Inbound rules |
| `AZURE_VM_HOST` = VM IP or FQDN | GitHub → Environments → development → Secrets |
| `AZURE_VM_USERNAME` = SSH user | Same |
| `CHATBOT_SERVER_KEY` = private key | Same |
| sshd running on VM | `systemctl status sshd` on VM |
