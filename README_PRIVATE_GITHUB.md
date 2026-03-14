# MDT Hub - Private GitHub sync

This project is intended to be pushed to a **private** GitHub repository.

## One-time setup

1) Create a private repo on GitHub, e.g.:
- `family3253/mdt-hub-private`

2) Add it as remote and push:

```bash
cd /home/chenyechao/.openclaw/workspace/mdt-hub
git remote add origin git@github.com:family3253/mdt-hub-private.git
git push -u origin main
```

## Daily workflow

```bash
cd /home/chenyechao/.openclaw/workspace/mdt-hub
git add -A
git commit -m "<msg>" || true
git push
```

## Notes

- `vendor/` sources are not committed (fetched by `deploy/bootstrap.sh`).
- Runtime artifacts are ignored: `.run/`, `*.log`, `*.pid`, `backend/mdt.db`, `backend/.venv/`.
