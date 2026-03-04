# Runbook: Clean NVMe Migration (Keep Repo Safe)

## 1. Preserve repository state
```bash
cd /data/srv/aios/AI-OS
git fetch origin
git status
git push
git push --all origin
git push --tags origin
```

## 2. Optional external backup
```bash
rsync -aHAX --info=progress2 /data/srv/aios/AI-OS/ /media/n04d/backup/AI-OS/
```

## 3. Install OS on NVMe
- Flash/install target must be NVMe (`/dev/nvme0n1`).
- Boot without SD after install.

## 4. Rehydrate repo
```bash
sudo mkdir -p /data/srv/aios
sudo chown -R "$USER":"$USER" /data/srv/aios
cd /data/srv/aios
git clone git@github.com:N04D/AI-OS.git
cd AI-OS
```

## 5. Rehydrate Python env
```bash
python3 -m venv /tmp/aios-venv
source /tmp/aios-venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```
