# System Snapshot

## Storage
- Root filesystem: `/dev/mmcblk0p2` (ext4, ~15G)
- Root free space observed: ~357M at 98% usage
- NVMe data filesystem: `/dev/nvme0n1p2` (ext4, ~234G)
- Boot partition: `/dev/mmcblk0p1`

## Key risk
System instability due to near-full SD root. Priority is migration to NVMe root.

## Validation commands
```bash
df -h
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,MODEL
findmnt -no SOURCE,TARGET,FSTYPE,OPTIONS /
```
